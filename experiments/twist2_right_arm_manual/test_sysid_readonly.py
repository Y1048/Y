"""Generated parser fixtures and source architecture checks only."""
import json
import tempfile
import unittest
from pathlib import Path
import sysid_readonly_parse as parser
from sysid_capture import JOINT_NAMES

ROOT=Path(__file__).resolve().parent

def row(k,command=True):
    n=1000000000+k*2000000;v=[float(k+i) for i in range(29)]
    r={'schema':parser.SCHEMA,'session':'generated','sequence':k,'provenance':{'kind':'measured','source':'test'},
      'clock':{'source':'fixture','domain':'fixture'},'joint_indices':list(range(29)),'joint_names':list(JOINT_NAMES),
      'units':{'time':'ns'},'acceptance':'unknown','state_receive_ns':n,'state_tick':k+1,'state_crc':1,'mode_pr':0,'mode_machine':5,
      'has_command':command,'command_receive_ns':n-1000 if command else None,'command_age_ns':1000 if command else None,
      'command_crc':2 if command else None,'measured_q':v,'measured_dq':v,'torque_estimate':v,'temperature':[20]*29,
      'motor_status':[0]*29,'imu_rpy':[0.,0.,0.],'imu_gyro':[0.,0.,0.],'imu_accel':[0.,0.,9.81],'dropped_samples':0}
    for key in parser.COMMAND:r[key]=v if command else None
    return r

def save(path,rows,complete=True,dropped=0):
    path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
    Path(str(path)+'.receipt.json').write_text(json.dumps({'schema':'g1.sysid.readonly-dds.receipt.v1','complete':complete,'written':len(rows),'dropped':dropped,'acceptance':'unknown'}))

class ReadonlyTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'x.jsonl'
    def tearDown(self):self.tmp.cleanup()
    def test_source_has_no_command_path(self):
        source=(ROOT/'sysid_readonly_dds.cpp').read_text()
        for forbidden in ('ChannelPublisher','MotionSwitcherClient','LocoClient','Write('):self.assertNotIn(forbidden,source)
        self.assertEqual(source.count('ChannelSubscriber<'),2)
        cmake=(ROOT/'native_vr_build/CMakeLists.txt').read_text()
        block=cmake[cmake.index('add_executable(g1_sysid_readonly_dds'):]
        self.assertNotIn('configure_torch(g1_sysid_readonly_dds)',block)
    def test_roundtrip_command_and_state_only(self):
        save(self.path,[row(0,False),row(1,True)]);rows=parser.read(self.path)
        self.assertFalse(rows[0]['has_command']);self.assertTrue(rows[1]['has_command'])
    def test_incomplete_or_gap_rejected(self):
        save(self.path,[row(0)],False)
        with self.assertRaisesRegex(ValueError,'receipt'):parser.read(self.path)
        self.path.unlink();Path(str(self.path)+'.receipt.json').unlink();r=[row(0),row(2)];save(self.path,r)
        with self.assertRaisesRegex(ValueError,'sequence'):parser.read(self.path)
    def test_conflicting_same_command_rejected(self):
        r=[row(0),row(1)];r[1]['command_receive_ns']=r[0]['command_receive_ns'];r[1]['command_age_ns']=r[1]['state_receive_ns']-r[1]['command_receive_ns'];r[1]['kp'][0]+=1;save(self.path,r)
        with self.assertRaisesRegex(ValueError,'conflicting'):parser.read(self.path)
    def test_repeated_state_tick_is_reported(self):
        r=[row(0),row(1)];r[1]['state_tick']=r[0]['state_tick'];save(self.path,r)
        self.assertEqual(parser.inspect(self.path)['repeated_state_ticks'],1)
    def test_nonfinite_rejected(self):
        r=row(0);r['measured_q'][0]=float('nan');save(self.path,[r])
        with self.assertRaisesRegex(ValueError,'nonfinite'):parser.read(self.path)

if __name__=='__main__':unittest.main()
