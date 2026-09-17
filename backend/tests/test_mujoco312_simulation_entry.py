"""Local engine selection and fail-closed hardware boundary; no device runtime."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "MuJoCo_G1_Controller/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))
import run_mink_g1_simulation_312 as entry
from gate7_relay_provenance_guard import (
    require_live_candidate_for_relay, require_live_hardware_provenance,
)
from arm_sdk_teleop_contract import Gate7ContractError


def test_simulation_packet_cannot_enter_hardware():
    original = {"command_provenance": "live_mink", "session_id": "test"}
    packet = entry.MarkSimulation(lambda: original)()
    assert original["command_provenance"] == "live_mink"
    assert packet["simulation_only"] is True
    assert packet["hardware_output_authorized"] is False
    assert packet["simulation_engine"] == "mujoco-3.12.0"
    for guard in (require_live_candidate_for_relay, require_live_hardware_provenance):
        with pytest.raises(Gate7ContractError):
            guard(json.dumps(packet))


def test_seed_environment_forwarding_without_shell_interpolation(monkeypatch):
    from types import SimpleNamespace
    observed=[]
    monkeypatch.setenv("G1_MINK_INITIAL_SEED", "C:/path with spaces/seed.json")
    monkeypatch.setenv("G1_MINK_INITIAL_SESSION", "test-session")
    monkeypatch.setattr(entry, "LoadEngine", lambda: SimpleNamespace(__version__="3.12.0", __file__="test"))
    monkeypatch.setitem(sys.modules, "run_mink_g1_right_arm_prototype", SimpleNamespace(_state_packet=lambda: {}))
    monkeypatch.setitem(sys.modules, "run_mink_g1_right_arm_virtual_center_live",
                        SimpleNamespace(main=lambda: observed.extend(sys.argv)))
    monkeypatch.setattr(sys, "argv", ["entry", "--seed-from-environment", "--initial-state-check-only", "report.json"])
    assert entry.main()==0
    assert observed[observed.index("--initial-lowstate-seed")+1]=="C:/path with spaces/seed.json"
    assert observed[observed.index("--initial-lowstate-session")+1]=="test-session"
    assert observed[observed.index("--initial-state-check-only")+1]=="report.json"


def test_partial_seed_environment_rejected_before_engine(monkeypatch):
    monkeypatch.setenv("G1_MINK_INITIAL_SEED", "seed.json")
    monkeypatch.delenv("G1_MINK_INITIAL_SESSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["entry", "--seed-from-environment"])
    monkeypatch.setattr(entry, "LoadEngine", lambda: pytest.fail("engine must not load"))
    with pytest.raises(SystemExit) as error:entry.main()
    assert error.value.code==2


@pytest.mark.parametrize("solver", ["vanilla", "hierarchical"])
def test_isolated_import_validation(solver):
    result = subprocess.run([sys.executable, str(Path(entry.__file__)),
        "--validate-only", "--ik-solver", solver], capture_output=True,
        text=True, timeout=30, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MuJoCo 3.12.0" in result.stdout
    assert "no runtime started" in result.stdout


def test_hardware_profile_rejected_before_import():
    result = subprocess.run([sys.executable, str(Path(entry.__file__)),
        "--collision-profile", "hardware-guarded", "--validate-only"],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_missing_engine_does_not_fall_back(monkeypatch, tmp_path):
    monkeypatch.delitem(sys.modules, "mujoco", raising=False)
    monkeypatch.setattr(entry, "ENGINE_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="missing"):
        entry.LoadEngine()


def test_preloaded_engine_rejected(monkeypatch):
    monkeypatch.setitem(sys.modules, "mujoco", object())
    with pytest.raises(RuntimeError, match="fresh Python"):
        entry.LoadEngine()


def test_launcher_does_not_change_physical_selection():
    physical = (ROOT / "tools/START_G1_GATE7_STANDARD_MINK.bat").read_text()
    assert "--mujoco312" not in physical
    local = (ROOT / "START_VR_STANDARD_MINK.bat").read_text()
    assert "--standard-mink --mujoco312" in local
    shared = (ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
    assert 'if "%CAMERA_REQUESTED%"=="0" goto :camera_checks_done' in shared
    assert shared.index('goto :camera_checks_done') < shared.index('Test-Connection')


def test_simulation_return_is_local_and_wrappers_do_not_duplicate():
    source = (ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
    assert 'if /I "%DISPLAY_MODE%"=="simulation" if /I "%IK_MODE%"=="virtual-center" if "%EXTERNAL_FEEDBACK%"=="0" (' in source
    assert 'gate7_live_dry_run.py --measured-source mink' in source
    assert 'gate7_live_arm_sdk.py' not in source
    for name in ('START_G1_GATE7_LIVE_DRY_RUN.bat', 'START_G1_GATE7_VR_RECORDING.bat'):
        assert 'call START_VR_HAND_TO_MUJOCO.bat --external-feedback' in (ROOT / 'tools' / name).read_text()


@pytest.mark.parametrize("arguments, expected", [
    ([], "1"), (["--hierarchical"], "1"), (["--hardware-display"], "0"),
    (["--hardware-display", "--standard-mink"], "0"),
    (["--mujoco311"], "0"), (["--baseline"], "0"), (["--vanilla-mink"], "0"),
])
def test_local_engine_default_preserves_hardware_and_legacy(tmp_path, arguments, expected):
    import os
    if os.name != "nt":
        pytest.skip("CMD configuration only")
    source = (ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
    prefix = source.split("echo ========================================", 1)[0]
    script = tmp_path / "select.bat"
    script.write_text(prefix + '\necho ENGINE=%LOCAL_ENGINE_312%\n')
    result = subprocess.run(["cmd.exe", "/d", "/c", str(script), *arguments],
                            capture_output=True, text=True, check=True)
    assert f"ENGINE={expected}" in result.stdout
