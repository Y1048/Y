"""Offline generated keyboard fixtures; no SSH, DDS or G1 motor execution."""
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import g1_unity_keyboard_gateway as keyboard
import G1_INPUT_RECEIVE_AUDIT as audit
import G1_VR_TELEOP_LAUNCH as launch
import G1_GROOT_REMOTE_LAUNCH as remote

spec = importlib.util.spec_from_file_location('keyboard_heading_test', ROOT / 'tools/onboard/g1_omni_heading_controller.py')
heading = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = heading
# Windows cannot import terminal drivers. Tests call pure parsing/math only.
with mock.patch.dict(sys.modules, {'termios': types.ModuleType('termios'), 'tty': types.ModuleType('tty')}):
    spec.loader.exec_module(heading)


class KeyboardTests(unittest.TestCase):
    def packet(self, **change):
        return dict(schema=keyboard.SCHEMA, token='a'*32, request_sequence=1,
                    focused=True, forward=0, left=0, turn_left=0, **{}) | change

    def command(self, **change):
        return keyboard.velocity(self.packet(**change), 'a'*32, {1: 10.0}, 10.01)

    def values(self, command):
        adapter=keyboard.OmniKeyboardAdapter(0.)
        adapter.accept(command,0.)
        return adapter.values(0.)

    def outer(self, command=(0.2, 0, 0.2)):
        return dict(schema='g1.observation.audit.v1', observation_only=True, session='a'*32,
                    sequence=1, payload={'omni':dict(status='FRESH_LIVE', source_session='keyboard',
                    source_age_s=0.01, source_receive_age_s=0.01, values=self.values(command))})

    def test_six_directions_and_zero(self):
        for name, index in [('forward', 0), ('left', 1), ('turn_left', 2)]:
            for sign in (-1, 1):
                expected = [0.0]*3; expected[index] = sign*.2
                self.assertEqual(tuple(expected), self.command(**{name:sign}))
        self.assertEqual((0., 0., 0.), self.command())

    def test_diagonal_has_same_translation_speed(self):
        x,y,w = self.command(forward=1, left=1, turn_left=1)
        self.assertAlmostEqual(.2, math.hypot(x,y))
        self.assertEqual(.2,w)

    def test_focus_loss_zeros_all_axes(self):
        self.assertEqual((0.,0.,0.),self.command(forward=1,left=1,turn_left=1,focused=False))

    def test_expired_replayed_and_reordered_requests_rejected(self):
        pending = {0:10.,1:10.}
        keyboard.velocity(self.packet(), 'a'*32, pending,10.01)
        self.assertEqual({},pending)
        for packet, requests, now in [(self.packet(), pending,10.02),
            (self.packet(),{1:10.},10.151), (self.packet(request_sequence=0),pending,10.02)]:
            with self.assertRaises(ValueError): keyboard.velocity(packet,'a'*32,requests,now)

    def test_bad_samples_rejected(self):
        for field,value in [('forward',True),('left',float('nan')),('turn_left',2),
                            ('focused',1),('token','wrong'),('schema','wrong'),('request_sequence',True)]:
            with self.subTest(field=field), self.assertRaises(ValueError): self.command(**{field:value})

    def test_tap_schema_and_explicit_origin(self):
        source=dict(schema=audit.SOURCE_SCHEMA, observation_only=True, stream='omni',
                    session='b'*32, sequence=1, source_monotonic_s=1.0,
                    values=self.values((.2,0.,-.2)))
        self.assertEqual(source,audit.validate_source(source))
        self.assertEqual(0.,source['values']['arm_yaw_deg'])
        self.assertTrue(source['values']['calibrated'])
        for field,value in [('vx',float('inf')),('yaw_rate',.3),('source_origin','omni_connect'),('arm_yaw_deg',float('nan')),('calibrated',False)]:
            bad=json.loads(json.dumps(source)); bad['values'][field]=value
            with self.assertRaises(ValueError):audit.validate_source(bad)

    def test_existing_receiver_accepts_keyboard_without_new_flags(self):
        sample=heading.parse_omni_observation(json.dumps(self.outer()).encode(),1.)
        self.assertEqual(.2,sample.vx)
        self.assertEqual(0.,sample.arm_yaw_rad)

    def test_pc_combined_sender_snapshot_to_unmodified_receiver(self):
        source=dict(schema=audit.SOURCE_SCHEMA, observation_only=True, stream='omni',
                    session='b'*32, sequence=1, source_monotonic_s=1.,
                    values=self.values((.2,-.1,0.)))
        sources=audit.LiveSources()
        self.assertTrue(sources.accept(json.dumps(source).encode(),('127.0.0.1',12345),1.01))
        outer=self.outer();outer['payload']['omni']=sources.snapshot('omni',1.02)
        sample=heading.parse_omni_observation(json.dumps(outer).encode(),2.)
        self.assertEqual((.2,-.1,0.),(sample.vx,sample.vy,sample.arm_yaw_rad))

    def test_virtual_heading_both_directions_and_release(self):
        for rate in (-.2,.2):
            adapter=keyboard.OmniKeyboardAdapter(0.)
            follower=heading.HeadingFollower(1.5,.7,.01,-1)
            follower.update(0.,1.2)  # Existing Omni/G1 initial direction calibration.
            for i in range(120):
                adapter.accept((.2,0.,rate),i/60)
                values=adapter.values((i+1)/60)
            self.assertAlmostEqual(-rate*2,math.radians(values['arm_yaw_deg']))
            packet=self.outer();packet['payload']['omni']['values']=values
            sample=heading.parse_omni_observation(json.dumps(packet).encode(),2.)
            target,error,wz=follower.update(sample.arm_yaw_rad,1.2)
            self.assertAlmostEqual(rate*2,target)
            self.assertGreater(wz*rate,0.)
            adapter.accept((0.,0.,0.),2.)
            held=adapter.values(3.)
            self.assertEqual(values['arm_yaw_deg'],held['arm_yaw_deg'])
            self.assertEqual(0.,held['vx'])
            # Release holds a direction; robot can finish its outstanding turn.
            _,_,wz=follower.update(math.radians(held['arm_yaw_deg']),1.2)
            self.assertGreater(wz*rate,0.)
            _,_,wz=follower.update(math.radians(held['arm_yaw_deg']),1.2+target)
            self.assertEqual(0.,wz)

    def test_expired_input_stops_heading_and_stall_does_not_catch_up(self):
        a=keyboard.OmniKeyboardAdapter(0.); a.accept((.2,0.,.2),0.)
        for i in range(1,21): v=a.values(i*.01)
        self.assertAlmostEqual(-.2*keyboard.TIMEOUT,math.radians(v['arm_yaw_deg']))
        self.assertEqual((0.,0.,0.),a.command)
        last=v['arm_yaw_deg'];self.assertEqual(last,a.values(10.)['arm_yaw_deg'])
        a.accept((0.,0.,.2),10.)
        self.assertEqual(last,a.values(11.)['arm_yaw_deg'])
        with self.assertRaises(ValueError):a.values(10.)

    def test_reverse_focus_loss_and_wrap(self):
        a=keyboard.OmniKeyboardAdapter(0.)
        a.yaw_rad=math.radians(179.99)
        a.accept((0.,0.,-.2),0.)
        first=a.values(.1)['arm_yaw_deg']
        self.assertGreater(first,180.)
        a.accept((0.,0.,.2),.1)
        self.assertAlmostEqual(179.99,a.values(.2)['arm_yaw_deg'])
        a.accept(self.command(focused=False,turn_left=1),.2)
        self.assertAlmostEqual(179.99,a.values(.3)['arm_yaw_deg'])

    def test_omni_self_test_unchanged(self):
        self.assertEqual(0,heading.run_self_test())

    def test_launch_excludes_omni_and_rejects_conflict(self):
        plan=launch.launch_plan(set(),True,base_input='keyboard',no_groot_actuation=True)
        self.assertIn('keyboard',plan); self.assertNotIn('omni',plan); self.assertNotIn('groot',plan)
        for existing,mode in [({'omni'},'keyboard'),({'keyboard'},'omni')]:
            with self.assertRaises(RuntimeError):launch.launch_plan(existing,True,base_input=mode)

    def test_receiver_and_remote_launcher_identical_to_baseline(self):
        for name in ('tools/onboard/g1_omni_heading_controller.py',
                     'tools/G1_GROOT_REMOTE_LAUNCH.py','tools/g1_quiet_observation.py'):
            baseline=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
            self.assertEqual(baseline.replace(b'\r\n',b'\n'),
                             (ROOT/name).read_bytes().replace(b'\r\n',b'\n'))
        self.assertEqual('-1',remote.HEADING_ARGV[remote.HEADING_ARGV.index('--yaw-sign')+1])

    def test_real_local_udp_preview_and_input_timeout(self):
        # Actual local UDP and gateway process, generated Unity replies only.
        # --preview has no observation tap and no G1 destination.
        with keyboard.bound(keyboard.UNITY_PORT) as unity, tempfile.TemporaryFile() as log:
            child=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/g1_unity_keyboard_gateway.py'),
                '--preview'],stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                received=0
                end=time.monotonic()+0.6
                while time.monotonic()<end:
                    self.assertIsNone(child.poll())
                    try: raw,peer=unity.recvfrom(2048)
                    except BlockingIOError:
                        time.sleep(.002); continue
                    request=json.loads(raw)
                    request.update(focused=True,forward=1,left=0,turn_left=-1)
                    unity.sendto(json.dumps(request).encode(),peer)
                    received+=1
                self.assertGreater(received,5)
                time.sleep(.3)  # Simulate frozen/closed Unity: gateway must output zero.
            finally:
                child.terminate(); child.wait(timeout=5)
            log.seek(0); output=log.read().decode()
        self.assertIn('vx=0.200 vy=0.000 yaw_rate=-0.200',output)
        self.assertTrue(output.rstrip().endswith('vx=0.000 vy=0.000 yaw_rate=0.000'),output)

    def test_no_robot_output_in_preview_source(self):
        source=(ROOT/'tools/g1_unity_keyboard_gateway.py').read_text()
        self.assertNotIn('unitree_sdk',source)
        self.assertNotIn('ChannelPublisher',source)
        self.assertNotIn('192.168.',source)


if __name__ == '__main__': unittest.main()
