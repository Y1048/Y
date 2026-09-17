"""Summarize recorded live-cycle target derivatives. Offline only."""
import argparse
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()
rows = [json.loads(line) for line in args.path.open(encoding="utf-8")]
sends = [row for row in rows if row["kind"] == "send_attempt"]
acks = [row for row in rows if row["kind"] == "ack"]
limit = math.radians(60.0)
previous_q = None
previous_v = [0.0] * 7
previous_time = None
violations = []
for row in sends:
    packet = row["packet"]
    q = packet["joints"]
    if previous_q is not None:
        dt = packet["sample_time_s"] - previous_time
        velocity = [(q[i] - previous_q[i]) / dt for i in range(7)]
        acceleration = [(velocity[i] - previous_v[i]) / dt for i in range(7)]
        for axis, value in enumerate(acceleration):
            if abs(value) > limit + 1e-7:
                violations.append({
                    "sequence": packet["sequence"], "event": packet["event"],
                    "joint": axis + 22, "dt_s": dt,
                    "acceleration_rad_s2": value,
                    "limit_rad_s2": limit,
                    "velocity_rad_s": velocity[axis],
                    "previous_velocity_rad_s": previous_v[axis],
                    "relay_time": row["time"],
                })
        previous_v = velocity
    previous_q = q
    previous_time = packet["sample_time_s"]
print(json.dumps({
    "path": str(args.path), "send_count": len(sends), "ack_count": len(acks),
    "events": {event: sum(row["packet"]["event"] == event for row in sends)
               for event in sorted({row["packet"]["event"] for row in sends})},
    "last_ack": acks[-1] if acks else None,
    "first_violations": violations[:20], "violation_count": len(violations),
}, indent=2))
