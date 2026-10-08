"""Execute the real C# command-target contract with constructor-only Unity stubs.

This validates pure decoding/validation/accessor logic, not Unity rendering or
the Editor's JSON deserializer. No Unity process or control transport is started.
"""
import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Unity_G1_VR/Assets/G1Teleop/G1GoalPreviewState.cs'
POWERSHELL = shutil.which('pwsh')

STUBS = r'''
namespace UnityEngine {
    public struct Vector3 {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x=x; this.y=y; this.z=z; }
    }
    public struct Quaternion {
        public float x, y, z, w;
        public Quaternion(float x, float y, float z, float w) {
            this.x=x; this.y=y; this.z=z; this.w=w;
        }
    }
}
'''

HARNESS = r'''
public static class GoalFrameChecks {
    private static int count;
    private static void Check(bool condition, string reason) {
        ++count;
        if (!condition) throw new InvalidOperationException(reason);
    }
    private static G1GoalPreviewState.Frame Example() {
        return new G1GoalPreviewState.Frame {
            schema="g1.bimanual.command.target.v1", valid=true,
            status="checked_command_fk", source_sequence=17, feedback_sequence=23,
            age_s=.02,
            left_world_m=new float[] { 1, 2, 3 },
            right_world_m=new float[] { -4, 5, -6 },
            left_world_wxyz=new float[] { 1, 0, 0, 0 },
            right_world_wxyz=new float[] { .8f, 0, .6f, 0 }
        };
    }
    private static void Reject(Action<G1GoalPreviewState.Frame> mutate, string reason) {
        var value=Example();
        mutate(value);
        Check(!G1GoalPreviewState.Valid(value), reason);
        Check(!G1GoalPreviewState.Fresh(value, 0, .01), reason+" passed freshness");
        Check(!G1GoalPreviewState.ValidForFeedback(value, 17, 23), reason+" passed feedback validation");
    }
    public static int Run() {
        count=0;
        var value=Example();
        Check(G1GoalPreviewState.Valid(value), "Valid command FK example rejected");
        Check(!G1GoalPreviewState.Valid(null), "Missing frame accepted");
        Check(!G1GoalPreviewState.Valid(new G1GoalPreviewState.Frame()), "Empty frame accepted");
        Reject(x=>x.schema="g1.bimanual.goal.preview.v1", "Legacy v1 accepted");
        Reject(x=>x.schema="g1.bimanual.goal.preview.v2", "Independent geometric preview accepted");
        Reject(x=>x.schema=null, "Missing schema accepted");
        Reject(x=>x.status="checked_goal_prefix", "Legacy prefix status accepted");
        Reject(x=>x.status="geometric_goal_converged", "Geometric convergence accepted as command FK");
        Reject(x=>x.status="geometric_goal_partial", "Geometric partial accepted as command FK");
        Reject(x=>x.status="inactive", "Inactive target accepted");
        Reject(x=>x.status="waiting", "Unready status accepted");
        Reject(x=>x.valid=false, "Invalid result accepted");
        Reject(x=>x.left_world_m=null, "Missing position accepted");
        Reject(x=>x.right_world_m=new float[2], "Short position accepted");
        Reject(x=>x.left_world_m[2]=float.NaN, "Nonfinite position accepted");
        Reject(x=>x.right_world_wxyz=null, "Missing orientation accepted");
        Reject(x=>x.left_world_wxyz=new float[4], "Zero quaternion accepted");
        Reject(x=>x.right_world_wxyz=new float[] { 2, 0, 0, 0 }, "Unnormalized quaternion accepted");
        Reject(x=>x.left_world_wxyz[1]=float.NaN, "Nonfinite quaternion accepted");
        Reject(x=>x.age_s=-.001, "Negative source age accepted");
        Reject(x=>x.age_s=.201, "Expired source accepted");
        Reject(x=>x.age_s=double.NaN, "Nonfinite source age accepted");
        Reject(x=>x.source_sequence=-1, "Negative sequence accepted");
        Reject(x=>x.source_sequence=9007199254740992L, "Unsafe integer sequence accepted");
        Reject(x=>x.feedback_sequence=-1, "Negative feedback sequence accepted");
        Reject(x=>x.feedback_sequence=9007199254740992L, "Unsafe feedback sequence accepted");

        value=Example();
        Check(G1GoalPreviewState.Fresh(value, 10, 10.17), "Fresh result rejected");
        Check(!G1GoalPreviewState.Fresh(value, 10, 10.19), "Elapsed receipt time ignored");
        Check(!G1GoalPreviewState.Fresh(value, 10, 9.99), "Reversed local clock accepted");
        Check(!G1GoalPreviewState.Fresh(value, double.NaN, 10), "NaN receipt clock accepted");
        Check(!G1GoalPreviewState.Fresh(value, 10, double.PositiveInfinity), "Infinite local clock accepted");
        Check(G1GoalPreviewState.ValidForFeedback(value, 17, 23), "Exact command packet rejected");
        Check(!G1GoalPreviewState.ValidForFeedback(value, 18, 23), "Earlier input source accepted");
        Check(!G1GoalPreviewState.ValidForFeedback(value, 16, 23), "Future input source accepted");
        Check(!G1GoalPreviewState.ValidForFeedback(value, 17, 24), "Earlier feedback FK accepted");
        Check(!G1GoalPreviewState.ValidForFeedback(value, 17, 22), "Future feedback FK accepted");
        value.age_s=.20;
        Check(G1GoalPreviewState.Fresh(value, 10, 10), "Maximum age boundary rejected");
        Check(!G1GoalPreviewState.Fresh(value, 10, 10.001), "Maximum age did not expire");
        var left=G1GoalPreviewState.Position(value, true);
        var right=G1GoalPreviewState.Position(value, false);
        var rotation=G1GoalPreviewState.RightRotation(value);
        Check(left.x==1 && left.y==2 && left.z==3, "Left position order changed");
        Check(right.x==-4 && right.y==5 && right.z==-6, "Right position order changed");
        Check(rotation.x==0 && rotation.y==.6f && rotation.z==0 && rotation.w==.8f,
              "Wire wxyz was not mapped to Unity xyzw");
        Check(value.right_world_wxyz[0]==.8f && value.right_world_m[0]==-4,
              "Read-only accessor mutated payload");
        return count;
    }
}
'''


class GoalFrameTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt' and POWERSHELL,
                         'PowerShell 7 Roslyn C# compiler required for actual source')
    def test_real_csharp_frame_contract_and_accessors(self):
        source = SOURCE.read_text(encoding='utf-8-sig')
        script = ("$ErrorActionPreference='Stop'\nAdd-Type -TypeDefinition @'\n"
                  + source + STUBS + HARNESS
                  + "\n'@\n$count = [GoalFrameChecks]::Run()\n"
                    "Write-Output ('PASS checks=' + $count)\n")
        result = subprocess.run(
            [POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertIn(b'PASS checks=', result.stdout)


if __name__ == '__main__':
    unittest.main()
