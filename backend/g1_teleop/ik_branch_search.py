"""Additional multi-seed branches for difficult right-arm targets."""

from __future__ import annotations

from types import ModuleType

import numpy as np


def install_expanded_multiseed_branches(ik_fallback_module: ModuleType) -> None:
    """Add shoulder-pitch/roll branches to the existing fallback seed set.

    The default fallback already explores shoulder yaw, elbow flexion and a
    ready-pose seed. Targets near the front of the torso can require a different
    shoulder pitch/roll branch with the elbow lifted. These extra seeds make that
    branch reachable without forcing a particular elbow position in normal IK.
    """

    if getattr(ik_fallback_module, "_EXPANDED_MULTI_SEED_BRANCHES_INSTALLED", False):
        return

    original_seed_candidates = ik_fallback_module._seed_candidates

    def expanded_seed_candidates(base, start_q, settings):
        seeds = list(original_seed_candidates(base, start_q, settings))
        if len(start_q) < 4:
            return seeds

        shoulder_offset = float(settings.multiseed.shoulder_yaw_offset_rad)
        existing = {name for name, _ in seeds}
        extra = (
            ("shoulder_pitch_plus", 0, shoulder_offset),
            ("shoulder_pitch_minus", 0, -shoulder_offset),
            ("shoulder_roll_plus", 1, shoulder_offset),
            ("shoulder_roll_minus", 1, -shoulder_offset),
        )
        for name, index, offset in extra:
            if name in existing:
                continue
            seed = np.asarray(start_q, dtype=float).copy()
            seed[index] += offset
            seeds.append((name, seed))
        return seeds

    ik_fallback_module._seed_candidates = expanded_seed_candidates
    ik_fallback_module._EXPANDED_MULTI_SEED_BRANCHES_INSTALLED = True


def install_position_only_candidate_scoring(ik_fallback_module: ModuleType) -> None:
    """Score whole-arm fallback branches by Cartesian position, not wrist rotation.

    In the configured teleoperation stack the shoulder/elbow joints own wrist
    position while hand orientation is repaired afterwards by a dedicated
    wrist-only DLS overlay. Keeping rotation error in the coupled/multiseed score
    can therefore choose a worse arm branch merely because that branch happens to
    reduce wrist rotation before the wrist overlay runs.

    Preserve the existing joint-motion and joint-margin regularizers, but remove
    rotation from both the normalized pose score and multiseed candidate score.
    """

    if getattr(ik_fallback_module, "_POSITION_ONLY_CANDIDATE_SCORING_INSTALLED", False):
        return

    original_candidate_score = ik_fallback_module._candidate_score

    def position_only_normalized_score(settings, position_error_m, rotation_error_rad):
        del rotation_error_rad
        return float(position_error_m) / float(settings.position_error_exit_m)

    def position_only_candidate_score(
        settings,
        model,
        base,
        start_q,
        candidate_q,
        position_error_m,
        rotation_error_rad,
    ):
        del rotation_error_rad
        # Reuse the module helpers for the regularization terms so behavior stays
        # identical apart from removing wrist orientation from arm-branch choice.
        pose = float(position_error_m) / float(settings.position_error_exit_m)
        motion = float(np.linalg.norm(np.asarray(candidate_q) - np.asarray(start_q)))
        margin = ik_fallback_module._joint_limit_margin(model, base, candidate_q)
        return (
            pose
            + settings.multiseed.joint_motion_weight * motion
            + settings.multiseed.joint_margin_weight * (1.0 - margin)
        )

    ik_fallback_module._normalized_score = position_only_normalized_score
    ik_fallback_module._candidate_score = position_only_candidate_score
    ik_fallback_module._POSITION_ONLY_CANDIDATE_SCORING_INSTALLED = True
    ik_fallback_module._ORIGINAL_CANDIDATE_SCORE = original_candidate_score
