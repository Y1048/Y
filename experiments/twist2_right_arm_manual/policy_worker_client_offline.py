"""Bounded local policy IPC; closes only the subprocess created by this client."""
import json
import math
import queue
import subprocess
import threading
import time

class PolicyWorkerError(RuntimeError):
    pass

class PolicyWorkerClient:
    def __init__(self, command, startup_timeout=10., response_timeout=.03):
        if not all(math.isfinite(t) and t>0 for t in (startup_timeout,response_timeout)):
            raise ValueError("timeout")
        self.timeout=response_timeout
        self.reason=""
        self.sequence=0
        self.jobs=queue.Queue(maxsize=1)
        self.lock=threading.Lock()
        self.p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        self.thread=threading.Thread(target=self._io,daemon=True)
        self.thread.start()
        try:
            ready=self._exchange(None,startup_timeout)
            if not isinstance(ready,dict) or ready.get("ready") is not True:
                self._fail("worker_bad_ready")
        except BaseException:
            self.close()
            raise

    def _io(self):
        while True:
            job=self.jobs.get()
            if job is None: return
            payload,result=job
            try:
                if payload is not None:
                    self.p.stdin.write(payload)
                    self.p.stdin.flush()
                raw=self.p.stdout.readline(65537)
                if not raw: raise PolicyWorkerError("worker_eof")
                if len(raw)>65536 or not raw.endswith(b"\n"):
                    raise PolicyWorkerError("worker_response_size")
                result.put((True,raw))
            except Exception as error:
                result.put((False,error))

    def _fail(self, reason):
        if not self.reason:self.reason=reason
        self.close()
        raise PolicyWorkerError(self.reason)

    def _exchange(self, payload, timeout):
        if self.reason: raise PolicyWorkerError(self.reason)
        deadline=time.perf_counter()+timeout
        result=queue.Queue(maxsize=1)
        self.jobs.put_nowait((payload,result))
        try:
            ok,raw=result.get(timeout=max(0,deadline-time.perf_counter()))
        except queue.Empty:
            self._fail("worker_timeout")
        if not ok:
            self._fail(str(raw) if isinstance(raw,PolicyWorkerError) else "worker_io_error")
        def Unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError("duplicate")
                result[key]=value
            return result
        try:
            value=json.loads(raw,object_pairs_hook=Unique,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError,UnicodeError):
            self._fail("worker_invalid_json")
        if time.perf_counter()>deadline:self._fail("worker_timeout")
        return value

    def infer(self, observations):
        if len(observations)!=1432 or any(isinstance(x,bool) or not isinstance(x,(int,float))
                or not math.isfinite(x) for x in observations):
            self._fail("invalid_observation")
        if not self.lock.acquire(blocking=False):
            self._fail("worker_concurrent_request")
        try:
            self.sequence+=1
            payload=(json.dumps(dict(request_id=self.sequence,observation=observations),allow_nan=False)+"\n").encode()
            value=self._exchange(payload,self.timeout)
            if not isinstance(value,dict) or type(value.get("request_id")) is not int or value["request_id"]!=self.sequence:
                self._fail("worker_response_id")
            action=value.get("action")
            if not isinstance(action,list) or len(action)!=29 or any(
                isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>2
                for x in action):
                self._fail("worker_invalid_action")
            return value
        finally:self.lock.release()

    def close(self):
        if self.p.poll() is None:
            self.p.terminate()
            try:self.p.wait(timeout=1)
            except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=1)
        try:self.jobs.put_nowait(None)
        except queue.Full:pass
        self.thread.join(timeout=1)
        if not self.thread.is_alive():
            self.p.stdin.close();self.p.stdout.close()
