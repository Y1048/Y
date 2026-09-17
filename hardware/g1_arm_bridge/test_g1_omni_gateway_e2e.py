"""PC-only WebSocket -> discovery -> UDP integration test."""

import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import websockets


TOKEN = "e2eToken0123456789abcdef"
WS_PORT = 32124
DISCOVERY_PORT = 55118
VELOCITY_PORT = 55117


async def omni_handler(websocket):
    samples = []
    for index in range(8):
        samples.append({"armYaw": 110.0, "movementXY": [0.01, -0.02]})
    samples.extend([
        {"armYaw": 110.0, "movementXY": [0.01, 0.60]},
        {"armYaw": 112.0, "movementXY": [0.35, 0.60]},
        {"armYaw": 114.0, "movementXY": [0.35, 0.60]},
    ])
    for sample in samples:
        await websocket.send(json.dumps(sample))
        await asyncio.sleep(0.03)


async def serve(stop: threading.Event, ready: threading.Event):
    async with websockets.serve(omni_handler, "127.0.0.1", WS_PORT):
        ready.set()
        while not stop.is_set():
            await asyncio.sleep(0.02)


def discovery_sender(stop: threading.Event):
    packet = json.dumps({
        "schema": "g1.velocity.discovery.v1",
        "robot_id": "synthetic-g1",
        "velocity_port": VELOCITY_PORT,
        "sequence": 0,
        "relay_token": TOKEN,
    }).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop.is_set():
        sock.sendto(packet, ("127.0.0.1", DISCOVERY_PORT))
        time.sleep(0.03)
    sock.close()


def main():
    root = Path(__file__).resolve().parents[2]
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", VELOCITY_PORT))
    receiver.settimeout(3.0)
    stop = threading.Event()
    ready = threading.Event()
    ws_thread = threading.Thread(
        target=lambda: asyncio.run(serve(stop, ready)), daemon=True)
    ws_thread.start()
    if not ready.wait(3.0):
        raise RuntimeError("fake Omni WebSocket did not start")
    discovery_thread = threading.Thread(
        target=discovery_sender, args=(stop,), daemon=True)
    discovery_thread.start()
    command = [
        sys.executable, "-B",
        str(root / "hardware/g1_arm_bridge/g1_omni_velocity_gateway.py"),
        "--relay-token", TOKEN,
        "--omni-url", f"ws://127.0.0.1:{WS_PORT}",
        "--discovery-port", str(DISCOVERY_PORT),
        "--calibration-seconds", "0.15",
        "--max-samples", "11",
    ]
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    packets = []
    try:
        while process.poll() is None or len(packets) < 1:
            try:
                raw, _ = receiver.recvfrom(4096)
            except socket.timeout:
                break
            packets.append(json.loads(raw))
        output, _ = process.communicate(timeout=3.0)
        if process.returncode != 0:
            raise RuntimeError(output)
        if not packets:
            raise RuntimeError("no velocity packet received")
        if not all(packet.get("schema") == "g1.velocity.command.v1"
                   for packet in packets):
            raise RuntimeError("wrong command schema")
        if not any(packet["velocity"][0] > 0.1 for packet in packets):
            raise RuntimeError("forward movement was not mapped")
        if not any(packet["velocity"][1] < -0.1 for packet in packets):
            raise RuntimeError("lateral movement was not mapped")
        if not any(packet["velocity"][2] > 0.0 for packet in packets):
            raise RuntimeError("yaw delta was not mapped")
        if packets[-1]["velocity"] != [0.0, 0.0, 0.0]:
            raise RuntimeError("gateway exit did not send zero velocity")
        print(json.dumps({
            "status": "PASS",
            "packets": len(packets),
            "forward_seen": True,
            "lateral_seen": True,
            "yaw_seen": True,
            "final_zero": True,
        }))
    finally:
        stop.set()
        if process.poll() is None:
            process.terminate()
        receiver.close()


if __name__ == "__main__":
    main()
