# Isaac Lab G1 IK 비교 검토

검토일: 2026-09-03. 범위: 공개 소스 정적 검토와 현재 로컬 소스 비교.
Isaac Sim 설치, 예제 실행, 제어 코드 변경, 물리 출력은 하지 않았다.

## 결론

- Unity / MuJoCo / Mink를 유지한다. 시뮬레이터 교체를 권할 근거는 없다.
- Isaac Lab의 자세 보정 분리와 동일 손목 프레임의 6D task는 비교 실험 가치가 있다.
- 읽은 G1 IK 호출 경로에는 우리와 동등한 자기충돌 거리 제약이 연결돼 있지 않다.
  따라서 영상의 부드러운 움직임을 우리 안전 조건에서의 우월성으로 해석하면 안 된다.
- 지금 재현된 정지의 원인을 먼저 계측하고, 이후 같은 로그로 요소별 비교한다.

## 출처와 적용 범위

[포럼 5번 댓글](https://forums.developer.nvidia.com/t/meta-quest-for-humanoid-g1-teleoperation-in-isaac-sim/360846/5)은
Quest 2 / ALVR 20.14.1 / SteamVR / Isaac Sim 5.1 + Isaac Lab로 고정 베이스 G1 상체를 조작했다는 사용자 보고다.
작성자가 사용한 Isaac Lab 커밋과 모든 설정은 댓글에 제시되지 않았다.
아래는 그 실험의 완전한 복제가 아니라 현재 공개 코드의 비교다.

Isaac Lab 검토 커밋: `b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8`.
현재 main을 GitHub tree API로 확인한 뒤, 아래 소스는 이 커밋으로 고정하여 읽었다.

## 실제 호출 흐름

`FixedBaseUpperBodyIKG1EnvCfg`
-> `G1TriHandUpperBodyRetargeter`
-> `PinkInverseKinematicsAction.process_actions`
-> pelvis 기준 손목 목표
-> `PinkIKController.compute`
-> `pink.solve_ik(..., solver="daqp")`
-> 현재 q + 속도 * dt
-> 시뮬레이션 articulation의 관절 위치 목표.

이 경로는 SDK2 / rt/arm_sdk 물리 출력 코드가 아니다.
고정 베이스 설정은 root를 고정하지만, 연결된 IK joint 목록에는 양팔과 허리도 포함한다.
우리의 오른팔 7축 / 나머지 고정 조건과 자유도가 다르다.
[환경 설정](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomanipulation/pick_place/fixed_base_upper_body_ik_g1_env_cfg.py#L73-L83),
[IK joint 설정](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomanipulation/pick_place/configs/pink_controller_cfg.py#L71-L81),
[출력 적용](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/envs/mdp/actions/pink_task_space_actions.py#L274-L320).

## 비교

| 항목 | Isaac Lab의 확인한 G1 경로 | 현재 프로젝트 |
| --- | --- | --- |
| IK | Pink + Pinocchio + DAQP | Mink + MuJoCo + 선택된 QP solver |
| 손목 목표 | yaw link의 위치와 회전을 하나의 LocalFrameTask로 처리 | roll link 위치 task와 yaw link 회전 task 분리, 외부 목표는 yaw link |
| 가중치 | 위치 8, 회전 2 | 기본값 위치 8, 회전 2; 손목 한계 근처 회전 비용 완화 |
| task gain / LM damping | 0.5 / 10 | 0.35 / 1e-5 |
| 자세 보정 | NullSpacePostureTask, 어깨와 허리 선택 | 일반 PostureTask; 손목 자세 비용을 낮춤 |
| 주기 | physics dt 1/200, decimation 4; apply_actions에서 physics dt로 IK | 제어 dt 1/60 |
| 충돌 경계 | 읽은 IK 호출에 거리 barrier / collision limit 인자 없음 | CollisionAvoidanceLimit + 중간 자세 거리 검사, 현재 목표 여유 20mm |
| 다음 자세 채택 | IK 성공 시 q + v*dt | 3단계 예측, 여러 보폭으로 줄이며 오차 감소와 거리 조건을 함께 검사 |
| IK 실패 | 예외 시 현재 관절값 반환 | 후보를 채택 못하면 local_limit / 현재 q 유지 |

가중치 숫자가 같아도 오차식, task 분리, 시간 간격, 감쇠, 제약이 달라 동작이 같지는 않다.
gain은 각도/초 속도 제한이 아니며, LM damping 숫자도 현재 구현에 그대로 이식할 수 없다.
[G1 비용 설정](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomanipulation/pick_place/configs/pink_controller_cfg.py#L17-L62),
[Pink solve / 실패 처리](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/controllers/pink_ik/pink_ik.py#L188-L228).

로컬 확인 위치:
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py`: 기본 비용, gain, dt.
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py`: task 구성, 손목 비용, 충돌 제약, engage 기준 저장.
- `MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py`: 예측, merit 감소 조건, 보폭 축소, 중간 거리 검사.

## 참고할 요소와 그대로 쓰면 안 되는 요소

### 자세 보정 분리

NullSpacePostureTask는 손목 Jacobian들을 쌓고 `N = I - J+ J` 형태의 투영을 구성한다.
G1 설정은 자세 오차 대상에서 손목을 제외하고 어깨와 허리를 선택한다.
손목 목표와 자세 유지가 서로 다투는 현상을 줄이려는 설계로 참고할 가치가 있다.
다만 가중 QP 안의 정규화된 투영이며, 충돌/관절 제약까지 포함한 엄격한 task 우선순위 보장으로 해석하지 않는다.
우리 한 팔에서는 허리를 고정한 채 오른팔 Jacobian과 선택된 어깨 관절로 따로 검증해야 한다.
[NullSpacePostureTask](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/controllers/pink_ik/null_space_posture_task.py#L153-L248).

### 동일 손목 프레임 6D task

LocalFrameTask는 pelvis 기준 목표와 현재 손목 사이 SE(3) 오차 및 Jlog6 기반 Jacobian을 계산한다.
우리 가상 중심의 위치 예측과 실제 yaw 손목 merit 사이 차이를 점검하는 비교 기준이다.
이 구조만으로 인간다운 팔꿈치 자세나 충돌 회피가 보장되지는 않는다.
[LocalFrameTask](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/controllers/pink_ik/local_frame_task.py#L66-L105).

### 안전 처리와 좌표계는 그대로 복사하지 않음

읽은 controller는 collision barrier를 solve_ik에 전달하지 않고,
PinkKinematicsConfiguration도 controlled model을 구성할 때 충돌 모델을 전달하지 않는다.
이는 해당 IK 경로에 대한 결론이지 Isaac Sim의 물리 접촉 처리나 모든 Isaac Lab 기능이 없다는 뜻은 아니다.
`fail_on_joint_limit_violation=False`도 현재 상태 검사 동작에 관한 설정이며 모든 QP 관절 제한을 끈다는 뜻은 아니다.
[모델 구성](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/controllers/pink_ik/pink_kinematics_configuration.py#L51-L82),
[상태 제한 검사](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/controllers/pink_ik/pink_kinematics_configuration.py#L155-L158).

TriHand retargeter는 손목 데이터가 없으면 원점/단위회전 값을 대입하고, 손별 고정 회전과 wxyz quaternion을 사용한다.
이 기본값을 우리 실제 G1 명령에 연결하면 안 된다. 추적 손실 disarm / watchdog과 기존 좌표 계약을 유지한다.
이미 정상 매핑이 확인된 Unity 경로에 저 회전 상수를 추가하지 않는다.
[retargeter](https://github.com/isaac-sim/IsaacLab/blob/b0542fe2d45bf91c4e1d9ef6952b9c709c80b4e8/source/isaaclab/isaaclab/devices/openxr/retargeters/humanoid/unitree/trihand/g1_upper_body_retargeter.py#L78-L145).

## 다음 비교 절차

1. 보존한 `logs/quality/quest_motion_20260903_153321_session.jsonl` 첫 active 구간의
   상대 시각 5.468~8.531초를 현재 planner로 재현한다.
2. 실패 원인을 QP 실패 / merit 증가 / 관절 제한 / 중간 충돌 거리 부족으로 분리한다.
   local_limit 하나로는 왜 멈췄는지 판별할 수 없다.
3. 현재 코드와 분리한 실험에서 하나씩 비교한다: 동일 손목 6D task, null-space 자세 보정, 감쇠 조정.
4. 같은 모델, 원시 목표, 초기 q, 40/100 deg/s, 충돌 pair와 20mm 거리 조건을 유지한다.
   모델 엔진 버전도 맞추고, 여러 설정을 동시에 바꾸지 않는다.
5. 정지 시간, 위치/회전 오차, 상완 이동량, 관절 속도, 최소 거리와 한계 복귀를 함께 평가한다.
   손목만 잘 맞고 몸통을 관통하는 결과는 개선으로 채택하지 않는다.

현재 판정은 **참고 가치 있음 / 교체 및 효과 검증은 미완료**다.
추가 Quest 시험 전에 이미 확보한 기록으로 실패 원인부터 좁힌다.
