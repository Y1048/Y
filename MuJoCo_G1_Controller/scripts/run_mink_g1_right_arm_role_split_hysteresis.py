"""Role-split Mink controller with wrist-limit hysteresis.

Normal operation keeps proximal orientation assistance at exactly zero so wrist
rotation does not make shoulder/elbow twitch. Proximal assistance is enabled
only when a wrist joint is genuinely close to its mechanical limit, and remains
latched until the wrist has recovered enough margin. The trigger depends only on
joint-limit margin; there is no hand-speed classification and no hard freeze.
"""

from __future__ import annotations

import math

import run_mink_g1_right_arm_role_split as role_split


# Normal wrist rotation: no shoulder/elbow help at all.
role_split.PROXIMAL_ORIENTATION_ASSIST_MIN = 0.0
role_split.PROXIMAL_ORIENTATION_ASSIST_MAX = 0.14

# Enter assist only very near a wrist limit. Keep it latched until the wrist has
# recovered substantially farther from the limit to avoid assist on/off chatter.
ASSIST_ENTER_MARGIN_DEG = 10.0
ASSIST_RELEASE_MARGIN_DEG = 18.0
ASSIST_FULL_MARGIN_DEG = 3.0
ASSIST_LATCH_FLOOR = 0.03

# Keep exported status/console thresholds meaningful for this variant.
role_split.WRIST_LIMIT_ASSIST_START_DEG = ASSIST_ENTER_MARGIN_DEG
role_split.WRIST_LIMIT_ASSIST_FULL_DEG = ASSIST_FULL_MARGIN_DEG

raw_write_status = role_split._original_write_status


class HysteresisState:
    assist_latched = False


def _hysteretic_proximal_orientation_assist(self, configuration) -> float:
    self._resolve_dofs(configuration)
    model = configuration.model
    q = configuration.q
    margins: list[float] = []

    for joint_id in self._wrist_joint_ids:
        if not bool(model.jnt_limited[joint_id]):
            continue
        qpos_adr = int(model.jnt_qposadr[joint_id])
        low, high = model.jnt_range[joint_id]
        value = float(q[qpos_adr])
        margin_rad = max(
            0.0,
            min(value - float(low), float(high) - value),
        )
        margins.append(math.degrees(margin_rad))

    if not margins:
        min_margin = float("inf")
        HysteresisState.assist_latched = False
    else:
        min_margin = min(margins)
        if HysteresisState.assist_latched:
            if min_margin >= ASSIST_RELEASE_MARGIN_DEG:
                HysteresisState.assist_latched = False
        elif min_margin <= ASSIST_ENTER_MARGIN_DEG:
            HysteresisState.assist_latched = True

    if not HysteresisState.assist_latched:
        assist = 0.0
    elif min_margin <= ASSIST_FULL_MARGIN_DEG:
        assist = role_split.PROXIMAL_ORIENTATION_ASSIST_MAX
    elif min_margin >= ASSIST_ENTER_MARGIN_DEG:
        # While recovering inside the hysteresis band, keep a small stable assist
        # instead of dropping immediately back to zero and being pulled by posture.
        assist = ASSIST_LATCH_FLOOR
    else:
        span = ASSIST_ENTER_MARGIN_DEG - ASSIST_FULL_MARGIN_DEG
        fraction = (ASSIST_ENTER_MARGIN_DEG - min_margin) / span
        smooth = fraction * fraction * (3.0 - 2.0 * fraction)
        assist = ASSIST_LATCH_FLOOR + smooth * (
            role_split.PROXIMAL_ORIENTATION_ASSIST_MAX
            - ASSIST_LATCH_FLOOR
        )

    role_split.RoleSplitFrameTask.last_min_wrist_limit_margin_deg = min_margin
    role_split.RoleSplitFrameTask.last_proximal_orientation_assist = float(assist)
    return float(assist)


def _write_status_with_hysteresis(payload: dict) -> None:
    payload["wrist_limit_assist_policy"] = "hysteresis"
    payload["wrist_limit_assist_latched"] = HysteresisState.assist_latched
    payload["wrist_limit_assist_enter_deg"] = ASSIST_ENTER_MARGIN_DEG
    payload["wrist_limit_assist_release_deg"] = ASSIST_RELEASE_MARGIN_DEG
    payload["wrist_limit_assist_full_deg"] = ASSIST_FULL_MARGIN_DEG
    payload["wrist_limit_assist_latch_floor"] = ASSIST_LATCH_FLOOR
    raw_write_status(payload)


def main() -> None:
    role_split.RoleSplitFrameTask._proximal_orientation_assist = (
        _hysteretic_proximal_orientation_assist
    )
    # role_split._write_role_split_status ultimately calls this module global.
    role_split._original_write_status = _write_status_with_hysteresis

    print("============================================================")
    print("G1 Mink ROLE-SPLIT + WRIST-LIMIT HYSTERESIS")
    print("Normal proximal orientation assist : 0%")
    print(
        "Assist latch                         : enter <= "
        f"{ASSIST_ENTER_MARGIN_DEG:.0f} deg, release >= "
        f"{ASSIST_RELEASE_MARGIN_DEG:.0f} deg"
    )
    print(
        "Near-limit assist                    : "
        f"{ASSIST_LATCH_FLOOR*100:.0f}% -> "
        f"{role_split.PROXIMAL_ORIENTATION_ASSIST_MAX*100:.0f}%"
    )
    print("Speed modes                          : NONE")
    print("Hard freeze                          : NONE")
    print("============================================================")
    role_split.main()


if __name__ == "__main__":
    main()
