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
