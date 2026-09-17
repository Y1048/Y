"""Local subprocess fault injection and C++ stop propagation; no robot IO."""
import json
import sys
import time
import unittest
from policy_worker_client_offline import PolicyWorkerClient,PolicyWorkerError
import test_raw_event_clock as raw_fixture

PREFIX="import sys,json,time\nprint(json.dumps({'ready':True}),flush=True)\nr=json.loads(sys.stdin.readline())\n"
def Command(body):return [sys.executable,"-u","-c",PREFIX+body]
CASES={
 "worker_timeout":"time.sleep(2)",
 "worker_eof":"sys.exit(3)",
 "worker_invalid_json":"print('{',flush=True)",
 "worker_response_id":"print(json.dumps({'request_id':999,'action':[0]*29}),flush=True)",
 "worker_invalid_action":"print(json.dumps({'request_id':r['request_id'],'action':[True]*29}),flush=True)",
 "worker_response_size":"print('x'*65537,flush=True)",
}

class WorkerClientTests(unittest.TestCase):
 def test_faults_latch_and_cleanup(self):
  for reason,body in CASES.items():
   with self.subTest(reason=reason):
    c=PolicyWorkerClient(Command(body))
    t0=time.perf_counter()
    with self.assertRaisesRegex(PolicyWorkerError,reason):c.infer([0.]*1432)
    self.assertLess(time.perf_counter()-t0,1.)
    self.assertIsNotNone(c.p.poll());self.assertFalse(c.thread.is_alive())
    with self.assertRaisesRegex(PolicyWorkerError,reason):c.infer([0.]*1432)
    c.close()
 def test_valid_correlated_response(self):
  c=PolicyWorkerClient(Command("print(json.dumps({'request_id':r['request_id'],'action':[0]*29}),flush=True)"))
  try:self.assertEqual(c.infer([0.]*1432)["action"],[0]*29)
  finally:c.close()
 def test_startup_timeout(self):
  with self.assertRaisesRegex(PolicyWorkerError,"worker_timeout"):
   PolicyWorkerClient([sys.executable,"-u","-c","import time;time.sleep(2)"],startup_timeout=.03)
 def test_nan_and_duplicate_json(self):
  for raw in ('{"request_id":1,"action":[NaN]}','{"request_id":1,"request_id":1,"action":[]}'):
   with self.subTest(raw=raw):
    c=PolicyWorkerClient(Command("print("+repr(raw)+",flush=True)"))
    with self.assertRaisesRegex(PolicyWorkerError,"worker_invalid_json"):c.infer([0.]*1432)
 def test_faults_stop_cpp_pending_history(self):
  for reason,body in CASES.items():
   with self.subTest(reason=reason):
    fixture=raw_fixture.RawEventTests()
    fixture.setUp()
    try:
     before=fixture.Pending()
     c=PolicyWorkerClient(Command(body))
     with self.assertRaises(PolicyWorkerError) as error:c.infer([0.]*1432)
     row=fixture.X("stop",6.145,reason=str(error.exception))
     fixture.CheckStop(before,row,reason,6.15)
    finally:fixture.tearDown()

if __name__=="__main__":unittest.main()
