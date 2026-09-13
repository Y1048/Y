import ast, json, tempfile, unittest
from pathlib import Path
import numpy as np
import real_response_log as log
import real_response_identification as ident


def record(sequence, command, q, dq):
    t = 1_000_000_000 + sequence * 10_000_000
    zero = [0.0] * 7
    return {"schema":log.SCHEMA,"session_id":"fixture","sequence":sequence,"state":"active",
        "source_provenance":{"controller_commit":"fixture"},"target_monotonic_ns":t-2_000_000,
        "command_monotonic_ns":t-1_000_000,"lowstate_monotonic_ns":t,"target_q_rad":command.tolist(),
        "command_q_rad":command.tolist(),"command_dq_rad_s":zero,"kp_nm_rad":[40.0]*7,
        "kd_nm_s_rad":[5.0]*7,"tau_ff_nm":zero,"measured_q_rad":q.tolist(),"measured_dq_rad_s":dq.tolist()}


class RealResponseTest(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/"trace.jsonl"
    def tearDown(self): self.tmp.cleanup()
    def rows(self):
        q=np.zeros(7);dq=np.zeros(7);rows=[]
        for i in range(80):
            command=np.full(7, .2 if i>=10 else 0.)
            rows.append(record(i,command,q,dq));acc=8*(command-q)-1.5*dq+.01
            dq=dq+acc*.01;q=q+dq*.01
        return rows
    def test_async_round_trip_and_fit(self):
        with log.AsyncResponseLog(self.path) as writer:
            for row in self.rows(): writer.append(row)
        trace=log.parse_trace(self.path);result=ident.estimate(trace)
        self.assertEqual(trace.dropped_sequences,0);self.assertEqual(result["samples"],80)
        self.assertIsNone(result["recommended_hardware_gains"])
        self.assertAlmostEqual(result["joint_models"][0]["command_error_gain_s2"],8,places=4)
        self.assertAlmostEqual(result["joint_models"][0]["effective_damping_s1"],1.5,places=4)
    def test_gap_is_detected_and_fit_refused(self):
        rows=self.rows();rows.pop(20);self.path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
        trace=log.parse_trace(self.path);self.assertEqual(trace.dropped_sequences,1)
        with self.assertRaisesRegex(ValueError,"sequence_gaps"):ident.estimate(trace)
    def test_nonmonotonic_clock_rejected(self):
        rows=self.rows();rows[20]["lowstate_monotonic_ns"]=rows[19]["lowstate_monotonic_ns"]-1
        self.path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"nonmonotonic_clock"):log.parse_trace(self.path)
    def test_schema_and_nonfinite_rejected(self):
        bad=self.rows()[0];bad["measured_q_rad"][2]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid_measured_q_rad"):log.validate_record(bad)
    def test_module_has_no_command_capability_imports(self):
        source=Path(log.__file__).read_text(encoding="utf-8")
        imports=[]
        for node in ast.walk(ast.parse(source)):
            if isinstance(node,ast.Import): imports.extend(x.name for x in node.names)
            elif isinstance(node,ast.ImportFrom): imports.append(node.module or "")
        for forbidden in ("unitree_sdk", "socket", "subprocess"):
            self.assertFalse(any(name==forbidden or name.startswith(forbidden+".") for name in imports))


if __name__ == "__main__": unittest.main()
