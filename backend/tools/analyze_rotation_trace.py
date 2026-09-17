"""Summarize sampled Unity rotation provenance locally; never opens a socket."""

import argparse
import json
import math
from pathlib import Path


def GetQuaternion(value):
    values = [value[key] for key in ("x", "y", "z", "w")] if isinstance(value, dict) else value
    if len(values) != 4 or not all(math.isfinite(float(x)) for x in values):
        raise ValueError("invalid quaternion")
    norm = math.sqrt(sum(float(x) ** 2 for x in values))
    if norm < 1e-8:
        raise ValueError("zero quaternion")
    return [float(x) / norm for x in values]


def GetAngle(first, second):
    dot = abs(sum(a * b for a, b in zip(GetQuaternion(first), GetQuaternion(second))))
    return math.degrees(2 * math.acos(min(1., dot)))


def AnalyzeRows(rows, threshold_deg=5.):
    """Compare consecutive tracked samples; deduplicate packet snapshots per session."""
    if not math.isfinite(threshold_deg) or threshold_deg <= 0:
        raise ValueError("threshold must be positive and finite")
    events = []
    previous = None
    packet_previous = None
    packet_count = 0
    count = 0
    for row in rows:
        count += 1
        time_s = float(row["time_s"])
        if not math.isfinite(time_s):
            raise ValueError("nonfinite sample time")
        if previous is not None and time_s <= previous["time_s"]:
            raise ValueError("sample times must increase")
        changes = {}
        if previous is not None and row["tracked"] and previous["tracked"]:
            for field in ("source_wrist", "semantic_wrist", "heading"):
                changes[field] = GetAngle(previous[field], row[field])
        revision_changed = previous is not None and row["engagement_revision"] != previous["engagement_revision"]
        frame_changed = previous is not None and row["anatomical_used"] != previous["anatomical_used"]
        packet_text = row.get("last_sent_packet", "")
        packet_step = None
        if packet_text:
            packet = json.loads(packet_text)
            GetQuaternion(packet["right"]["rot"])
            if packet_previous is None or packet["session_id"] != packet_previous["session_id"]:
                packet_count += 1
                packet_previous = packet
            elif packet["sequence"] > packet_previous["sequence"]:
                if packet["right"]["valid"] and packet_previous["right"]["valid"]:
                    packet_step = GetAngle(packet_previous["right"]["rot"], packet["right"]["rot"])
                packet_count += 1
                packet_previous = packet
            elif packet["sequence"] < packet_previous["sequence"]:
                raise ValueError("packet sequence moved backwards within session")
        if (revision_changed or frame_changed
                or any(value >= threshold_deg for value in changes.values())
                or (packet_step is not None and packet_step >= threshold_deg)):
            events.append({"sample_time_s": time_s, "sample_steps_deg": changes,
                           "packet_step_deg": packet_step,
                           "engagement_revision_changed": revision_changed,
                           "anatomical_selection_changed": frame_changed})
        previous = row
    return {"samples": count, "unique_packet_snapshots": packet_count,
            "threshold_deg": threshold_deg, "events": events,
            "limitations": "Sampled observations, not causal attribution or complete packet capture. "
                           "Packet and source sample times may differ; skipped packets are not reconstructed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--threshold-deg", type=float, default=5.)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.trace.with_suffix(".analysis.json")
    if output.resolve() == args.trace.resolve():
        parser.error("output must not overwrite input")
    try:
        with args.trace.open(encoding="utf-8-sig") as stream:
            result = AnalyzeRows((json.loads(line) for line in stream if line.strip()), args.threshold_deg)
        output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"[FAIL] {error}\n[ACTION] Check the trace format and output directory.\n")
    print(f"Samples: {result['samples']}; events: {len(result['events'])}")
    print(f"Result saved to: {output.resolve()}")


if __name__ == "__main__":
    main()
