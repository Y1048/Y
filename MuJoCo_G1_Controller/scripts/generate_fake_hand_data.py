import csv
import math
from pathlib import Path


out_path = Path(__file__).resolve().parents[1] / "data" / "fake_hand_tracking.csv"
out_path.parent.mkdir(parents=True, exist_ok=True)
duration = 20.0
dt = 0.02

with out_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["time", "left_x", "left_y", "left_z", "right_x", "right_y", "right_z"])

    steps = int(duration / dt)
    for i in range(steps + 1):
        t = i * dt

        left_x = 0.18 + 0.08 * math.sin(0.55 * t)
        left_y = 0.0
        left_z = 0.72 + 0.06 * math.sin(0.85 * t)

        right_x = -left_x
        right_y = 0.0
        right_z = left_z

        writer.writerow([
            f"{t:.3f}",
            f"{left_x:.5f}",
            f"{left_y:.5f}",
            f"{left_z:.5f}",
            f"{right_x:.5f}",
            f"{right_y:.5f}",
            f"{right_z:.5f}",
        ])

print(f"wrote {out_path}")
