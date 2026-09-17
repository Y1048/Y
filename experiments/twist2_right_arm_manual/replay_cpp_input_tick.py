"""Replay a Windows shadow capture through the C++ memory-only 50 Hz tick.

No sockets, WSL, SDK, policy or controller imports. Baseline is simulated, not G1.
"""
import argparse
import ast
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def LoadEncoder():
    # Match today's serializer for legacy Infinity diagnostic fields. Execute only
    # the reviewed pure helper with a fake sink; never import/run the controller.
    source = ROOT / 'MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == '_send_state')
    namespace = {'json': json, 'math': math}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)

    def Encode(packet):
        class Sink:
            payload = None

            def sendto(self, payload, address):
                self.payload = payload

        sink = Sink()
        namespace['_send_state'](sink, packet, 'unused', 0)
        return sink.payload.decode('utf-8')

    return Encode


def BuildTicks(packets):
    """Keep every packet in arrival order; no latest-only filtering before C++."""
    if not packets:
        raise ValueError('empty_capture')
    previous = -1
    for packet in packets:
        receipt = packet['received_at']
        if not math.isfinite(receipt) or receipt < 0 or receipt < previous or receipt > 180:
            raise ValueError('invalid_capture_clock')
        previous = receipt
    events = []
    index = 0
    for tick in range(1, math.ceil((previous + .3) / .02) + 1):
        now = tick * .02
        batch = []
        while index < len(packets) and packets[index]['received_at'] <= now:
            batch.append(packets[index])
            index += 1
        events.append(dict(now=now, packets=batch))
    return events


def Replay(capture, executable):
    capture_bytes = capture.read_bytes()
    encoder = LoadEncoder()
    packets = []
    baseline = None
    for line in capture_bytes.decode('utf-8-sig').splitlines():
        sample = json.loads(line)
        if not sample.get('payload_base64'):
            continue
        packet = json.loads(base64.b64decode(sample['payload_base64'], validate=True))
        if baseline is None and packet.get('input_command_mode') == 'active':
            baseline = packet['all_joint_q_rad']
        packets.append(dict(received_at=sample['elapsed_s'], payload=encoder(packet)))
    if baseline is None:
        raise ValueError('capture_has_no_active_baseline')
    events = BuildTicks(packets)
    config = dict(baseline=baseline, now=0, maximum_delta=math.radians(10))
    result = subprocess.run([str(executable)],
                            input=''.join(json.dumps(e)+'\n' for e in [config, *events]),
                            text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    if len(rows) != len(events):
        raise ValueError('incomplete_cpp_output')
    previous = baseline
    max_rate = 0
    violations = []
    stop_reason = None
    counts = dict(active=0, waiting=0, stopped=0)
    trace = []
    for event, row in zip(events, rows):
        mode, q = row['mode'], row['q']
        counts[mode] += 1
        if len(q) != 29 or not all(math.isfinite(x) for x in q):
            raise ValueError('invalid_cpp_candidate')
        if q[:22] != baseline[:22]:
            violations.append('non_target_changed')
        rate = max(abs(a-b)/.02 for a, b in zip(q, previous))
        max_rate = max(max_rate, rate)
        if rate > .08 + 1e-12:
            violations.append('rate_exceeded')
        if mode != 'active' and q != previous:
            violations.append('moved_while_inactive')
        if stop_reason is not None and (mode != 'stopped' or row['reason'] != stop_reason):
            violations.append('stop_not_latched')
        if mode == 'stopped' and stop_reason is None:
            stop_reason = row['reason']
        if mode == 'active':
            goal = json.loads(event['packets'][-1]['payload'])['right_arm']['joints']
            if any(not min(old, target) <= new <= max(old, target)
                   for old, new, target in zip(previous[22:], q[22:], goal)):
                violations.append('overshoot')
        trace.append(dict(now=event['now'], packets=len(event['packets']), **row))
        previous = q
    report = dict(schema='g1.twist2.cpp_tick_replay.offline.v1', offline_only=True,
                  hardware_output_authorized=False, publisher_created=False,
                  baseline_source='first_active_mink_simulation_not_g1',
                  capture=str(capture.resolve()), capture_sha256=hashlib.sha256(capture_bytes).hexdigest(),
                  executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  serialization='current_pure_send_helper_with_fake_sink',
                  packets=len(packets), tick_period_s=.02, tick_counts=counts,
                  maximum_observed_rate_rad_s=max_rate, stop_reason=stop_reason,
                  violations=sorted(set(violations)), baseline=baseline)
    return report, trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--executable', type=Path,
                        default=ROOT / 'logs/test_results/test_upper_target_offline.exe')
    parser.add_argument('--output-dir', required=True, type=Path, help='New local directory; never overwritten')
    args = parser.parse_args()
    report, trace = Replay(args.capture, args.executable)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (args.output_dir / 'ticks.jsonl').write_text(
        ''.join(json.dumps(row)+'\n' for row in trace), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 1 if report['violations'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
