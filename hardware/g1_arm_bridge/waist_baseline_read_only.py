"""Bounded LowState recording; no command publisher or UDP forwarding."""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def Summarize(samples):
    """Describe observed samples only; never authorize hardware output."""
    if len(samples) < 2:
        raise ValueError("at least two samples required")
    for sample in samples:
        for key in ("q_rad", "dq_rad_s"):
            if len(sample[key]) != 29 or not all(math.isfinite(v) for v in sample[key]):
                raise ValueError("invalid 29-joint vector")
    times = [s["elapsed_s"] for s in samples]
    if not all(math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("sample times must increase")
    axes = {}
    for index, name in zip(range(12, 15), ("yaw", "roll", "pitch")):
        q = [math.degrees(s["q_rad"][index]) for s in samples]
        speed = sorted(abs(math.degrees(s["dq_rad_s"][index])) for s in samples)
        axes[name] = {"initial_deg": q[0], "final_deg": q[-1],
                      "span_deg": max(q)-min(q),
                      "max_initial_deviation_deg": max(abs(v-q[0]) for v in q),
                      "abs_speed_p95_deg_s": speed[math.ceil(0.95*len(speed))-1],
                      "abs_speed_max_deg_s": speed[-1]}
    return {"samples": len(samples), "observed_duration_s": times[-1]-times[0],
            "max_sample_gap_s": max(b-a for a, b in zip(times, times[1:])),
            "max_observed_lowstate_age_s": max(s["age_s"] for s in samples),
            "waist": axes,
            "mode_pairs": sorted({(s["mode_pr"], s["mode_machine"]) for s in samples}),
            "hardware_authorized": False,
            "limitations": ["Sampled joint coordinates, not torso IMU or balance assessment.",
                            "No MotionSwitcher ai/Regular confirmation.",
                            "No safety pass/fail threshold or physical authorization."]}


def Capture(snapshot, decode, stream, *, duration=15.0, wait_s=10.0,
            timeout_s=0.25, monotonic=time.monotonic, sleep=time.sleep):
    """Record fresh samples at up to 30 Hz; fail on loss, never reuse stale q."""
    if not all(math.isfinite(v) and v > 0 for v in (duration, wait_s, timeout_s)):
        raise ValueError("capture durations must be finite and positive")
    started = monotonic()
    first = None
    previous_sequence = None
    samples = []
    while True:
        now = monotonic()
        state, sequence, last_rx = snapshot()
        age = now-last_rx
        if first is None and now-started >= wait_s:
            raise TimeoutError("no fresh LowState before initial timeout")
        if first is not None and (state is None or not math.isfinite(age) or age < 0 or age > timeout_s):
            raise TimeoutError("LowState lost/stale during recording")
        if state is not None and math.isfinite(age) and 0 <= age <= timeout_s:
            if first is None:
                first = now
            if sequence != previous_sequence:
                sample = dict(decode(state), elapsed_s=now-first, age_s=age, sequence=sequence)
                stream.write(json.dumps(sample, allow_nan=False)+"\n")
                stream.flush()
                samples.append(sample)
                previous_sequence = sequence
            if now-first >= duration:
                return samples
        sleep(1/30)


def Run(directory):
    # Import SDK-dependent code only for the explicit read-only capture command.
    import read_only_lowstate as bridge
    import subprocess
    interface = subprocess.check_output(
        ["ip", "-o", "-4", "addr", "show"], text=True)
    interfaces = [line.split()[1] for line in interface.splitlines()
                  if "192.168.123.99/24" in line.split()]
    if len(interfaces) != 1:
        raise RuntimeError("expected one local 192.168.123.99/24 interface; inspect PC network")
    bridge.ChannelFactoryInitialize(0, interfaces[0])
    monitor = bridge.ReadOnlyG1LowState()
    subscriber = bridge.ChannelSubscriber(bridge.TOPIC_LOWSTATE, bridge.LowState_)
    subscriber.Init(monitor.callback, 10)

    def Decode(state):
        return {"q_rad": bridge._read_g1_29_vector(state, "q"),
                "dq_rad_s": bridge._read_g1_29_vector(state, "dq"),
                "mode_pr": bridge._state_uint8(state, "mode_pr"),
                "mode_machine": bridge._state_uint8(state, "mode_machine")}

    with (directory / "samples.jsonl").open("x", encoding="utf-8") as stream:
        return Summarize(Capture(monitor.snapshot, Decode, stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if not args.capture:
        parser.error("--capture is required; this records read-only state for 15 seconds")
    directory = ROOT / "logs/read_only_baselines" / datetime.now().strftime("waist_%Y%m%d_%H%M%S_%f")
    directory.mkdir(parents=True, exist_ok=False)
    print("READ ONLY: rt/lowstate; no publisher, command, mode change or UDP forwarding.", flush=True)
    print("Keep the robot uncommanded by this program. Recording 15 seconds after first data.", flush=True)
    print(f"Result folder: {directory}", flush=True)
    result = {"completed": False, "hardware_authorized": False, "publisher_created": False,
              "started_at": datetime.now().isoformat(), "error": None}
    code = 2
    try:
        result.update(Run(directory))
        result["completed"] = True
        code = 0
        for axis, values in result["waist"].items():
            print(f"{axis}: span={values['span_deg']:.3f} deg; speed p95={values['abs_speed_p95_deg_s']:.3f} deg/s")
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(f"[INCOMPLETE] {result['error']}")
        print("[ACTION] Inspect Ethernet/LowState and this result; do not start a physical trial.")
    finally:
        path = directory / "summary.json"
        path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        print(f"Result saved to: {path}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
