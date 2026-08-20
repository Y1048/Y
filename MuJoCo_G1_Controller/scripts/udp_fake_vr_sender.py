import json
import math
import socket
import time
import uuid


HOST = "127.0.0.1"
PORT = 5005

def euler_xyz_to_quaternion(roll, pitch, yaw):
    half_roll = 0.5 * roll
    half_pitch = 0.5 * pitch
    half_yaw = 0.5 * yaw
    cosine_roll = math.cos(half_roll)
    sine_roll = math.sin(half_roll)
    cosine_pitch = math.cos(half_pitch)
    sine_pitch = math.sin(half_pitch)
    cosine_yaw = math.cos(half_yaw)
    sine_yaw = math.sin(half_yaw)
    return [
        sine_roll * cosine_pitch * cosine_yaw
        - cosine_roll * sine_pitch * sine_yaw,
        cosine_roll * sine_pitch * cosine_yaw
        + sine_roll * cosine_pitch * sine_yaw,
        cosine_roll * cosine_pitch * sine_yaw
        - sine_roll * sine_pitch * cosine_yaw,
        cosine_roll * cosine_pitch * cosine_yaw
        + sine_roll * sine_pitch * sine_yaw,
    ]


def smoothstep(value):
    clamped_value = max(0.0, min(1.0, value))
    return clamped_value * clamped_value * (3.0 - 2.0 * clamped_value)


def normalize_quaternion(quaternion):
    magnitude = math.sqrt(sum(value * value for value in quaternion))
    return [value / magnitude for value in quaternion]


def slerp_quaternion(start_quaternion, end_quaternion, blend_value):
    start_value = normalize_quaternion(start_quaternion)
    end_value = normalize_quaternion(end_quaternion)
    dot_value = sum(
        start_value[index] * end_value[index]
        for index in range(4)
    )
    if dot_value < 0.0:
        end_value = [-value for value in end_value]
        dot_value = -dot_value

    dot_value = max(-1.0, min(1.0, dot_value))
    if dot_value > 0.9995:
        return normalize_quaternion([
            start_value[index]
            + blend_value * (end_value[index] - start_value[index])
            for index in range(4)
        ])

    angle_value = math.acos(dot_value)
    sine_value = math.sin(angle_value)
    start_weight = math.sin((1.0 - blend_value) * angle_value) / sine_value
    end_weight = math.sin(blend_value * angle_value) / sine_value
    return [
        start_weight * start_value[index] + end_weight * end_value[index]
        for index in range(4)
    ]


def create_pose(position, roll_degrees, pitch_degrees, yaw_degrees):
    return {
        "position": position,
        "rotation": euler_xyz_to_quaternion(
            math.radians(roll_degrees),
            math.radians(pitch_degrees),
            math.radians(yaw_degrees),
        ),
    }


# The first and last poses are identical so the sequence loops without a jump.
# Positions remain on the robot's right side and inside the operational workspace.
MOTION_KEYFRAMES = [
    (2.8, create_pose([0.34, -0.24, 0.92], 0.0, 0.0, 0.0)),
    (3.2, create_pose([0.37, -0.24, 0.95], -2.0, 4.0, -2.0)),
    (3.0, create_pose([0.40, -0.25, 0.97], -3.0, 6.0, -3.0)),
    (3.2, create_pose([0.42, -0.25, 0.99], -4.0, 8.0, -3.0)),
    (3.2, create_pose([0.42, -0.25, 0.95], -3.0, 7.0, -2.0)),
    (3.4, create_pose([0.40, -0.28, 0.98], -2.0, 6.0, 4.0)),
    (2.8, create_pose([0.37, -0.24, 0.95], 0.0, 3.0, 0.0)),
    (2.0, create_pose([0.34, -0.24, 0.92], 0.0, 0.0, 0.0)),
]


def sample_motion(elapsed_time):
    total_duration = sum(duration for duration, _ in MOTION_KEYFRAMES[:-1])
    loop_time = elapsed_time % total_duration
    accumulated_time = 0.0

    for keyframe_index in range(len(MOTION_KEYFRAMES) - 1):
        duration, start_pose = MOTION_KEYFRAMES[keyframe_index]
        end_pose = MOTION_KEYFRAMES[keyframe_index + 1][1]
        if loop_time <= accumulated_time + duration:
            phase_value = smoothstep(
                (loop_time - accumulated_time) / duration)
            position = [
                start_pose["position"][axis_index]
                + phase_value
                * (end_pose["position"][axis_index]
                   - start_pose["position"][axis_index])
                for axis_index in range(3)
            ]
            rotation = slerp_quaternion(
                start_pose["rotation"],
                end_pose["rotation"],
                phase_value,
            )
            return position, rotation
        accumulated_time += duration

    final_pose = MOTION_KEYFRAMES[-1][1]
    return final_pose["position"], final_pose["rotation"]


def main():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Sending human-like inspection motion to {HOST}:{PORT}")
    print("Motion phases: rest, raise, approach, vertical scan, lateral scan, retract.")
    print("Keep the UDP IK demo open. Press Ctrl+C to stop.")

    session_id = f"fake-vr-{uuid.uuid4().hex}"
    sequence = 0
    start_time = time.monotonic()
    try:
        while True:
            position, rotation = sample_motion(time.monotonic() - start_time)
            message = {
                "session_id": session_id,
                "sequence": sequence,
                "right": {
                    "pos": position,
                    "rot": rotation,
                    "valid": True,
                },
            }
            udp_socket.sendto(
                json.dumps(message).encode("utf-8"),
                (HOST, PORT),
            )
            sequence += 1
            time.sleep(1.0 / 60.0)
    except KeyboardInterrupt:
        print("\nStopping fake VR sender and releasing the clutch.")
    finally:
        release_message = {
            "session_id": session_id,
            "sequence": sequence,
            "right": {
                "valid": False,
            },
        }
        encoded_message = json.dumps(release_message).encode("utf-8")
        for _ in range(3):
            udp_socket.sendto(encoded_message, (HOST, PORT))
            time.sleep(0.01)
        udp_socket.close()


if __name__ == "__main__":
    main()
