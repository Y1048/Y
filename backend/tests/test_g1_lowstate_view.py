import ast
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import g1_lowstate_view as view

class LowStateTests(unittest.TestCase):
    def sample(self):
        return dict(schema='g1.lowstate.view.v1',session='session',sequence=1,
                    source_monotonic_s=10.,age_s=0.,crc_valid=True,
                    q_rad=[0.]*29,dq_rad_s=[0.]*29,tau_est_nm=[0.]*29)
    def test_joint_order(self):
        self.assertEqual(29,len(view.NAMES));self.assertEqual(29,len(set(view.NAMES)))
        self.assertEqual('left_hip_pitch',view.NAMES[0]);self.assertEqual('right_ankle_roll',view.NAMES[11])
        self.assertEqual('left_shoulder_pitch',view.NAMES[15]);self.assertEqual('right_shoulder_pitch',view.NAMES[22])
        self.assertEqual('right_wrist_yaw',view.NAMES[28])
    def test_validation(self):
        self.assertEqual(self.sample(),view.validate(self.sample()))
        for field,value in [('crc_valid',False),('q_rad',[0.]*12),('q_rad',[float('nan')]*29),('dq_rad_s',[float('inf')]*29),('sequence',True),('age_s',1.),('schema','other')]:
            packet=self.sample();packet[field]=value
            with self.assertRaises(ValueError):view.validate(packet)
    def test_remote_no_publisher_or_commands(self):
        ast.parse(view.REMOTE,feature_version=(3,6))
        self.assertIn("ChannelSubscriber('rt/lowstate'",view.REMOTE)
        for token in ('ChannelPublisher','LowCmd','MotionSwitcher','SportClient','socket.bind'):
            self.assertNotIn(token,view.REMOTE)
