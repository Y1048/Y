"""Unitree simulator-compatible shared-memory image transport."""

from __future__ import annotations

import ctypes
import time
from multiprocessing import shared_memory
import numpy as np

from .camera import CameraFrame


SHM_SIZE_PER_IMAGE = 640 * 480 * 3 + 128


def shared_memory_name(image_name: str) -> str:
    if not image_name or len(image_name.encode("ascii")) > 15:
        raise ValueError("image_name must be non-empty ASCII with at most 15 bytes")
    return f"isaac_{image_name}_image_shm"


class UnitreeImageHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("timestamp", ctypes.c_uint64),
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("channels", ctypes.c_uint32),
        ("image_name", ctypes.c_char * 16),
        ("data_size", ctypes.c_uint32),
        ("encoding", ctypes.c_uint32),
        ("quality", ctypes.c_uint32),
    ]


class UnitreeSimImageWriter:
    """Feed MuJoCo images to TeleImager's existing simulator camera adapter."""

    def __init__(self) -> None:
        self._memories: dict[str, shared_memory.SharedMemory] = {}
        self._last_timestamp_ms = 0

    def _memory(self, image_name: str) -> shared_memory.SharedMemory:
        name = shared_memory_name(image_name)
        if name in self._memories:
            return self._memories[name]
        try:
            memory = shared_memory.SharedMemory(name=name)
        except FileNotFoundError:
            memory = shared_memory.SharedMemory(name=name, create=True, size=SHM_SIZE_PER_IMAGE)
        self._memories[name] = memory
        return memory

    def write_frame(self, frame: CameraFrame, image_name: str = "head") -> int:
        return self.write_bgr(image_name, frame.color_bgr)

    def write_bgr(self, image_name: str, image_bgr: np.ndarray) -> int:
        image = np.asarray(image_bgr)
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image_bgr must be a uint8 HxWx3 array")
        image = np.ascontiguousarray(image)
        height, width, channels = image.shape
        payload = image.tobytes()
        header_size = ctypes.sizeof(UnitreeImageHeader)
        memory = self._memory(image_name)
        if header_size + len(payload) > memory.size:
            raise ValueError("image does not fit Unitree simulator shared memory")

        timestamp_ms = max(time.time_ns() // 1_000_000, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        header = UnitreeImageHeader(
            timestamp=timestamp_ms,
            height=height,
            width=width,
            channels=channels,
            image_name=image_name.encode("ascii"),
            data_size=len(payload),
            encoding=0,
            quality=0,
        )

        # A zero timestamp keeps readers on the previous frame until the new payload is complete.
        pending = UnitreeImageHeader(
            timestamp=0,
            height=height,
            width=width,
            channels=channels,
            image_name=image_name.encode("ascii"),
            data_size=len(payload),
            encoding=0,
            quality=0,
        )
        memory.buf[:header_size] = ctypes.string_at(ctypes.byref(pending), header_size)
        memory.buf[header_size : header_size + len(payload)] = payload
        memory.buf[:header_size] = ctypes.string_at(ctypes.byref(header), header_size)
        return timestamp_ms

    def close(self, unlink: bool = False) -> None:
        for memory in self._memories.values():
            memory.close()
            if unlink:
                try:
                    memory.unlink()
                except FileNotFoundError:
                    pass
        self._memories.clear()

    def __enter__(self) -> "UnitreeSimImageWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
