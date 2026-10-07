"""Offline fixtures only; these do not certify G1 hardware or deployment."""
import csv
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools/onboard'/f'{name}.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
reader=load('read_groot_command_observer')
patcher=load('prepare_groot_command_observer')

class ObserverTests(unittest.TestCase):
    def write(self, rows, fields=None):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'fixture.csv'
        with path.open('w',newline='',encoding='utf-8') as f:
            f.write('# schema=groot.command.observation.v1; clock=G1 std::chrono::steady_clock ns; fixture=generated\n')
            w=csv.DictWriter(f,fieldnames=fields or reader.FIELDS); w.writeheader(); w.writerows(rows)
            f.write('# final dropped=0 invalid=0 errors=0\n')
        return path
    def row(self, seq=1):
        x=dict.fromkeys(reader.FIELDS,0)
        x.update(writer_sequence=seq,write_begin_ns=100+seq*10,write_end_ns=101+seq*10,
                 target_created_ns=90,state_available=1,state_received_ns=80)
        for i in range(29): x['sent_q'+str(i)]=i/100
        return x
    def test_round_trip_and_29_joint_order(self):
        rows=reader.read_log(self.write([self.row(),self.row(2)]))
        self.assertEqual(len(reader.JOINT_NAMES),29)
        self.assertEqual(reader.JOINT_NAMES[15],'left_shoulder_pitch')
        self.assertEqual(reader.JOINT_NAMES[28],'right_wrist_yaw')
        self.assertEqual(rows[1]['sent_q28'],.28)
    def test_gap_and_nonmonotonic(self):
        for seq in (1,3):
            with self.assertRaises(ValueError): reader.read_log(self.write([self.row(),self.row(seq)]))
    def test_invalid_data(self):
        for key,value in [('kp22',float('nan')),('sent_q15',float('inf')),('state_available',0),
                          ('state_received_ns',999),('write_end_ns',1),('arms_active',2),
                          ('dropped_total',1),('invalid_total',1),('sent_q22','')]:
            row=self.row(); row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): reader.read_log(self.write([row]))
    def test_joint_header_reordering(self):
        fields=reader.FIELDS.copy(); fields[-1],fields[-2]=fields[-2],fields[-1]
        with self.assertRaises(ValueError): reader.read_log(self.write([self.row()],fields))
    def test_source_mismatch_rejected(self):
        with self.assertRaises(ValueError): patcher.instrument(b'other source')
    def test_incomplete_or_final_loss_rejected(self):
        for footer in ('', '# final dropped=1 invalid=0 errors=0\n'):
            path=self.write([self.row()])
            text=path.read_text().replace('# final dropped=0 invalid=0 errors=0\n',footer)
            path.write_text(text)
            with self.assertRaises(ValueError): reader.read_log(path)
    def test_header_has_no_publisher_or_network(self):
        h=(ROOT/'tools/onboard/groot_command_observer.hpp').read_text()
        for forbidden in ('unitree/', 'ChannelPublisher', 'sendto(', 'socket(', 'LowCmd'):
            self.assertNotIn(forbidden,h)
    @unittest.skipUnless(os.environ.get('GROOT_OBSERVER_BASELINE'), 'requires separately retrieved pinned G1 source')
    def test_pinned_control_path_preservation(self):
        raw=Path(os.environ['GROOT_OBSERVER_BASELINE']).read_bytes()
        old=raw.decode().replace('\r\n','\n'); new=patcher.instrument(raw)
        for start,end in [('const std::array<float, kDofs> kGrootKp','using ObservationFrame'),
                          ('void set_external_arm_goal(','std::atomic<int> gSignalCount'),
                          ('LowCmd compose_lowcmd(','int run_compose_test()'),
                          ('class ActuationLogger {','class ActuationController {')]:
            self.assertEqual(old[old.index(start):old.index(end)],new[new.index(start):new.index(end)])
        for token in ('publisher_->Write(', 'new unitree::robot::ChannelPublisher',
                      'advance_external_arm_target(&arm_target, arm_goal);'):
            self.assertEqual(old.count(token),new.count(token))
        patch=''.join(__import__('difflib').unified_diff(old.splitlines(True),new.splitlines(True),
                     'a/src/g1_balance_actuator.cpp','b/src/g1_balance_actuator.cpp'))
        self.assertEqual(patch,(ROOT/'tools/onboard/groot_command_observer.patch').read_text())

if __name__=='__main__': unittest.main()
