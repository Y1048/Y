"""Exercise CLI exit contracts without importing rendering or robot dependencies."""

import ast
import math
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"


def test_camera_read_deadline_csharp_without_network(tmp_path):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell required")
    source = (TOOLS.parents[1] / "Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs").read_text(encoding="utf-8-sig")
    method = source.split("    private static bool ReadExactly(", 1)[1].split("    private void StopReceiver()", 1)[0]
    method = "    private static bool ReadExactly(" + method
    harness = r'''
using System;
using System.IO;
using System.Threading;
using System.Diagnostics;
public class CameraReadHarness {
METHOD
class FakeStream : MemoryStream {
    public int Timeout;
    public int Delay;
    public FakeStream(byte[] bytes) : base(bytes) {}
    public override int ReadTimeout { get { return Timeout; } set { Timeout = value; } }
    public override int Read(byte[] b, int offset, int count) {
        if (Delay > Timeout) throw new IOException("read timed out");
        Thread.Sleep(Delay);
        return base.Read(b, offset, Math.Min(1, count));
    }
}
static long Deadline(int ms) { return Stopwatch.GetTimestamp() + Stopwatch.Frequency * ms / 1000; }
static void Check(bool value) { if (!value) throw new Exception("assertion failed"); }
public static void Run() {
    byte[] target = new byte[4];
    Check(ReadExactly(new FakeStream(new byte[4]), target, 4, CancellationToken.None, Deadline(1000)));
    Check(!ReadExactly(new FakeStream(new byte[1]), target, 4, CancellationToken.None, Deadline(1000)));
    Check(!ReadExactly(new FakeStream(new byte[4]), target, 4, new CancellationToken(true), Deadline(1000)));
    foreach (int mode in new int[] {0, 1}) {
        try {
            FakeStream stream = new FakeStream(new byte[4]);
            stream.Delay = mode == 1 ? 30 : 0;
            ReadExactly(stream, target, 4, CancellationToken.None, Deadline(mode == 0 ? -1 : 20));
            throw new Exception("deadline was ignored");
        } catch (IOException) {}
    }
    long shared = Deadline(1000);
    Check(ReadExactly(new FakeStream(new byte[4]), target, 4, CancellationToken.None, shared));
    Thread.Sleep(1050);
    try {
        ReadExactly(new FakeStream(new byte[4]), target, 4, CancellationToken.None, shared);
        throw new Exception("payload reset the deadline");
    } catch (IOException) {}
}
}
'''.replace("METHOD", method)
    path = tmp_path / "harness.cs"
    path.write_text(harness, encoding="utf-8")
    environment = os.environ.copy()
    environment["CAMERA_HARNESS"] = str(path)
    result = subprocess.run([powershell, "-NoProfile", "-Command",
                             "$ErrorActionPreference='Stop'; Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:CAMERA_HARNESS)); [CameraReadHarness]::Run(); 'PASS'"],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and "PASS" in result.stdout, result.stdout + result.stderr
    receiver = source.split("private void ReceiveFrames(", 1)[1].split("private static bool ReadExactly(", 1)[0]
    assert receiver.count("frame_deadline))") == 2


@pytest.mark.parametrize("name,field", [
    (name, field) for name, fields in (
        ("g1_camera_tcp_bridge.py", ("fps", "camera_timeout", "connect_timeout", "reconnect_delay")),
        ("g1_camera_replay_tcp.py", ("fps", "duration", "connect_timeout", "reconnect_delay")),
    ) for field in fields
])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "30"])
def test_camera_cli_rejects_nonfinite_without_transport(name, field, value):
    path = TOOLS.parents[1] / "hardware" / "g1_arm_bridge" / name
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "ValidateArguments")
    namespace = {"math": math, "argparse": SimpleNamespace(Namespace=SimpleNamespace)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    args = dict(host="127.0.0.1", port=5010, fps=20.0, duration=0.0, quality=80,
                camera_timeout=1.0, connect_timeout=1.0, reconnect_delay=1.0)
    namespace["ValidateArguments"](SimpleNamespace(**args))
    args[field] = value
    with pytest.raises(SystemExit):
        namespace["ValidateArguments"](SimpleNamespace(**args))


@pytest.mark.parametrize("name", ["CONFIGURE_G1_ETHERNET_ADMIN.ps1", "RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"])
@pytest.mark.parametrize("scenario", ["ok", "wrong_dhcp", "extra_address", "missing_interface"])
def test_network_final_state_is_verified(tmp_path, name, scenario):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell required")
    scripts = tmp_path / "tools"
    scripts.mkdir()
    shutil.copyfile(TOOLS.parents[1] / "tools" / name, scripts / name)
    shutil.copyfile(TOOLS.parents[1] / "tools" / "G1_ETHERNET_DNS.ps1", scripts / "G1_ETHERNET_DNS.ps1")
    shutil.copyfile(TOOLS.parents[1] / "tools" / "G1_ETHERNET_TRANSACTION.ps1", scripts / "G1_ETHERNET_TRANSACTION.ps1")
    marker = tmp_path / "logs" / "runtime" / "g1_ethernet_configured.txt"
    marker.parent.mkdir(parents=True)
    marker.write_text("old success")
    environment = os.environ.copy()
    environment.update(TEST_NET_ROOT=str(tmp_path), TEST_NET_SCRIPT=name, TEST_NET_SCENARIO=scenario)
    # Every network cmdlet used by these scripts is shadowed; only temp files change.
    command = r'''
function Get-NetAdapter { [pscustomobject]@{InterfaceDescription='ASIX AX88772A mock'; ifIndex=7; Name='mock'; InterfaceGuid='00000000-0000-0000-0000-000000000007'} }
function Get-ItemProperty { param($LiteralPath,$ErrorAction) [pscustomobject]@{NameServer=''} }
function Get-DnsClientServerAddress { param($InterfaceIndex,$AddressFamily,$ErrorAction) [pscustomobject]@{InterfaceIndex=7;AddressFamily=2} }
function Get-NetRoute {}
function Set-NetIPInterface {}
function Remove-NetIPAddress { param($InterfaceIndex,$AddressFamily,$PolicyStore,$IPAddress,$ErrorAction,[switch]$Confirm) }
function New-NetIPAddress {}
function Set-DnsClientServerAddress {}
function Get-NetIPInterface {
    if ($env:TEST_NET_SCENARIO -eq 'missing_interface') { return }
    $dhcp = if ($env:TEST_NET_SCRIPT -like 'CONFIGURE*') { 'Disabled' } else { 'Enabled' }
    if ($env:TEST_NET_SCENARIO -eq 'wrong_dhcp') { $dhcp = 'wrong' }
    [pscustomobject]@{Dhcp=$dhcp}
}
function Get-NetIPAddress {
    if ($env:TEST_NET_SCRIPT -like 'CONFIGURE*') {
        [pscustomobject]@{IPAddress='192.168.123.99'; PrefixLength=24; PrefixOrigin='Manual';SkipAsSource=$false;Type='Unicast';ValidLifetime=[timespan]::MaxValue;PreferredLifetime=[timespan]::MaxValue}
    }
    if ($env:TEST_NET_SCENARIO -eq 'extra_address') {
        [pscustomobject]@{IPAddress='192.168.123.88'; PrefixLength=24; PrefixOrigin='Manual';SkipAsSource=$false;Type='Unicast';ValidLifetime=[timespan]::MaxValue;PreferredLifetime=[timespan]::MaxValue}
    }
}
try { & (Join-Path $env:TEST_NET_ROOT ('tools\' + $env:TEST_NET_SCRIPT)) }
catch { Write-Output $_.Exception.Message; exit 1 }
'''
    result = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                            env=environment, capture_output=True, text=True, timeout=20)
    assert (result.returncode == 0) == (scenario == "ok"), result.stdout + result.stderr
    assert marker.exists() == (scenario == "ok" and name.startswith("CONFIGURE"))
    if scenario != "ok":
        assert "verification failed" in result.stdout or "Unsupported IPv4 interface state" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("name", ["CONFIGURE_G1_ETHERNET_ADMIN.ps1", "RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"])
@pytest.mark.parametrize("count,index,accepted", [(0, 0, False), (2, 0, False), (1, 0, True), (2, 2, True), (1, 9, False)])
def test_adapter_selection_is_unambiguous(name, count, index, accepted):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell required")
    source = (TOOLS.parents[1] / "tools" / name).read_text(encoding="utf-8-sig")
    # Execute only the read-only selection prefix; no network setters are included.
    prefix = source.split("$adapter = $adapters[0]", 1)[0]
    assert "Set-Net" not in prefix and "Remove-Net" not in prefix
    command = f'''
function Get-NetAdapter {{
    for ($i = 1; $i -le {count}; $i++) {{
        [pscustomobject]@{{ InterfaceDescription = 'ASIX AX88772A mock'; ifIndex = $i }}
    }}
}}
try {{
    & {{ {prefix}
        Write-Output "SELECTED:$($adapters[0].ifIndex)"
    }} -InterfaceIndex {index}
}} catch {{ Write-Output $_.Exception.Message; exit 1 }}
'''
    result = subprocess.run([powershell, "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=20)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if accepted:
        assert f"SELECTED:{index or 1}" in result.stdout
    else:
        assert "no settings were changed" in result.stdout


@pytest.mark.parametrize("scenario", ["ok", "start", "stop", "format", "missing_etl", "missing_text"])
def test_network_capture_checks_native_failures(tmp_path, scenario):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell required")
    scripts = tmp_path / "tools"
    scripts.mkdir()
    script = scripts / "DETECT_G1_NETWORK_ADMIN.ps1"
    shutil.copyfile(TOOLS.parents[1] / "tools" / script.name, script)
    environment = os.environ.copy()
    environment["TEST_CAPTURE_ROOT"] = str(tmp_path)
    environment["TEST_CAPTURE_SCENARIO"] = scenario
    # Function shadows the executable: no real capture or administrator action.
    command = r'''
function pktmon {
    $operation = $args[0]
    $global:LASTEXITCODE = 0
    if ($operation -eq $env:TEST_CAPTURE_SCENARIO) {
        $global:LASTEXITCODE = 7
        return
    }
    $directory = Join-Path $env:TEST_CAPTURE_ROOT 'logs\runtime'
    if ($operation -eq 'start' -and $env:TEST_CAPTURE_SCENARIO -ne 'missing_etl') {
        [IO.File]::WriteAllText((Join-Path $directory 'g1_network_capture.etl'), 'mock')
    }
    if ($operation -eq 'format' -and $env:TEST_CAPTURE_SCENARIO -ne 'missing_text') {
        [IO.File]::WriteAllText((Join-Path $directory 'g1_network_capture.txt'), 'mock')
    }
}
function Start-Sleep { param($Seconds) }
& (Join-Path $env:TEST_CAPTURE_ROOT 'tools\DETECT_G1_NETWORK_ADMIN.ps1')
'''
    result = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                            env=environment, capture_output=True, text=True, timeout=20)
    done = tmp_path / "logs" / "runtime" / "g1_network_capture.done"
    assert (result.returncode == 0) == (scenario == "ok"), result.stdout + result.stderr
    assert done.exists() == (scenario == "ok")
    if scenario != "ok":
        assert "[ERROR]" in result.stdout
        assert "Capture completion was not recorded" in result.stdout

CASES = [
    ("diagnose_recorded_reach", "result", "quality_status", "REVIEW_REQUIRED", 3),
    ("benchmark_mink_candidate", "report", "status", "PLANNER_ONLY_BUDGET_MET", 0),
    ("benchmark_mink_candidate", "report", "status", "PARITY_FAILURE", 1),
    ("benchmark_mink_candidate", "report", "status", "DEADLINE_MISSES", 2),
    ("benchmark_mink_rendered_replay", "report", "status", "PACED_RENDER_BUDGET_MET", 0),
    ("benchmark_mink_rendered_replay", "report", "status", "PARITY_OR_RENDER_FAILURE", 1),
    ("benchmark_mink_rendered_replay", "report", "status", "DEADLINE_MISSES", 2),
    ("benchmark_mink_rendered_replay", "report", "status", "DISPLAY_AGE_MISSES", 2),
    ("verify_feasible_target", "report", "status", "OFFLINE_CRITERIA_MET", 0),
    ("verify_feasible_target", "report", "status", "REVIEW_REQUIRED", 3),
    ("compare_recorded_pose_speeds", "result", "quality_status", "OFFLINE_CRITERIA_MET", 0),
    ("compare_recorded_pose_speeds", "result", "quality_status", "REVIEW_REQUIRED", 3),
    ("inspect_feasible_target_return", "result", "verdict", "OFFLINE_CRITERIA_MET", 0),
    ("inspect_feasible_target_return", "result", "verdict", "REVIEW_REQUIRED", 3),
    ("diagnose_mink_distance_invariance", "report", "status", "BLOCK_DEPLOYMENT", 4),
    ("diagnose_mink_distance_invariance", "report", "status", "REVIEW_REQUIRED", 3),
]


@pytest.mark.parametrize("module,variable,key,status,expected", CASES)
def test_report_status_controls_process_exit(module, variable, key, status, expected):
    tree = ast.parse((TOOLS / (module + ".py")).read_text(encoding="utf-8-sig"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    if module in ("diagnose_recorded_reach", "inspect_feasible_target_return", "benchmark_mink_candidate"):
        entry = {"diagnose_recorded_reach": "RunDiagnosis", "inspect_feasible_target_return": "RunInspection",
                 "benchmark_mink_candidate": "RunReport"}[module]
        block = main.body[-1]
        assert isinstance(block, ast.Try)
        forwarded = block.body[0]
        assert isinstance(forwarded, ast.Return) and isinstance(forwarded.value, ast.Call)
        assert forwarded.value.func.id == entry
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == entry)
    if module == "benchmark_mink_rendered_replay":
        boundary = main.body[-1]
        assert isinstance(boundary, ast.Try)
        block = boundary.body[0]
        assert isinstance(block, ast.With)
        forwarded = block.body[-1]
        assert isinstance(forwarded, ast.Return) and isinstance(forwarded.value, ast.Call)
        assert isinstance(forwarded.value.func, ast.Name) and forwarded.value.func.id == "RunReplay"
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "RunReplay")
    assert isinstance(main.body[-1], ast.Return)
    value = {"status": status} if key == "verdict" else status
    namespace = {variable: {key: value}}
    expression = ast.Expression(main.body[-1].value)
    code = eval(compile(expression, module, "eval"), namespace)
    assert code == expected
    # Execute the real entry-point wrapper with a stubbed expensive main.
    guard = tree.body[-1]
    assert isinstance(guard, ast.If)
    wrapper = ast.Module(body=[guard], type_ignores=[])
    with pytest.raises(SystemExit) as result:
        exec(compile(wrapper, module, "exec"), {"__name__": "__main__", "main": lambda: code})
    assert result.value.code == expected


@pytest.mark.parametrize("duration", [0.0, 0.001, -1.0, float("nan"), float("inf"), -float("inf")])
def test_kinematics_rejects_zero_step_duration(duration):
    tree = ast.parse((TOOLS / "verify_virtual_center_kinematics.py").read_text(encoding="utf-8-sig"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "GetStepCount")
    namespace = {"math": math, "base": SimpleNamespace(DT=0.02)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "steps", "exec"), namespace)
    with pytest.raises(ValueError):
        namespace["GetStepCount"](duration)
    assert namespace["GetStepCount"](0.02) == 1
    assert namespace["GetStepCount"](1.0) == 50
    assert namespace["GetStepCount"](42.0) == 2100


@pytest.mark.parametrize("stale", [False, True])
def test_unity_prebuilt_timestamp_gate(tmp_path, stale):
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is required")
    unity = tmp_path / "unity"
    source = unity / "Assets" / "Receiver.cs"
    assembly = unity / "Temp" / "bin" / "Debug" / "Assembly-CSharp.dll"
    project = unity / "Assembly-CSharp.csproj"
    source.parent.mkdir(parents=True)
    assembly.parent.mkdir(parents=True)
    for path in (source, assembly, project):
        path.write_text("fixture", encoding="utf-8")
        os.utime(path, (1000000000, 1000000000))
    if stale:
        os.utime(source, (1000000100, 1000000100))
    script = (TOOLS / "verify_unity_state_packets.ps1").read_text(encoding="utf-8-sig")
    gate = script[script.index("$assemblyPath ="):script.index("[xml]$project =")]
    command = "$ErrorActionPreference='Stop'; $unity=$env:G1_TEST_UNITY; " + gate
    process = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                             env={**os.environ, "G1_TEST_UNITY": str(unity)},
                             capture_output=True, text=True, timeout=30)
    assert (process.returncode != 0) == stale, process.stderr


@pytest.mark.parametrize("state", ["valid", "changed", "missing_hash"])
def test_apk_hash_gate(tmp_path, state):
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is required")
    root = TOOLS.parents[1]
    launcher = (root / "tools/BUILD_AND_INSTALL_VR_APK.bat").read_text(encoding="utf-8-sig")
    builder = (root / "Unity_G1_VR/Assets/Editor/G1VRBuild.cs").read_text(encoding="utf-8-sig")
    assert 'GetEnvironmentVariable("G1_APK_OUTPUT_PATH")' in builder
    assert 'set "G1_APK_OUTPUT_PATH=%APK_PATH%"' in launcher
    assert '"%ADB_EXE%" -s "%DEVICE_SERIAL%" install -r "%APK_PATH%"' in launcher
    line = next(line for line in launcher.splitlines() if "$expected=(Get-Content" in line)
    command = line.split('-Command "', 1)[1][:-1]
    apk = tmp_path / "new.apk"
    apk.write_bytes(b"build result")
    if state != "missing_hash":
        Path(str(apk) + ".sha256").write_text(hashlib.sha256(apk.read_bytes()).hexdigest().upper())
    if state == "changed":
        apk.write_bytes(b"different build")
    process = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "G1_APK_OUTPUT_PATH": str(apk)}, capture_output=True, text=True, timeout=30)
    assert (process.returncode == 0) == (state == "valid"), process.stderr
