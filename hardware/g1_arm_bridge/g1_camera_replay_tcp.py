#!/usr/bin/env python3
"""G1 없이 Unity 카메라 PiP를 검증하는 로컬 JPEG 재생기.

Unitree SDK와 DDS를 import하지 않는다. 움직이는 합성 JPEG를 실제 카메라와
동일한 G1CM/TCP 패킷으로 loopback에만 보내 Unity 표시 경로를 검증한다.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import signal
import socket
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from g1_camera_tcp_bridge import (
    BuildFramePacket,
    ConnectUnity,
    DEFAULT_HOST,
    DEFAULT_PORT,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIRECTORY = PROJECT_ROOT / "logs" / "camera"
DEFAULT_FPS = 20.0
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_QUALITY = 82


def LoadFont(size: int):
    """Windows와 테스트 환경 모두에서 사용할 수 있는 글꼴을 고른다."""
    candidates = (
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "DejaVuSansMono-Bold.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def BuildReplayJpeg(
    sequence: int,
    elapsed_s: float,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    quality: int = DEFAULT_QUALITY,
) -> bytes:
    """움직임과 출처가 명확한 합성 테스트 프레임을 JPEG로 만든다."""
    if width < 320 or height < 240:
        raise ValueError("replay frame must be at least 320x240")
    if not math.isfinite(elapsed_s) or elapsed_s < 0.0:
        raise ValueError("elapsed_s must be finite and non-negative")
    if quality < 40 or quality > 95:
        raise ValueError("JPEG quality must be between 40 and 95")

    image = Image.new("RGB", (width, height), (26, 31, 40))
    draw = ImageDraw.Draw(image)
    title_font = LoadFont(max(20, height // 16))
    status_font = LoadFont(max(15, height // 27))
    detail_font = LoadFont(max(13, height // 34))

    banner_height = max(58, height // 7)
    draw.rectangle((0, 0, width, banner_height), fill=(214, 77, 36))
    draw.text(
        (width // 2, banner_height // 2),
        "OFFLINE REPLAY - NOT LIVE G1 VIDEO",
        font=title_font,
        fill=(255, 255, 255),
        anchor="mm",
    )

    grid_top = banner_height
    grid_step = max(32, width // 12)
    for x_value in range(0, width, grid_step):
        draw.line((x_value, grid_top, x_value, height), fill=(58, 68, 82), width=1)
    for y_value in range(grid_top, height, grid_step):
        draw.line((0, y_value, width, y_value), fill=(58, 68, 82), width=1)

    center_x = width // 2
    center_y = (banner_height + height) // 2
    draw.line((center_x - 45, center_y, center_x + 45, center_y), fill=(245, 245, 245), width=3)
    draw.line((center_x, center_y - 45, center_x, center_y + 45), fill=(245, 245, 245), width=3)
    draw.ellipse(
        (center_x - 10, center_y - 10, center_x + 10, center_y + 10),
        outline=(245, 245, 245),
        width=3,
    )

    phase = elapsed_s * 1.4
    travel_x = max(70, width // 3)
    travel_y = max(45, height // 6)
    marker_x = center_x + int(math.sin(phase) * travel_x)
    marker_y = center_y + int(math.cos(phase * 0.73) * travel_y)
    marker_radius = max(16, width // 32)
    draw.ellipse(
        (
            marker_x - marker_radius,
            marker_y - marker_radius,
            marker_x + marker_radius,
            marker_y + marker_radius,
        ),
        fill=(39, 202, 157),
        outline=(255, 255, 255),
        width=3,
    )
    draw.line((center_x, center_y, marker_x, marker_y), fill=(255, 210, 64), width=3)

    status_top = height - max(88, height // 5)
    draw.rectangle((0, status_top, width, height), fill=(16, 20, 27))
    draw.rectangle((20, status_top + 18, 42, status_top + 40), fill=(39, 202, 157))
    draw.text(
        (54, status_top + 15),
        "SOURCE: SYNTHETIC / G1 DISCONNECTED",
        font=status_font,
        fill=(238, 242, 247),
    )
    draw.text(
        (20, status_top + 51),
        f"FRAME {sequence & 0xFFFFFFFF:010d}   ELAPSED {elapsed_s:8.2f} s   TCP 127.0.0.1:5011",
        font=detail_font,
        fill=(172, 187, 205),
    )

    buffer = io.BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=False,
        subsampling=0,
    )
    return buffer.getvalue()


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OFFLINE synthetic G1 camera replay to Unity",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY)
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="seconds to run; zero means until Ctrl+C",
    )
    parser.add_argument("--connect-timeout", type=float, default=1.0)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    return parser.parse_args()


def ValidateArguments(args: argparse.Namespace) -> None:
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("offline replay output is restricted to loopback")
    if args.port < 1 or args.port > 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.fps <= 0.0 or args.fps > 60.0:
        raise SystemExit("--fps must be > 0 and <= 60")
    if args.quality < 40 or args.quality > 95:
        raise SystemExit("--quality must be between 40 and 95")
    if args.duration < 0.0:
        raise SystemExit("--duration must be >= 0")
    if args.connect_timeout <= 0.0 or args.reconnect_delay <= 0.0:
        raise SystemExit("timeouts and reconnect delay must be > 0")


def WriteResult(result: dict[str, object], result_directory: Path = RESULT_DIRECTORY) -> Path:
    result_directory.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    result_path = result_directory / f"camera_offline_replay_{timestamp}.json"
    result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return result_path


def main() -> int:
    args = ParseArguments()
    ValidateArguments(args)
    stop_requested = False

    def RequestStop(_signal_number, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, RequestStop)
    signal.signal(signal.SIGTERM, RequestStop)

    print("G1 camera PiP -- OFFLINE REPLAY")
    print("--------------------------------")
    print(f"Unity TCP: {args.host}:{args.port}")
    print(f"Frame rate: {args.fps:.1f} Hz")
    print("Source: synthetic JPEG test pattern")
    print("Unitree SDK: NOT IMPORTED")
    print("DDS: NOT CREATED")
    print("Robot command: IMPOSSIBLE from this process")

    connection: socket.socket | None = None
    sequence = 0
    sent_frames = 0
    connection_errors = 0
    send_errors = 0
    start_wall_ns = time.time_ns()
    start_time = time.monotonic()
    next_frame_time = start_time
    next_status_time = start_time + 1.0

    try:
        while not stop_requested:
            current_time = time.monotonic()
            elapsed_s = current_time - start_time
            if args.duration > 0.0 and elapsed_s >= args.duration:
                break

            if connection is None:
                try:
                    connection = ConnectUnity(
                        args.host,
                        args.port,
                        args.connect_timeout,
                    )
                    print("[CONNECTED] Unity camera PiP listener is ready.")
                    next_frame_time = time.monotonic()
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

            jpeg_payload = BuildReplayJpeg(sequence, current_time - start_time)
            packet = BuildFramePacket(jpeg_payload, sequence, time.time_ns())
            try:
                connection.sendall(packet)
                sequence = (sequence + 1) & 0xFFFFFFFF
                sent_frames += 1
            except OSError as exc:
                send_errors += 1
                print(f"[RECONNECT] Unity replay stream interrupted: {exc}")
                try:
                    connection.close()
                except OSError:
                    pass
                connection = None
                continue

            if current_time >= next_status_time:
                print(
                    f"[STREAMING] frames={sent_frames} "
                    f"latest_jpeg={len(jpeg_payload)} bytes "
                    f"send_errors={send_errors}"
                )
                next_status_time = current_time + 1.0
    except KeyboardInterrupt:
        stop_requested = True
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    end_wall_ns = time.time_ns()
    result = {
        "schema": "g1.camera.offline_replay.result.v1",
        "passed": sent_frames > 0,
        "source": "synthetic_offline_replay",
        "robot_connected": False,
        "unitree_sdk_loaded": False,
        "dds_created": False,
        "command_output_enabled": False,
        "host": args.host,
        "port": args.port,
        "requested_fps": args.fps,
        "frames_sent": sent_frames,
        "connection_errors": connection_errors,
        "send_errors": send_errors,
        "started_time_ns": start_wall_ns,
        "finished_time_ns": end_wall_ns,
        "elapsed_s": (end_wall_ns - start_wall_ns) / 1_000_000_000.0,
    }
    result_path = WriteResult(result)
    print(f"[STOPPED] Forwarded {sent_frames} offline camera frames.")
    print(f"[RESULT] {result_path}")
    if sent_frames == 0:
        print("[ACTION] Start Unity Play mode, then run this replay again.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
