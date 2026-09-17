"""Deterministic raw packet interruption tests; zero-action policy fixture, no IO."""
import json
import subprocess
import unittest
from test_cpp_upper_target import ROOT, Packet

BASE=[-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
def Raw(seq=1, release=False):
    p=json.loads(Packet(seq))
    p["all_joint_q_rad"]=BASE
    p["right_arm"]["joints"]=BASE[22:]
    if release:
        p["input_command_mode"]="pinch_disengaged"
        p["right_arm"]["active"]=False;p["right_arm"]["command_state"]="hold"
    return json.dumps(p).encode().hex()

class RawEventTests(unittest.TestCase):
    def setUp(self):
        self.p=subprocess.Popen([str(ROOT/"logs/test_results/test_event_clock_loop.exe")],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.p.stdin.write(json.dumps(dict(fixture="frozen_policy_previous_target_writer",
                                          baseline=BASE,raw_input=True))+"\n")
        self.p.stdin.flush()
    def tearDown(self):
        self.p.stdin.close()
        try: code=self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill();self.p.wait();raise
        error=self.p.stderr.read();self.p.stdout.close();self.p.stderr.close()
        self.assertEqual(code,0,error)
    def X(self,op,now,**kw):
        self.p.stdin.write(json.dumps(dict(op=op,now=now,**kw))+"\n");self.p.stdin.flush()
        line=self.p.stdout.readline()
        self.assertTrue(line,"harness exited")
        return json.loads(line)
    def Pending(self):
        for n in range(56):
            at=5+n*.02
            self.assertEqual(self.X("build",at,packets=[])["reason"],"")
            self.assertEqual(self.X("finish",at+.001,action=[0]*29)["reason"],"")
        self.X("packet",6.12,hex=Raw())
        self.X("build",6.12,packets=[])
        done=self.X("finish",6.121,action=[0]*29)
        self.assertEqual(done["commits"],1)
        self.X("writer",6.123)
        row=self.X("build",6.14,packets=[])
        self.assertTrue(row["pending"])
        return row
    def CheckStop(self,before,row,why,now):
        self.assertEqual(row["reason"],why)
        for key in ("history","previous_action","commits","writer_q","writes"):
            self.assertEqual(row[key],before[key],key)
        self.assertIsNone(row["desired"]);self.assertFalse(row["pending"])
        self.assertEqual(row["input_depth"],0)
        later=self.X("finish",now,action=[0]*29)
        self.assertEqual(later["discarded"],1)
        self.assertEqual(later["history"],before["history"])
        resumed=self.X("packet",now,hex=Raw(999))
        self.assertEqual(resumed["reason"],why)
        self.assertEqual(self.X("writer",now+.002)["writer_q"],before["writer_q"])
    def test_release_same_time_as_finish_and_reengage(self):
        b=self.Pending()
        self.CheckStop(b,self.X("packet",6.145,hex=Raw(2,True)),"input_disengaged",6.145)
    def test_invalid_json_during_inference(self):
        b=self.Pending()
        self.CheckStop(b,self.X("packet",6.145,hex=b"{".hex()),"parse_error",6.15)
    def test_duplicate_after_fifo_drain(self):
        b=self.Pending()
        self.CheckStop(b,self.X("packet",6.145,hex=Raw()),"session_or_sequence",6.15)
    def test_timeout_boundary_and_late_completion(self):
        b=self.Pending()
        self.assertEqual(self.X("poll",6.37)["reason"],"")
        self.CheckStop(b,self.X("poll",6.370001),"receiver_timeout",6.38)
    def test_oversize(self):
        b=self.Pending()
        self.CheckStop(b,self.X("packet",6.145,hex=(b" "*16385).hex()),"datagram_too_large",6.15)
    def test_queue_overflow_during_inference(self):
        b=self.Pending()
        for seq in range(2,66):
            r=self.X("packet",6.141+seq*.00001,hex=Raw(seq))
            self.assertEqual(r["input_depth"],seq-1)
        self.CheckStop(b,self.X("packet",6.142,hex=Raw(66)),"queue_overflow",6.15)
    def test_fifo_does_not_coalesce_bad_middle(self):
        b=self.Pending()
        self.X("packet",6.145,hex=Raw(3))
        self.CheckStop(b,self.X("packet",6.145,hex=Raw(2)),"session_or_sequence",6.15)
    def test_idle_has_no_timeout_before_engage(self):
        p=json.loads(bytes.fromhex(Raw(1,True)))
        p["input_command_mode"]="idle";p["right_arm"]["command_state"]="idle"
        r=self.X("packet",1,hex=json.dumps(p).encode().hex())
        self.assertEqual(r["input_depth"],0)
        self.assertEqual(self.X("poll",100)["reason"],"")
    def test_fifo_valid_batch_drains_once(self):
        self.Pending()
        self.X("packet",6.145,hex=Raw(2));self.X("packet",6.146,hex=Raw(3))
        self.assertEqual(self.X("finish",6.147,action=[0]*29)["input_depth"],2)
        r=self.X("build",6.16,packets=[])
        self.assertEqual(r["input_depth"],0);self.assertEqual(r["reason"],"")
        r=self.X("finish",6.161,action=[0]*29)
        self.assertEqual(r["reason"],"")
        self.assertEqual(r["commits"],3)

if __name__=="__main__": unittest.main()
