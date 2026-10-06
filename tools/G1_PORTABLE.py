"""Portable Windows entry point backed only by runtime/python."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from g1_embedded_runtime import (  # noqa: E402
    PYTHON_EXE,
    ROOT,
    SITE_PACKAGES,
    child_environment,
    python_command,
    require_embedded_interpreter,
)
import g1_teleop_dependencies as dependencies  # noqa: E402


def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def run_checked(command, *, env=None):
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def engine_env():
    env = child_environment()
    env["G1_OBSERVATION_TAP"] = env.get("G1_OBSERVATION_TAP", "1")
    env["G1_OMNI_UNITY_HEADING"] = env.get("G1_OMNI_UNITY_HEADING", "1")
    return env


def check_runtime(check_camera=True):
    require_embedded_interpreter()
    if not dependencies.probe():
        raise RuntimeError("Bundled Python runtime validation failed.")
    env = engine_env()
    result = run_checked(
        python_command(ROOT / "tools" / "g1_portable_environment.py"),
        env=env,
    )
    if result:
        raise RuntimeError("Bundled IK/model validation failed.")
    if check_camera:
        from g1_camera_ssh import check_environment
        check_environment()
    print("[PORTABLE] Bundled Python and pinned dependencies are ready.")
    return 0


def teleop(args):
    require_embedded_interpreter()
    # The dedicated ASIX G1 cable can retain an unrelated static PC address.
    # Repair it before selecting a robot host or starting any worker/motor owner.
    requested_host = 'auto'
    if '--host' in args:
        index = args.index('--host')
        requested_host = args[index + 1] if index + 1 < len(args) else ''
    if requested_host == 'auto' and '--check-only' not in args:
        from g1_portable_environment import dedicated_wired_adapter_needing_address
        adapter_index = dedicated_wired_adapter_needing_address()
        if adapter_index is not None:
            print('[G1 NETWORK] Dedicated USB Ethernet address differs from '
                  '192.168.123.99/24; requesting Windows UAC repair.', flush=True)
            rc = elevated_powershell(
                ROOT / 'tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1',
                ['-InterfaceIndex', str(adapter_index), '-VerifyRobotSsh'],
            )
            if rc:
                raise RuntimeError('G1 Ethernet repair failed or was cancelled; '
                                   'original network settings were preserved or restored. '
                                   'No teleop workers were started.')
    dependencies.ensure()
    import G1_VR_TELEOP_LAUNCH as launcher
    return launcher.main(args)


def camera(args):
    require_embedded_interpreter()
    dependencies.ensure()
    import G1_CAMERA_LAUNCH as launcher
    return launcher.main(args)


def bimanual(mode, args):
    require_embedded_interpreter()
    output = ROOT / "logs" / "test_results" / "bimanual" / f"{mode}_{stamp()}.jsonl"
    runtime_mode = "demo" if mode == "demo" else "unity"
    command = python_command(
        ROOT / "MuJoCo_G1_Controller" / "scripts" / "g1_bimanual_runtime.py",
        "--mode", runtime_mode,
        *(["--viewer"] if runtime_mode == "demo" else []),
        "--output", str(output),
        *args,
    )
    return run_checked(command, env=engine_env())


def report_latest(args, strict_quest=False):
    require_embedded_interpreter()
    report_dir = ROOT / "logs" / "test_results" / "bimanual" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    prefix = "quest_cycle" if strict_quest else "session"
    now = stamp()
    forwarded = [
        "--mode", "report", "--latest",
        "--json-output", str(report_dir / f"{prefix}_{now}.json"),
        "--markdown-output", str(report_dir / f"{prefix}_{now}.md"),
    ]
    if strict_quest:
        forwarded += ["--replay", "--require-quest-cycle", "--strict"]
    forwarded += args
    command = python_command(
        ROOT / "MuJoCo_G1_Controller" / "scripts" / "g1_bimanual_runtime.py",
        *forwarded,
    )
    rc = run_checked(command, env=engine_env())
    print(("QUEST CYCLE VERIFY " + ("PASS" if rc == 0 else "FAIL"))
          if strict_quest else f"Report saved under {report_dir}")
    return rc


def resolve_unity(args):
    require_embedded_interpreter()
    import G1_VR_TELEOP_LAUNCH as launcher
    editor = launcher.resolve_unity_editor()
    print(editor)
    return 0


def build_install_apk(args):
    require_embedded_interpreter()
    import G1_VR_TELEOP_LAUNCH as launcher
    editor = launcher.resolve_unity_editor()
    project = ROOT / "Unity_G1_VR"
    adb = Path(os.environ.get(
        "ADB_EXE",
        str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) /
            "Meta Quest Developer Hub" / "resources" / "bin" / "adb.exe"),
    ))
    if not adb.is_file():
        raise RuntimeError("Meta Quest Developer Hub adb was not found. Set ADB_EXE explicitly.")
    build_id = uuid.uuid4().hex
    apk = ROOT / "Builds" / build_id / "G1TeleopVR.apk"
    log = ROOT / "logs" / "unity" / f"unity_vr_apk_build_{build_id}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = launcher.unity_environment()
    env["G1_APK_OUTPUT_PATH"] = str(apk)
    rc = subprocess.run(
        [str(editor), "-batchmode", "-quit", "-projectPath", str(project),
         "-executeMethod", "G1VRBuild.BuildApk", "-logFile", str(log)],
        cwd=ROOT, env=env,
    ).returncode
    if rc:
        raise RuntimeError(f"Unity APK build failed. Inspect {log}")
    if not apk.is_file():
        raise RuntimeError(f"APK was not created: {apk}")
    hash_path = Path(str(apk) + ".sha256")
    if not hash_path.is_file():
        raise RuntimeError("APK hash record is missing.")
    expected = hash_path.read_text(encoding="ascii").strip().upper()
    with apk.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", expected) or actual != expected:
        raise RuntimeError("APK hash mismatch; refusing install.")
    subprocess.run([str(adb), "devices"], cwd=ROOT, check=False)
    serial = args.serial
    if not serial:
        serial = input("Enter the exact Quest serial shown as device above: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", serial):
        raise RuntimeError("A valid explicit Quest serial is required.")
    rc = subprocess.run([str(adb), "-s", serial, "install", "-r", str(apk)], cwd=ROOT).returncode
    if rc:
        raise RuntimeError("APK install failed; verify adb authorization.")
    print(f"APK installed: {apk}")
    print(f"Device: {serial}")
    return 0


def elevated_powershell(script: Path, extra):
    args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra]
    quoted = subprocess.list2cmdline(args).replace("'", "''")
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
        f"-ArgumentList '{quoted}'; exit $p.ExitCode",
    ]
    return subprocess.run(command, cwd=ROOT).returncode


def ethernet(command_name, args):
    script_name = (
        "CONFIGURE_G1_ETHERNET_ADMIN.ps1"
        if command_name == "ethernet-configure"
        else "RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1"
    )
    extra = []
    if args.interface_index:
        extra = ["-InterfaceIndex", str(args.interface_index)]
    rc = elevated_powershell(ROOT / "tools" / script_name, extra)
    if rc:
        raise RuntimeError(f"Ethernet operation failed with code {rc}.")
    return 0


def archive_validate(args):
    require_embedded_interpreter()
    import G1_ARCHIVE_OFFLINE_VALIDATE as validator
    return validator.main(args)


def main(argv=None):
    require_embedded_interpreter()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "teleop", "camera", "bimanual-demo", "bimanual-unity",
            "report-latest", "verify-latest-quest", "check-runtime",
            "resolve-unity", "build-install-apk", "archive-validate",
            "ethernet-configure", "ethernet-restore",
        ),
    )
    ns, rest = parser.parse_known_args(argv[:1] if argv else argv)
    rest = argv[1:]

    if ns.command == "teleop":
        return teleop(rest)
    if ns.command == "camera":
        return camera(rest)
    if ns.command == "bimanual-demo":
        return bimanual("demo", rest)
    if ns.command == "bimanual-unity":
        return bimanual("unity", rest)
    if ns.command == "report-latest":
        return report_latest(rest)
    if ns.command == "verify-latest-quest":
        return report_latest(rest, strict_quest=True)
    if ns.command == "check-runtime":
        sub = argparse.ArgumentParser(prog="G1_PORTABLE.py check-runtime")
        sub.add_argument("--check-only", action="store_true")
        sub.add_argument("--pc-only", action="store_true")
        opts = sub.parse_args(rest)
        return check_runtime(check_camera=not opts.pc_only)
    if ns.command == "resolve-unity":
        sub = argparse.ArgumentParser(prog="G1_PORTABLE.py resolve-unity")
        sub.add_argument("--check-unity-path", action="store_true")
        sub.parse_args(rest)
        return resolve_unity(ns)
    if ns.command == "archive-validate":
        return archive_validate(rest)
    if ns.command == "build-install-apk":
        sub = argparse.ArgumentParser(prog="G1_PORTABLE.py build-install-apk")
        sub.add_argument("--serial")
        sub.add_argument("--check-unity-path", action="store_true")
        opts = sub.parse_args(rest)
        if opts.check_unity_path:
            return resolve_unity(opts)
        return build_install_apk(opts)
    if ns.command in ("ethernet-configure", "ethernet-restore"):
        sub = argparse.ArgumentParser(prog="G1_PORTABLE.py " + ns.command)
        sub.add_argument("--interface-index", type=int, default=0)
        return ethernet(ns.command, sub.parse_args(rest))
    raise AssertionError(ns.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("[PORTABLE FAILED] " + str(error), file=sys.stderr)
        raise SystemExit(1)
