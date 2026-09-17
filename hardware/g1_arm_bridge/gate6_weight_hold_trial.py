#!/usr/bin/env python3
"""One explicitly confirmed HOLD; no automatic escalation or G1 file writes."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from gate6_arm_sdk_hold import load_runtime_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WSL_ROOT = "/mnt/c/Users/user/Desktop/G1_Teleop_Project"
WEIGHTS = {"1": 0.6, "2": 0.8, "3": 1.0}


def BuildTrialConfig(source, weight):
    if weight not in WEIGHTS.values():
        raise ValueError("only 0.6, 0.8 and 1.0 are supported")
    if source.get("hardware_output_authorized") is not False:
        raise ValueError("base HOLD configuration must remain locked")
    expected = {"ramp_up_s": 3.0, "hold_s": 3.0, "ramp_down_s": 3.0,
                "publish_hz": 250.0, "release_zero_cycles": 25,
                "proximal_kp": 80.0, "proximal_kd": 3.0,
                "wrist_kp": 40.0, "wrist_kd": 1.5}
    for key, value in expected.items():
        if source.get(key) != value:
            raise ValueError(f"review changed HOLD setting before trial: {key}")
    config = dict(source)
    config["maximum_weight"] = weight
    return config


def LocalToWSL(path):
    return WSL_ROOT + "/" + path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def RunChecked(args, log_path):
    with log_path.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(args, cwd=PROJECT_ROOT, stdout=stream,
                                   stderr=subprocess.STDOUT)
        try:
            returncode = process.wait()
        except KeyboardInterrupt:
            print("[STOP] Keep L2+B ready. Waiting for the child release path; not killing it.", flush=True)
            process.wait(timeout=30)
            raise
    print(log_path.read_text(encoding="utf-8", errors="replace"), flush=True)
    if returncode != 0:
        raise RuntimeError(f"exit {returncode}; inspect {log_path}")


def RunTrial(weight, confirmation):
    base_path = PROJECT_ROOT / "config/g1_gate6_hold.json"
    load_runtime_config(base_path)
    config = BuildTrialConfig(json.loads(base_path.read_text(encoding="utf-8")), weight)
    if confirmation != "Y":
        print("[CANCELLED] No WSL, publisher or robot command started.")
        return 0
    token = uuid.uuid4().hex
    directory = PROJECT_ROOT / "logs/physical_tests" / (
        datetime.now().strftime("gate6_hold_%Y%m%d_%H%M%S_") + token[:8])
    directory.mkdir(parents=True, exist_ok=False)
    config_path = directory / "config.json"
    mode_path = directory / "mode.json"
    precheck_path = directory / "precheck.json"
    status_path = directory / "status.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Result folder: {directory}", flush=True)
    forwarder = None
    forward_log = None
    try:
        # The physical operator must also exclude publishers on other computers.
        processes = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--", "ps", "-eo", "pid,args"], text=True)
        names = ("gate6_arm_sdk_hold", "gate7_live_arm_sdk", "g1_right_arm_jog",
                 "g1_right_elbow_jog", "twist2", "lowcmd")
        if any(name in processes for name in names):
            raise RuntimeError("possible competing WSL controller; close it and inspect before retry")
        windows = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | Select-Object -ExpandProperty CommandLine"],
            text=True)
        if any(name in windows for name in names):
            raise RuntimeError("possible competing Windows controller; close it before retry")
        scripts = WSL_ROOT + "/hardware/g1_arm_bridge/"
        forward_log = (directory / "forwarder.log").open("w", encoding="utf-8")
        forwarder = subprocess.Popen(
            ["wsl", "-d", "Ubuntu", "--", "timeout", "--signal=TERM", "15s",
             "bash", scripts + "start_read_only_wsl.sh", "--timeout", "0.25",
             "--print-hz", "0.1", "--forward-host", "127.0.0.1", "--forward-port",
             "5007", "--forward-hz", "100", "--forward-token", token],
            cwd=PROJECT_ROOT, stdout=forward_log, stderr=subprocess.STDOUT)
        time.sleep(1.0)
        RunChecked(["wsl", "-d", "Ubuntu", "--", "bash",
                    scripts + "query_motion_mode_wsl.sh", "--output", LocalToWSL(mode_path)],
                   directory / "mode.log")
        RunChecked([sys.executable, "-B", str(PROJECT_ROOT / "hardware/g1_arm_bridge/check_startup_readiness_entry.py"),
                    "--host", "0.0.0.0", "--port", "5007", "--motion-mode-json", str(mode_path),
                    "--output", str(precheck_path), "--expected-forward-token", token],
                   directory / "precheck.log")
        # Finish our bounded read-only process before creating the physical publisher.
        forwarder.wait(timeout=25)
        print(f"[PHYSICAL START] weight={weight:.1f}; fixed arms; 3+3+3 seconds. L2+B ready.", flush=True)
        config["hardware_output_authorized"] = True
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        RunChecked(["wsl", "-d", "Ubuntu", "--", "bash", scripts + "start_gate6_hold_wsl.sh",
                    "--config", LocalToWSL(config_path), "--precheck-json", LocalToWSL(precheck_path),
                    "--status-json", LocalToWSL(status_path),
                    "--event-log", LocalToWSL(directory / "events.jsonl"),
                    "--enable-hardware-output", "--confirm", config["hardware_confirmation_phrase"],
                    "--confirm-grounded-regular", config["grounded_regular_confirmation_phrase"]],
                   directory / "hold.log")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        details = status["details"]
        if (status["command_output_enabled"] or status["fault"]["active"]
                or not details.get("zero_release_completed")
                or details.get("release_zero_frames_sent") != 25):
            raise RuntimeError("release evidence incomplete; use remote stop if needed")
        print("[DONE] Software release complete. Inspect motion/sound and logs before next trial.")
        return 0
    finally:
        config["hardware_output_authorized"] = False
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"[LOCKED] Result folder: {directory}", flush=True)
        if forwarder is not None and forwarder.poll() is None:
            forwarder.wait(timeout=25)
        if forward_log is not None:
            forward_log.close()


def main():
    print("1: 0.6 / 2: 0.8 / 3: 1.0 / other: cancel")
    selection = input("Select one reviewed step: ").strip()
    if selection not in WEIGHTS:
        return 0
    weight = WEIGHTS[selection]
    print(f"Authorize ONE physical fixed-pose HOLD at weight {weight:.1f}.")
    print("Grounded Regular; area clear; L2+B ready; no other arm/waist publisher.")
    print("Proceed only after the previous step's logs and observed motion were reviewed.")
    confirmation = input("All conditions met and authorize this trial? [Y/N]: ").strip().upper()
    try:
        return RunTrial(weight, confirmation)
    except Exception as exc:
        print(f"[FAILED] {exc}")
        print("[ACTION] Do not repeat after abnormal motion. Keep the remote ready; inspect logs.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
