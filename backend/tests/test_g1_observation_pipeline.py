"""Generated loopback fixtures through real producers; no Quest/G1/motor input.

Reserves observation-only localhost ports 55070/55071 for this bounded test.
Run serially with receiver tests; never terminate an existing port owner.
"""
import asyncio
from contextlib import ExitStack
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'tools/G1_INPUT_RECEIVE_AUDIT.py'
RUNTIME = ROOT / 'MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py'
OMNI = ROOT / 'hardware/g1_arm_bridge/g1_omni_velocity_gateway.py'
JOINT_NAMES = [side + '_' + joint + '_joint'
               for side in ('left', 'right') for joint in
               ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
                'wrist_roll', 'wrist_pitch', 'wrist_yaw')]


class ObservationPipelineTests(unittest.TestCase):
    def test_generated_unity_and_fake_omni_reach_observation_receiver_together(self):
        import websockets

        engine = Path(os.environ.get('G1_BIMANUAL_ENGINE_ROOT',
            str(Path.home() / 'Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0')))
        self.assertTrue((engine / 'mujoco/__init__.py').is_file(),
                        'Select the isolated MuJoCo 3.12.0 engine before this test')
        for port in (55070, 55071):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as check:
                if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                    check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                check.bind(('127.0.0.1', port))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ephemeral:
            ephemeral.bind(('127.0.0.1', 0))
            unity_port = ephemeral.getsockname()[1]
        self.assertNotIn(unity_port, (5020, 55070, 55071))

        stop_server, server_ready = threading.Event(), threading.Event()
        server_info = {}

        async def fake_omni(ws):
            # Generated samples, not measured Omni data: still -> forward/right/turn.
            try:
                for index in range(130):
                    if stop_server.is_set():
                        break
                    moving = index >= 8
                    packet = dict(movementXY=[.25 if moving else 0., .65 if moving else 0.],
                                  armYaw=110. + max(0, index - 8) * .6)
                    await ws.send(json.dumps(packet))
                    await asyncio.sleep(.03)
            except websockets.ConnectionClosed:
                pass

        async def serve():
            async with websockets.serve(fake_omni, '127.0.0.1', 0) as server:
                server_info['port'] = server.sockets[0].getsockname()[1]
                server_ready.set()
                while not stop_server.is_set():
                    await asyncio.sleep(.02)

        def server_thread_main():
            try:
                asyncio.run(serve())
            except BaseException as error:
                server_info['error'] = repr(error)
                server_ready.set()

        thread = threading.Thread(target=server_thread_main, daemon=True)
        thread.start()
        processes, handles = [], []

        def stop_process(process):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

        try:
            self.assertTrue(server_ready.wait(5), 'fake WebSocket startup timeout')
            self.assertNotIn('error', server_info, server_info.get('error'))
            self.assertNotEqual(server_info['port'], 32123)
            with tempfile.TemporaryDirectory(prefix='generated_observation_fixture_') as directory, ExitStack() as cleanup:
                tmp = Path(directory)
                env = os.environ.copy()
                env['G1_OBSERVATION_TAP'] = '1'
                env['G1_BIMANUAL_ENGINE_ROOT'] = str(engine)
                env.pop('G1_USE_HARDWARE_INITIAL_STATE', None)

                def launch(name, arguments):
                    output = tmp / (name + '.console.txt')
                    handle = output.open('w', encoding='utf-8')
                    handles.append(handle)
                    cleanup.callback(handle.close)
                    process = subprocess.Popen(
                        [sys.executable, '-u', '-B', *map(str, arguments)],
                        cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
                    processes.append(process)
                    cleanup.callback(stop_process, process)
                    return process, output

                simulation, sim_console = launch('generated_unity', [
                    RUNTIME, '--mode', 'unity', '--headless', '--port', unity_port,
                    '--compute-hz', '60',
                    '--seconds', '11', '--output', tmp / 'generated_unity.jsonl'])
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    console = sim_console.read_text(encoding='utf-8')
                    if 'listener_ready' in console:
                        break
                    self.assertIsNone(simulation.poll(), console)
                    time.sleep(.05)
                else:
                    self.fail('simulation startup timeout: ' + sim_console.read_text(encoding='utf-8'))

                receiver_log = tmp / 'generated_loopback_received.jsonl'
                receiver, rx_console = launch('observation_receiver', [
                    AUDIT, 'receive', '--bind', '127.0.0.1', '--allow-peer', '127.0.0.1',
                    '--seconds', '8', '--print-hz', '100', '--log', receiver_log])
                sender, tx_console = launch('observation_sender', [
                    AUDIT, 'send-live', '--host', '127.0.0.1',
                    '--seconds', '7', '--send-hz', '60', '--print-hz', '100'])
                omni, omni_console = launch('generated_omni', [
                    OMNI, '--dry-run', '--omni-url', 'ws://127.0.0.1:' + str(server_info['port']),
                    '--process-hz', '60',
                    '--calibration-seconds', '.15', '--max-samples', '120',
                    '--csv', tmp / 'generated_omni.csv'])

                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as unity:
                    unity.bind(('127.0.0.1', 0))
                    unity.setblocking(False)
                    session = 'generated_fixture_' + uuid.uuid4().hex
                    began = time.monotonic()
                    sequence = 0
                    while time.monotonic() - began < 4.3:
                        elapsed = time.monotonic() - began
                        engage = .25 <= elapsed < 2.8
                        offset = min(.01, max(0., elapsed - .3) * .005) if engage else 0.
                        hand = lambda sign: dict(tracked=True,
                            position_m=[sign * (.22 + offset), -.24, .38],
                            quaternion_wxyz=[1., 0., 0., 0.])
                        packet = dict(schema='g1.bimanual.unity.sim.v1', simulation_only=True,
                            session=session, sequence=sequence, sender_time_s=sequence * .02,
                            engage=engage, return_home=elapsed >= 2.8,
                            left=hand(-1.), right=hand(1.))
                        unity.sendto(json.dumps(packet).encode(), ('127.0.0.1', unity_port))
                        for _ in range(8):
                            try:
                                unity.recvfrom(8192)
                            except BlockingIOError:
                                break
                        sequence += 1
                        time.sleep(.02)

                for process, console in ((omni, omni_console), (sender, tx_console),
                                         (receiver, rx_console), (simulation, sim_console)):
                    process.wait(timeout=12)
                    self.assertEqual(process.returncode, 0, console.read_text(encoding='utf-8'))
                rows = [json.loads(line) for line in receiver_log.read_text(encoding='utf-8').splitlines()]
                received = [row for row in rows if row.get('kind') == 'received_observation']
                sim_rows = [json.loads(line) for line in (tmp/'generated_unity.jsonl').read_text(encoding='utf-8').splitlines()]
                run = sim_rows[0]
                self.assertEqual(run['motion_limits']['velocity_rad_s'], [3.] * 14)
                self.assertEqual(run['motion_limits']['acceleration_rad_s2'], [3.] * 14)
                self.assertEqual(run['return_profile']['velocity_rad_s'], [3.] * 14)
                self.assertEqual(run['return_profile']['acceleration_rad_s2'], [3.] * 14)
                self.assertIs(run['simulation_only'], True)
                self.assertIs(run['hardware_output_authorized'], False)
                states = [row for row in sim_rows if row.get('kind') == 'state']
                state_by_sequence = {row['feedback_sequence']: row for row in states}
                self.assertEqual(len(state_by_sequence), len(states))
                self.assertGreater(len(states), 100)
                dt = run['simulation_dt_s']
                self.assertEqual(dt, 1./60.)
                maximum_speed = [0.] * 14
                maximum_acceleration = [0.] * 14
                previous_velocity = None
                for previous, current in zip(states, states[1:]):
                    # These are adjacent solver steps, not resampled UDP/display rows.
                    self.assertEqual(current['compute_tick'], previous['compute_tick'] + 1)
                    self.assertEqual(current['feedback_sequence'], previous['feedback_sequence'] + 1)
                    self.assertEqual(current['joint_names'], JOINT_NAMES)
                    self.assertEqual(len(current['q_rad']), 14)
                    self.assertTrue(all(math.isfinite(q) for q in current['q_rad']))
                    velocity = [(q - p) / dt for p, q in zip(previous['q_rad'], current['q_rad'])]
                    for joint, speed in enumerate(velocity):
                        maximum_speed[joint] = max(maximum_speed[joint], abs(speed))
                        self.assertLessEqual(abs(speed), 3. + 1e-6, JOINT_NAMES[joint])
                        if previous_velocity is not None:
                            acceleration = abs(speed - previous_velocity[joint]) / dt
                            maximum_acceleration[joint] = max(maximum_acceleration[joint], acceleration)
                            # Existing solver validation allows this numerical tolerance.
                            self.assertLessEqual(acceleration, 3. + 1e-3, JOINT_NAMES[joint])
                    previous_velocity = velocity
                self.assertGreater(max(maximum_speed[:7]), .001, 'left IK output did not move')
                self.assertGreater(max(maximum_speed[7:]), .001, 'right IK output did not move')

                with (tmp/'generated_omni.csv').open(newline='', encoding='utf-8') as source:
                    omni_rows = list(csv.DictReader(source))
                omni_by_sequence = {int(row['sample_sequence']): row for row in omni_rows}
                self.assertEqual(len(omni_by_sequence), len(omni_rows))
                calibration_end = next(index for index, row in enumerate(omni_rows)
                                       if row['calibrated'] == '1')
                self.assertGreater(calibration_end, 0)
                # The generated stationary prefix makes the measured world bias zero.
                for row in omni_rows[:calibration_end + 1]:
                    self.assertEqual((float(row['mx']), float(row['my'])), (0., 0.))
                independent_mapping_checks = 0
                for row in omni_rows[calibration_end + 1:]:
                    # Independent world -> body oracle with the gateway's unchanged
                    # 0.08 per-axis deadzone and 0.8 m/s scale/limit; no mapper reuse.
                    theta = math.radians(float(row['arm_yaw_deg']))
                    world_x, world_y = float(row['mx']), float(row['my'])
                    body = (world_x * math.cos(theta) + world_y * math.sin(theta),
                            -world_x * math.sin(theta) + world_y * math.cos(theta))
                    for key, value in zip(('vx', 'vy'), body):
                        expected = (0. if abs(value) <= .08 else
                                    math.copysign(min(.8, (abs(value) - .08) * .8 / .92), value))
                        self.assertAlmostEqual(float(row[key]), expected, places=12)
                    independent_mapping_checks += 1
                self.assertGreater(independent_mapping_checks, 30)

                joint_copies = omni_copies = 0
                for row in received:
                    payload = row['packet']['payload']
                    arms = payload['arm']['values']
                    if arms is not None:
                        original = state_by_sequence[arms['feedback_sequence']]
                        self.assertEqual(arms['joint_names'], original['joint_names'])
                        self.assertEqual(arms['joint_indices'], list(range(15, 29)))
                        self.assertEqual(arms['left_q_rad'] + arms['right_q_rad'], original['q_rad'])
                        self.assertEqual(arms['compute_tick'], original['compute_tick'])
                        self.assertEqual(arms['sequence'], original['sequence'])
                        joint_copies += 1
                    feet = payload['omni']['values']
                    if feet is not None:
                        original = omni_by_sequence[feet['sample_sequence']]
                        for key in ('mx', 'my', 'arm_yaw_deg', 'omni_yaw_rate_deg_s',
                                    'vx', 'vy', 'yaw_rate', 'yaw_diff_deg', 'yaw_step_diff_deg'):
                            # CSV stores unrounded floats for these fields, as does JSON.
                            self.assertEqual(feet[key], float(original[key]), key)
                        self.assertEqual(feet['raw_sample_sequence'], feet['sample_sequence'])
                        self.assertEqual(feet['processed_monotonic_s'], float(original['processed_monotonic_s']))
                        # Only the CSV receipt timestamp is formatted to nine decimals.
                        self.assertAlmostEqual(feet['source_monotonic_s'],
                                               float(original['receive_monotonic_s']), delta=1e-8)
                        self.assertGreaterEqual(feet['processed_monotonic_s'], feet['source_monotonic_s'])
                        omni_copies += 1
                self.assertGreater(joint_copies, 30)
                self.assertGreater(omni_copies, 30)
                simultaneous = [row for row in received if all(
                    row['packet']['payload'][stream]['status'] == 'FRESH_LIVE'
                    for stream in ('arm', 'omni'))]
                self.assertGreater(len(simultaneous), 30)
                arm_sequences, omni_sequences = set(), set()
                mapped_nonzero = tracking_seen = returning_seen = False
                for row in simultaneous:
                    self.assertEqual(row['motor_acceptance'], 'NOT_CHECKED')
                    packet = row['packet']
                    self.assertIs(packet['observation_only'], True)
                    arm = packet['payload']['arm']
                    omni_stream = packet['payload']['omni']
                    arms, feet = arm['values'], omni_stream['values']
                    self.assertIs(arms['simulation_only'], True)
                    self.assertEqual(arms['source_origin'], 'bimanual_ik_simulation')
                    self.assertEqual(arms['joint_indices'], list(range(15, 29)))
                    self.assertEqual(arms['joint_names'], JOINT_NAMES)
                    self.assertEqual(len(arms['left_q_rad']), 7)
                    self.assertEqual(len(arms['right_q_rad']), 7)
                    arm_sequences.add(arms['feedback_sequence'])
                    omni_sequences.add(feet['sample_sequence'])
                    tracking_seen |= arms['state'] == 'tracking'
                    returning_seen |= arms['state'] == 'returning'
                    mapped_nonzero |= feet['calibrated'] and feet['vx'] > .1 and feet['vy'] < -.1 and feet['yaw_rate'] > .1
                self.assertGreater(len(arm_sequences), 30)
                self.assertGreater(len(omni_sequences), 30)
                self.assertTrue(mapped_nonzero)
                self.assertTrue(tracking_seen)
                self.assertTrue(returning_seen)
                # IK keeps generating targets after input ends. Its fresh output must
                # remain distinguishable from stale Unity input and a stopped Omni source.
                self.assertTrue(any(
                    row['packet']['payload']['arm']['status'] == 'FRESH_LIVE' and
                    (row['packet']['payload']['arm']['values'] or {}).get('unity_input_status') == 'STALE' and
                    row['packet']['payload']['omni']['status'] == 'STALE'
                    for row in received))
                tx_rows = [json.loads(line) for line in tx_console.read_text(encoding='utf-8').splitlines()
                           if line.startswith('{')]
                self.assertTrue(any(row['receiver_status'] == 'ACK_CONFIRMED' and
                                    row['ack_verified_count'] > 30 for row in tx_rows))
                # Configured rates are independent: display repeats existing snapshots.
                self.assertTrue(any(row['display_repeated_snapshot'] for row in tx_rows))
                self.assertTrue(all(row['display_target_hz'] == 100 for row in tx_rows))
                self.assertTrue(all(row['send_target_hz'] == 60 for row in tx_rows))
                for row in simultaneous:
                    self.assertEqual(row['packet']['payload']['arm']['values']['compute_hz'], 60)
                    self.assertEqual(row['packet']['payload']['omni']['values']['processing_hz'], 60)
                rx_frames = [json.loads(line) for line in rx_console.read_text(encoding='utf-8').splitlines()
                             if line.startswith('{')]
                self.assertGreater(len(rx_frames), len(received))
                self.assertTrue(any(row['display_repeated_snapshot'] for row in rx_frames))
                self.assertEqual(sim_rows[0]['loop_clock'], 'perf_counter')
                self.assertEqual(sim_rows[0]['simulation_dt_s'], 1./60.)
                periods = [row['loop_period_ms'] for row in states if row['loop_period_ms'] is not None]
                display_span = rx_frames[-1]['display_monotonic_s']-rx_frames[0]['display_monotonic_s']
                receive_span = received[-1]['receiver_monotonic_s']-received[0]['receiver_monotonic_s']
                print('GENERATED_CLOCKED_PIPELINE '+json.dumps(dict(
                    data_kind='synthetic_Unity_and_WebSocket_loopback_not_measured_G1',
                    joint_limit_rad_s=3., joint_limit_rad_s2=3.,
                    max_joint_speed_rad_s=maximum_speed,
                    max_joint_acceleration_rad_s2=maximum_acceleration,
                    exact_joint_copies=joint_copies, exact_omni_copies=omni_copies,
                    independent_world_to_body_checks=independent_mapping_checks,
                    ik_observed_hz=1000*len(periods)/sum(periods),
                    ik_deadline_misses=states[-1]['deadline_misses'],
                    received_packets=len(received), receive_observed_hz=(len(received)-1)/receive_span,
                    display_frames=len(rx_frames), display_observed_hz=(len(rx_frames)-1)/display_span,
                    repeated_display_frames=sum(row['display_repeated_snapshot'] for row in rx_frames),
                    displayed_source_sequences_preserved=True)), flush=True)
        finally:
            stop_server.set()
            for process in processes:
                stop_process(process)
            for handle in handles:
                handle.close()
            thread.join(timeout=5)


class ObservationLauncherTests(unittest.TestCase):
    def test_worker_commands_are_observation_only_without_executing_them(self):
        path = ROOT / 'tools/G1_INPUT_OBSERVATION_LAUNCH.py'
        spec = importlib.util.spec_from_file_location('observation_launcher_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        commands = {worker: module.worker_command(worker, '127.0.0.1', 'generated_fixture')
                    for worker in module.WORKERS}
        self.assertIn('--dry-run', commands['omni'])
        self.assertIn('send-live', commands['send'])
        self.assertIn('--mode', commands['arm'])
        self.assertIn('unity', commands['arm'])
        self.assertIn('g1_bimanual_runtime.py', ' '.join(commands['arm']))
        self.assertIn('G1_INPUT_RECEIVE_AUDIT.py receive', ' '.join(commands['receive']))
        self.assertEqual(module.COMPUTE_HZ, 60)
        self.assertEqual(module.DISPLAY_HZ, 100)
        self.assertIn('--print-hz 100', ' '.join(commands['receive']))
        self.assertIn('--print-hz 100', ' '.join(commands['send']))
        self.assertIn('--send-hz 60', ' '.join(commands['send']))
        self.assertIn('--process-hz 60', ' '.join(commands['omni']))
        self.assertIn('--compute-hz 60', ' '.join(commands['arm']))
        for command in commands.values():
            text = ' '.join(command)
            for forbidden in ('--enable-actuation', 'groot_balance_actuator',
                              'RUN_PC_TWIST2', 'START_TWIST2', 'rt/lowcmd'):
                self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
