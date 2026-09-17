"""Exact-output equivalence of isolated CPU worker and direct verified model."""
import io
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
import torch
from offline_policy_adapter import ReadVerifiedPolicy
from replay_cpp_receiver_log import ROOT

class WorkerTests(unittest.TestCase):
    def test_exact_outputs(self):
        torch.set_num_threads(1)
        model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(
            ROOT/"references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt")),
            map_location="cpu").eval()
        p=subprocess.Popen([sys.executable,str(Path(__file__).with_name("policy_cpu_worker_offline.py"))],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertTrue(json.loads(p.stdout.readline())["ready"])
            with torch.inference_mode():
                for case in range(8):
                    obs=[math.sin(i*.13+case)*case*.01 for i in range(1432)]
                    expected=model(torch.tensor([obs],dtype=torch.float32)).clamp(-2,2).tolist()[0]
                    p.stdin.write(json.dumps(obs)+"\n");p.stdin.flush()
                    got=json.loads(p.stdout.readline())
                    with self.subTest(case=case):
                        self.assertEqual(got["action"],expected)
                        self.assertGreaterEqual(got["total_ms"],0)
        finally:
            p.stdin.close()
            try: code=p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait();raise
            p.stdout.close()
            self.assertEqual(code,0)

if __name__=="__main__": unittest.main()
