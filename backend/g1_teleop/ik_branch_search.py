"""Additional multi-seed branches and lightweight search policy for right-arm IK."""

from __future__ import annotations

from types import ModuleType

import numpy as np


DEFAULT_MULTISEED_SEARCH_INTERVAL_CALLS = 8


def install_expanded_multiseed_branches(ik_fallback_module: ModuleType) -> None:
    """Add shoulder-pitch/roll branches to the existing fallback seed set."""
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
    """Score whole-arm fallback branches by Cartesian position, not wrist rotation."""
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


def install_multiseed_search_cadence(
    ik_fallback_module: ModuleType,
    *,
    interval_calls: int = DEFAULT_MULTISEED_SEARCH_INTERVAL_CALLS,
) -> None:
    """Run the expensive full multi-seed search only periodically while fallback is active.

    Coupled fallback remains available every control call. The full branch search
    evaluates many seeds and several DLS/collision iterations per seed; doing that
    every viewer cycle can halve the effective control rate and create visible
    zero-order-hold stepping. The first multi-seed request runs immediately, then
    subsequent requests are skipped until ``interval_calls`` fallback calls have
    elapsed.
    """
    if isinstance(interval_calls, bool) or int(interval_calls) < 1:
        raise ValueError("interval_calls must be an integer >= 1")
    if getattr(ik_fallback_module, "_MULTISEED_SEARCH_CADENCE_INSTALLED", False):
        return

    original_multiseed_candidate = ik_fallback_module._multiseed_candidate
    counter = 0

    def throttled_multiseed_candidate(*args, **kwargs):
        nonlocal counter
        counter += 1
        should_search = counter == 1 or counter >= int(interval_calls)
        if should_search:
            counter = 0
            return original_multiseed_candidate(*args, **kwargs)

        # Match the original return contract. Coupled fallback still executes on
        # this cycle; only the heavyweight branch enumeration is deferred.
        return None, float("inf"), float("inf"), None, []

    ik_fallback_module._multiseed_candidate = throttled_multiseed_candidate
    ik_fallback_module._MULTISEED_SEARCH_CADENCE_INSTALLED = True
    ik_fallback_module._MULTISEED_SEARCH_INTERVAL_CALLS = int(interval_calls)
