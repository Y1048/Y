"""Local receive-only Mink shadow. Never connects to G1 or forwards packets."""

import argparse
import base64
import json
import math
import socket
import time
import uuid
from pathlib import Path

from vr_input_offline import VRInputStudy, parse_mink_arm_sample

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def Run(output_dir, *, port=5008, duration_s=180, ready=None):
    """Receive on loopback only; ready is an optional local-test callback.

    First valid active Mink pose is a SIMULATION baseline, never measured G1.
    Every accepted datagram is recorded with its candidate. No output socket exists.
    """
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("positive finite duration required")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    result = {"schema": "g1.twist2.vr_shadow.result.v1", "hardware_output_authorized": False,
              "publisher_created": False, "robot_command_sent": False,
              "baseline_source": "first_active_mink_simulation_not_g1",
              "datagrams": 0, "active_updates": 0, "invalid_before_baseline": 0,
              "stop_reason": None, "transport_error": None, "completed": False}
    study = None
    started = time.perf_counter()
    last_print = started
    print("TWIST2 VR INPUT SHADOW -- LOCAL RECEIVE ONLY", flush=True)
    print("NO G1 / NO DDS / NO C++ policy / NO forwarding", flush=True)
    print("The visible MuJoCo/Unity robot is NOT driven by this shadow.", flush=True)
    print(f"Result directory: {output_dir.resolve()}", flush=True)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                receiver.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            receiver.bind(("127.0.0.1", port))
            receiver.settimeout(0.02)
            print(f"[LISTENING] 127.0.0.1:{receiver.getsockname()[1]}", flush=True)
            if ready is not None:
                ready(receiver.getsockname()[1])
            with (output_dir / "samples.jsonl").open("x", encoding="utf-8") as stream:
                while time.perf_counter() - started < duration_s:
                    payload = None
                    try:
                        payload, _ = receiver.recvfrom(65535)
                    except socket.timeout:
                        pass
                    now = time.perf_counter()
                    candidate = None
                    if payload is not None:
                        result["datagrams"] += 1
                    if study is None and payload is not None:
                        try:
                            sample = parse_mink_arm_sample(payload)
                            if (sample.active and sample.input_command_mode == "active"
                                    and sample.input_packet_age_s <= 0.25
                                    and sample.minimum_clearance_m >= 0):
                                study = VRInputStudy(sample.all_joint_q_rad,
                                    session_id=sample.session_id, initial_sequence=sample.sequence,
                                    now_s=now, maximum_delta_rad=math.radians(10), timeout_s=0.25)
                                candidate = study.GetResult("baseline")
                                print("[BASELINE] Simulation pose captured; study range +/-10 deg.", flush=True)
                        except (ValueError, TypeError, KeyError, OverflowError):
                            result["invalid_before_baseline"] += 1
                    elif study is not None:
                        candidate = study.Step(payload, now_s=now,
                                               received_s=now if payload is not None else None)
                    if payload is not None or candidate is not None:
                        stream.write(json.dumps({"elapsed_s": now-started,
                            "payload_base64": base64.b64encode(payload).decode() if payload is not None else None,
                            "candidate": candidate}, allow_nan=False) + "\n")
                        stream.flush()
                    if candidate is not None:
                        if candidate["mode"] == "active":
                            result["active_updates"] += 1
                        if candidate["mode"] == "stopped":
                            result["stop_reason"] = candidate["reason"]
                            print(f"[STOPPED] {candidate['reason']}; no automatic re-engage.", flush=True)
                            break
                    if now - last_print >= 1:
                        mode = "waiting_for_engage" if study is None else candidate["mode"]
                        print(f"[{mode.upper()}] packets={result['datagrams']} active={result['active_updates']}", flush=True)
                        last_print = now
                result["completed"] = True
    except KeyboardInterrupt:
        result["stop_reason"] = "operator_interrupt"
        result["completed"] = True
    except OSError as error:
        result["transport_error"] = str(error)
        print(f"[ERROR] {error}", flush=True)
        print("[ACTION] Close the old UDP 5008 receiver; do not kill unrelated processes.", flush=True)
    finally:
        result["baseline_captured"] = study is not None
        result["elapsed_s"] = time.perf_counter() - started
        result["input_observed"] = result["active_updates"] > 0
        path = output_dir / "result.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Result saved to: {path.resolve()}", flush=True)
        if (output_dir / "samples.jsonl").exists():
            print(f"Samples saved to: {(output_dir / 'samples.jsonl').resolve()}", flush=True)
        if not result["input_observed"]:
            print("[ACTION] No active motion observed. Start Unity Play and engage; then retry this receiver.", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=180)
    args = parser.parse_args()
    output = PROJECT_ROOT / "logs" / "test_results" / (
        "twist2_vr_shadow_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
    result = Run(output, duration_s=args.duration_s)
    return 0 if result["completed"] and result["input_observed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
