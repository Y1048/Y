"""Add initial-yaw-relative Omni body velocity columns to an existing CSV."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hardware.g1_arm_bridge.g1_omni_velocity_gateway import (
    MOVEMENT_DEADZONE,
    YAW_OFFSET_DEG,
    omni_to_body_velocity,
    wrapped_delta_degrees,
)

ADDED_COLUMNS = (
    "time_s", "yaw_relative_deg", "vx_forward", "vy_right", "vy_left",
    "theta_deg", "movement_magnitude",
)


def _number(row: dict[str, str], names: tuple[str, ...]) -> float:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            result = float(value)
            if math.isfinite(result):
                return result
    raise ValueError("missing finite column: " + "/".join(names))


def convert(input_path: Path, output_path: Path | None = None,
            yaw_offset_deg: float = YAW_OFFSET_DEG,
            deadzone: float = MOVEMENT_DEADZONE) -> Path:
    output_path = output_path or input_path.with_name(
        input_path.stem + "_corrected" + input_path.suffix)
    with input_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")
        rows = list(reader)
        original_columns = list(reader.fieldnames)
    if not rows:
        raise ValueError("CSV has no data rows")

    initial_yaw = _number(rows[0], ("arm_yaw_deg", "yaw", "armYaw"))
    first_time = _number(rows[0], ("receive_monotonic_s", "elapsed_s", "time_s", "timestamp"))
    converted = []
    for row in rows:
        movement_x = _number(row, ("movement_x", "mx"))
        movement_y = _number(row, ("movement_y", "my"))
        yaw = _number(row, ("arm_yaw_deg", "yaw", "armYaw"))
        sample_time = _number(row, ("receive_monotonic_s", "elapsed_s", "time_s", "timestamp"))
        yaw_relative = wrapped_delta_degrees(yaw, initial_yaw)
        vx_forward, vy_right = omni_to_body_velocity(
            movement_x, movement_y, yaw, initial_yaw, yaw_offset_deg, deadzone)
        updated = dict(row)
        updated.update({
            "time_s": sample_time - first_time,
            "yaw_relative_deg": yaw_relative,
            "vx_forward": vx_forward,
            "vy_right": vy_right,
            "vy_left": -vy_right,
            "theta_deg": yaw_relative + yaw_offset_deg,
            "movement_magnitude": math.hypot(movement_x, movement_y),
        })
        converted.append(updated)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = original_columns + [name for name in ADDED_COLUMNS if name not in original_columns]
    with output_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(converted)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--yaw-offset-deg", type=float, default=YAW_OFFSET_DEG)
    parser.add_argument("--deadzone", type=float, default=MOVEMENT_DEADZONE)
    args = parser.parse_args()
    print(convert(args.input_csv, args.output, args.yaw_offset_deg, args.deadzone))


if __name__ == "__main__":
    main()
