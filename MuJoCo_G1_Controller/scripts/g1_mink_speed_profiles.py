"""Named comparison presets. Values are radians; does not enable robot output."""
import math

def speed_profile(name):
    if name == "yesterday":
        return {"name": name, "velocity_rad_s": [0.7] * 7,
                "acceleration_rad_s2": [math.radians(10)] * 7}
    if name == "today":
        return {"name": name, "velocity_rad_s": [math.radians(90)] * 4 + [math.radians(180)] * 3,
                "acceleration_rad_s2": [math.radians(60)] * 7}
    raise ValueError(f"Unknown speed profile: {name}")


def live_joint_bounds():
    """Keep live IK targets 0.08 rad inside the native hard joint bounds.

    The native state guard remains at 0.05 rad.  The extra 0.03 rad is a
    braking/servo-following reserve so a checked target cannot sit directly on
    the state guard, as happened at right shoulder yaw in trial 8071.
    """
    import struct
    def f32(x):
        return struct.unpack('f', struct.pack('f', x))[0]
    lower = [-3.0892, -2.2515, -2.618, -1.0472, -1.972222054, -1.614429558, -1.614429558]
    upper = [2.6704, 1.5882, 2.618, 2.0944, 1.972222054, 1.614429558, 1.614429558]
    return ([f32(x) + .0801 for x in lower], [f32(x) - .0801 for x in upper])
