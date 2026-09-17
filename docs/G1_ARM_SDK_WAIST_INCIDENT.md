# Arm SDK weight 증가 시 허리 기울어짐

작성일: 2026-09-07. 기존 Windows 저장 로그를 재분석했다. 새 로봇 시험은 하지 않았다.

## 확인된 현상

사용자가 실제 몸통 기울어짐을 관찰했다. 아래 시험은 VR 목표 추종이 아니라
시작 양팔 자세를 유지하는 Gate6 HOLD였다. 기록된 명령 표본에서 팔15..28의
목표 변경량은 세 시험 모두0deg다. 따라서 움직이는 VR/IK 목표가 없어도
이 현상이 발생했다. 다른 전신 제어 요인까지 배제한 것은 아니다.

| 최대 weight | 명령 표본 수 | 허리 yaw 변화 폭 | roll 변화 폭 | pitch 변화 폭 | 종료 fault |
|---|---:|---:|---:|---:|---|
| 0.6 | 36 | 0.017648deg | 0.183812deg | 0.111332deg | 없음 |
| 0.8 | 36 | 0.021484deg | 0.190804deg | 0.180854deg | 없음 |
| 1.0 | 32 | 0.167271deg | 5.186992deg | 5.048893deg | base speed 초과 |

집계는 events.jsonl에서 sampled_command가 존재하는 행만 사용했다.
각 축 변화 폭은 그 표본의 max(q)-min(q)이며 IMU 몸통 기울기나 시작각 대비
최대 편차가 아니다. READY/종료 행을 포함한 과거 집계와 소수값이 다를 수 있다.
약4Hz 상태 로그이므로 전체250Hz 송신/실측의 최대값을 보증하지 않는다.
낮은 weight에서 fault가 없었다고 해당 설정의 안전성이 확립된 것은 아니다.

## 명령 구성

- 클라이언트: Windows 프로젝트의 WSL Python SDK2/DDS, 당시 인터페이스 eth2.
- 출력 rt/arm_sdk, 입력 rt/lowstate. MotionSwitcher 조회 form=0/name=ai.
- 관측 mode_pr=0, mode_machine=5. 이 숫자만으로 소유권을 판정하지 않는다.
- 설정250Hz, acquire3초/HOLD3초/release3초, 종료 zero-weight25회.
- 양팔15..28: 시작 실측각 고정, mode1. 어깨/팔꿈치 kp80/kd3,
  손목 kp40/kd1.5. 허리12..14: 각 프레임 실측q, mode/kp/kd/dq/tau 모두0.
- slot29.q: 전체 실행에서 사용하는 단일 weight. 관측104개 명령 표본 모두
  허리 mode/kp/kd=0 확인. 이것이 Regular 허리 유지라는 뜻인지는 미확인이다.

## weight 1.0 시험 시간 흐름

- 첫 HOLD 표본 11:59:25: 허리 roll+0.494deg, pitch-2.127deg.
- 마지막 HOLD 표본 11:59:28: roll+5.401deg, pitch-6.487deg.
  즉 weight 감소를 시작하기 전부터 변화가 있었다.
- RELEASE 중 runtime base speed0.157m/s가 제한0.150m/s를 넘어 fault.
  이는 프로그램이 보고한 중단 원인이지 기울어짐의 근본 원인 판정은 아니다.
- fault release 기록: zero25회 성공, 마지막 write weight0,
  external_authority_handoff_confirmed=false.
- 최종 상태 기록의 lowstate_age_s는3.1116초다. 종료 시 저장 자세가 실시간
  회복 확인이라는 해석은 불가하다. Write 성공도 firmware 인수 확인이 아니다.
  사용자는 시험 후 안정된 자세라고 설명했으며 이는 별도의 육안 관찰이다.

## 가능한 원인과 아직 모르는 것

허리 zero gain과 공유 weight 처리의 조합이 허리 지지를 바꾸었을 가능성을
조사 중이다. firmware 수신/혼합 규격을 확보하지 못했으므로 원인 확정은 아니다.
SDK 버전과 로봇 제어 firmware 버전은 구분해야 한다. 제어 firmware 버전은 미확인.
현재 확보한 송신 코드만으로 오른팔 단독 제어권 선택 기능을 입증할 수 없다.

## 공식 지원에 확인할 질문

1. G1 29DoF/3DoF 허리 Regular에서 rt/arm_sdk slot29 weight는 어느 관절에 적용되는가?
2. 오른팔22..28만 SDK에 위임하고 허리12..14 및 왼팔15..21을 Regular에 남기는 지원 방식은?
3. 허리 mode=0, kp=kd=0의 처리 의미는 명령 무시인가, 지원 토크 감소인가, 다른 처리인가?
4. 허리도 SDK HOLD가 필요하다면 현재 firmware의 권장 mode/PD/전환/반환 절차는?

기존 A/B 코드에는 시작 허리각 HOLD가 있지만 감시 및 종료 보호가 부족하다.
static_stand는 Regular를 해제하고 TWIST2/rt/lowcmd로 전신을 제어하므로
그 게인이나 성공 결과를 현재 arm_sdk 경로에 그대로 적용할 수 없다.
답변과 적용 조건을 확인하기 전, 기존 기울어짐 경로의 재실행은 보류한다.

## 근거 파일

프로젝트 루트 기준 아래 각 디렉터리의 config.json, events.jsonl, hold.log,
status.json을 함께 확인한다. 원본은 변경하지 않았다.

- logs/physical_tests/gate6_hold_20260907_115747_b771ceae (0.6)
- logs/physical_tests/gate6_hold_20260907_115826_a9a710e8 (0.8)
- logs/physical_tests/gate6_hold_20260907_115904_a84b17e7 (1.0)

명령 구현: hardware/g1_arm_bridge/arm_sdk_hold_contract.py의
build_measured_hold_frame 및 gate6_arm_sdk_hold.py의 _apply_frame.

## 이번 작업

- 검토: 저장3회 시험을 동일한 표본 조건으로 재집계하고 명령/실측/종료 증거 구분.
- 코드 수정: 없음. 보고서와 CHAT_HANDOFF만 갱신.
- 테스트: JSON 파싱/수치 재집계 및 문서 diff 검사. 새 물리/WSL/DDS 실행 없음.
- 남은 항목: firmware 규격/버전 확인과 허리 HOLD 물리 조건 검토. 문의는 아직 발송하지 않음.
