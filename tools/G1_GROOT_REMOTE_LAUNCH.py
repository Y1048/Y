"""Own the two GROOT onboard processes used by integrated VR teleop.

The launcher never changes the remote command contract. It validates the
expected files/processes, preserves exact existing instances, refuses
conflicting instances, and owns only SSH children started by this invocation.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import subprocess
import sys
import threading

from g1_ssh_login import ensure_login, identity_options

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = "/home/unitree/groot_onboard_runtime"
HEADING_ARGV = (
    "python3", "-u", "tools/g1_omni_heading_controller.py",
    "--yaw-sign", "-1",
)
ACTUATOR_ARGV = (
    "./build/groot_balance_actuator",
    "--normal",
    "--enable-actuation",
    "--acknowledge-harness",
    "--accept-handoff-risk",
    "--supervisor-off",
    "--external-controller",
    "--interface", "eth0",
    "--duration", "300",
)

REMOTE_INSPECT = r"""
import json, os, shutil
root = "/home/unitree/groot_onboard_runtime"
errors = []
heading = os.path.join(root, "tools/g1_omni_heading_controller.py")
actuator = os.path.join(root, "build/groot_balance_actuator")
if not os.path.isdir(root): errors.append("missing_runtime_dir")
if not os.path.isfile(heading): errors.append("missing_heading_controller")
if not os.path.isfile(actuator): errors.append("missing_balance_actuator")
if os.path.isfile(actuator) and not os.access(actuator, os.X_OK):
    errors.append("balance_actuator_not_executable")
if shutil.which("python3") is None: errors.append("python3_missing")
rows = []
for name in os.listdir("/proc"):
    if not name.isdigit():
        continue
    try:
        raw = open("/proc/" + name + "/cmdline", "rb").read()
        args = [item.decode(errors="replace") for item in raw.split(b"\0") if item]
        if not args:
            continue
        names = [os.path.basename(item) for item in args]
        if ("g1_omni_heading_controller.py" not in names
                and "groot_balance_actuator" not in names):
            continue
        rows.append({
            "pid": int(name),
            "args": args,
            "cwd": os.readlink("/proc/" + name + "/cwd"),
        })
    except (FileNotFoundError, PermissionError, OSError):
        pass
print(json.dumps({"errors": errors, "processes": rows}))
"""


def _ssh_base(host: str) -> list[str]:
    return [
        "ssh.exe", *identity_options(), "-T",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
        "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
        "unitree@" + host,
    ]
def _managed_remote_command(argv: tuple[str, ...]) -> str:
    command = shlex.join(argv)
    cleanup = 'kill -TERM "$child" 2>/dev/null || true'
    return (
        "cd " + shlex.quote(REMOTE_DIR) + " || exit 1"
        + "; trap " + shlex.quote(cleanup) + " HUP INT TERM EXIT"
        + "; " + command + " & child=$!"
        + '; wait "$child"; rc=$?'
        + "; trap - HUP INT TERM EXIT"
        + '; exit "$rc"'
    )


def ssh_command(host: str, argv: tuple[str, ...]) -> list[str]:
    return _ssh_base(host) + [_managed_remote_command(argv)]


def inspect_remote(host: str) -> list[dict]:
    result = subprocess.run(
        _ssh_base(host) + ["python3 -"],
        input=REMOTE_INSPECT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("errors"):
        raise RuntimeError(
            "GROOT remote preflight failed: " + ", ".join(payload["errors"]))
    return list(payload.get("processes") or [])
def _match_process(row: dict, target: str, expected_tail: tuple[str, ...]) -> bool:
    args = list(row.get("args") or [])
    indices = [
        index for index, arg in enumerate(args)
        if Path(arg).name == target
    ]
    if not indices:
        return False
    if len(indices) != 1:
        raise RuntimeError("Ambiguous remote process arguments for " + target)
    index = indices[0]
    if row.get("cwd") != REMOTE_DIR or tuple(args[index:]) != expected_tail:
        raise RuntimeError(
            "Conflicting remote " + target + " process is already running; preserved.")
    return True


def classify_existing(rows: list[dict]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        if _match_process(
                row, "g1_omni_heading_controller.py", HEADING_ARGV[2:]):
            if "heading" in found:
                raise RuntimeError("Duplicate GROOT heading controllers found; preserved.")
            found.add("heading")
            continue
        if _match_process(
                row, "groot_balance_actuator", ACTUATOR_ARGV):
            if "actuator" in found:
                raise RuntimeError("Duplicate GROOT balance actuators found; preserved.")
            found.add("actuator")
    return found
def _tee(name: str, child: subprocess.Popen, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as output:
        assert child.stdout is not None
        for line in child.stdout:
            text = "[" + name.upper() + "] " + line.rstrip()
            print(text, flush=True)
            output.write(text + "\n")
            output.flush()


def _spawn(host: str, name: str, argv: tuple[str, ...], log_path: Path):
    child = subprocess.Popen(
        ssh_command(host, argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    thread = threading.Thread(
        target=_tee, args=(name, child, log_path), daemon=True)
    thread.start()
    return child, thread


def run(host: str, *, confirmed: bool) -> int:
    if not confirmed:
        raise RuntimeError("GROOT actuation requires integrated-launch confirmation.")
    ensure_login(host)
    existing = classify_existing(inspect_remote(host))
    print("[GROOT KEEP] " + (", ".join(sorted(existing)) or "none"), flush=True)
    folder = ROOT / "logs/test_results/groot_remote" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(parents=True, exist_ok=False)
    children: dict[str, subprocess.Popen] = {}
    threads = []
    stopped = threading.Event()

    def wait_for_stop():
        if not sys.stdin.isatty():
            return
        try:
            input("GROOT active. Press Enter to stop processes owned by this launcher. ")
        except (EOFError, KeyboardInterrupt):
            pass
        stopped.set()

    try:
        if "heading" not in existing:
            child, thread = _spawn(
                host, "heading", HEADING_ARGV, folder / "heading.log")
            children["heading"] = child
            threads.append(thread)
        if "actuator" not in existing:
            child, thread = _spawn(
                host, "actuator", ACTUATOR_ARGV, folder / "actuator.log")
            children["actuator"] = child
            threads.append(thread)
        print("[GROOT START] " + (", ".join(children) or
              "none; exact remote processes already exist"), flush=True)
        print("[GROOT LOGS] " + str(folder), flush=True)
        threading.Thread(target=wait_for_stop, daemon=True).start()
        while not stopped.wait(0.25):
            exited = [
                (name, child.returncode)
                for name, child in children.items()
                if child.poll() is not None
            ]
            if exited:
                print("[GROOT EXIT] " + repr(exited), flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        for name, child in reversed(list(children.items())):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=1)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--check-command", action="store_true")
    args = parser.parse_args(argv)
    if args.check_command:
        print(shlex.join(HEADING_ARGV))
        print(shlex.join(ACTUATOR_ARGV))
        return 0
    return run(args.host, confirmed=args.confirmed)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError, RuntimeError, ValueError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("[GROOT REMOTE FAILED] " + str(error), file=sys.stderr)
        raise SystemExit(1)
