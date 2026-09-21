# Omni + 양팔 실시간 수신 확인과 카메라 (모터 출력 없음)

입력 관찰은 G1에서 **PC가 보낸 관찰 데이터만 수신·출력**한다. 관찰 경로는
Unitree SDK/DDS를 사용하지 않는다. 통합 실행의 별도 카메라 창만 기존 SDK2
`VideoClient.GetImageSample`로 영상을 읽어 Unity에 전달한다.
GROOT/TWIST2 제어기, LowCmd, 모터 출력, 모드 전환은 실행하지 않는다.
GROOT 통합은 사용자 요청으로 보류했다.

2026-09-21 담당 범위: **우리는 양팔14축과 Omni 이동값을 정확히 생성·전달하고,
로봇 제어는 상대가 담당하며 나중에 통합한다.** 현재 완료 기준은 필드·단위·축·순서와
시각/순번/최신성이 보존된 입력값을 상대 수신 측에서 확인할 수 있는 것이다.

통합 전제는 **하체·상체 동시제어이며 모드 전환은 없다.** Omni 이동값과 양팔 관절값을
함께 제공한다. 팔의 ready/tracking/return은 입력 상태이며 하체/상체 제어 모드 전환을 뜻하지 않는다.

앞서 논의한 **G1 내부 Python 외부제어기 → UDP → C++ 실제 제어기**는 향후 통합 구조다.
현재 Python 도구는 **입력 수신부만 모사**한다. 실제 G1 관절 초기각 읽기, C++/LowCmd 연결,
PD·하체 정책·균형·모드 전환·회전각 추종은 현재 우리 담당 작업에 포함하지 않는다.
`initial_g1_q_rad=null`, `initial_g1_q_status=NOT_MEASURED`, `cpp_command_sent=false`로
미구현/미실행 상태를 표시한다. 가상의 초기각이나 IK 목표각을 실측 초기각으로 기록하지 않는다.

```text
Quest → Unity → 양팔 Mink IK ──┐
                              ├→ PC 관찰 수집기 → UDP 55070 → G1 수신창
Omni Connect → Gateway dry-run ┘                    ← 순번/SHA256 ACK
          각 생산자 → 127.0.0.1:55071

G1 카메라 → 기존 WSL 카메라 브리지 → TCP 127.0.0.1:5011 → Unity 패널
```

저장 CSV/JSONL을 재생하지 않는다. **계산·관찰 송신은 60Hz, PC/G1 표시는 100Hz**다.
IK의 검증된 `dt=1/60초`를 유지하고, Omni 최신 입력 처리와 PC 수집·송신도 같은
16.667ms 목표 주기를 사용한다. 화면은 별도 스레드에서 10ms마다 최신값을 출력한다.
원본 순번·생성 시각은 유지하며, 반복 표시는 새 센서 표본으로 취급하지 않는다.

| 단계 | 목표 주기 |
|---|---|
| Unity 손 입력 | 기존 최대60Hz, Unity frame에 종속 |
| 양팔 IK | 60Hz / 16.667ms |
| Omni Gateway 계산 tick | 60Hz / 16.667ms, 새 raw 표본이 있을 때만 갱신 |
| PC 관찰 수집·G1 송신 | 60Hz / 16.667ms |
| PC 송신창·G1 수신창 표시 | 100Hz / 10ms, 최신값 반복 표시 포함 |

양팔 14축의 현재 관절 목표 제한은 모두 **각속도 3.0 rad/s, 각가속도 3.0 rad/s²**다.
`MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py`에서 관리하며 추적·제동·복귀에
같이 적용한다. 둘 다 각도 단위로 환산하면 약171.887°/s,171.887°/s²다.
이 값은 상한이며 실제 추종 속도는 목표·IK·충돌 검사에 따라 더 낮을 수 있다.
기존 어깨/팔꿈치90°/s·손목180°/s·가속도60°/s²에서 변경한 것이다.
단독 오른팔 경로의 설정이나 G1 실제 gain/제어기 설정은 변경하지 않았다.

새 run 로그는 `motion_limits`에 적용값을 기록한다. 과거 로그의 제한은 당시 값으로
판정하며, 다른 제한으로 현재 코드를 재생하면 과거 관절 경로와 정확히 일치한다고 주장하지 않는다.
프로그램이 실행 중이었다면 다음 arm 프로세스 시작부터 새 설정을 읽는다.

Omni Bluetooth/WebSocket의 원본 센서 주파수를 변경하지 않는다. 서로 독립적인
프로세스의 주기를 맞춘 것이며 동일 위상·동시 센서 취득을 보장하지 않는다.
Windows/Linux Python은 hard realtime이 아니므로 연산·출력이 늦으면 deadline을
건너뛰고 횟수를 기록한다. 밀린 계산/표시를 몰아서 실행하지 않는다.

양팔과 Omni가 완전히 동일한 시각에 생성·도착한 값은 아니다. PC에서 독립적으로
갱신된 각 입력의 최신값을16.667ms마다 묶어 G1의55070으로 전송한다. 따라서 하나의
패킷으로 함께 수신돼도 각 `source_monotonic_s`와 `source_age_s`는 다를 수 있다.
이는 PC의 IK 생성/Omni 수신 시각이며 장치 간 센서 측정시각 동기화나 보간은 하지 않는다.

## 실행

PC 프로젝트 루트에서:

```powershell
.\tools\START_G1_VR_TELEOP.bat
```

주소가 다른 경우:

```powershell
.\tools\START_G1_VR_TELEOP.bat --host 192.168.123.164
```

열리는 창은 `receive`(G1 SSH), `send`(PC 송신/ACK), `omni`, `arm`, 카메라 다섯 개다.
같은 작업본·설정의 입력 생산자와 송수신 자식 프로세스, 기존 카메라 프로세스가
살아 있으면 그대로 두고 빠진 창만 실행한다. 종료 후 Enter를 기다리는 빈 창은
실행 중인 생산자로 취급하지 않는다. 다른 설정/알 수 없는 포트 점유는 자동 종료하지 않는다.
이미 실행 중인 프로세스의 소스가 최신인지까지 보증하는 기능은 아니다.

`--host`는 관찰 송수신 주소다. 카메라는 기존 WSL Ubuntu, G1 연결 NIC
`192.168.123.99/24`, `/home/user/.venvs/g1-teleop` 환경을 그대로 사용한다.
통합 배치가 네트워크 설정이나 SDK 설치를 변경하지 않는다.

실행 없이 준비 상태만 확인하려면 `--check-only`를 붙인다. 다른 PC/터미널에서
G1 수신기를 이미 실행했다면 `--no-receiver`를 붙인다.
기존 `START_G1_INPUT_OBSERVATION.bat`(입력만), `START_G1_CAMERA_TO_UNITY.bat`(영상만)도 유지한다.
이전 입력 전용 배치를 새 통합 배치와 함께 추가 실행할 필요는 없다.

1. `receive` 창에서 G1 SSH 비밀번호를 입력한다.
2. Omni Connect가 실행되고 장치가 연결돼 있어야 한다. 첫 1초 표본으로 기존
   Gateway 원점·이동 영점 보정을 한다. 재보정하려면 Omni 관찰 창을 다시 시작한다.
3. 기존 Unity 양팔 씬에서 Play → engage → 손 움직임을 수행한다.
4. `send`에서 `ACK_CONFIRMED`, 두 입력에서 `FRESH_LIVE`를 확인한다.
   팔의 `unity_input_status=FRESH`도 별도로 확인한다.

Omni 창이 연결 대기 중이면 `[OMNI CONNECTION]`에 `CONNECTING` 또는
`RETRY_WAIT`가 나온다. 연결 timeout은2초이며 실패/끊김 후0.5~2초 간격으로
자동 재시도한다. Omni Connect를 먼저 켜고 Bluetooth 장치 연결을 확인한다.
연결 뒤 데이터가 잠시 없으면 `WAIT_SAMPLE`로 기다리며, 수신 timeout만으로
프로그램을 종료하지 않는다. 원래 표본의 시각은 유지하므로 오래된 값을 새 입력으로
표시하지 않는다. 잘못된 JSON/필드/비정상 수치는 여전히 오류로 종료한다.

다른 관찰 창이 이미 실행 중일 때 **Omni 창만** 다시 시작하려면:

```powershell
.\tools\START_G1_INPUT_OBSERVATION.bat --worker omni
```

모터 제어가 없으므로 이 도구 때문에 Regular 모드로 변경할 필요는 없다.
종료는 관찰 창과 카메라 창에서 Ctrl+C 또는 해당 창 닫기.
Unity Play/Omni Connect는 사용자가 별도로 시작하고 종료한다. 카메라는 Unity Play 후
5011 수신기가 열리면 연결하며 최대20fps를 요청한다. 카메라 주기를 IK60Hz/표시100Hz와 혼동하지 않는다.
원래 별도로 실행하던 제어 프로그램은 이 도구의 관리 대상이 아니다.

G1 수신기만 직접 실행할 경우:

```bash
cd /home/unitree/g1_input_audit_20260921_7e83c4
python3 -u G1_INPUT_RECEIVE_AUDIT.py receive --print-hz 100
```

수정본의 `python3 -u G1_INPUT_RECEIVE_AUDIT.py receive` 명령도 기본100Hz로 동작한다.
이 창을 이미 실행했다면 전체 launcher의 `receive` 창을 추가로 실행하지 않는다.
PC 쪽 세 창과 카메라만 시작하려면 `START_G1_VR_TELEOP.bat --no-receiver`를 사용한다.

G1 수신기는 Python 표준 라이브러리만 사용한다. 기존 제어용 포트5014/5017 및
예전 관찰 수신기를 동시에 실행하지 말라는 뜻은 아니다. 다만 **55070을 사용하는
관찰 수신기는 하나만** 실행해야 한다. `already in use`이면 다음으로 점유자를 확인한다.

```bash
ss -unlp | grep 55070
```

자신이 띄운 이전 관찰 수신기 창에서 Ctrl+C로 종료한다. 무관한 프로세스를 종료하거나
`SO_REUSEADDR`로 중복 수신기를 띄우지 않는다. 새 통합 배치는 일치하는 관찰용 양팔
프로세스를 유지한다. 다른 모드로 실행한 시뮬레이터가5020을 사용하면 자신의 기존 창에서
종료한 뒤 실행한다. Unity Play 정지/재개만으로 Python이 재시작되지는 않는다.

## 표시 값

| 항목 | 형식 / 단위 |
|---|---|
| `left_q_rad` | 길이7 실수 배열, 왼팔15~21, rad |
| `right_q_rad` | 길이7 실수 배열, 오른팔22~28, rad |
| 팔 내부 순서 | shoulder_pitch, shoulder_roll, shoulder_yaw, elbow, wrist_roll, wrist_pitch, wrist_yaw |
| `state`, `reason` | IK ready/tracking/returning/blocked 및 이유 |
| `unity_input_status`, `unity_input_age_s` | 원본 Unity 입력 도착 여부·PC 로컬 수신 후 경과초 |
| `mx`, `my` | Omni 월드 기준 원래 이동 벡터, 무차원 |
| `arm_yaw_deg`, `omni_yaw_rate_deg_s` | Omni arm 방향(deg), 필터 이전 yaw 변화율(deg/s) |
| `vx`, `vy`, `yaw_rate` | 현재 몸체 기준 전진·왼쪽 속도와 회전속도, m/s·m/s·rad/s |
| `yaw_diff_deg`, `yaw_step_diff_deg` | 시작 원점 대비 yaw 차이, 이전 샘플 대비 yaw 차이(deg) |
| `calibrated` | 영점 보정 완료 여부 |

### 2026-09-21 이동 좌표계 수정

사용자가 지정한 입력 계약은 `mx/my`가 월드 기준 이동 벡터이며,
`armYaw=0°`에서 `mx`가 전진(`vx`), `my`가 왼쪽(`vy`)과 같은 축이라는 것이다.
양의 yaw는 월드 +X에서 +Y 방향이다. 이전 코드의 `vx←my`, `vy←-mx`만 적용하던
가정을 대체한다. 센서의 축·부호를 독립 실측하여 확정한 결과와는 구분한다.

```text
x = mx - zero_x
y = my - zero_y
theta = 현재 절대 armYaw (degree → radian)
body_forward =  cos(theta) * x + sin(theta) * y
body_left    = -sin(theta) * x + cos(theta) * y
vx = 기존 전진 scale × deadzone(body_forward), 기존 상한 적용
vy = 기존 좌우 scale × deadzone(body_left), 기존 상한 적용
```

따라서 45° 방향으로 똑바로 걷는 월드 벡터는 `vx>0, vy≈0`으로 변환된다.
작은 입력을 단위 벡터로 정규화하지 않으며, 예시의 `vx=1.0`을 강제하지 않는다.
현재 속도 scale/상한은 축별 0.8 m/s, 이동 deadzone은 0.08 그대로다.

이 결과가 기존 관찰 JSON의 **`vx`, `vy`**, CSV의 동일 열에 들어간다.
기존 command encoder를 사용할 때도 `velocity=[vx,vy,yaw_rate]`의 앞 두 값에 들어간다.
필드명·배열 순서·단위·수신 프로토콜은 변경하지 않는다. 원본 `mx/my/raw_json_text`와
`yaw_rate`, `yaw_diff_deg` 계산도 유지한다. 과거 CSV는 다시 계산하거나 덮어쓰지 않는다.

방향 정렬을 위한 calibration은 필요 없다. 첫 각도를 뺀 `yaw_diff_deg`를
이동 변환에 쓰지 않고 현재 절대 `armYaw`를 사용하므로 시작 방향이 112°여도 처리한다.
기존 1초 calibration은 정지 중 월드 `mx/my` 오프셋 평균을 구하는 용도로 유지한다.
상대 yaw의 시작점은 첫 표본에서 잡는다. 변경 전 실행 중인 Omni 창은 코드를
자동 갱신하지 않으므로 다음 Omni 창 실행부터 적용된다.

팔 값은 **시뮬레이션 IK 목표**이며 실제 G1 관절 측정값이 아니다. `simulation_only=true`를
유지한다. `ACK_CONFIRMED`는 동일 패킷의 순번·SHA256을 G1 관찰 수신기가 돌려줬다는
뜻이다. 모터 수신·실행은 항상 `motor_acceptance=NOT_CHECKED`다.

`FRESH_LIVE`는 PC 생산자 생성시각과 마지막 수신이 모두0.75초 이내일 때만 표시한다.
같은 패킷을 다시 보내도 원본 freshness를 갱신하지 않는다. 양팔 IK가 ready에서 계속
계산되는 동안에도 Unity 입력이 없으면 `unity_input_status=WAIT/STALE`로 구분한다.
PC와 G1의 monotonic clock을 서로 빼지 않는다. G1은 PC가 보고한 원본 age와
자신이 관찰 패킷을 마지막 수신한 후 경과시간을 각각 표시한다.
`display_payload`는 화면 갱신 시 그 경과시간을 더한 표시용 사본이다. 원문 패킷과
SHA256은 그대로 유지한다. PC→G1 전송 지연은 계측되지 않아 age에 포함되지 않는다.
`display_sequence`, `display_repeated_snapshot`, `display_target_hz`,
`display_intervals_skipped`로 화면 주기와 원본 갱신을 구분한다.

Omni 관찰 CSV는 **60Hz tick에서 선택한 새 원본 표본의 부분집합**이다.
`receive_monotonic_s`/`raw_json_text`는 원래 WebSocket 표본을 보존하고,
`raw_sample_sequence`, `raw_samples_skipped`, `processing_hz`, `process_tick`,
`processed_monotonic_s`, `processing_deadlines_missed`를 추가한다. 모든 WebSocket
메시지의 무손실 저장은 아니다. 기존 별도 Omni CSV 기록기는 기본 이벤트 방식 그대로다.

## 구현 범위

- 기본 실행은 변경되지 않는다. 새 launcher가 자식 프로세스에만 `G1_OBSERVATION_TAP=1`을 설정한다.
- launcher의 `COMPUTE_HZ=60`, `DISPLAY_HZ=100`에서 각 worker 옵션을 전달한다.
  IK는 검증된60Hz만 허용한다. IK 주기를 변경하려면 별도 검증이 필요하다.
- Omni `--process-hz 60`은 관찰 dry-run에서만 허용한다. 기본값0은 기존 event 방식이다.
- Omni tap은 `--dry-run`에서만 허용한다. discovery/velocity command 송신을 함께 켤 수 없다.
- IK 알고리즘·필터·속도·복귀·PD·모델 파일은 변경하지 않는다.
- tap 송신은 nonblocking localhost UDP이며 실패는 관찰 drop으로 처리한다.
- G1 stdout 및 파일 기록은 bounded 비동기 queue로 분리한다. 화면/파일이 밀리면
  drop 수를 표시하고 수신/ACK를 계속한다. 파일 drop이 있으면 무손실 기록이라고 해석하지 않는다.
- G1은 수신 원문에 대한 SHA256과 전체 packet, 순서·누락 정보를 JSONL로 보존한다.

실행 검증 결과 및 배포 SHA256은 `docs/validation/input_live_observation_20260921/`에
기록한다. generated fixture 시험과 실제 Quest/Omni 사용자 계측을 구분한다.
