"""Check model isolation without opening sockets or invoking hardware entry points."""
import ast
import json
import hashlib
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace

import mujoco
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))
import run_mink_g1_right_arm_prototype as controller
from gate7_mink_arm_sdk_offline import CollisionPathValidator


@pytest.mark.parametrize("failure", [None, "startup", "run", "close", "load"])
def test_render_replay_xml_lifetime(monkeypatch, tmp_path, failure):
    monkeypatch.syspath_prepend(str(ROOT / "backend/tools"))
    import benchmark_mink_rendered_replay as tool
    import offline_render_worker as worker

    before = shared_bytes()
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["render", "capture", "reference", "--repeats", "1",
                                      "--decoupled-render", "--result-json", str(output)])
    paths, closed = [], []

    def load(capture, report, segment, path):
        paths.append(Path(path))
        assert paths[-1].is_file()
        if failure == "load":
            raise ValueError("injected load")
        model = mujoco.MjModel.from_xml_path(str(path))
        return model, model.qpos0.copy(), [], [], {}

    class Renderer:
        def __init__(self, path, *args):
            assert Path(path) == paths[-1] and Path(path).is_file()
            if failure == "startup":
                raise RuntimeError("injected startup")

        def Close(self):
            assert paths[-1].is_file()
            closed.append(True)
            if failure == "close":
                raise RuntimeError("injected close")

    def run(*args):
        assert paths[-1].is_file()
        if failure == "run":
            raise RuntimeError("injected run")
        return {"trajectory_parity": True, "render_check": {"nonblank_and_changing": True},
                "late_frames": [], "render_worker": {"screenshots": []},
                "timings": {"work_ms": {}}, "wall_duration_s": 0}, {}

    monkeypatch.setattr(tool, "LoadReplay", load)
    monkeypatch.setattr(worker, "ProcessRenderer", Renderer)
    monkeypatch.setattr(tool, "RunRenderedReplay", run)
    if failure:
        assert tool.main() == 1
    else:
        assert tool.main() == 0
    assert paths and not paths[-1].parent.exists()
    assert closed == ([] if failure in ("startup", "load") else [True])
    assert shared_bytes() == before
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == (
        "ERROR" if failure else "PACED_RENDER_BUDGET_MET")


@pytest.mark.parametrize("explicit_path", [False, True])
def test_render_replay_loads_isolated_model(monkeypatch, tmp_path, explicit_path):
    monkeypatch.syspath_prepend(str(ROOT / "backend/tools"))
    import benchmark_mink_rendered_replay as tool

    path = controller._prepare_mink_xml(output_path=tmp_path / "model.xml")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    capture = tmp_path / "capture"
    capture.write_bytes(b"fixture")
    report = tmp_path / "reference.json"
    report.write_text(json.dumps({"capture_sha256": hashlib.sha256(b"fixture").hexdigest(),
        "model_xml_sha256": digest, "mujoco_version": mujoco.__version__, "horizon_steps": 3}), encoding="utf-8")
    report.with_name("reference_s1_limit_avoidance.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(controller.g1, "DEMO_XML", tmp_path / "absent.xml")
    monkeypatch.setattr(tool.comparison.probe, "_decode_capture", lambda _: ({}, []))
    monkeypatch.setattr(tool.comparison, "GetActiveSegments", lambda _: [(
        {"value": {"all_joint_q_rad": [0.] * 29}}, [])])
    result = tool.LoadReplay(capture, report, 1, path) if explicit_path else tool.LoadReplay(capture, report, 1)
    assert result[0].nq > 0
    assert result[-1]["model_xml_sha256"] == digest
    assert result[-1]["model_xml_path"] is None


@pytest.mark.parametrize("filename,visible", [
    ("run_mink_g1_right_arm_prototype", False),
    ("run_mink_g1_right_arm_virtual_center_live", False),
    ("run_mink_g1_right_arm_virtual_center_live", True),
])
def test_live_entry_model_block_isolated(filename, visible):
    source = ROOT / "MuJoCo_G1_Controller/scripts" / (filename + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    assignment = next(n for n in main.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "model"
                              for lhs in n.targets for t in ast.walk(lhs)))
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
                   and (n.func.id if isinstance(n.func, ast.Name) else n.func.attr) == "_prepare_mink_xml"
                   for n in ast.walk(main))
    before = shared_bytes()
    calls = []

    def load(show_inspection_scene=False):
        calls.append(show_inspection_scene)
        return controller.LoadMinkModel(show_inspection_scene)

    namespace = {"base": SimpleNamespace(LoadMinkModel=load,
                 LoadMinkModelWithMetadata=lambda show_inspection_scene=False: (load(show_inspection_scene), {})), "LoadMinkModel": load,
                 "LoadMinkModelWithMetadata": lambda: (load(), {}),
                 "args": SimpleNamespace(show_inspection_scene=visible)}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), "exec"), namespace)
    assert calls == [visible]
    assert namespace["model"].nq > 0
    assert shared_bytes() == before


def test_jog_provenance_uses_validator_model(monkeypatch, tmp_path):
    import right_arm_jog_safety_guard as guard
    validator = CollisionPathValidator()
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(controller.g1, "DEMO_XML", tmp_path / "missing-shared.xml")
    provenance = guard.build_jog_permit_provenance(config, validator.model_metadata)
    assert provenance["generated_model_sha256"] == validator.model_metadata["model_xml_sha256"]
    guard.validate_jog_permit_provenance({"provenance": provenance}, config, validator.model_metadata)
    with pytest.raises(ValueError, match="does not match"):
        guard.validate_jog_permit_provenance({"provenance": provenance}, config,
                                           {"model_xml_sha256": "0" * 64})
    with pytest.raises(ValueError, match="requires"):
        guard.build_jog_permit_provenance(config)
    legacy = dict(provenance)
    legacy.pop("model_binding")
    with pytest.raises(ValueError, match="does not match"):
        guard.validate_jog_permit_provenance({"provenance": legacy}, config, validator.model_metadata)


def shared_bytes():
    path = Path(controller.g1.DEMO_XML)
    return path.read_bytes() if path.exists() else None


@pytest.mark.parametrize("failure", [False, True])
def test_shared_loader_cleanup_and_model_parity(failure):
    import numpy as np

    before = shared_bytes()
    original = controller._prepare_mink_xml
    paths = []
    expected = []

    def prepare(*args, **kwargs):
        path = original(*args, **kwargs)
        paths.append(path)
        if failure:
            raise RuntimeError("injected load preparation failure")
        expected.append(mujoco.MjModel.from_xml_path(str(path)))
        return path

    with patch.object(controller, "_prepare_mink_xml", side_effect=prepare):
        if failure:
            with pytest.raises(RuntimeError, match="injected"):
                controller.LoadMinkModel()
        else:
            model = controller.LoadMinkModel()
            for field in ("qpos0", "jnt_range", "body_pos", "geom_pos", "mesh_vert"):
                np.testing.assert_array_equal(getattr(model, field), getattr(expected[0], field))
    assert paths and all(not path.parent.exists() for path in paths)
    assert shared_bytes() == before


@pytest.mark.parametrize("filename", [
    "audit_wrist_target_mapping", "diagnose_recorded_reach", "compare_synthetic_ik",
    "diagnose_mink_collision_feasibility", "compare_mink_step_acceptance",
    "diagnose_mink_distance_invariance", "compare_recorded_ik_hierarchy",
    "compare_recorded_pose_speeds", "verify_feasible_target", "verify_virtual_center_kinematics",
    "inspect_feasible_target_return",
    "benchmark_mink_candidate",
])
def test_diagnostic_uses_fresh_loader(filename):
    source = ROOT / "backend/tools" / (filename + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    entry = "RunDiagnosis" if filename == "diagnose_recorded_reach" else "main"
    if filename == "inspect_feasible_target_return":
        entry = "RunInspection"
    if filename == "benchmark_mink_candidate":
        entry = "RunReport"
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == entry)
    assignment = next(node for node in main.body if isinstance(node, ast.Assign) and
                      any(isinstance(target, ast.Name) and target.id == "model"
                          for lhs in node.targets for target in ast.walk(lhs)))
    sentinel = object()
    base = SimpleNamespace(LoadMinkModel=lambda: sentinel, LoadMinkModelWithMetadata=lambda: (sentinel, {}))
    namespace = {"base": base, "probe": SimpleNamespace(base=base)}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), "exec"), namespace)
    assert namespace["model"] is sentinel


def test_prototype_packet_preserves_fields_and_adds_loaded_identity():
    import mink
    from gate7_capture_mujoco_replay import CheckReplayModelIdentity

    source = ROOT / "MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    load = next(node for node in main.body if isinstance(node, ast.Assign) and
                isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and
                node.value.func.id == "LoadMinkModelWithMetadata")
    namespace = {"LoadMinkModelWithMetadata": controller.LoadMinkModelWithMetadata}
    exec(compile(ast.Module(body=[load], type_ignores=[]), str(source), "exec"), namespace)
    model = namespace["model"]
    configuration = mink.Configuration(model)
    configuration.update(controller._initial_configuration(model))
    addresses = [int(model.jnt_qposadr[controller._joint_id(model, name)])
                 for name in controller.g1.G1_29_JOINTS]
    packet = controller._state_packet(configuration, addresses[22:29], addresses,
                                      False, [0, 0, 0], None, False)
    original = json.loads(json.dumps(packet))
    additions = [node for node in ast.walk(main) if isinstance(node, ast.Assign) and
                 any(isinstance(lhs, ast.Subscript) and isinstance(lhs.value, ast.Name) and
                     lhs.value.id == "packet" and isinstance(lhs.slice, ast.Constant) and
                     lhs.slice.value == "model_metadata" for lhs in node.targets)]
    assert len(additions) == 1
    namespace["packet"] = packet
    exec(compile(ast.Module(body=additions, type_ignores=[]), str(source), "exec"), namespace)
    assert {k: v for k, v in packet.items() if k != "model_metadata"} == original
    class Sink:
        def sendto(self, payload, target):
            self.payload = payload
    sink = Sink()
    controller._send_state(sink, packet, "127.0.0.1", 1)
    decoded = json.loads(sink.payload)
    assert CheckReplayModelIdentity([{"value": decoded}], namespace["model_metadata"]).startswith("XML AND EXPLICIT ASSETS MATCH")


def test_metadata_hashes_loaded_xml_not_shared_file(monkeypatch, tmp_path):
    shared = tmp_path / "unrelated.xml"
    shared.write_text("not the generated model", encoding="utf-8")
    monkeypatch.setattr(controller.g1, "DEMO_XML", shared)
    original = controller._prepare_mink_xml
    expected = []

    def prepare(*args, **kwargs):
        path = original(*args, **kwargs)
        expected.append(hashlib.sha256(path.read_bytes()).hexdigest())
        return path

    with patch.object(controller, "_prepare_mink_xml", side_effect=prepare):
        model, metadata = controller.LoadMinkModelWithMetadata()
    assert model.nq > 0
    assert metadata["model_xml_sha256"] == expected[0]
    assert metadata["model_xml_sha256"] != hashlib.sha256(shared.read_bytes()).hexdigest()
    assert metadata["model_xml_path"] is None
    assert "excludes runtime limits" in metadata["hash_scope"]


@pytest.mark.parametrize("mismatch", [None, "capture", "model", "segment"])
def test_return_inspection_reference_binding(monkeypatch, tmp_path, mismatch):
    monkeypatch.syspath_prepend(str(ROOT / "backend/tools"))
    import inspect_feasible_target_return as tool
    import numpy as np

    model, metadata = controller.LoadMinkModelWithMetadata()
    capture = tmp_path / "capture.jsonl"
    capture.write_text("fixture", encoding="utf-8")
    report = tmp_path / "reference.json"
    report.write_text(json.dumps({
        "capture_sha256": "wrong" if mismatch == "capture" else hashlib.sha256(capture.read_bytes()).hexdigest(),
        "model_xml_sha256": "wrong" if mismatch == "model" else metadata["model_xml_sha256"],
        "mujoco_version": mujoco.__version__,
    }), encoding="utf-8")
    report.with_name("reference_s2_limit_avoidance.jsonl").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["inspect", str(capture), str(report),
                                      "--variant", "candidate", "--result-json", str(output)])
    monkeypatch.setattr(controller, "LoadMinkModelWithMetadata", lambda: (model, metadata))
    monkeypatch.setattr(controller.g1, "DEMO_XML", tmp_path / "absent-shared.xml")
    monkeypatch.setattr(tool.comparison.probe, "_decode_capture", lambda _: ({}, []))
    monkeypatch.setattr(tool.comparison, "GetActiveSegments", lambda _: (None, (
        {"value": {"all_joint_q_rad": [0.] * 29}}, [])))
    if mismatch == "segment":
        monkeypatch.setattr(tool.comparison, "GetActiveSegments", lambda _: [])
    calls = []

    def run(actual_model, initial, *args):
        assert actual_model is model
        assert np.isfinite(initial).all()
        calls.append(True)
        return {"verdict": {"status": "OFFLINE_CRITERIA_MET"}}

    monkeypatch.setattr(tool, "Run", run)
    if mismatch:
        assert tool.main() == 1
        failure = json.loads(output.read_text())
        assert failure["verdict"]["status"] == "FAIL"
        assert ("second active segment" if mismatch == "segment" else "does not match reference") in failure["error"]
        assert not calls
    else:
        assert tool.main() == 0
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved["hashes"]["model"] == metadata["model_xml_sha256"]
        assert saved["model_metadata"] == metadata
        assert calls == [True]


@pytest.mark.parametrize("mismatch", [None, "capture", "model", "engine", "horizon", "segment"])
def test_candidate_reference_binding(monkeypatch, tmp_path, mismatch):
    monkeypatch.syspath_prepend(str(ROOT / "backend/tools"))
    import benchmark_mink_candidate as tool

    model, metadata = controller.LoadMinkModelWithMetadata()
    capture = tmp_path / "capture.jsonl"
    capture.write_text("fixture", encoding="utf-8")
    report = tmp_path / "reference.json"
    report.write_text(json.dumps({
        "capture_sha256": "wrong" if mismatch == "capture" else hashlib.sha256(capture.read_bytes()).hexdigest(),
        "model_xml_sha256": "wrong" if mismatch == "model" else metadata["model_xml_sha256"],
        "mujoco_version": "wrong" if mismatch == "engine" else mujoco.__version__,
        "horizon_steps": 4 if mismatch == "horizon" else 3,
    }), encoding="utf-8")
    report.with_name("reference_s2_limit_avoidance.jsonl").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["benchmark", str(capture), str(report),
                                      "--repeats", "1", "--result-json", str(output)])
    monkeypatch.setattr(controller, "LoadMinkModelWithMetadata", lambda: (model, metadata))
    monkeypatch.setattr(controller.g1, "DEMO_XML", tmp_path / "absent.xml")
    monkeypatch.setattr(tool.comparison.probe, "_decode_capture", lambda _: ({}, []))
    monkeypatch.setattr(tool.comparison, "GetActiveSegments", lambda _: (None, (
        {"value": {"all_joint_q_rad": [0.] * 29}}, [])))
    calls = []

    def run(actual_model, *args):
        assert actual_model is model
        calls.append(True)
        return {"trajectory_parity": True, "timing": {"deadline_misses": 0}}

    monkeypatch.setattr(tool, "RunBenchmark", run)
    if mismatch == "segment":
        monkeypatch.setattr(tool.comparison, "GetActiveSegments", lambda _: [])
    if mismatch:
        assert tool.main() == 1
        failure = json.loads(output.read_text())
        assert failure["status"] == "FAIL"
        assert ("Requested segment" if mismatch == "segment" else "does not match reference") in failure["error"]
        assert not calls
    else:
        assert tool.main() == 0
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved["model_xml_sha256"] == metadata["model_xml_sha256"]
        assert saved["model_xml_path"] is None
        assert saved["status"] == "PLANNER_ONLY_BUDGET_MET"
        assert calls == [True]


def test_offline_collision_validator_keeps_shared_model(monkeypatch):
    monkeypatch.delenv("G1_USE_HARDWARE_INITIAL_STATE", raising=False)
    before = shared_bytes()
    original = controller._prepare_mink_xml
    paths = []

    def prepare(*args, **kwargs):
        path = kwargs["output_path"]
        assert path != Path(controller.g1.DEMO_XML)
        paths.append(path)
        return original(*args, **kwargs)

    with patch.object(controller, "_prepare_mink_xml", side_effect=prepare):
        first = CollisionPathValidator()
        second = CollisionPathValidator()
    assert paths[0] != paths[1]
    assert all(not path.exists() for path in paths)
    assert first.model.nq == second.model.nq
    assert first.geom_pairs == second.geom_pairs
    mujoco.mj_forward(first.model, first.data)
    assert shared_bytes() == before


@pytest.mark.parametrize("visible", [False, True])
def test_lowstate_model_loader_without_socket(monkeypatch, visible):
    import live_lowstate_mujoco as live

    monkeypatch.delenv("G1_USE_HARDWARE_INITIAL_STATE", raising=False)
    before = shared_bytes()
    with patch.object(live.socket, "socket", side_effect=AssertionError("network forbidden")):
        model, data, _ = live.LoadModel(show_inspection_scene=visible)
    mujoco.mj_forward(model, data)
    assert model.nq > 0
    assert shared_bytes() == before


@pytest.mark.parametrize("identity", ["match", "mismatch", "legacy", "mixed", "assets", "xml_only", "limits", "engine", "old_runtime"])
def test_capture_replay_checks_actual_xml_before_viewer(monkeypatch, capsys, identity):
    import gate7_capture_mujoco_replay as replay
    import live_lowstate_mujoco as live

    monkeypatch.delenv("G1_USE_HARDWARE_INITIAL_STATE", raising=False)
    before = shared_bytes()
    model, data, _, metadata = live.LoadModel(include_metadata=True)
    addresses = live.ResolveFullBodyQposAddresses(model)
    packet = {"offset_s": 0.0, "value": {}, "sample": SimpleNamespace(
        input_command_mode="active", all_joint_q_rad=data.qpos[addresses].copy())}
    if identity != "legacy":
        packet["value"]["model_metadata"] = dict(metadata)
    if identity == "mismatch":
        packet["value"]["model_metadata"]["model_xml_sha256"] = "0" * 64
    if identity == "assets":
        packet["value"]["model_metadata"]["model_assets_sha256"] = "0" * 64
    if identity == "xml_only":
        packet["value"]["model_metadata"].pop("model_assets_sha256")
    if identity == "limits":
        packet["value"]["model_metadata"]["model_joint_limits_sha256"] = "0" * 64
    if identity == "engine":
        packet["value"]["model_metadata"]["mujoco_version"] = "other-version"
    if identity == "old_runtime":
        packet["value"]["model_metadata"].pop("model_joint_limits_sha256")
        packet["value"]["model_metadata"].pop("mujoco_version")
    packets = [packet]
    if identity == "mixed":
        packets.append({**packet, "value": {}, "offset_s": 0.1})
    monkeypatch.setattr(replay, "_decode_capture", lambda _: ({"capture_id": "fixture"}, packets))
    monkeypatch.setattr(sys, "argv", ["replay", "fixture", "--validate-only"])
    monkeypatch.setattr(replay.mujoco.viewer, "launch_passive",
                        lambda *a, **k: pytest.fail("viewer forbidden"))
    if identity in {"mismatch", "assets", "limits", "engine"}:
        monkeypatch.setattr(replay, "ApplyFullBodyPose",
                            lambda *a: pytest.fail("mismatch must reject before applying pose"))
        with pytest.raises(ValueError, match="mismatch"):
            replay.main()
    else:
        assert replay.main() == 0
        output = capsys.readouterr().out
        expected = {"match": "JOINT LIMITS AND ENGINE MATCH", "xml_only": "assets unverified",
                    "old_runtime": "joint limits/engine unverified"}
        assert expected.get(identity, "UNVERIFIED") in output
    assert shared_bytes() == before


@pytest.mark.parametrize("tag,directory", [("mesh", "meshdir"), ("hfield", "meshdir"), ("texture", "texturedir")])
def test_asset_hash_detects_content_change(tmp_path, tag, directory):
    assets = tmp_path / "assets"
    assets.mkdir()
    asset = assets / "fixture.bin"
    asset.write_bytes(b"original")
    xml = tmp_path / "model.xml"
    xml.write_text(f'<mujoco><compiler {directory}="assets"/><asset><{tag} file="fixture.bin"/></asset></mujoco>')
    before = controller.GetModelAssetHash(xml)
    assert controller.GetModelAssetHash(xml) == before
    asset.write_bytes(b"modified")
    assert controller.GetModelAssetHash(xml) != before
    asset.unlink()
    with pytest.raises(FileNotFoundError):
        controller.GetModelAssetHash(xml)


def test_asset_hash_rejects_unhandled_includes(tmp_path):
    xml = tmp_path / "model.xml"
    xml.write_text('<mujoco><include file="other.xml"/></mujoco>')
    with pytest.raises(ValueError, match="unsupported"):
        controller.GetModelAssetHash(xml)


def test_asset_change_during_load_is_rejected(monkeypatch):
    hashes = iter(["a" * 64, "b" * 64])
    monkeypatch.setattr(controller, "GetModelAssetHash", lambda _: next(hashes))
    with pytest.raises(RuntimeError, match="changed during loading"):
        controller.LoadMinkModelWithMetadata()


def test_applied_joint_limit_digest_detects_changes():
    model = controller.LoadMinkModel()
    controller._apply_operational_joint_limits(model)
    original = controller.GetJointLimitMetadata(model)
    assert original["mujoco_version"] == mujoco.__version__
    index = controller._joint_id(model, controller.g1.RIGHT_ARM_JOINTS[0])
    model.jnt_range[index, 0] += 0.001
    assert controller.GetJointLimitMetadata(model) != original


@pytest.mark.parametrize("filename", [
    "run_mink_g1_right_arm_prototype",
    "run_mink_g1_right_arm_virtual_center_live",
])
def test_live_attaches_applied_joint_limit_metadata(filename):
    source = ROOT / "MuJoCo_G1_Controller/scripts" / (filename + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    statements = [n for n in main.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
    apply = next(n for n in statements if "_apply_operational_joint_limits" in ast.unparse(n))
    update = next(n for n in statements if "model_metadata.update" in ast.unparse(n))
    assert main.body.index(apply) < main.body.index(update)
    model = controller.LoadMinkModel()
    namespace = {"model": model, "model_metadata": {}, "base": controller,
                 "_apply_operational_joint_limits": controller._apply_operational_joint_limits,
                 "GetJointLimitMetadata": controller.GetJointLimitMetadata}
    exec(compile(ast.Module(body=[apply, update], type_ignores=[]), str(source), "exec"), namespace)
    assert namespace["model_metadata"] == controller.GetJointLimitMetadata(model)


def test_fk_export_without_shared_model_or_output(tmp_path, monkeypatch):
    import export_g1_mink_fk_reference as exporter

    before = shared_bytes()
    output = tmp_path / "reference.json"
    monkeypatch.setattr(exporter, "OUTPUT_PATH", output)
    exporter.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["frame"] == "right_wrist_yaw_link"
    assert len(report["samples"]) == len(exporter.SAMPLES_DEG)
    assert report["samples"][0]["unity_wrist_delta_m"] == [0.0, 0.0, 0.0]
    assert shared_bytes() == before


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("filename,function", [
    ("verify_initial_pose_sync.py", "main"),
    ("diagnose_initial_pose_collision.py", "main"),
    ("check_startup_readiness.py", "evaluate_collision_window"),
    ("plan_startup_transition.py", "main"),
    ("simulate_startup_recovery.py", "main"),
    ("replay_startup_recovery.py", "Main"),
    ("edit_startup_ready_pose.py", "CreateModel"),
])
def test_pose_sync_model_load_block_is_isolated(fail, filename, function):
    # Execute just the real load block, not main (which reads hardware capture).
    source = ROOT / "hardware/g1_arm_bridge" / filename
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function)
    block = next(node for node in main.body if isinstance(node, ast.With))
    paths = []
    original = controller._prepare_mink_xml
    before = shared_bytes()

    def prepare(*args, **kwargs):
        paths.append(kwargs["output_path"])
        if fail:
            raise RuntimeError("injected generation failure")
        return original(*args, **kwargs)

    namespace = {"controller": controller, "tempfile": tempfile, "Path": Path, "mujoco": mujoco}
    with patch.object(controller, "_prepare_mink_xml", side_effect=prepare):
        if fail:
            with pytest.raises(RuntimeError, match="injected"):
                exec(compile(ast.Module(body=[block], type_ignores=[]), str(source), "exec"), namespace)
        else:
            exec(compile(ast.Module(body=[block], type_ignores=[]), str(source), "exec"), namespace)
            assert namespace["model"].nq > 0
    assert len(paths) == 1 and not paths[0].parent.exists()
    assert shared_bytes() == before


def test_precheck_collision_window_without_network(monkeypatch):
    import check_startup_readiness as precheck

    monkeypatch.delenv("G1_USE_HARDWARE_INITIAL_STATE", raising=False)
    before = shared_bytes()
    packet = SimpleNamespace(telemetry=SimpleNamespace(
        all_joint_names=precheck.EXPECTED_G1_29_JOINT_NAMES,
        all_joint_q_rad=(0.0,) * 29,
        all_joint_dq_rad_s=(0.0,) * 29,
    ))
    # Only the numerical helper runs; main would receive UDP and is not invoked.
    with patch.object(precheck.socket, "socket", side_effect=AssertionError("network forbidden")):
        result = precheck.evaluate_collision_window([packet])
    assert result["sample_count"] == 1
    assert result["collision_pair_count"] > 0
    assert shared_bytes() == before


def test_editor_model_without_viewer_or_pose_save(monkeypatch):
    import edit_startup_ready_pose as editor
    import numpy as np

    monkeypatch.delenv("G1_USE_HARDWARE_INITIAL_STATE", raising=False)
    before = shared_bytes()
    pose = np.asarray(controller.g1.DEFAULT_RIGHT_ARM_READY_DEGREES, dtype=float)
    with patch.object(editor.mujoco.viewer, "launch_passive", side_effect=AssertionError("viewer forbidden")), \
         patch.object(editor, "SavePose", side_effect=AssertionError("config write forbidden")):
        _, model, data, pairs = editor.CreateModel(pose)
    assert pairs
    actual = [data.qpos[model.jnt_qposadr[controller._joint_id(model, name)]] for name in controller.g1.RIGHT_ARM_JOINTS]
    np.testing.assert_allclose(actual, np.radians(pose), atol=1e-12)
    assert shared_bytes() == before
