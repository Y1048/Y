"""Paired input protocol/state tests and a real loopback synthetic sender."""
import copy
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import (UnityCycle, PairedHandFilter, decode, BASIS, SCHEMA,
                                   WORLD_SCHEMA, WORLD_FRAME, mink,
                                   TRACKING_LOSS_RETURN_DELAY_S)
from g1_bimanual_limits import TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2, TRACKING_JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_return import BimanualReturnMotion


def packet(sequence=0, engage=False, session='test', tracked=True, returning=False):
    return dict(schema=SCHEMA, simulation_only=True, session=session, sequence=sequence,
        sender_time_s=sequence / 60, engage=engage, return_home=returning,
        left=dict(tracked=tracked, position_m=[-.22, -.24, .38], quaternion_wxyz=[1, 0, 0, 0]),
        right=dict(tracked=tracked, position_m=[.22, -.24, .38], quaternion_wxyz=[1, 0, 0, 0]))


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.sim = Mock()
        self.sim.state = 'tracking'
        self.sim.home_targets = {s: mink.SE3.identity() for s in ('left', 'right')}
        self.cycle = UnityCycle(self.sim)

    def engage(self):
        self.cycle.receive(packet(), 0.)
        self.cycle.receive(packet(1, True), .02)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_validation_nonfinite_missing_duplicates(self):
        self.assertEqual(decode(json.dumps(packet()).encode()), packet())
        for field, value in [('sequence', True), ('sender_time_s', float('nan')),
                             ('engage', 1), ('simulation_only', False)]:
            p = packet()
            p[field] = value
            with self.assertRaises(ValueError):
                decode(json.dumps(p).encode())
        p = packet()
        del p['right']
        with self.assertRaises(ValueError):
            decode(json.dumps(p).encode())
        with self.assertRaises(ValueError):
            decode(b'{"schema":1,"schema":2}')

    def test_startup_active_requires_inactive_edge(self):
        self.cycle.receive(packet(0, True), 0)
        self.assertEqual(self.cycle.state, 'ready')
        self.cycle.receive(packet(1, False), .02)
        self.cycle.receive(packet(2, True), .04)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_world_frame_bypasses_legacy_filter(self):
        p0 = packet(0, False)
        p1 = packet(1, True)
        p2 = packet(2, True)
        for value in (p0, p1, p2):
            value['schema'] = WORLD_SCHEMA
            value['input_frame'] = WORLD_FRAME
            value['base_yaw_rad'] = 0.0
        p2['right']['position_m'][0] += .123
        self.cycle.legacy_filter.reset = Mock(
            side_effect=AssertionError('world path used legacy reset'))
        self.cycle.legacy_filter.update = Mock(
            side_effect=AssertionError('world path used legacy update'))
        self.assertTrue(self.cycle.receive(p0, 0.0))
        self.assertTrue(self.cycle.receive(p1, .02))
        self.assertIsNone(self.cycle.origins)
        self.assertTrue(self.cycle.receive(p2, .04))
        np.testing.assert_allclose(
            self.cycle.hands['right']['position_m'],
            p2['right']['position_m'])
        self.cycle.legacy_filter.reset.assert_not_called()
        self.cycle.legacy_filter.update.assert_not_called()

    def test_mapping_same_frame_both_hands(self):
        self.engage()
        p = packet(2, True)
        delta = np.array([.01, .02, .03])
        rotation = mink.SO3.exp(np.array([.1, -.2, .3]))
        for side in ('left', 'right'):
            p[side]['position_m'] = (np.array(p[side]['position_m']) + delta).tolist()
            p[side]['quaternion_wxyz'] = rotation.wxyz.tolist()
        self.cycle.receive(p, .04)
        self.cycle.tick(.04)
        goals = self.sim.step.call_args.args[0]
        for goal in goals.values():
            position_alpha = -np.expm1(-(2/60-1/60)/.060)
            rotation_alpha = -np.expm1(-(2/60-1/60)/.050)
            np.testing.assert_allclose(goal.translation(), position_alpha*np.array([.03, -.01, .02]))
            filtered_rotation = mink.SO3.exp(rotation_alpha*np.array([.1, -.2, .3]))
            np.testing.assert_allclose(goal.rotation().as_matrix(), BASIS @ filtered_rotation.as_matrix() @ BASIS.T)

    def test_pinch_return_ignores_early_engage_then_rearms(self):
        self.engage()
        self.cycle.receive(packet(2, True, returning=True), .04)
        self.assertEqual(self.cycle.state, 'returning')
        self.cycle.receive(packet(3, True), .06)
        self.cycle.tick(.06)
        self.sim.step.assert_called_with(returning=True)
        self.sim.state = 'ready'
        self.cycle.tick(.08)
        self.cycle.receive(packet(4, True), .09)
        self.assertEqual(self.cycle.state, 'ready')
        self.cycle.receive(packet(5), .1)
        self.cycle.receive(packet(6, True), .12)
        self.assertEqual(self.cycle.state, 'tracking')

    def test_tracking_grace_timeout_and_reordering(self):
        self.engage()
        self.assertFalse(self.cycle.receive(packet(1, True), .5))
        self.assertEqual(self.cycle.received, .02)
        self.cycle.receive(packet(2, True, tracked=False), .03)
        self.cycle.tick(.03)
        self.assertEqual(self.cycle.state, 'tracking')
        # Fresh packets keep the communication timeout independent from the
        # longer hand-loss grace period.
        self.cycle.receive(packet(3, True, tracked=False), .7)
        self.cycle.tick(.7)
        self.cycle.receive(packet(4, True, tracked=False), 1.3)
        self.cycle.tick(1.3)
        self.cycle.receive(packet(5, True, tracked=False), 1.54)
        self.cycle.tick(1.54)
        self.assertEqual(self.cycle.reason, 'tracking_lost')
        other = UnityCycle(self.sim)
        other.receive(packet(), 0)
        other.receive(packet(1, True), .01)
        other.tick(.77)
        self.assertEqual(other.reason, 'input_timeout')

    def test_recorded_short_left_hand_losses_brake_then_resume(self):
        # Measured input-flag loss durations from the 2026-10-07 16:57 session.
        # This is a state-machine fixture, not a measured robot response replay.
        for duration in (.828, .407, 1.359):
            with self.subTest(duration=duration):
                sim = Mock(state='tracking')
                sim.home_targets = self.sim.home_targets
                cycle = UnityCycle(sim)
                cycle.receive(packet(), 0.)
                cycle.receive(packet(1, True), .02)
                sequence = 2
                for elapsed in np.arange(0., duration, 1/60):
                    p = packet(sequence, True)
                    p['left']['tracked'] = False
                    cycle.receive(p, .04 + elapsed)
                    cycle.tick(.04 + elapsed)
                    self.assertEqual(cycle.state, 'tracking')
                    self.assertEqual(cycle.last_tick_action, 'tracking_braking')
                    sequence += 1
                sim.step.assert_not_called()
                sim.brake.assert_called_with('tracking_unavailable')
                cycle.receive(packet(sequence, True), .04 + duration)
                cycle.tick(.04 + duration)
                self.assertEqual(cycle.state, 'tracking')
                self.assertEqual(cycle.last_tick_action, 'tracking')
                self.assertIsNone(cycle.loss_since)
                sim.step.assert_called_once()

    def test_sustained_single_hand_loss_returns_at_boundary(self):
        self.engage()
        for sequence, elapsed in enumerate((0., .6, 1.2, 1.499, 1.501), 2):
            p = packet(sequence, True)
            p['right']['tracked'] = False
            self.cycle.receive(p, .04 + elapsed)
            self.cycle.tick(.04 + elapsed)
            self.assertEqual(self.cycle.state,
                             'returning' if elapsed >= TRACKING_LOSS_RETURN_DELAY_S else 'tracking')
        self.assertEqual(self.cycle.reason, 'tracking_lost')

    def test_recovered_hand_resets_loss_timer(self):
        self.engage()
        for sequence, elapsed, tracked in ((2,.04,False),(3,.64,False),
                (4,1.24,False),(5,1.34,True),(6,1.44,False),
                (7,2.04,False),(8,2.64,False)):
            self.cycle.receive(packet(sequence, True, tracked=tracked), elapsed)
            self.cycle.tick(elapsed)
            self.assertEqual(self.cycle.state, 'tracking')
        self.assertAlmostEqual(self.cycle.loss_since, 1.44)

    def test_pinch_still_returns_during_hand_loss_grace(self):
        self.engage()
        self.cycle.receive(packet(2, True, tracked=False), .04)
        self.cycle.tick(.04)
        self.cycle.receive(packet(3, True, tracked=False, returning=True), .06)
        self.assertEqual(self.cycle.state, 'returning')
        self.assertEqual(self.cycle.reason, 'pinch')

    def test_real_solver_brakes_and_recovers_without_return(self):
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        cycle.receive(packet(), 0.)
        cycle.receive(packet(1, True), sim.dt)
        previous_velocity = np.zeros(14)
        sequence = 2
        for tick in range(140):
            p = packet(sequence, True)
            p['right']['position_m'][2] += .03
            # 1.25 s of invalid left-hand input. The invalid position must
            # never be solved, even if it contains an arbitrarily distant goal.
            if 30 <= tick < 105:
                p['left']['tracked'] = False
                p['left']['position_m'] = [9.,9.,9.]
            now = (sequence+1)*sim.dt
            before = sim.config.q[sim.qids].copy()
            cycle.receive(p, now)
            cycle.tick(now)
            self.assertEqual(cycle.state, 'tracking')
            self.assertEqual(cycle.last_tick_action,
                'tracking_braking' if 30 <= tick < 105 else 'tracking')
            velocity = (sim.config.q[sim.qids]-before)/sim.dt
            np.testing.assert_allclose(velocity,sim.velocity[sim.dofs],atol=1e-9)
            self.assertTrue(np.all(np.abs(velocity)<=sim.caps+1e-6))
            self.assertLessEqual(float(np.max(np.abs(velocity-previous_velocity))/sim.dt),
                TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2+1e-5)
            self.assertGreaterEqual(sim.clearance(sim.config.q),sim.clearance_m)
            self.assertTrue(np.all(sim.config.q[sim.qids]>=sim.ranges[:,0]-1e-8))
            self.assertTrue(np.all(sim.config.q[sim.qids]<=sim.ranges[:,1]+1e-8))
            if tick==104:np.testing.assert_allclose(velocity,0.,atol=1e-9)
            previous_velocity=velocity
            sequence+=1
        self.assertIsNone(cycle.loss_since)

    def test_session_change_returns_and_blocked_is_not_ready(self):
        self.engage()
        self.cycle.receive(packet(0, True, session='new'), .04)
        self.assertEqual(self.cycle.reason, 'session_changed')
        self.sim.state = 'blocked'
        self.sim.reason = 'swept_clearance'
        self.cycle.tick(.05)
        self.assertEqual(self.cycle.state, 'blocked')

    def test_checked_target_feedback_uses_stationary_checked_tail_fk(self):
        sim = BimanualSimulation()
        zero_velocity = np.zeros(sim.model.nv)
        sim.brake_plan = [(sim.home.copy(), zero_velocity)]
        cycle = UnityCycle(sim)
        cycle.state = 'tracking'
        cycle.last_tick_action = 'tracking'
        cycle.world_input = True
        cycle.input_frame = WORLD_FRAME
        sim.state = 'tracking'
        for side, policy in sim.motion.items():
            policy.position_approach_rate_s = 1.0
            policy.orientation_approach_rate_s = 1.0
            policy.effective_target_position = np.array([9.0, 8.0, 7.0])
            policy.effective_target_rotation = np.eye(3)

        feedback = cycle.feedback()

        self.assertTrue(feedback['checked_target_valid'])
        for side in ('left', 'right'):
            expected = BASIS.T @ sim.home_targets[side].translation()
            np.testing.assert_allclose(
                feedback[side+'_checked_target_world_m'],
                expected,
                atol=1e-10,
                rtol=0,
            )
            self.assertFalse(np.allclose(
                feedback[side+'_checked_target_world_m'],
                feedback[side+'_ik_target_world_m'],
            ))

    def test_checked_target_rejects_nonstationary_tail_endpoint(self):
        sim = BimanualSimulation()
        velocity = np.zeros(sim.model.nv)
        velocity[sim.dofs[0]] = 0.01
        sim.brake_plan = [(sim.home.copy(), velocity)]
        self.assertIsNone(sim.checked_stop_target_poses())

    def test_near_hands_stop_consumes_residual_acceleration_before_probe(self):
        motion = BimanualReturnMotion.__new__(BimanualReturnMotion)
        sim = Mock()
        sim.velocity = np.zeros(4)
        sim.dofs = np.array([1, 2])
        sim.acceleration = np.array([0.0, 0.25, 0.0, 0.0])

        def consume_stationary_sample(reason, *, returning):
            self.assertEqual(reason, 'return_near_hands_stop')
            self.assertTrue(returning)
            sim.acceleration[:] = 0.0
            return True

        sim.brake.side_effect = consume_stationary_sample
        motion.sim = sim
        motion._begin_separation = Mock(return_value=True)

        self.assertTrue(motion._step_near_hands_stop())
        sim.brake.assert_called_once_with(
            'return_near_hands_stop', returning=True)
        motion._begin_separation.assert_called_once_with()

    def test_near_hands_tracking_lost_cycle_returns_ready(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_near_hands_20260918.json').read_text())
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = fixture['q14']
        sim.config.update(q)
        sim.velocity[:] = 0.
        sim.velocity[sim.dofs] = fixture['velocity14']
        sim.acceleration[:] = 0.
        sim.acceleration[sim.dofs] = fixture['acceleration14']
        sim.brake_plan = []
        for item in fixture['brake_plan']:
            candidate = sim.home.copy()
            candidate[sim.qids] = item['q14']
            velocity = np.zeros(sim.model.nv)
            velocity[sim.dofs] = item['velocity14']
            sim.brake_plan.append((candidate, velocity))

        cycle = UnityCycle(sim)
        cycle.state = 'tracking'
        cycle.start_return('tracking_lost')
        previous_velocity = sim.velocity[sim.dofs].copy()
        minimum = sim.clearance(sim.config.q)
        maximum_acceleration = 0.
        stages = []

        for tick in range(900):
            before = sim.config.q.copy()
            cycle.tick((tick + 1) * sim.dt)
            velocity = (sim.config.q[sim.qids] - before[sim.qids]) / sim.dt
            np.testing.assert_allclose(velocity, sim.velocity[sim.dofs], atol=1e-10, rtol=0)
            acceleration = np.max(np.abs(velocity - previous_velocity)) / sim.dt
            maximum_acceleration = max(maximum_acceleration, float(acceleration))
            previous_velocity = velocity
            self.assertTrue(np.all(np.abs(velocity) <= sim.caps + 1e-6))
            self.assertTrue(np.all(sim.config.q[sim.qids] >= sim.ranges[:, 0] - 1e-8))
            self.assertTrue(np.all(sim.config.q[sim.qids] <= sim.ranges[:, 1] + 1e-8))
            clearance = sim.clearance(sim.config.q)
            minimum = min(minimum, clearance)
            self.assertGreaterEqual(clearance, sim.clearance_m)
            if not stages or stages[-1] != sim.return_motion.stage:
                stages.append(sim.return_motion.stage)
            if cycle.state == 'ready':
                break

        self.assertEqual(cycle.reason, 'tracking_lost')
        self.assertEqual(cycle.state, 'ready')
        self.assertEqual(sim.state, 'ready')
        self.assertEqual(sim.return_motion.stage, 'complete')
        self.assertTrue(sim.return_motion.near_hands_recovery)
        self.assertEqual(sim.return_motion.separation_side, 'left')
        self.assertEqual(stages,
                         ['near_hands_stop', 'separate_left', 'safe_waypoint', 'home', 'complete'])
        self.assertGreaterEqual(minimum, sim.clearance_m)
        self.assertLessEqual(maximum_acceleration, TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2 + 1e-5)
        self.assertEqual(np.max(np.abs(sim.velocity)), 0.)
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-6, rtol=0)

    def test_real_loopback_synthetic_sender(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            sender.bind(('127.0.0.1', 0))
            sender.settimeout(.1)
            output = Path(directory)/'loopback.jsonl'
            stdout_path, stderr_path = Path(directory)/'stdout.txt', Path(directory)/'stderr.txt'
            # Files cannot fill an unread stdout/stderr pipe. Startup stages
            # identify import/model/listener/exit delays without extending budgets.
            with stdout_path.open('w', encoding='utf-8') as out_file, stderr_path.open('w', encoding='utf-8') as err_file:
                process = subprocess.Popen([sys.executable, '-B',
                    str(ROOT/'MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py'),
                    '--engine-root', str(Path(sys.modules['mujoco'].__file__).resolve().parent.parent),
                    '--mode', 'unity', '--headless', '--seconds', '4',
                    '--port', str(port), '--output', str(output)],
                    stdout=out_file, stderr=err_file)
                try:
                    sequence = 0
                    deadline = time.monotonic()+30
                    feedback_started = False
                    states, backend_ids = set(), set()
                    bad_sent = False
                    previous_feedback_sequence = -1
                    while process.poll() is None and time.monotonic() < deadline:
                        p = packet(sequence, engage='ready' in states)
                        sender.sendto(json.dumps(p).encode(), ('127.0.0.1', port))
                        try:
                            raw, _ = sender.recvfrom(4096)
                            feedback = json.loads(raw)
                            if not feedback_started:
                                deadline = time.monotonic()+8
                                feedback_started = True
                            states.add(feedback['state'])
                            backend_ids.add(feedback['backend_id'])
                            self.assertGreater(feedback['feedback_sequence'],previous_feedback_sequence)
                            previous_feedback_sequence=feedback['feedback_sequence']
                            self.assertGreater(feedback['backend_started_ns'],0)
                            self.assertEqual(len(feedback['q_rad']),14)
                            self.assertEqual(feedback['joint_names'][0],'left_shoulder_pitch_joint')
                            self.assertEqual(feedback['joint_names'][7],'right_shoulder_pitch_joint')
                            self.assertTrue(np.isfinite(feedback['q_rad']).all())
                            if not bad_sent:
                                bad = packet()
                                bad['sender_time_s']=10**400
                                deep=json.dumps(packet())[:-1]+',"extra":'+'['*1100+'0'+']'*1100+'}'
                                for malformed in (json.dumps(bad).encode(),deep.encode(),b'{"x":1,"x":2}',b'\xff'):
                                    sender.sendto(malformed,('127.0.0.1',port))
                                bad_sent=True
                        except (socket.timeout,ConnectionResetError):
                            pass
                        sequence+=1
                        time.sleep(.015)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                        self.fail('Loopback did not exit. '+stdout_path.read_text(encoding='utf-8')+stderr_path.read_text(encoding='utf-8'))
                    out,err=stdout_path.read_text(encoding='utf-8'),stderr_path.read_text(encoding='utf-8')
                    self.assertEqual(process.returncode,0,out+err)
                    self.assertIn('tracking',states)
                    self.assertEqual(len(backend_ids),1)
                    for stage in ('engine_begin','engine_ready','controller_import_begin','controller_import_ready','model_begin','model_ready','listener_ready','first_feedback','normal_exit'):
                        self.assertIn(stage,out)
                    rows=[json.loads(x) for x in output.read_text(encoding='utf-8').splitlines()]
                    self.assertEqual(rows[0]['kind'],'run')
                    self.assertEqual(rows[0]['motion_policy'],'bimanual_motion_v1')
                    self.assertEqual(rows[0]['boundary_policy'],'bimanual_boundary_v1')
                    self.assertEqual(rows[0]['mujoco_version'],'3.12.0')
                    self.assertIn('g1_bimanual_motion_policy.py',rows[0]['source_sha256'])
                    states_in_log=[r for r in rows if r['kind']=='state']
                    self.assertTrue(all(r['control_tick_ms']>=0 for r in states_in_log))
                    self.assertTrue(all('ik_reason' in r and 'solver_error' in r for r in states_in_log))
                    self.assertTrue(all(r['simulation_only'] for r in states_in_log))
                    self.assertEqual(sum(r['kind']=='reject' for r in rows),4)
                    self.assertEqual(rows[-1]['kind'],'shutdown')
                except Exception:
                    # Keep the exact failed subprocess evidence beyond Temp cleanup.
                    destination=ROOT/'logs/test_results'/('bimanual_loopback_failure_'+str(time.time_ns()))
                    destination.mkdir(parents=True,exist_ok=False)
                    for path in (stdout_path,stderr_path,output):
                        if path.exists():
                            (destination/path.name).write_bytes(path.read_bytes())
                    print('LOOPBACK_FAILURE_ARTIFACTS',destination,flush=True)
                    raise
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
