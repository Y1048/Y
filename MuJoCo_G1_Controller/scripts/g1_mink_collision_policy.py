"""Named collision-distance policies for the G1 Mink runtime."""

COLLISION_PROFILE_MINK_DEFAULT = "mink-default"
COLLISION_PROFILE_HARDWARE_GUARDED = "hardware-guarded"

COLLISION_PROFILES = {
    COLLISION_PROFILE_MINK_DEFAULT: (0.005, 0.010),
    COLLISION_PROFILE_HARDWARE_GUARDED: (0.020, 0.040),
}

# Upstream Mink's one-step linearized collision constraint gets a small reserve
# in the local-detour profile so the discrete validation layer does not chatter.
MINK_DEFAULT_QP_RESERVE_M = 0.0005

# Compatibility name for offline tools that intentionally audit the guarded
# physical-output candidate policy.
TELEOP_COLLISION_TARGET_DISTANCE_M = COLLISION_PROFILES[
    COLLISION_PROFILE_HARDWARE_GUARDED
][0]


def ResolveCollisionProfile(name: str) -> tuple[float, float]:
    """Return (minimum, detection) distances for one named runtime profile."""
    try:
        return COLLISION_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown collision profile: {name}") from exc
