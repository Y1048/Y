"""Compare a native offline dump with the Python excitation preview."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from sysid_capture import decode
from sysid_excitation_plan import RIGHT_ARM
from sysid_excitation_preview import expand


SCHEMA = "g1.sysid.excitation-crosscheck.v1"
HEADER = [
    "time_s", "segment", "active_joint",
    *(f"offset_{joint}_rad" for joint in RIGHT_ARM),
    "active_velocity_rad_s", "active_acceleration_rad_s2",
]


def _number(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid_{label}") from error
    if not math.isfinite(result):
        raise ValueError(f"nonfinite_{label}")
    return result


def compare(plan_path, native_csv_path, episode):
    if episode not in ("training", "validation"):
        raise ValueError("episode")
    plan_path = Path(plan_path)
    native_csv_path = Path(native_csv_path)
    plan_bytes = plan_path.read_bytes()
    plan = decode(plan_bytes)
    expected = expand(plan)[episode]
    with native_csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADER:
            raise ValueError("native_header")
        actual = list(reader)
    if len(actual) != len(expected):
        raise ValueError("sample_count")

    maximum_error = 0.0
    for row_index, (row, reference) in enumerate(zip(actual, expected)):
        time_s, segment, active_joint, offsets, velocity, acceleration = reference
        if int(row["segment"]) != segment:
            raise ValueError(f"segment_{row_index}")
        parsed_joint = None if row["active_joint"] == "" else int(row["active_joint"])
        if parsed_joint != active_joint:
            raise ValueError(f"active_joint_{row_index}")
        pairs = [(_number(row["time_s"], "time"), time_s, 1e-10)]
        pairs.extend(
            (_number(row[f"offset_{joint}_rad"], "offset"), offsets[joint - 22], 1e-12)
            for joint in RIGHT_ARM
        )
        pairs.extend((
            (_number(row["active_velocity_rad_s"], "velocity"), velocity, 1e-12),
            (_number(row["active_acceleration_rad_s2"], "acceleration"), acceleration, 1e-12),
        ))
        for observed, wanted, tolerance in pairs:
            error = abs(observed - wanted)
            maximum_error = max(maximum_error, error)
            if error > tolerance:
                raise ValueError(f"numeric_mismatch_{row_index}")

    return {
        "schema": SCHEMA,
        "episode": episode,
        "samples": len(actual),
        "maximum_abs_numeric_error": maximum_error,
        "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "native_csv_sha256": hashlib.sha256(native_csv_path.read_bytes()).hexdigest(),
        "command_capable": False,
        "physical_execution_authorized": False,
        "recommended_hardware_gains": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("native_csv", type=Path)
    parser.add_argument("--episode", choices=("training", "validation"), required=True)
    args = parser.parse_args(argv)
    print(json.dumps(compare(args.plan, args.native_csv, args.episode), indent=2))


if __name__ == "__main__":
    main()
