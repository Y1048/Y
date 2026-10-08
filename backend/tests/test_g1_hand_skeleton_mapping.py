"""Compile the real bone selector; enums model the installed SDK's overlapping IDs."""
from pathlib import Path
import os, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
CSC=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
@unittest.skipUnless(CSC.exists(),'Windows C# compiler required')
class SkeletonMappingTests(unittest.TestCase):
    def test_legacy_and_openxr_semantics(self):
        helper=(ROOT/'Unity_G1_VR/Assets/G1Teleop/G1HandSkeletonMapping.cs').read_text()
        fixture=r'''
using System;
public class OVRSkeleton {
 public enum SkeletonType {None,HandLeft,HandRight,XRHandLeft,XRHandRight,Body,FullBody}
 public enum BoneId {Invalid=-1,Hand_WristRoot=0,XRHand_Palm=0,XRHand_Wrist=1,
 Hand_Index1=6,Hand_Middle1=9,Hand_Pinky1=16,
 XRHand_IndexProximal=7,XRHand_MiddleProximal=12,XRHand_LittleProximal=22}
}
public class Fixture {
 public static void Main() {
  foreach(var type in new[]{OVRSkeleton.SkeletonType.XRHandLeft,OVRSkeleton.SkeletonType.XRHandRight}) {
   Check(type,G1HandSkeletonMapping.Joint.Wrist,1);
   Check(type,G1HandSkeletonMapping.Joint.IndexBase,7);
   Check(type,G1HandSkeletonMapping.Joint.MiddleBase,12);
   Check(type,G1HandSkeletonMapping.Joint.PinkyBase,22);
  }
  foreach(var type in new[]{OVRSkeleton.SkeletonType.HandLeft,OVRSkeleton.SkeletonType.HandRight}) {
   Check(type,G1HandSkeletonMapping.Joint.Wrist,0);
   Check(type,G1HandSkeletonMapping.Joint.IndexBase,6);
   Check(type,G1HandSkeletonMapping.Joint.MiddleBase,9);
   Check(type,G1HandSkeletonMapping.Joint.PinkyBase,16);
  }
  foreach(var type in new[]{OVRSkeleton.SkeletonType.None,OVRSkeleton.SkeletonType.Body,OVRSkeleton.SkeletonType.FullBody})
   Check(type,G1HandSkeletonMapping.Joint.Wrist,-1);
  Check(OVRSkeleton.SkeletonType.XRHandLeft,(G1HandSkeletonMapping.Joint)99,-1);
  Console.WriteLine("PASS real bone mapping: overlapping palm/wrist IDs and anatomical bases");
 }
 static void Check(OVRSkeleton.SkeletonType t,G1HandSkeletonMapping.Joint j,int wanted) {
  if((int)G1HandSkeletonMapping.Bone(t,j)!=wanted) throw new Exception(t+" "+j);
 }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'fixture.cs'; source.write_text(fixture+'\n'+helper,encoding='utf-8')
            exe=Path(folder)/'fixture.exe'
            compiled=subprocess.run([str(CSC),'/nologo','/out:'+str(exe),str(source)],capture_output=True,timeout=30)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            run=subprocess.run([str(exe)],capture_output=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stdout.decode(errors='replace'))
            self.assertIn(b'PASS real bone mapping',run.stdout)
if __name__=='__main__':unittest.main()