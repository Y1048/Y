#!/usr/bin/env python3

import argparse
import csv
import time

import numpy as np

from unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelPublisher,
    ChannelSubscriber,
)
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC


WAIST_JOINTS = [12, 13, 14]
ARM_JOINTS = list(range(15, 29))
WEIGHT_INDEX = 29

CONTROL_HZ = 50.0
DT = 1.0 / CONTROL_HZ


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--iface", default="eth0")
    parser.add_argument(
        "--waist-mode",
        choices=["free", "hold", "offset"],
        required=True,
        help=(
            "free: 허리를 arm_sdk에서 제어하지 않음, "
            "hold: 시작 허리각 고정, "
            "offset: 시작 허리각 + pitch offset"
        ),
    )

    parser.add_argument(
        "--shoulder-pitch-offset",
        type=float,
        default=0.0,
        help="양쪽 shoulder pitch에 더할 값 [rad]",
    )
    parser.add_argument(
        "--waist-pitch-offset",
        type=float,
        default=0.0,
        help="waist pitch 시작각에 더할 값 [rad]",
    )

    # Unitree 공식 arm7 예제의 기본값
    parser.add_argument("--arm-kp", type=float, default=60.0)
    parser.add_argument("--arm-kd", type=float, default=1.5)
    parser.add_argument("--waist-kp", type=float, default=60.0)
    parser.add_argument("--waist-kd", type=float, default=1.5)

    parser.add_argument("--csv", default="g1_upper_body_test.csv")

    args = parser.parse_args()

    ChannelFactoryInitialize(0, args.iface)

    publisher = ChannelPublisher("rt/arm_sdk", LowCmd_)
    publisher.Init()

    subscriber = ChannelSubscriber("rt/lowstate", LowState_)
    subscriber.Init()

    print("Waiting for rt/lowstate...")

    state = None
    while state is None:
        state = subscriber.Read(timeout=0.1)

    q_initial = np.array(
        [motor.q for motor in state.motor_state],
        dtype=np.float64,
    )

    print("Connected.")
    print(
        "Initial waist [yaw, roll, pitch]:",
        np.round(q_initial[12:15], 4),
    )
    print(
        "Initial arms:",
        np.round(q_initial[15:29], 4),
    )

    target = q_initial.copy()

    # 양팔 shoulder pitch를 동일하게 변화
    target[15] += args.shoulder_pitch_offset
    target[22] += args.shoulder_pitch_offset

    if args.waist_mode == "offset":
        target[14] += args.waist_pitch_offset

    controlled_joints = ARM_JOINTS.copy()

    if args.waist_mode in ("hold", "offset"):
        controlled_joints = WAIST_JOINTS + controlled_joints

    command = unitree_hg_msg_dds__LowCmd_()
    command.mode_pr = 0
    command.mode_machine = state.mode_machine

    crc = CRC()

    print()
    print("Waist mode:", args.waist_mode)
    print("Controlled joints:", controlled_joints)
    print("Target waist:", np.round(target[12:15], 4))
    print()
    print("로봇이 크레인에 연결되어 있는지 확인하십시오.")
    input("준비됐으면 Enter를 누르십시오...")

    start_time = time.monotonic()
    last_weight = 0.0
    print_counter = 0

    with open(args.csv, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "time",
                "weight",
                "waist_yaw_q",
                "waist_roll_q",
                "waist_pitch_q",
                "waist_yaw_dq",
                "waist_roll_dq",
                "waist_pitch_dq",
                "waist_yaw_tau",
                "waist_roll_tau",
                "waist_pitch_tau",
                "imu_roll",
                "imu_pitch",
                "imu_yaw",
            ]
        )

        try:
            while True:
                loop_start = time.monotonic()
                elapsed = loop_start - start_time

                # 3초 동안 arm_sdk weight 0 -> 1
                weight = float(np.clip(elapsed / 3.0, 0.0, 1.0))

                # 5초 동안 현재 자세 -> 목표 자세
                target_ratio = float(np.clip(elapsed / 5.0, 0.0, 1.0))

                command.motor_cmd[WEIGHT_INDEX].q = weight

                for joint_id in controlled_joints:
                    motor_cmd = command.motor_cmd[joint_id]

                    q_ref = (
                        q_initial[joint_id]
                        + target_ratio
                        * (target[joint_id] - q_initial[joint_id])
                    )

                    motor_cmd.mode = 1
                    motor_cmd.q = float(q_ref)
                    motor_cmd.dq = 0.0
                    motor_cmd.tau = 0.0

                    if joint_id in WAIST_JOINTS:
                        motor_cmd.kp = args.waist_kp
                        motor_cmd.kd = args.waist_kd
                    else:
                        motor_cmd.kp = args.arm_kp
                        motor_cmd.kd = args.arm_kd

                command.crc = crc.Crc(command)
                publisher.Write(command)

                new_state = subscriber.Read(timeout=0.001)
                if new_state is not None:
                    state = new_state

                waist = state.motor_state
                rpy = state.imu_state.rpy

                writer.writerow(
                    [
                        elapsed,
                        weight,
                        waist[12].q,
                        waist[13].q,
                        waist[14].q,
                        waist[12].dq,
                        waist[13].dq,
                        waist[14].dq,
                        waist[12].tau_est,
                        waist[13].tau_est,
                        waist[14].tau_est,
                        rpy[0],
                        rpy[1],
                        rpy[2],
                    ]
                )
                file.flush()

                if print_counter % 25 == 0:
                    print(
                        f"t={elapsed:6.1f} "
                        f"weight={weight:.2f} "
                        f"waist_q="
                        f"[{waist[12].q:+.3f}, "
                        f"{waist[13].q:+.3f}, "
                        f"{waist[14].q:+.3f}] "
                        f"imu_pitch={rpy[1]:+.3f}"
                    )

                print_counter += 1
                last_weight = weight

                sleep_time = DT - (time.monotonic() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\nCtrl-C received. Releasing arm_sdk gradually...")

        finally:
            # 2초 동안 weight를 0으로 내려 arm_sdk 해제
            release_steps = int(2.0 * CONTROL_HZ)

            for step in range(release_steps):
                ratio = (step + 1) / release_steps
                command.motor_cmd[WEIGHT_INDEX].q = (
                    last_weight * (1.0 - ratio)
                )

                command.crc = crc.Crc(command)
                publisher.Write(command)
                time.sleep(DT)

            command.motor_cmd[WEIGHT_INDEX].q = 0.0
            command.crc = crc.Crc(command)
            publisher.Write(command)

            print("arm_sdk released.")
            print("CSV:", args.csv)


if __name__ == "__main__":
    main()
    
