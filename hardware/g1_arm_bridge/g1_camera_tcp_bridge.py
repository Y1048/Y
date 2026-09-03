#!/usr/bin/env python3
"""G1 front-camera JPEG reader and local Unity TCP forwarder.

Safety contract:
- Uses Unitree SDK2 VideoClient.GetImageSample only.
- Sends no motor, mode, camera-setting, or motion command.
- Forwards JPEG bytes only to a loopback TCP listener owned by Unity.
"""

from __future__ import annotations

import argparse
import signal
import socket
import struct
import sys
import time
from typing import Final


FRAME_MAGIC: Final[bytes] = b"G1CM"
FRAME_VERSION: Final[int] = 1
FRAME_HEADER: Final[struct.Struct] = struct.Struct("!4sIIQI")
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 5011
DEFAULT_FPS: Final[float] = 20.0
MAX_JPEG_BYTES: Final[int] = 4 * 1024 * 1024


def BuildFramePacket(
    jpeg_payload: bytes,
    sequence: int,
    timestamp_ns: int,
) -> bytes:
    payload = bytes(jpeg_payload)
    if len(payload) < 4 or len(payload) > MAX_JPEG_BYTES:
        raise ValueError("JPEG payload size is outside the accepted range")
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise ValueError("camera payload is not a complete JPEG image")
    if timestamp_ns < 0:
        raise ValueError("timestamp_ns must be non-negative")

    header = FRAME_HEADER.pack(
        FRAME_MAGIC,
        FRAME_VERSION,
        sequence & 0xFFFFFFFF,
        timestamp_ns,
        len(payload),
    )
    return header + payload


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 camera JPEG bridge to Unity",
    )
    parser.add_argument("network_interface")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--camera-timeout", type=float, default=3.0)
    parser.add_argument("--connect-timeout", type=float, default=1.0)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    return parser.parse_args()


def CreateVideoClient(network_interface: str, timeout_s: float):
    try:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.go2.video.video_client import VideoClient
    except ImportError as exc:
        raise SystemExit(
            "unitree_sdk2py VideoClient is unavailable in this WSL environment"
        ) from exc

    ChannelFactoryInitialize(0, network_interface)
    client = VideoClient()
    client.SetTimeout(timeout_s)
    client.Init()
    return client


def ConnectUnity(host: str, port: int, timeout_s: float) -> socket.socket:
    connection = socket.create_connection((host, port), timeout=timeout_s)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    connection.settimeout(max(1.0, timeout_s))
    return connection


def ValidateArguments(args: argparse.Namespace) -> None:
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("camera bridge output is restricted to loopback")
    if args.port < 1 or args.port > 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.fps <= 0.0 or args.fps > 60.0:
        raise SystemExit("--fps must be > 0 and <= 60")
    if args.camera_timeout <= 0.0 or args.connect_timeout <= 0.0:
        raise SystemExit("timeouts must be > 0")
    if args.reconnect_delay <= 0.0:
        raise SystemExit("--reconnect-delay must be > 0")


def main() -> int:
    args = ParseArguments()
    ValidateArguments(args)
    stop_requested = False

    def RequestStop(_signal_number, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, RequestStop)
    signal.signal(signal.SIGTERM, RequestStop)

    print("G1 front-camera bridge -- READ ONLY")
    print("-----------------------------------")
    print(f"G1 interface: {args.network_interface}")
    print(f"Unity TCP:    {args.host}:{args.port}")
    print(f"Frame rate:   {args.fps:.1f} Hz")
    print("Camera API:   VideoClient.GetImageSample")
    print("Robot command: IMPOSSIBLE from this process")

    video_client = CreateVideoClient(
        args.network_interface,
        args.camera_timeout,
    )
    unity_connection: socket.socket | None = None
    sequence = 0
    sent_frames = 0
    camera_errors = 0
    connection_errors = 0
    next_frame_time = time.monotonic()
    next_status_time = next_frame_time + 1.0

    try:
        while not stop_requested:
            if unity_connection is None:
                try:
                    unity_connection = ConnectUnity(
                        args.host,
                        args.port,
                        args.connect_timeout,
                    )
                    print("[CONNECTED] Unity camera PiP listener is ready.")
                except OSError:
                    connection_errors += 1
                    if connection_errors == 1 or connection_errors % 10 == 0:
                        print(
                            "[WAITING] Unity is not listening on TCP "
                            f"{args.port}; enter Play mode."
                        )
                    time.sleep(args.reconnect_delay)
                    continue

            current_time = time.monotonic()
            if current_time < next_frame_time:
                time.sleep(min(next_frame_time - current_time, 0.01))
                continue
            frame_period = 1.0 / args.fps
            next_frame_time = max(next_frame_time + frame_period, current_time)

            code, camera_data = video_client.GetImageSample()
            if code != 0 or not camera_data:
                camera_errors += 1
                if camera_errors == 1 or camera_errors % 30 == 0:
                    print(f"[WARNING] G1 camera read failed with code {code}.")
                continue

            try:
                packet = BuildFramePacket(
                    bytes(camera_data),
                    sequence,
                    time.time_ns(),
                )
                unity_connection.sendall(packet)
                sequence = (sequence + 1) & 0xFFFFFFFF
                sent_frames += 1
            except (OSError, ValueError) as exc:
                print(f"[RECONNECT] Unity camera stream interrupted: {exc}")
                try:
                    unity_connection.close()
                except OSError:
                    pass
                unity_connection = None
                continue

            if current_time >= next_status_time:
                print(
                    f"[STREAMING] frames={sent_frames} "
                    f"latest_jpeg={len(camera_data)} bytes "
                    f"camera_errors={camera_errors}"
                )
                next_status_time = current_time + 1.0
    finally:
        if unity_connection is not None:
            try:
                unity_connection.close()
            except OSError:
                pass

    print(f"[STOPPED] Forwarded {sent_frames} read-only camera frames.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
