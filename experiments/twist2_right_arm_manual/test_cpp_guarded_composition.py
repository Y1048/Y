"""Native synthetic faults and reference-constant drift checks. No sockets."""
import re
import subprocess
import unittest
from test_cpp_upper_target import ROOT, Packet

class GuardedTests(unittest.TestCase):
    def test_native_faults_and_composition(self):
        for case in ('valid','candidate_limit','crc','mode','deadman','emergency','imu','tilt','q','dq',
                     'torque','temperature','motor_fault','policy_missing','policy_old',
                     'policy_future','policy_state','policy_repeat','action_nan','action_range'):
            with self.subTest(case=case):
                r=subprocess.run([str(ROOT/'logs/test_results/test_guarded_composition.exe'),case],
                    input=Packet()+'\n',text=True,capture_output=True,timeout=5)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_reference_constants_have_not_drifted(self):
        reference=(ROOT/'references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp').read_text()
        snapshot=(ROOT/'experiments/twist2_right_arm_manual/offline_twist2_constants.hpp').read_text()
        for name in ('kDefault','kLower','kUpper','kActionScale','kActionLimit','kJointLimitMargin','kKp','kKd','kTorqueLimit'):
            with self.subTest(name=name):
                pattern=name+r' = (.*?);'
                normalize=lambda s: re.sub(r'\s+','',re.search(pattern,s,re.S).group(1))
                self.assertEqual(normalize(reference),normalize(snapshot))

if __name__=='__main__': unittest.main()
