"""Unity-free UDP end-to-end regression for the bimanual simulation path.

This starts only the loopback simulation backend on an ephemeral port. It does
not launch Unity and has no G1, DDS, SSH, or motor output path.
"""
import argparse
import json
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np

from g1_bimanual_runtime import load_engine

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py"
SCHEMA = "g1.bimanual.unity.sim.v1"
STATE_SCHEMA = "g1.bimanual.unity.sim.state.v1"


def make_packet(session, sequence, sender_time_s, engage=False,
                return_home=False, tracked=True, offset=0.0):
    hand = lambda sign: dict(
        tracked=tracked,
        position_m=[sign * offset, 0.0, 0.0],
        quaternion_wxyz=[1.0, 0.0, 0.0, 0.0])
    return dict(schema=SCHEMA, simulation_only=True, session=session,
                sequence=sequence, sender_time_s=sender_time_s,
                engage=engage, return_home=return_home,
                left=hand(-1.0), right=hand(1.0))


def free_loopback_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def send_packet(sock, port, packet):
    raw = json.dumps(packet, separators=(",", ":"), allow_nan=False).encode()
    sock.sendto(raw, ("127.0.0.1", port))


def valid_feedback(data, session):
    try:
        row = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (row.get("schema") != STATE_SCHEMA or
            row.get("simulation_only") is not True or
            row.get("session") != session):
        return None
    return row


def wait_feedback(sock, session, predicate, timeout_s, transitions):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        sock.settimeout(min(0.15, max(0.01, deadline - time.monotonic())))
        try:
            data, _ = sock.recvfrom(8192)
        except (socket.timeout, ConnectionResetError):
            continue
        row = valid_feedback(data.decode("utf-8"), session)
        if row is None:
            continue
        key = (row["state"], row.get("reason", ""))
        if not transitions or transitions[-1] != key:
            transitions.append(key)
        if predicate(row):
            return row
    raise TimeoutError("timed out waiting for bimanual feedback")


def wait_backend(sock, port, packet, timeout_s, transitions, process):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("simulation backend exited during startup")
        send_packet(sock, port, packet)
        try:
            return wait_feedback(
                sock, packet["session"],
                lambda row: row["state"] == "ready" and row["sequence"] >= 0,
                0.2, transitions)
        except TimeoutError:
            pass
    raise TimeoutError("simulation backend did not become ready")


def load_rows(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return rows


def state_transitions(rows):
    result = []
    for row in rows:
        if row.get("kind") != "state":
            continue
        key = (row.get("state"), row.get("reason", ""))
        if not result or result[-1] != key:
            result.append(key)
    return result


def verify_logged_limits(rows):
    from g1_bimanual_sim import BimanualSimulation

    sim = BimanualSimulation()
    if abs(sim.clearance_m - 0.005) > 1e-12:
        raise AssertionError("hard clearance changed")
    if abs(sim.return_motion.near_hands_threshold_m - 0.012) > 1e-12:
        raise AssertionError("near-hands threshold changed")
    np.testing.assert_allclose(
        sim.return_motion.acceleration_limits, np.deg2rad(60.0),
        atol=1e-12, rtol=0)

    states = [row for row in rows
              if row.get("kind") == "state" and row.get("q_rad")]
    if not states:
        raise AssertionError("no backend state rows were logged")
    minimum = float("inf")
    maximum_acceleration = 0.0
    previous_q = np.asarray(states[0]["q_rad"], dtype=float)
    previous_velocity = np.zeros(14)
    for row in states:
        q14 = np.asarray(row["q_rad"], dtype=float)
        if np.any(q14 < sim.ranges[:, 0] - 1e-8):
            raise AssertionError("joint lower range violated")
        if np.any(q14 > sim.ranges[:, 1] + 1e-8):
            raise AssertionError("joint upper range violated")
        full = sim.home.copy()
        full[sim.qids] = q14
        minimum = min(minimum, sim.clearance(full))
        velocity = (q14 - previous_q) / sim.dt
        acceleration = np.max(np.abs(velocity - previous_velocity)) / sim.dt
        maximum_acceleration = max(maximum_acceleration, float(acceleration))
        previous_q, previous_velocity = q14, velocity
    if minimum < sim.clearance_m - 1e-8:
        raise AssertionError(f"clearance violated: {minimum}")
    if maximum_acceleration > np.deg2rad(60.0) + 1e-3:
        raise AssertionError(
            f"acceleration violated: {np.rad2deg(maximum_acceleration)}")
    return minimum, maximum_acceleration


def run_cycle(args):
    engine = load_engine(args.engine_root)
    engine_root = Path(engine.__file__).resolve().parent.parent
    port = args.port or free_loopback_port()
    if port == 5020:
        raise ValueError("UDP regression must not use production simulation port 5020")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = args.output_dir / f"udp_cycle_{stamp}_{uuid.uuid4().hex[:8]}.jsonl"
    summary_path = args.output_dir / f"udp_cycle_{stamp}_{uuid.uuid4().hex[:8]}.json"

    command = [
        sys.executable, "-B", str(RUNTIME),
        "--engine-root", str(engine_root),
        "--mode", "unity", "--headless", "--port", str(port),
        "--output", str(log_path),
    ]
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    transitions = []
    session = "udp_cycle_" + uuid.uuid4().hex
    sequence = 0
    sender_time = 1.0
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(("127.0.0.1", 0))
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        client.ioctl(socket.SIO_UDP_CONNRESET, False)
    try:
        inactive = make_packet(session, sequence, sender_time, tracked=True)
        wait_backend(client, port, inactive, args.startup_timeout,
                     transitions, process)

        sequence += 1
        sender_time += 0.02
        engage = make_packet(
            session, sequence, sender_time, engage=True, tracked=True)
        send_packet(client, port, engage)
        wait_feedback(client, session,
                      lambda row: row["state"] == "tracking",
                      2.0, transitions)

        for index in range(1, 5):
            sequence += 1
            sender_time += 0.02
            motion = make_packet(
                session, sequence, sender_time, engage=True,
                tracked=True, offset=index * 0.0005)
            send_packet(client, port, motion)
            wait_feedback(client, session,
                          lambda row, s=sequence:
                              row["state"] == "tracking" and row["sequence"] >= s,
                          1.0, transitions)
        sequence += 1
        sender_time += 0.02
        pinch = make_packet(
            session, sequence, sender_time, engage=False,
            return_home=True, tracked=True)
        send_packet(client, port, pinch)
        wait_feedback(client, session,
                      lambda row: row["state"] == "returning"
                          and row.get("reason") == "pinch",
                      2.0, transitions)
        wait_feedback(client, session,
                      lambda row: row["state"] == "ready"
                          and row.get("reason") == "pinch",
                      args.return_timeout, transitions)

        sequence += 1
        sender_time += 0.02
        rearm = make_packet(session, sequence, sender_time, tracked=True)
        send_packet(client, port, rearm)
        wait_feedback(client, session,
                      lambda row, s=sequence:
                          row["state"] == "ready" and row["sequence"] >= s,
                      1.0, transitions)

        sequence += 1
        sender_time += 0.02
        reengage = make_packet(
            session, sequence, sender_time, engage=True, tracked=True)
        send_packet(client, port, reengage)
        wait_feedback(client, session,
                      lambda row, s=sequence:
                          row["state"] == "tracking" and row["sequence"] >= s,
                      2.0, transitions)
        time.sleep(0.15)
    finally:
        client.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    backend_output = process.stdout.read() if process.stdout else ""
    rows = load_rows(log_path)
    logged_transitions = state_transitions(rows)
    expected = [
        ("ready", ""),
        ("tracking", ""),
        ("returning", "pinch"),
        ("ready", "pinch"),
        ("tracking", ""),
    ]
    if logged_transitions[:len(expected)] != expected:
        raise AssertionError(
            f"unexpected state transitions: {logged_transitions}")
    if any(row.get("state") == "blocked"
           for row in rows if row.get("kind") == "state"):
        raise AssertionError("backend entered BLOCKED")
    accepted = sum(row.get("kind") == "input" and row.get("accepted")
                   for row in rows)
    if accepted < 8:
        raise AssertionError(f"too few accepted UDP inputs: {accepted}")
    minimum, maximum_acceleration = verify_logged_limits(rows)
    summary = dict(
        schema="g1.bimanual.udp_cycle.v1",
        simulation_only=True,
        hardware_output_authorized=False,
        port=port,
        backend_log=str(log_path),
        transitions=logged_transitions,
        accepted_inputs=accepted,
        minimum_clearance_mm=minimum * 1000.0,
        max_output_acceleration_deg_s2=float(
            np.rad2deg(maximum_acceleration)),
        backend_stdout_tail=backend_output.splitlines()[-20:],
        result="PASS")
    summary_path.write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print("BIMANUAL_UDP_CYCLE PASS")
    print(json.dumps(summary, indent=2, allow_nan=False))
    print(f"Summary: {summary_path}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "logs/test_results/bimanual/udp_cycle")
    parser.add_argument("--port", type=int, default=0,
                        help="0 chooses an ephemeral loopback port; 5020 is forbidden")
    parser.add_argument("--startup-timeout", type=float, default=12.0)
    parser.add_argument("--return-timeout", type=float, default=12.0)
    args = parser.parse_args(argv)
    try:
        return run_cycle(args)
    except (AssertionError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"BIMANUAL_UDP_CYCLE FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
