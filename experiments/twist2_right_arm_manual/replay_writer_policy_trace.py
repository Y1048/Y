"""Replay verified policy/blend positions through a file-only 2 ms C++ writer study.

Open-loop fixture replay: policy observations remain those of the source CPU run;
writer targets do not feed back into policy. This is not a physics simulation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from run_policy_history_offline import F32
from replay_cpp_receiver_log import ROOT
from offline_policy_adapter import EXPECTED_SHA256


def Run(source, output):
    trace_path = source / "normal.jsonl"
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    report = json.loads((source / "result.json").read_text(encoding="utf-8"))[0]
    if not report["passed"] or report["scenario"] != "normal" or report["reason"] != "input_disengaged":
        raise ValueError("verified normal CPU replay required")
    candidates = [r for r in rows if r.get("candidate") is not None]
    if report["policy_sha256"] != EXPECTED_SHA256 or report["hardware_output_authorized"]:
        raise ValueError("policy provenance or output boundary")
    if any(r["alpha"] != 1 for r in candidates):
        raise ValueError("this replay requires completed blend; feedforward fixture is zero")
    if not candidates or rows[-1]["reason"] != "input_disengaged":
        raise ValueError("complete candidate and stop trace required")
    capture = ROOT / "logs/test_results/twist2_cpp_quest_raw_20260907_152430/ticks.jsonl"
    baseline = next(json.loads(x)["baseline"] for x in capture.read_text().splitlines()
                    if json.loads(x).get("baseline") is not None)
    baseline = [F32(v) for v in baseline]
    start = candidates[0]["now_s"]
    release = rows[-1]["now_s"]
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for scenario in ("recorded_latency", "inference_stall", "state_gap", "release_pending"):
        trigger = start + .4
        ready = []
        worker_free = start
        for r in candidates:
            created = r["now_s"]
            duration = r["inference_ms"] / 1000
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("invalid latency")
            arrival = max(created, worker_free) + duration
            if scenario == "inference_stall" and created >= trigger:
                arrival = max(arrival, trigger + .1)
            if scenario == "release_pending" and created >= release - .03:
                arrival += .04
            worker_free = arrival
            ready.append(dict(created=created, at=arrival, q=r["candidate"]))
        # Initialization position is explicit; no publisher/candidate before first blend result.
        # First desired is installed at its actual scheduled arrival, then the 2 ms grid starts.
        activated = ready[0]["at"]
        process = subprocess.Popen([str(ROOT / "logs/test_results/test_writer_trace_loop.exe")],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1)
        def Exchange(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise RuntimeError(process.stderr.read())
            return json.loads(line)
        previous = baseline
        latest = None
        cursor = 0
        stopped_at = None
        stopped_q = None
        max_step = 0.
        checked = 0
        records = []
        # Desired created_at must be >= activation in the stricter study. Activate at
        # observation time, but evaluate first writer tick at first completion + 2 ms.
        process.stdin.write(json.dumps(dict(state_source="previous_target_zero_velocity_fixture",
                                           baseline=baseline, start=start)) + "\n")
        process.stdin.flush()
        end = release + .15
        try:
            for tick in range(1, math.ceil((end - activated) / .002) + 1):
                now = activated + tick * .002
                updates = []
                while cursor < len(ready) and ready[cursor]["at"] <= now:
                    item = ready[cursor]
                    updates.append(dict(q=item["q"], created=item["created"]))
                    latest = [F32(v) for v in item["q"]]
                    cursor += 1
                state_at = trigger if scenario == "state_gap" and now > trigger else now
                request = dict(now=now, state_at=state_at, updates=updates)
                if now >= release:
                    request["stop"] = "input_disengaged"
                row = Exchange(request)
                q = row["q"]
                if row["accepted"]:
                    if stopped_at is not None or latest is None:
                        raise ValueError("resumed or missing desired")
                    for i, (old, new, goal) in enumerate(zip(previous, q, latest)):
                        delta = abs(new - old)
                        max_step = max(max_step, delta)
                        if delta > (.004 if i < 12 else .0016) + 1e-7:
                            raise ValueError("writer rate")
                        if not min(old, goal) - 1e-7 <= new <= max(old, goal) + 1e-7:
                            raise ValueError("overshoot")
                    if q[12:22] != baseline[12:22]:
                        raise ValueError("held waist/left arm changed")
                    checked += 1
                else:
                    if stopped_at is None:
                        if q != previous:
                            raise ValueError("failed tick partially committed")
                        stopped_at, stopped_q = now, q
                    if q != stopped_q or not row["damping"]:
                        raise ValueError("stop did not freeze target and select damping")
                previous = q
                row.update(now=now, delivered=len(updates))
                records.append(row)
            expected = dict(recorded_latency="input_disengaged", inference_stall="command_timeout",
                            state_gap="state_timeout", release_pending="input_disengaged")[scenario]
            if records[-1]["reason"] != expected or stopped_at is None or checked == 0:
                raise ValueError((scenario, records[-1]["reason"], expected, checked))
            if scenario in ("recorded_latency", "release_pending") and not 0 <= stopped_at-release < .002 + 1e-10:
                raise ValueError("release was not propagated on next writer tick")
            if scenario == "inference_stall":
                if not trigger <= stopped_at < trigger + .064:
                    raise ValueError("command watchdog exceeded bound")
            if scenario == "state_gap" and not .02 < stopped_at-trigger < .022 + 1e-10:
                raise ValueError("state watchdog exceeded bound")
            if scenario == "release_pending" and records[-1]["discarded"] < 1:
                raise ValueError("pending completion was not exercised")
            result = dict(scenario=scenario, passed=True, accepted_ticks=checked,
                          stop_reason=expected, stop_at=stopped_at,
                          release_at=release, discarded_completions=records[-1]["discarded"],
                          maximum_step_rad=max_step, writer_period_s=.002,
                          state_source="previous_target_zero_velocity_fixture",
                          observation_feedback_connected=False, dynamics_tested=False,
                          simulated_time=True, hardware_output_authorized=False,
                          release_to_writer_ms=(stopped_at-release)*1000 if expected=="input_disengaged" else None)
            results.append(result)
            (output / (scenario + ".jsonl")).write_text(
                "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        finally:
            process.stdin.close()
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            if code:
                raise RuntimeError(process.stderr.read())
            process.stdout.close()
            process.stderr.close()
    summary = dict(passed=True, source=str(trace_path),
                   source_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                   policy_sha256=report["policy_sha256"], scenarios=results)
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(Run(args.source, args.output), indent=2))

