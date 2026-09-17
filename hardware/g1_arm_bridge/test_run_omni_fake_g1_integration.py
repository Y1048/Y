"""End-to-end test for the one-click loopback-only fake G1 harness."""

import asyncio
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

import websockets


WS_PORT = 32126
DISCOVERY_PORT = 56118
VELOCITY_PORT = 56117


async def omni_handler(websocket):
    index = 0
    while True:
        sample = {
            "armYaw": 110.0 + min(index, 80) * 0.15,
            "movementXY": [0.35 if index > 40 else 0.0,
                           0.55 if index > 40 else 0.0],
        }
        try:
            await websocket.send(json.dumps(sample))
        except websockets.ConnectionClosed:
            return
        index += 1
        await asyncio.sleep(0.02)


async def serve(stop, ready):
    async with websockets.serve(omni_handler, "127.0.0.1", WS_PORT):
        ready.set()
        while not stop.is_set():
            await asyncio.sleep(0.02)


def main():
    root = Path(__file__).resolve().parents[2]
    stop = threading.Event()
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: asyncio.run(serve(stop, ready)), daemon=True)
    thread.start()
    if not ready.wait(3.0):
        raise RuntimeError("fake Omni WebSocket did not start")
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "capture.csv"
        command = [
            sys.executable, "-B",
            str(root / "hardware/g1_arm_bridge/run_omni_fake_g1_integration.py"),
            "--duration-seconds", "2.2",
            "--omni-url", f"ws://127.0.0.1:{WS_PORT}",
            "--discovery-port", str(DISCOVERY_PORT),
            "--velocity-port", str(VELOCITY_PORT),
            "--csv", str(output),
        ]
        result = subprocess.run(command, cwd=root, text=True,
                                capture_output=True, timeout=10.0)
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        if '"status": "PASS"' not in result.stdout:
            raise RuntimeError(result.stdout)
        if '"physical_g1_output": false' not in result.stdout:
            raise RuntimeError("missing physical-output assertion")
        with output.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) < 20:
            raise RuntimeError("capture CSV too short")
        required = {
            "mx", "my", "omni_yaw_rate_deg_s", "vx", "vy", "yaw_rate",
            "yaw_diff_deg", "raw_json_text",
        }
        if not required.issubset(rows[0]):
            raise RuntimeError("capture CSV is missing raw/mapped columns")
        if any(row["schema"] != "g1.omni.timeseries.v1" for row in rows):
            raise RuntimeError("capture CSV schema mismatch")
        sequences = [int(row["sample_sequence"]) for row in rows]
        if sequences != list(range(len(rows))):
            raise RuntimeError("capture CSV sequence mismatch")
        sample = rows[-1]
        raw = json.loads(sample["raw_json_text"])
        if float(sample["mx"]) != float(raw["movementXY"][0]):
            raise RuntimeError("raw mx was not preserved")
        if float(sample["my"]) != float(raw["movementXY"][1]):
            raise RuntimeError("raw my was not preserved")
        print(json.dumps({"status": "PASS", "csv_rows": len(rows),
                          "loopback_only": True}))
    stop.set()


if __name__ == "__main__":
    main()
