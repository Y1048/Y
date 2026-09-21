# 양팔·Omni 입력 50Hz 콘솔 모니터

## 실행

프로젝트 폴더의 CMD 또는 PowerShell에서:

```powershell
.\tools\PRINT_G1_INPUTS_50HZ.bat
```

양팔 시뮬레이션은 기존 방식대로 실행한다. Omni 값이 필요하면 Omni Connect 연결 후
별도 창에서 기존 읽기 전용 Gateway를 실행한다:

```powershell
.\tools\START_OMNI_GATEWAY_READONLY.bat
```

이미 Omni CSV를 기록 중이면 Gateway를 중복 실행하지 않는다. 모니터는 최신 양팔
`logs/test_results/bimanual/unity_*.jsonl`과 최신 Omni CSV
`logs/test_results/omni_timeseries/*.csv` 또는 `omni_gateway_readonly/*.csv`를 자동 선택한다.
새 세션 탐색은 1초마다 한다. 다른 파일을 보려면 --arm-log / --omni-csv로 지정한다.
출력만 종료하려면 모니터 창에서 Ctrl+C. 원래 입력/제어 프로그램에는 영향을 주지 않는다.

## 출력

매 줄은 JSON이며 display_sequence, display_monotonic_s, arm, omni로 구성된다.
- arm.values.left_q_rad / right_q_rad: 각 7개 관절각 rad.
- 각 팔 순서: shoulder_pitch, shoulder_roll, shoulder_yaw, elbow, wrist_roll, wrist_pitch, wrist_yaw.
- arm: input sequence / feedback_sequence / session / state / reason.
- omni.values: mx, my, arm_yaw_deg, omni_yaw_rate_deg_s, vx, vy, yaw_rate,
  yaw_diff_deg, yaw_step_diff_deg, calibrated, sample_sequence.
- vx,vy 단위 m/s, yaw_rate rad/s. *_deg는 degree, *_deg_s는 degree/s.
- source_age_s: 로컬 monotonic 시각과 기록된 원본 시각의 차이.
- log_revision: 읽은 새 유효 sample 수. display_sequence만 증가하고 log_revision이
  같으면 이전 값을 반복 표시한 것이다.
- FRESH_LOG: 새로 읽은 원본 시각/갱신이 0.75초 이내. 제어 승인/전송 승인 아님.
- STALE: 원본 값 또는 새 기록 수신이 0.75초 이상 오래됨.
- HISTORICAL: 실행 전 존재하던 저장값. 실시간 수신으로 간주하지 않는다.
- WAIT: 파일/값을 기다리는 중. INVALID: 잘못된 schema/배열/수치로 값 표시 중단.
- CLOCK_MISMATCH: 원본 시각이 현재보다 미래. 재부팅 전후 monotonic 시계는 비교 불가.

**50Hz는 화면 출력 목표 주기다. 입력 샘플링·UDP 송신·G1 수신 주기를 변경하지 않는다.**
입력이 60Hz이면 화면은 그중 최신값만 보며 중간 표본을 모두 출력하지 않는다.
소스 로그 buffering 때문에 표시가 늦을 수 있다. 실제 동작 주기의 정밀 계측기로 사용하지 않는다.
콘솔/디스크 속도가 부족하면 50Hz보다 느릴 수 있으며 누락 화면을 몰아서 출력하지 않는다.

## G1 수신 여부

현재 양팔 14축 경로는 simulation-only이고 Arm Relay의 기존7축 실물 패킷과 다르다.
이 모니터는 기존 로그만 읽고 socket/SSH/SDK/DDS/새 publisher/모터출력을 생성하지 않는다.
`g1_rx=UNVERIFIED`, `arm_stage=SIMULATION_IK_NOT_G1_TX`,
`omni_stage=MAPPED_LOG_NOT_DELIVERY_ACK`를 항상 표시한다.
따라서 이 화면으로 G1이 수신했다거나 실행했다고 확인할 수 없다.
실제 수신 확인에는 추후 양팔 수신기에서 session/sequence와 수신값을 출력하거나 ACK가
필요하다. 현재 Omni CSV에도 packet delivery ACK는 없다. 아직 G1 수신 검증 미완료다.

## 검증

4개 unittest 통과: 14축 순서/finite 검증, 부분 기록/history/fresh/stale/invalid,
CSV 따옴표 및 multiline/부분쓰기, network/process-control import 부재.
기존 과거 PC 로그 2초 출력 smoke: 96줄, 약49.843Hz. 모든 스트림 HISTORICAL,
G1_RX UNVERIFIED를 확인했다. 실제 Omni/Quest 새 입력 및 G1 수신은 이번에 시험하지 않았다.
실행 파일은 runtime에 신규 2개만 설치한다. 기존 controller/relay/gateway 파일 변경 없음.
