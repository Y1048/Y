#!/usr/bin/env python3
"""G1 하드웨어 bring-up 과정이 공유하는 실행 상태와 fault 문서 형식.

통신 방식과 독립적이며 Unitree SDK를 import하거나 DDS publisher를 만들지 않는다.
로봇을 제어할 수 없고, 각 하드웨어 프로세스의 단계와 fail-closed fault 상태를
일관된 JSON 형태로 기록하는 데만 사용한다.
"""

from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1


class HardwarePhase(str, Enum):
    OFFLINE = "OFFLINE"
    READ_ONLY_WAIT = "READ_ONLY_WAIT"
    READ_ONLY_ACTIVE = "READ_ONLY_ACTIVE"
    SYNCED = "SYNCED"
    HOLD_READY = "HOLD_READY"
    HOLD_ACTIVE = "HOLD_ACTIVE"
    TELEOP_READY = "TELEOP_READY"
    TELEOP_ACTIVE = "TELEOP_ACTIVE"
    FAULT = "FAULT"


class FaultCode(str, Enum):
    NONE = "NONE"
    LOWSTATE_TIMEOUT = "LOWSTATE_TIMEOUT"
    LOWSTATE_INVALID = "LOWSTATE_INVALID"
    SYNC_TIMEOUT = "SYNC_TIMEOUT"
    JOINT_LIMIT = "JOINT_LIMIT"
    TARGET_ERROR = "TARGET_ERROR"
    DDS_ERROR = "DDS_ERROR"
    COMMAND_STREAM_STALE = "COMMAND_STREAM_STALE"
    PRECHECK_REQUIRED = "PRECHECK_REQUIRED"
    MOTION_MODE_MISMATCH = "MOTION_MODE_MISMATCH"
    OUTPUT_NOT_AUTHORIZED = "OUTPUT_NOT_AUTHORIZED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def build_status(
    *,
    phase: HardwarePhase,
    component: str,
    command_output_enabled: bool,
    publisher_present: bool,
    fault_code: FaultCode = FaultCode.NONE,
    fault_message: str = "",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one fail-closed hardware runtime status document."""

    fault_active = fault_code is not FaultCode.NONE
    if phase is HardwarePhase.FAULT and not fault_active:
        raise ValueError("FAULT phase requires a non-NONE fault_code")
    if fault_active and phase is not HardwarePhase.FAULT:
        raise ValueError("non-NONE fault_code requires FAULT phase")
    if command_output_enabled and not publisher_present:
        raise ValueError("command output cannot be enabled without a publisher")

    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at_unix": time.time(),
        "component": str(component),
        "phase": phase.value,
        "command_output_enabled": bool(command_output_enabled),
        "publisher_present": bool(publisher_present),
        "fail_closed": True,
        "fault": {
            "active": fault_active,
            "code": fault_code.value,
            "message": str(fault_message),
        },
        "details": dict(details or {}),
    }


def write_status(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a runtime JSON status file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")
    temporary.replace(path)
