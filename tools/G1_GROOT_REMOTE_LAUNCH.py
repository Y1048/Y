"""Own the two GROOT onboard processes used by integrated VR teleop.

Each onboard program receives its own forced SSH PTY and runs in the remote
foreground, matching the previously proven manual two-terminal workflow.
The supervisor owns only remote processes tagged with its session owner ID.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid

from g1_ssh_login import ensure_login, identity_options, ssh_executable

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = "/home/unitree/groot_onboard_runtime"
OWNER_ENV = "G1_GROOT_OWNER"
OWNER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
HEADING_ARGV = (
    "python3", "-u", "tools/g1_omni_heading_controller.py",
    "--yaw-sign", "-1",
)
ACTUATOR_BASE_ARGV = (
    "./build/groot_balance_actuator",
    "--normal",
    "--enable-actuation",
    "--acknowledge-harness",
    "--accept-handoff-risk",
    "--supervisor-off",
    "--external-controller",
    "--interface", "eth0",
)
ACTUATOR_FALLBACK_DURATION = ("--duration", "300")
ACTUATOR_UNLIMITED = ("--unlimited-duration",)

REMOTE_INSPECT = r"""
import json, os, shutil, subprocess
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
supports_unlimited = False
if not errors:
    try:
        probe = subprocess.run(
            [actuator, "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )
        supports_unlimited = "--unlimited-duration" in (probe.stdout or "")
    except Exception:
        pass
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
        owner = ""
        try:
            env = open("/proc/" + name + "/environ", "rb").read().split(b"\0")
            prefix = b"G1_GROOT_OWNER="
            for item in env:
                if item.startswith(prefix):
                    owner = item[len(prefix):].decode(errors="replace")
                    break
        except (FileNotFoundError, PermissionError, OSError):
            pass
        rows.append({
            "pid": int(name),
            "args": args,
            "cwd": os.readlink("/proc/" + name + "/cwd"),
            "owner": owner,
        })
    except (FileNotFoundError, PermissionError, OSError):
        pass
print(json.dumps({
    "errors": errors,
    "supports_unlimited_duration": supports_unlimited,
    "processes": rows,
}))
"""

REMOTE_SIGNAL = r"""
import json, os, signal, sys, time
owner = sys.argv[1]
target = sys.argv[2]
timeout = float(sys.argv[3])

def matching():
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            raw = open("/proc/" + name + "/cmdline", "rb").read()
            args = [item.decode(errors="replace") for item in raw.split(b"\0") if item]
            if not args or target not in [os.path.basename(item) for item in args]:
                continue
            env = open("/proc/" + name + "/environ", "rb").read().split(b"\0")
            if ("G1_GROOT_OWNER=" + owner).encode() not in env:
                continue
            found.append(int(name))
        except (FileNotFoundError, PermissionError, OSError):
            pass
    return found

pids = matching()
for pid in pids:
    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        pass
deadline = time.monotonic() + timeout
remaining = matching()
while remaining and time.monotonic() < deadline:
    time.sleep(0.1)
    remaining = matching()
print(json.dumps({"target": target, "signalled": pids, "remaining": remaining}))
if remaining:
    raise SystemExit(2)
"""


def actuator_argv(supports_unlimited_duration: bool) -> tuple[str, ...]:
    return ACTUATOR_BASE_ARGV + (
        ACTUATOR_UNLIMITED
        if supports_unlimited_duration
        else ACTUATOR_FALLBACK_DURATION
    )


def _ssh_base(host: str, *, tty: bool) -> list[str]:
    return [
        ssh_executable(), *identity_options(), "-tt" if tty else "-T",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
        "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
        "unitree@" + host,
    ]


def _foreground_remote_command(
        argv: tuple[str, ...], owner_id: str) -> str:
    if not OWNER_RE.fullmatch(owner_id):
        raise ValueError("Invalid GROOT owner id")
    return (
        "cd " + shlex.quote(REMOTE_DIR) + " || exit 1"
        + "; export " + OWNER_ENV + "=" + shlex.quote(owner_id)
        + "; exec " + shlex.join(argv)
    )


def ssh_command(
        host: str, argv: tuple[str, ...], owner_id: str) -> list[str]:
    return _ssh_base(host, tty=True) + [
        _foreground_remote_command(argv, owner_id)
    ]


def inspect_remote(host: str) -> dict:
    result = subprocess.run(
        _ssh_base(host, tty=False) + ["python3 -"],
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
    return payload


def _match_process(
        row: dict, target: str, expected_tail: tuple[str, ...]) -> bool:
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
            "Conflicting remote " + target
            + " process is already running; preserved.")
    return True


def classify_existing(
        rows: list[dict], expected_actuator_argv: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        if _match_process(
                row, "g1_omni_heading_controller.py", HEADING_ARGV[2:]):
            if "heading" in found:
                raise RuntimeError(
                    "Duplicate GROOT heading controllers found; preserved.")
            found.add("heading")
            continue
        if _match_process(
                row, "groot_balance_actuator", expected_actuator_argv):
            if "actuator" in found:
                raise RuntimeError(
                    "Duplicate GROOT balance actuators found; preserved.")
            found.add("actuator")
    return found


def _tee(name: str, child: subprocess.Popen, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as output:
        assert child.stdout is not None
        for line in child.stdout:
            rendered = "[" + name.upper() + "] " + line.rstrip()
            print(rendered, flush=True)
            output.write(rendered + "\n")
            output.flush()


def _spawn(
        host: str,
        name: str,
        argv: tuple[str, ...],
        owner_id: str,
        log_path: Path,
):
    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    )
    child = subprocess.Popen(
        ssh_command(host, argv, owner_id),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )
    thread = threading.Thread(
        target=_tee, args=(name, child, log_path), daemon=True)
    thread.start()
    return child, thread


def _require_still_running(name: str, child: subprocess.Popen) -> None:
    time.sleep(0.75)
    code = child.poll()
    if code is not None:
        raise RuntimeError(
            name + " exited during startup with code " + str(code)
            + "; inspect the GROOT log for the remote error.")


def _signal_owned(
        host: str, owner_id: str, target: str, timeout_s: float) -> dict:
    if not OWNER_RE.fullmatch(owner_id):
        raise ValueError("Invalid GROOT owner id")
    result = subprocess.run(
        _ssh_base(host, tty=False)
        + ["python3 - " + shlex.quote(owner_id) + " "
           + shlex.quote(target) + " " + str(float(timeout_s))],
        input=REMOTE_SIGNAL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s + 10.0,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Cannot verify remote " + target + " shutdown: "
            + (result.stderr or result.stdout or "no response")) from error
    if result.returncode or payload.get("remaining"):
        raise RuntimeError(
            "Remote " + target + " did not finish its controlled shutdown: "
            + json.dumps(payload, sort_keys=True))
    return payload


def graceful_stop_owned(host: str, owner_id: str) -> None:
    actuator = _signal_owned(
        host, owner_id, "groot_balance_actuator", 12.0)
    if actuator.get("signalled"):
        print(
            "[GROOT STOP] actuator SIGINT sent; controlled damping completed.",
            flush=True,
        )
    heading = _signal_owned(
        host, owner_id, "g1_omni_heading_controller.py", 4.0)
    if heading.get("signalled"):
        print("[GROOT STOP] heading controller stopped.", flush=True)


def _install_stop_handlers(stopped: threading.Event):
    previous = {}

    def request_stop(signum, frame):
        del signum, frame
        stopped.set()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, request_stop)
    return previous


def _restore_stop_handlers(previous) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def run(
        host: str,
        *,
        confirmed: bool,
        owner_id: str | None = None,
) -> int:
    if not confirmed:
        raise RuntimeError(
            "GROOT actuation requires integrated-launch confirmation.")
    ensure_login(host)
    status = inspect_remote(host)
    unlimited = bool(status.get("supports_unlimited_duration"))
    selected_actuator = actuator_argv(unlimited)
    existing = classify_existing(
        list(status.get("processes") or []), selected_actuator)
    owner_id = owner_id or uuid.uuid4().hex
    if not OWNER_RE.fullmatch(owner_id):
        raise ValueError("Invalid GROOT owner id")

    print(
        "[GROOT DURATION] "
        + ("unlimited" if unlimited else
           "300 s fallback; onboard binary has no --unlimited-duration yet"),
        flush=True,
    )
    print(
        "[GROOT KEEP] " + (", ".join(sorted(existing)) or "none"),
        flush=True,
    )
    folder = ROOT / "logs/test_results/groot_remote" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(parents=True, exist_ok=False)
    children: dict[str, subprocess.Popen] = {}
    threads = []
    stopped = threading.Event()
    previous_handlers = _install_stop_handlers(stopped)
    runtime_failure = None

    def wait_for_stop():
        if not sys.stdin.isatty():
            return
        try:
            input(
                "GROOT active. Press Enter for controlled damping shutdown; "
                "do not close this window to stop normally. ")
        except (EOFError, KeyboardInterrupt):
            pass
        stopped.set()

    try:
        if "heading" not in existing:
            child, thread = _spawn(
                host, "heading", HEADING_ARGV, owner_id,
                folder / "heading.log")
            children["heading"] = child
            threads.append(thread)
            _require_still_running("heading controller", child)

        if "actuator" not in existing:
            child, thread = _spawn(
                host, "actuator", selected_actuator, owner_id,
                folder / "actuator.log")
            children["actuator"] = child
            threads.append(thread)
            _require_still_running("balance actuator", child)

        print(
            "[GROOT START] " + (", ".join(children)
                               or "none; exact remote processes already exist"),
            flush=True,
        )
        print("[GROOT LOGS] " + str(folder), flush=True)
        threading.Thread(target=wait_for_stop, daemon=True).start()
        while not stopped.wait(0.25):
            exited = [
                (name, child.returncode)
                for name, child in children.items()
                if child.poll() is not None
            ]
            if exited:
                runtime_failure = "Owned GROOT process ended: " + repr(exited)
                print("[GROOT EXIT] " + repr(exited), flush=True)
                break
    except KeyboardInterrupt:
        stopped.set()
    finally:
        stop_error = None
        try:
            graceful_stop_owned(host, owner_id)
        except Exception as error:
            stop_error = error
            print("[GROOT STOP FAILED] " + str(error), file=sys.stderr)
        for name, child in reversed(list(children.items())):
            if child.poll() is None and stop_error is None:
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=1)
        _restore_stop_handlers(previous_handlers)
        if stop_error is not None:
            raise RuntimeError(
                "Controlled GROOT shutdown did not complete; "
                "do not assume damping is active.") from stop_error

    if runtime_failure:
        raise RuntimeError(runtime_failure)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--owner-id")
    parser.add_argument("--check-command", action="store_true")
    args = parser.parse_args(argv)
    if args.check_command:
        print(shlex.join(HEADING_ARGV))
        print("300s:", shlex.join(actuator_argv(False)))
        print("unlimited:", shlex.join(actuator_argv(True)))
        return 0
    return run(
        args.host,
        confirmed=args.confirmed,
        owner_id=args.owner_id,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError, RuntimeError, ValueError,
        json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("[GROOT REMOTE FAILED] " + str(error), file=sys.stderr)
        raise SystemExit(1)
