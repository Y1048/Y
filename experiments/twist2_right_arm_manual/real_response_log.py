"""Versioned, command-incapable real-response trace writer and parser.

This module deliberately has no Unitree SDK, DDS, socket, subprocess, or gain
mutation imports.  A controller may hand already-observed records to
AsyncResponseLog; this module can only validate and write them to a local file.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import queue
import threading
from typing import Iterable

SCHEMA = "g1.real-response.v1"
JOINT_INDICES = tuple(range(22, 29))
JOINT_NAMES = (
    "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw",
    "right_elbow", "right_wrist_roll", "right_wrist_pitch", "right_wrist_yaw",
)
VECTOR_FIELDS = ("target_q_rad", "command_q_rad", "command_dq_rad_s", "kp_nm_rad",
                 "kd_nm_s_rad", "tau_ff_nm", "measured_q_rad", "measured_dq_rad_s")


def _strict_loads(text: str) -> dict:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate_json_key")
            out[key] = value
        return out
    def bad_constant(_):
        raise ValueError("nonfinite_json")
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=bad_constant)
    if not isinstance(value, dict):
        raise ValueError("record_root_must_be_object")
    return value


def _finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_record(record: dict) -> dict:
    required = {
        "schema", "session_id", "sequence", "state", "source_provenance",
        "target_monotonic_ns", "command_monotonic_ns", "lowstate_monotonic_ns",
        *VECTOR_FIELDS,
    }
    if set(record) - (required | {"measured_tau_nm", "imu", "motor"}):
        raise ValueError("unknown_field")
    if not required.issubset(record):
        raise ValueError("missing_field")
    if record["schema"] != SCHEMA:
        raise ValueError("unexpected_schema")
    if not isinstance(record["session_id"], str) or not record["session_id"] or len(record["session_id"]) > 128:
        raise ValueError("invalid_session_id")
    if type(record["sequence"]) is not int or record["sequence"] < 0:
        raise ValueError("invalid_sequence")
    if record["state"] not in ("idle", "initializing", "active", "return", "hold", "fault"):
        raise ValueError("invalid_state")
    provenance = record["source_provenance"]
    if not isinstance(provenance, dict) or not isinstance(provenance.get("controller_commit"), str) or not provenance["controller_commit"]:
        raise ValueError("invalid_source_provenance")
    for key in ("target_monotonic_ns", "command_monotonic_ns", "lowstate_monotonic_ns"):
        if type(record[key]) is not int or record[key] < 0:
            raise ValueError("invalid_monotonic_timestamp")
    if not record["target_monotonic_ns"] <= record["command_monotonic_ns"]:
        raise ValueError("target_after_command")
    for key in VECTOR_FIELDS:
        value = record[key]
        if not isinstance(value, list) or len(value) != 7 or not all(_finite_number(x) for x in value):
            raise ValueError(f"invalid_{key}")
    if "measured_tau_nm" in record:
        value = record["measured_tau_nm"]
        if value is not None and (not isinstance(value, list) or len(value) != 7 or not all(_finite_number(x) for x in value)):
            raise ValueError("invalid_measured_tau_nm")
    return record


@dataclass(frozen=True)
class Trace:
    records: tuple[dict, ...]
    sha256: str
    dropped_sequences: int


def parse_trace(path: Path | str) -> Trace:
    raw = Path(path).read_bytes()
    records = tuple(validate_record(_strict_loads(line)) for line in raw.decode("utf-8").splitlines() if line.strip())
    if not records:
        raise ValueError("empty_trace")
    dropped = 0
    previous = None
    previous_clocks = None
    session = records[0]["session_id"]
    for record in records:
        if record["session_id"] != session:
            raise ValueError("mixed_session")
        clocks = tuple(record[k] for k in ("target_monotonic_ns", "command_monotonic_ns", "lowstate_monotonic_ns"))
        if previous_clocks is not None and any(a > b for a, b in zip(previous_clocks, clocks)):
            raise ValueError("nonmonotonic_clock")
        if previous is not None:
            if record["sequence"] <= previous:
                raise ValueError("nonmonotonic_sequence")
            dropped += record["sequence"] - previous - 1
        previous, previous_clocks = record["sequence"], clocks
    return Trace(records, hashlib.sha256(raw).hexdigest(), dropped)


class AsyncResponseLog:
    """Bounded asynchronous JSONL sink. Queue overflow is explicit and fatal."""
    def __init__(self, path: Path | str, capacity: int = 4096):
        if capacity < 1:
            raise ValueError("invalid_capacity")
        self.path = Path(path)
        self._queue: queue.Queue = queue.Queue(capacity)
        self._error = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="real-response-log", daemon=False)
        self._thread.start()

    def append(self, record: dict) -> None:
        if self._closed:
            raise RuntimeError("logger_closed")
        validate_record(record)
        if self._error:
            raise RuntimeError("logger_failed") from self._error
        try:
            self._queue.put_nowait(json.dumps(record, separators=(",", ":"), allow_nan=False))
        except queue.Full as exc:
            raise RuntimeError("logger_queue_overflow") from exc

    def _run(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("x", encoding="utf-8", newline="\n") as stream:
                while True:
                    item = self._queue.get()
                    if item is None:
                        break
                    stream.write(item + "\n")
                stream.flush()
        except BaseException as exc:
            self._error = exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put(None)
        self._thread.join()
        if self._error:
            raise RuntimeError("logger_failed") from self._error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
