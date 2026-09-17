# IK 및 Omni 시계열 기록

이 문서는 Unity/Mink가 만든 오른팔 관절 목표와 Omni 입력·변환 결과를 실제 G1 명령 경로와 분리해 CSV로 기록하는 방법을 정리한다. 두 로거 모두 G1 SDK, DDS, SSH, LowCmd를 사용하지 않는다.

## 1. IK 오른팔 각도 형식

Mink 출력은 UDP `127.0.0.1:5008`의 JSON 스키마 `g1.mink.right_arm.state.v1`이다. 관절각 단위는 모두 **radian**이다.

```json
{
  "schema": "g1.mink.right_arm.state.v1",
  "sequence": 123,
  "state_source": "mink_simulation",
  "all_joint_names": ["29 joint names"],
  "all_joint_q_rad": ["29 finite radians"],
  "right_arm": {
    "joints": ["7 finite radians"],
    "active": true,
    "command_state": "tracking"
  },
  "input_command_mode": "tracked",
  "session_id": "session identifier",
  "input_packet_age_s": 0.003,
  "timestamp": 1234567890.0
}
```

`right_arm.joints`는 `all_joint_q_rad[22:29]`와 정확히 같아야 한다.

| index | joint |
|---:|---|
| 22 | `right_shoulder_pitch_joint` |
| 23 | `right_shoulder_roll_joint` |
| 24 | `right_shoulder_yaw_joint` |
| 25 | `right_elbow_joint` |
| 26 | `right_wrist_roll_joint` |
| 27 | `right_wrist_pitch_joint` |
| 28 | `right_wrist_yaw_joint` |

## 2. IK CSV 기록

2026-09-09에 사용자가 확인한 simulation v5 IK와 pinch 복귀를 그대로 사용하면서 기록하려면 실행한다.

```powershell
.\tools\START_MINK_ARM_CYCLE_SIMULATION.bat today
```

Unity가 이미 열려 있으면 Play를 시작한다. 이 경로는 `vanilla 6D + upstream Mink collision + position-priority recovery v5`와 today 90/180 deg/s, 60 deg/s2 설정을 사용하며 pinch 복귀와 재engage를 포함한다. 파일은 `logs/test_results/mink_right_arm_csv/`에 생성된다. 후보 UDP 5008 출력과 G1 출력은 만들지 않고 같은 pre-relay JSON을 송신 구성 지점에서 직접 기록한다. 별도 `RECORD_MINK_RIGHT_ARM_CSV.bat`은 외부 수신 시험용이다.

CSV에는 수신 monotonic 시각, Mink의 Unix 시각, sequence/session, active/상태, 입력 age, 오차·충돌 진단값과 오른팔 7개 관절각이 기록된다. 마지막 `raw_json_text` 열에는 UDP로 수신한 UTF-8 JSON 평문 전체를 변형 없이 함께 보존한다. CSV 안의 쉼표와 따옴표는 표준 CSV quoting으로 감싸진다. 스키마·29축 순서·중복 관절값·유한값·UTF-8·증가 sequence가 맞지 않는 패킷은 기록하지 않고 reject 수에 포함한다.

## 3. Omni 원본 및 변환 CSV 기록

Omni Connect에 연결한 뒤 실행한다.

```powershell
.\tools\START_OMNI_GATEWAY_READONLY.bat
```

종료는 `Ctrl+C`다. 파일은 `logs/test_results/omni_gateway_readonly/`에 생성된다. `--dry-run`이 고정되어 있으므로 discovery와 G1 UDP 송신을 만들지 않는다.

| CSV 열 | 의미·단위 |
|---|---|
| `movement_x`, `movement_y` | Omni `movementXY` 원본 |
| `arm_yaw_deg` | Omni arm 절대 yaw, degree |
| `arm_yaw_from_origin_deg` | 연결 뒤 첫 sample을 0도로 본 상대 yaw, degree |
| `arm_yaw_step_diff_deg` | 직전 sample과의 wrap 보정 yaw 차, degree |
| `arm_yaw_rate_raw_deg_s` | yaw 차 / sample 시간, degree/s; deadzone/filter 전 |
| `vx`, `vy` | 원점·deadzone·축 보정 뒤 속도, m/s |
| `yaw_rate` | deadzone/filter/clamp 뒤 회전속도, rad/s |
| `calibrated` | movement 원점 보정 완료 여부 |

시작 시 움직이고 있어도 원본 열은 그대로 기록된다. 다만 처음 1초 동안 계산된 `vx/vy/yaw_rate`는 보정 구간이라 0이다. 정확한 원점이 필요하면 실행 직후 1초 동안 Omni를 가능한 한 움직이지 않는다.

## 검증 범위

단위 테스트는 JSON 중복키, 29축/오른팔 순서, 중복 관절값 불일치, 비유한값, yaw wrap과 상대 원점 계산을 검사한다. 이 검사는 CSV 계약과 오프라인 계산 검증이며 실제 Quest, Omni 또는 G1 동작 검증이 아니다.
