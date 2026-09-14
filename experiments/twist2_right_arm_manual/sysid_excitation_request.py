"""Create an offline excitation request from saved state and literal C++ arrays."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

from sysid_capture import canonical, decode
from sysid_excitation_plan import RIGHT_ARM, SCHEMA as REQUEST_SCHEMA, build
from sysid_readonly_parse import read


SPEC_SCHEMA = "g1.sysid.excitation-draft-spec.v1"
RECEIPT_SCHEMA = "g1.sysid.excitation-request-receipt.v1"


def _arrays(path):
    source = re.sub(r"//[^\n]*|/\*.*?\*/", "", Path(path).read_text(encoding="utf-8"), flags=re.S)
    def array(name):
        found = re.search(r"\b" + name + r"\s*=\s*\{([^}]+)\}", source)
        if not found: raise ValueError(f"missing_cpp_array_{name}")
        tokens = [x.strip() for x in found.group(1).split(",") if x.strip()]
        if len(tokens) != 29 or any(not re.fullmatch(r"[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?[fF]?", x) for x in tokens):
            raise ValueError(f"invalid_cpp_array_{name}")
        values = [float(x.rstrip("fF")) for x in tokens]
        if not all(math.isfinite(x) for x in values): raise ValueError(f"nonfinite_cpp_array_{name}")
        return values
    margin_match = re.search(r"\bkJointLimitMargin\s*=\s*([-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)[fF]?", source)
    if not margin_match: raise ValueError("missing_joint_limit_margin")
    margin = float(margin_match.group(1))
    return array("kKp"), array("kKd"), [x + margin for x in array("kLower")], [x - margin for x in array("kUpper")]


def _spec(value):
    required = {"schema", "contract_id", "amplitude_rad", "velocity_limit_rad_s",
                "acceleration_limit_rad_s2", "sample_period_s", "hold_s", "cycles",
                "tail_s", "pose_range_tolerance_rad", "velocity_tolerance_rad_s",
                "termination_owner_contract"}
    if not isinstance(value, dict) or set(value) != required or value["schema"] != SPEC_SCHEMA:
        raise ValueError("draft_spec")
    return value


def create(capture_path, common_source, controller_source, spec):
    spec = _spec(spec)
    rows = read(capture_path)
    for key in ("tail_s", "pose_range_tolerance_rad", "velocity_tolerance_rad_s"):
        if type(spec[key]) not in (int, float) or not math.isfinite(spec[key]) or spec[key] <= 0:
            raise ValueError(key)
    end = rows[-1]["state_receive_ns"]
    tail = [x for x in rows if (end - x["state_receive_ns"]) * 1e-9 <= spec["tail_s"]]
    if len(tail) < 2 or (tail[-1]["state_receive_ns"] - tail[0]["state_receive_ns"]) * 1e-9 < spec["tail_s"] * .9:
        raise ValueError("insufficient_stable_tail")
    if len({(x["mode_pr"], x["mode_machine"]) for x in tail}) != 1:
        raise ValueError("unstable_observed_mode")
    start = [statistics.median(x["measured_q"][j] for x in tail) for j in range(29)]
    for j in RIGHT_ARM:
        if max(x["measured_q"][j] for x in tail) - min(x["measured_q"][j] for x in tail) > spec["pose_range_tolerance_rad"]:
            raise ValueError(f"pose_not_stable_joint_{j}")
        if max(abs(x["measured_dq"][j]) for x in tail) > spec["velocity_tolerance_rad_s"]:
            raise ValueError(f"velocity_not_stable_joint_{j}")
    kp, kd, lower, upper = _arrays(common_source)
    sources = {
        "twist2_common.hpp": hashlib.sha256(Path(common_source).read_bytes()).hexdigest(),
        "controller.cpp": hashlib.sha256(Path(controller_source).read_bytes()).hexdigest(),
    }
    bundle_hash = hashlib.sha256(canonical(sources)).hexdigest()
    request = {
        "schema": REQUEST_SCHEMA, "contract_id": spec["contract_id"],
        "controller_source_sha256": bundle_hash, "joint_indices": list(RIGHT_ARM),
        "start_q_rad": start, "soft_lower_q_rad": lower, "soft_upper_q_rad": upper,
        "kp_nm_rad": kp, "kd_nm_s_rad": kd,
        "amplitude_rad": spec["amplitude_rad"],
        "velocity_limit_rad_s": spec["velocity_limit_rad_s"],
        "acceleration_limit_rad_s2": spec["acceleration_limit_rad_s2"],
        "sample_period_s": spec["sample_period_s"], "hold_s": spec["hold_s"],
        "cycles": spec["cycles"], "termination_owner_contract": spec["termination_owner_contract"],
    }
    build(request)  # full bounds/type validation before returning a draft
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "capture_sha256": hashlib.sha256(Path(capture_path).read_bytes()).hexdigest(),
        "capture_session": rows[0]["session"], "tail_samples": len(tail),
        "observed_mode": {"mode_pr": tail[-1]["mode_pr"], "mode_machine": tail[-1]["mode_machine"]},
        "source_sha256": sources, "controller_source_sha256": bundle_hash,
        "request_sha256": hashlib.sha256(canonical(request)).hexdigest(),
        "physical_execution_authorized": False, "recommended_hardware_gains": None,
    }
    return request, receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path); parser.add_argument("spec", type=Path)
    parser.add_argument("--common-source", type=Path, required=True)
    parser.add_argument("--controller-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    request, receipt = create(args.capture, args.common_source, args.controller_source,
                              decode(args.spec.read_bytes()))
    with args.output.open("xb") as stream: stream.write(canonical(request))
    with Path(str(args.output) + ".receipt.json").open("xb") as stream: stream.write(canonical(receipt))


if __name__ == "__main__": main()
