"""Exercise actual C# ACK validation; engine JSON decoding is tested in Editor.

Only the unused LowState receiver dependency is stubbed. No sockets or robot.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Unity_G1_VR/Assets/G1Teleop/G1MeasuredStartState.cs'
POWERSHELL = shutil.which('pwsh')
STUBS = r'''
namespace UnityEngine {}
public sealed class G1LowStateLegView {
    public sealed class Frame {
        public string session; public long sequence;
        public double source_monotonic_s, age_s; public bool crc_valid;
        public string[] joint_names; public float[] q_rad, dq_rad_s;
    }
    public Frame LatestState; public double ReceivedAt;
    public bool IsFreshAt(double now) { return false; }
}
'''
HARNESS = r'''
public static class StartAckChecks {
    static int count;
    static void Check(bool ok, string reason) {
        ++count; if (!ok) throw new Exception(reason);
    }
    public static int Run() {
        var sample = new G1MeasuredStartState.Snapshot {
            session = "robot-A", receipt_age_s = .01 };
        foreach (string session in new string[] { null, "" })
        foreach (float[] body in new float[][] { null, new float[0] }) {
            var pending = new G1MeasuredStartState.Acknowledgement {
                reason = "settling_measurement", session = session, body_q_rad = body };
            Check(G1MeasuredStartState.Valid(pending), "Pending null/empty rejected");
            Check(!G1MeasuredStartState.CanEngage(pending, 0, sample, true), "Pending engaged");
            pending.ready = true;
            Check(!G1MeasuredStartState.Valid(pending), "Revision zero claims ready");
        }
        var ack = new G1MeasuredStartState.Acknowledgement {
            reason = "waiting_measurement", session = "robot-A" };
        Check(!G1MeasuredStartState.Valid(ack), "Revision zero has session");
        ack.session = ""; ack.body_q_rad = new float[15];
        Check(!G1MeasuredStartState.Valid(ack), "Revision zero has body");
        ack.revision = 1;
        Check(!G1MeasuredStartState.Valid(ack), "Initialized ACK lacks session");
        ack.session = "robot-A"; ack.body_q_rad = new float[0];
        Check(!G1MeasuredStartState.Valid(ack), "Initialized ACK lacks body");
        ack.body_q_rad = new float[15]; ack.ready = true;
        Check(G1MeasuredStartState.CanEngage(ack, 1, sample, true), "Valid seed rejected");
        Check(!G1MeasuredStartState.CanEngage(ack, 0, sample, true), "Wrong revision accepted");
        Check(!G1MeasuredStartState.CanEngage(ack, 1, sample, false), "Stale command accepted");
        sample.receipt_age_s = .101;
        Check(!G1MeasuredStartState.CanEngage(ack, 1, sample, true), "Stale sample accepted");
        foreach (float bad in new float[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity }) {
            ack.body_q_rad[0] = bad;
            Check(!G1MeasuredStartState.Valid(ack), "Nonfinite body accepted");
        }
        ack.body_q_rad[0] = 0; ack.reason = "";
        Check(!G1MeasuredStartState.Valid(ack), "Missing reason accepted");
        Check(!G1MeasuredStartState.Valid(null), "Null ACK accepted");
        return count;
    }
}
'''


class StartAckTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'PowerShell C# compiler required')
    def test_actual_ack_validation_preserves_engage_boundary(self):
        script = ("$ErrorActionPreference='Stop'\nAdd-Type -TypeDefinition @'\n"
                  + SOURCE.read_text(encoding='utf-8-sig') + STUBS + HARNESS
                  + "\n'@\nWrite-Output ('PASS checks=' + [StartAckChecks]::Run())\n")
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertIn(b'PASS checks=', result.stdout)


if __name__ == '__main__':
    unittest.main()
