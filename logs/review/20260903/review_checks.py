"""Read-only source checks and isolated reproductions; no SDK or network I/O."""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))


def CheckSources():
    spec = importlib.util.spec_from_file_location(
        "review_index", ROOT / "backend/tools/build_code_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reviewed = set((OUTPUT / "reviewed_paths.txt").read_text(encoding="utf-8").splitlines())
    partial = {"hardware/g1_arm_bridge/gate7_live_dry_run.py",
               "hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py"}
    rows = []
    for path in module.CollectFiles(ROOT):
        raw = path.read_bytes()
        source = raw.decode("utf-8-sig")
        status = "text_read_only"
        error = ""
        try:
            if path.suffix == ".py":
                ast.parse(source, filename=str(path))
                status = "python_ast_pass"
            elif path.suffix == ".json":
                json.loads(source)
                status = "json_parse_pass"
        except Exception as exc:
            status, error = "parse_failed", str(exc)
        relative = path.relative_to(ROOT).as_posix()
        depth = ("full_text_review" if relative in reviewed else
                 "partial_control_path_review" if relative in partial else "static_only")
        rows.append(dict(path=relative,
                         sha256=hashlib.sha256(raw).hexdigest(),
                         lines=len(source.splitlines()), static_check=status,
                         error=error, semantic_review=depth))
    with (OUTPUT / "source_checks.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return dict(files=len(rows), lines=sum(row["lines"] for row in rows),
                review_depth={depth: sum(row["semantic_review"] == depth for row in rows)
                    for depth in ("full_text_review", "partial_control_path_review", "static_only")},
                parse_failures=[row for row in rows if row["error"]])


def CheckStructuredAssets():
    results = []
    with (OUTPUT / "full_inventory.csv").open(encoding="utf-8-sig") as stream:
        inventory = list(csv.DictReader(stream))
    for item in inventory:
        if item["Category"] in {"unity_generated", "runtime_evidence"}:
            continue
        path = ROOT / item["Path"]
        if path.suffix.lower() not in {".xml", ".urdf", ".json", ".csproj"}:
            continue
        try:
            if path.suffix.lower() == ".json":
                json.loads(path.read_text(encoding="utf-8-sig"))
            else:
                ET.parse(path)
            results.append(dict(path=item["Path"], status="parse_pass"))
        except Exception as exc:
            results.append(dict(path=item["Path"], status="parse_failed", error=str(exc)))
    (OUTPUT / "structured_assets.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return dict(files=len(results), failures=[item for item in results if item["status"] != "parse_pass"])


def ReproduceFindings():
    from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose, parse_mink_arm_sample
    from gate7_live_arm_sdk import LoadLiveHardwareConfig
    from gate7_mink_arm_sdk_offline import _mink_packet
    from ruckig_gate7_controller import RuckigGate7TeleopController

    observations = {}
    config_path = ROOT / "config/g1_gate7_live_hardware_output.json"
    malformed = json.loads(config_path.read_text(encoding="utf-8"))
    malformed["hardware_output_authorized"] = "false"
    malformed_path = OUTPUT / "invalid_boolean_fixture.json"
    malformed_path.write_text(json.dumps(malformed), encoding="utf-8")
    observations["string_false_authorizes_in_loader"] = LoadLiveHardwareConfig(
        malformed_path).hardware_output_authorized

    # Execute only main's finalizer and return statement, with fake objects.
    # No initialization, authorization, DDS imports, or command loop is executed.
    source_path = ROOT / "hardware/g1_arm_bridge/gate7_live_arm_sdk.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    block = next(node for node in main.body if isinstance(node, ast.Try))
    final_return = main.body[-1]
    function = ast.FunctionDef(name="Finalize", args=ast.arguments(
        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=block.finalbody + [final_return], decorator_list=[])
    isolated = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))

    class FailedPublisher:
        def Write(self, _message):
            raise OSError("injected publisher failure")

    class Clock:
        @staticmethod
        def monotonic():
            return 1.0

    snapshot = SimpleNamespace(all_q_rad=(0.0,) * 29, mode_pr=0, mode_machine=5)
    result = {"passed": True, "release_zero_frames": 0, "command_output_enabled": True}
    environment = dict(result=result, publisher=FailedPublisher(), command_message=SimpleNamespace(),
        command_crc=SimpleNamespace(Crc=lambda _message: 0),
        args=SimpleNamespace(gate7_config=None, hardware_config=None),
        load_gate7_config=lambda _: SimpleNamespace(command_hz=250.0),
        LoadLiveHardwareConfig=lambda _: SimpleNamespace(release_ramp_s=2.0, release_zero_cycles=25),
        buffer=SimpleNamespace(snapshot=lambda: snapshot), last_target=(0.0,) * 14,
        last_weight=1.0, time=Clock, ReleaseWeight=lambda *_: 1.0,
        build_measured_hold_frame=lambda *_args, **_kwargs: object(),
        _apply_frame=lambda *_: None, mink_socket=None, unity_socket=None,
        result_path=OUTPUT / "release_failure_fixture_result.json", json=json)
    exec(compile(isolated, str(source_path), "exec"), environment)
    return_code = environment["Finalize"]()
    observations["release_failure"] = dict(result, exit_code=return_code)

    config = load_gate7_config(ROOT / "config/g1_gate7_mink_arm_sdk.json")
    regular = load_regular_arm_pose(ROOT / "config/g1_regular_arm_pose.json")
    validation_calls = []
    def Validate(trajectory, posture):
        validation_calls.append((trajectory, posture))
        return True, "recorded"
    controller = RuckigGate7TeleopController(regular, config, return_path_validator=Validate)
    measured = regular.reference_all_joint_q_rad
    states = []
    for sequence in range(1, 11):
        target = list(measured)
        target[22] += 0.01
        packet = json.loads(_mink_packet(sequence=sequence, session_id="review-only",
            input_mode="active", all_q_rad=tuple(target), active=True))
        packet["timestamp"] = 1.0
        sample = parse_mink_arm_sample(json.dumps(packet))
        decision = controller.step(sample, measured, 0.004)
        states.append(decision.state)
    observations["old_source_timestamp"] = dict(timestamp=1.0, final_state=states[-1],
        command_candidate_valid=decision.command_candidate_valid)
    observations["active_path_collision_validator_calls"] = len(validation_calls)
    from arm_sdk_hold_contract import blend_weight
    from gate6_arm_sdk_hold import load_runtime_config
    gate6_config = load_runtime_config(ROOT / "config/g1_gate6_interrupt_release_test.json")
    gate6_path = ROOT / "hardware/g1_arm_bridge/gate6_arm_sdk_hold.py"
    gate6_tree = ast.parse(gate6_path.read_text(encoding="utf-8"))
    interrupt_branch = next(node for node in ast.walk(gate6_tree)
        if isinstance(node, ast.If) and "stop_requested.is_set()" in ast.unparse(node.test))
    phase, weight, done = blend_weight(gate6_config.ramp_up_s * 0.1,
        ramp_up_s=gate6_config.ramp_up_s, hold_s=gate6_config.hold_s,
        ramp_down_s=gate6_config.ramp_down_s, maximum_weight=gate6_config.maximum_weight)
    before_weight = weight
    environment = dict(config=gate6_config, schedule_phase=phase, weight=weight,
        done=done, now_s=1.0, started_s=0.0,
        stop_requested=SimpleNamespace(is_set=lambda: True))
    isolated = ast.fix_missing_locations(ast.Module(body=[interrupt_branch], type_ignores=[]))
    exec(compile(isolated, str(gate6_path), "exec"), environment)
    observations["gate6_interrupt_during_acquire"] = dict(
        weight_before=before_weight, weight_after=environment["weight"],
        phase_after=environment["schedule_phase"])

    timings = {}
    for fps in (30, 60, 72, 90):
        timer = 0.0
        hold = 0.0
        for frame in range(1, fps * 3):
            timer += 1.0 / fps
            if timer < 1.0 / 60:
                continue
            timer = 0.0
            hold += 1.0 / 60
            if hold + 1e-12 >= 0.5:
                timings[str(fps)] = frame / fps
                break
    observations["nominal_0_5s_hold_elapsed_by_fps"] = timings
    observations["sdk_imported"] = any(name.startswith("unitree_sdk") for name in sys.modules)
    return observations


if __name__ == "__main__":
    result = dict(source_checks=CheckSources(), structured_assets=CheckStructuredAssets(),
                  findings=ReproduceFindings())
    (OUTPUT / "review_checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
