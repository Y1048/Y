"""CPU inference and C++ safety stages on one synthetic event clock; no robot IO."""
import argparse
import gc
import heapq
import io
import json
from pathlib import Path
import subprocess
import sys
from contextlib import nullcontext
from policy_worker_client_offline import PolicyWorkerClient, PolicyWorkerError
import time
from offline_policy_adapter import ReadVerifiedPolicy, EXPECTED_SHA256
from run_policy_history_offline import F32
from replay_cpp_receiver_log import ROOT, Replay


def Run(output, raw_input=False, fixed_inference_ms=None, isolated_policy=False):
    if not isolated_policy:
        import torch
    if isolated_policy and not raw_input:
        raise ValueError("isolated worker currently requires raw-input single scenario")
    if fixed_inference_ms is not None and not 0 < fixed_inference_ms <= 1000:
        raise ValueError("fixed inference duration")
    capture = ROOT / "logs/test_results/twist2_cpp_quest_raw_20260907_152430/ticks.jsonl"
    Replay(capture)
    rows = [json.loads(x) for x in capture.read_text().splitlines()]
    baseline = next(r["baseline"] for r in rows if r.get("baseline") is not None)
    release = next(r["now_s"] for r in rows if r.get("mode") == "stopped")
    defaults = [-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
    worker=None
    try:
        if isolated_policy:
            worker=PolicyWorkerClient([sys.executable,str(Path(__file__).with_name("policy_cpu_worker_offline.py"))])
        else:
            torch.set_num_threads(1)
            model = torch.jit.load(io.BytesIO(ReadVerifiedPolicy(
                ROOT / "references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt")),
                map_location="cpu").eval()
            # Explicit warm-up outside the simulated task. Cold-start is not a timing claim.
            with torch.inference_mode():
                for _ in range(10):
                    model(torch.zeros((1,1432), dtype=torch.float32))
        output.mkdir(parents=True, exist_ok=False)
        results = []
        for scenario in (("normal",) if raw_input else ("normal", "stale_finish", "writer_stop_pending", "release_pending")):
            process = subprocess.Popen([str(ROOT / "logs/test_results/test_event_clock_loop.exe")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            process.stdin.write(json.dumps(dict(fixture="frozen_policy_previous_target_writer",
                                               baseline=baseline,raw_input=raw_input))+"\n")
            process.stdin.flush()
            queue=[];serial=0
            def Push(at, priority, kind, payload=None):
                nonlocal serial
                serial+=1;heapq.heappush(queue,(at,priority,serial,kind,payload))
            for r in rows:
                if r["event"]=="packet":
                    Push(r["received_at_s"],-1 if raw_input else 3,"packet",dict(hex=r["payload_hex"],at=r["received_at_s"]))
                elif r["event"]=="tick" and r["now_s"] < release:
                    Push(r["now_s"],4,"build")
            if not raw_input: Push(release,0,"stop")
            pending=False;packets=[];injected=False;writer_started=False;reason=""
            expected_history=[0.]*1270;previous=[0.]*29;commits=0;observations=None
            writer_q=None;frozen=None;trace=[];inferences=0;max_latency=0.;stopped_at=None
            timing=[]
            def Exchange(request):
                process.stdin.write(json.dumps(request)+"\n");process.stdin.flush()
                line=process.stdout.readline()
                if not line: raise RuntimeError(process.stderr.read())
                return json.loads(line)
            try:
                with (nullcontext() if isolated_policy else torch.inference_mode()):
                    while queue:
                        now,_,_,kind,payload=heapq.heappop(queue)
                        if now > release+.1: break
                        if kind=="packet":
                            if not raw_input:
                                packets.append(payload);continue
                            row=Exchange(dict(op="packet",now=now,hex=payload["hex"]))
                        elif kind=="build":
                            if pending or reason: continue
                            row=Exchange(dict(op="build",now=now,packets=packets));packets=[]
                            if "observation" in row:
                                observations=row["observation"]
                                if observations[127:1397]!=expected_history or observations[98:127]!=previous:
                                    raise ValueError("observation history mismatch")
                                gc_events=[]
                                def GCEvent(phase, info):
                                    gc_events.append(dict(phase=phase,generation=info["generation"],
                                                          at=time.perf_counter()))
                                gc.callbacks.append(GCEvent)
                                try:
                                    cpu0=time.thread_time()
                                    t0=time.perf_counter()
                                    worker_timing=None;worker_failure=None
                                    if isolated_policy:
                                        try:
                                            worker_timing=worker.infer(observations)
                                            action=worker_timing.pop("action")
                                        except PolicyWorkerError as error:
                                            worker_failure=str(error)
                                            action=None
                                        t1=t2=t3=time.perf_counter()
                                    else:
                                        tensor=torch.tensor([observations],dtype=torch.float32)
                                        t1=time.perf_counter()
                                        raw=model(tensor)
                                        t2=time.perf_counter()
                                        action=raw.clamp(-2,2).tolist()[0]
                                        t3=time.perf_counter()
                                    cpu_elapsed=time.thread_time()-cpu0
                                finally:
                                    gc.callbacks.remove(GCEvent)
                                duration=t3-t0
                                timing.append(dict(now=now,tensor_ms=None if isolated_policy else (t1-t0)*1000,model_ms=None if isolated_policy else (t2-t1)*1000,
                                    output_ms=None if isolated_policy else (t3-t2)*1000,total_ms=duration*1000,
                                    calling_thread_cpu_ms=cpu_elapsed*1000,gc_events=gc_events,
                                    isolated_policy=isolated_policy,worker_timing=worker_timing))
                                max_latency=max(max_latency,duration);inferences+=1
                                delay=duration if fixed_inference_ms is None else fixed_inference_ms/1000
                                if not injected and writer_started and (
                                    (scenario in ("stale_finish","writer_stop_pending") and now>29)
                                    or (scenario=="release_pending" and now>release-.03)):
                                    injected=True
                                    delay=max(delay,.04)
                                Push(now+delay,0 if worker_failure else 2,"worker_failure" if worker_failure else "finish",worker_failure or action)
                                pending=True
                        elif kind=="worker_failure":
                            row=Exchange(dict(op="stop",now=now,reason=payload));pending=False
                        elif kind=="finish":
                            row=Exchange(dict(op="finish",now=now,action=payload));pending=False
                            if "committed_q" in row:
                                if reason: raise ValueError("commit after stop")
                                commits+=1
                                expected_history=expected_history[127:]+observations[:127]
                                previous=[max(-2.,min(2.,F32(F32(F32(q)-F32(d))/.5)))
                                          for q,d in zip(row["committed_q"],defaults)]
                            if row["writer_q"] is not None and not writer_started:
                                writer_started=True;Push(now+.002,1,"writer")
                        elif kind=="writer":
                            request=dict(op="writer",now=now)
                            if scenario=="writer_stop_pending" and injected and pending:
                                request["state_at"]=now-.03
                            row=Exchange(request)
                            Push(now+.002,1,"writer")
                        else:
                            row=Exchange(dict(op="stop",now=now,reason="input_disengaged"))
                        if row["commits"]!=commits or row["history"]!=expected_history or row["previous_action"]!=previous:
                            raise ValueError("history changed without accepted Finish")
                        q=row["writer_q"]
                        if row["reason"]:
                            if not reason:
                                stopped_at=now;frozen=writer_q
                            if row["desired"] is not None or row["pending"] or q!=frozen:
                                raise ValueError("stop failed atomic clear/freeze")
                            reason=row["reason"]
                        elif q is not None and writer_q is not None:
                            if kind=="writer":
                                for i,(old,new,goal) in enumerate(zip(writer_q,q,row["desired"])):
                                    if abs(new-old)>(.004 if i<12 else .0016)+1e-7:
                                        raise ValueError("writer rate")
                                    if not min(old,goal)-1e-7<=new<=max(old,goal)+1e-7:
                                        raise ValueError("writer overshoot")
                            if q[12:22]!=[F32(v) for v in baseline[12:22]]:
                                raise ValueError("held joints changed")
                        writer_q=q
                        trace.append(dict(now=now,event=kind,reason=row["reason"],commits=commits,
                                          writes=row["writes"],discarded=row["discarded"],pending=row["pending"]))
                (output/(scenario+"_timing.json")).write_text(json.dumps(timing,indent=2))
                expected=dict(normal="input_disengaged",stale_finish="state_expired_during_inference",
                              writer_stop_pending="state_timeout",release_pending="input_disengaged")[scenario]
                if reason!=expected or commits==0 or trace[-1]["writes"]==0:
                    (output/"failure.json").write_text(json.dumps(dict(scenario=scenario,reason=reason,
                        commits=commits,maximum_inference_ms=max_latency*1000,trace=trace),indent=2))
                    raise ValueError((scenario,reason,expected,commits))
                if scenario!="normal" and not injected: raise ValueError("fault not exercised")
                if scenario in ("writer_stop_pending","release_pending") and trace[-1]["discarded"]<1:
                    raise ValueError("late completion not discarded")
                result=dict(scenario=scenario,passed=True,reason=reason,stop_at=stopped_at,
                            commits=commits,writes=trace[-1]["writes"],inferences=inferences,
                            discarded=trace[-1]["discarded"],maximum_inference_ms=max_latency*1000,
                            simulated_time=True,cpu_warmed_up=True,warmup_count=10,history_checked_every_event=True,
                            physical_state=False,policy_state="frozen_virtual_baseline",
                            writer_state="previous_target_zero_velocity",dynamics_tested=False)
                results.append(result)
                (output/(scenario+".jsonl")).write_text("".join(json.dumps(r)+"\n" for r in trace))
            finally:
                process.stdin.close()
                try: code=process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait();raise
                if code: raise RuntimeError(process.stderr.read())
                process.stdout.close();process.stderr.close()
        summary=dict(passed=True,policy_sha256=EXPECTED_SHA256,hardware_output_authorized=False,
                     isolated_policy=isolated_policy,raw_input_monitor=raw_input,fixed_inference_ms=fixed_inference_ms,scenarios=results)
        (output/"result.json").write_text(json.dumps(summary,indent=2)+"\n")
        return summary
    finally:
        if worker is not None:
            worker.close()



if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--raw-input",action="store_true")
    p.add_argument("--fixed-inference-ms",type=float,help="Explicit synthetic completion delay; measured CPU latency still reported")
    p.add_argument("--isolated-policy",action="store_true",help="Measure CPU worker round-trip including JSON and pipes")
    args=p.parse_args()
    print(json.dumps(Run(args.output,args.raw_input,args.fixed_inference_ms,args.isolated_policy),indent=2))
