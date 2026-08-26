#!/usr/bin/env python3
"""Patch local G1ExistingHandTargetBinder.cs without overwriting user edits.

Only the engagement UI/alignment reference moves from wrist to palm center.
Wrist calibration, motion delta, UDP targets, and Mink robot control stay wrist-based.
The patch is fail-closed and writes a timestamped backup before modification.
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Unity_G1_VR" / "Assets" / "G1Teleop" / "G1ExistingHandTargetBinder.cs"
BACKUP_DIR = ROOT / "logs" / "runtime"

class PatchError(RuntimeError):
    pass

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise PatchError(f"{label}: source pattern not found")
    if text.count(old) != 1:
        raise PatchError(f"{label}: expected one source pattern, found {text.count(old)}")
    return text.replace(old, new, 1)

def replace_exact_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count == 0:
        if text.count(new) == expected:
            return text
        raise PatchError(f"{label}: source pattern not found")
    if count != expected:
        raise PatchError(f"{label}: expected {expected} source patterns, found {count}")
    return text.replace(old, new)

def apply_patch(text: str) -> str:
    text = replace_once(text,
        "    public bool use_palm_center = false;\n",
        "    public bool use_palm_center = false;\n    public bool use_palm_center_for_engagement = true;\n",
        "palm engage option")
    text = replace_once(text,
        "    public Vector3 TrackedHandPosition { get; private set; }\n",
        "    public Vector3 TrackedHandPosition { get; private set; }\n    public Vector3 EngagementTrackingPosition { get; private set; }\n",
        "engagement tracking property")
    text = replace_once(text,
        "    public Vector3 EngagementTargetPosition { get; private set; }\n",
        "    public Vector3 EngagementTargetPosition { get; private set; }\n    public Vector3 EngagementTargetAlignmentPosition { get; private set; }\n",
        "engagement target property")
    text = replace_once(text,
        "    private Quaternion engagement_target_local_rotation = Quaternion.identity;\n",
        "    private Quaternion engagement_target_local_rotation = Quaternion.identity;\n    private Vector3 engagement_palm_local_offset = Vector3.zero;\n",
        "palm offset state")
    text = replace_once(text,
        "        EngagementTargetRotation = OperatorHeading\n            * engagement_target_local_rotation;\n        target_transform.position = EngagementTargetPosition;\n",
        "        EngagementTargetRotation = OperatorHeading\n            * engagement_target_local_rotation;\n        UpdateEngagementTargetAlignmentPosition();\n        target_transform.position = EngagementTargetPosition;\n",
        "target palm update")
    text = replace_once(text,
        "        AlignmentPositionError = Vector3.Distance(\n            TrackedWristPosition,\n            EngagementTargetPosition);\n",
        "        AlignmentPositionError = Vector3.Distance(\n            EngagementTrackingPosition,\n            EngagementTargetAlignmentPosition);\n",
        "engagement distance")
    text = replace_exact_count(text,
        "                alignment_reference_position = TrackedWristPosition;\n",
        "                alignment_reference_position = EngagementTrackingPosition;\n",
        2,
        "stability references")
    text = replace_once(text,
        "            float position_change = Vector3.Distance(\n                alignment_reference_position,\n                TrackedWristPosition);\n",
        "            float position_change = Vector3.Distance(\n                alignment_reference_position,\n                EngagementTrackingPosition);\n",
        "stability motion")
    text = replace_once(text,
        "        TrackedHandPosition = GetPalmCenterPosition();\n",
        "        TrackedHandPosition = GetPalmCenterPosition();\n        UpdateEngagementPalmReference();\n",
        "palm reference refresh")

    methods = '''    private void UpdateEngagementPalmReference()\n    {\n        EngagementTrackingPosition = TrackedWristPosition;\n        engagement_palm_local_offset = Vector3.zero;\n\n        if (use_palm_center_for_engagement)\n        {\n            ResolveAnatomicalHandTransforms();\n            if (middle_finger_base_transform != null)\n            {\n                EngagementTrackingPosition = Vector3.Lerp(\n                    TrackedWristPosition,\n                    middle_finger_base_transform.position,\n                    0.50f);\n                engagement_palm_local_offset = Quaternion.Inverse(TrackedWristRotation)\n                    * (EngagementTrackingPosition - TrackedWristPosition);\n            }\n        }\n\n        UpdateEngagementTargetAlignmentPosition();\n    }\n\n    private void UpdateEngagementTargetAlignmentPosition()\n    {\n        EngagementTargetAlignmentPosition = EngagementTargetPosition\n            + EngagementTargetRotation * engagement_palm_local_offset;\n    }\n\n'''
    anchor = "    private Vector3 GetPalmCenterPosition()\n"
    if methods not in text:
        if text.count(anchor) != 1:
            raise PatchError("could not locate GetPalmCenterPosition insertion point")
        text = text.replace(anchor, methods + anchor, 1)
    return text

def validate(text: str) -> None:
    required = [
        "use_palm_center_for_engagement = true",
        "EngagementTrackingPosition",
        "EngagementTargetAlignmentPosition",
        "UpdateEngagementPalmReference();",
        "Vector3 hand_delta = TrackedWristPosition - neutral_wrist_position;",
    ]
    missing = [x for x in required if x not in text]
    if missing:
        raise PatchError("validation failed: " + ", ".join(missing))
    if text.count("alignment_reference_position = EngagementTrackingPosition;") != 2:
        raise PatchError("validation failed: both stability references were not patched")
    if "AlignmentPositionError = Vector3.Distance(\n            EngagementTrackingPosition,\n            EngagementTargetAlignmentPosition);" not in text:
        raise PatchError("validation failed: engagement distance is not palm-centered")

def main() -> int:
    if not SOURCE.exists():
        print(f"[FAIL] Missing source: {SOURCE}")
        return 2
    original = SOURCE.read_text(encoding="utf-8")
    try:
        patched = apply_patch(original)
        validate(patched)
    except PatchError as exc:
        print(f"[FAIL] {exc}")
        print("[SAFE] Source was not modified.")
        return 3
    if patched == original:
        print("[PASS] Palm-center engagement patch already applied.")
        return 0
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"G1ExistingHandTargetBinder.before_palm_engage_{stamp}.cs"
    backup.write_text(original, encoding="utf-8")
    SOURCE.write_text(patched, encoding="utf-8")
    print("[PASS] Palm-center engagement patch applied.")
    print(f"[BACKUP] {backup.relative_to(ROOT)}")
    print("[CHANGED] Engage position + hold-still use palm center.")
    print("[UNCHANGED] Mink/control translation remains wrist-based.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
