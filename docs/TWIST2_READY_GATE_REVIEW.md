# TWIST2 준비 조건 분리 검토

## 최신 로컬 split/relative native 후보 연결 완료 (2026-09-08)

- 기존 native 진단 target과 분리된 g1_twist2_vr_split_candidate CMake target 추가.
  기본빌드 제외(EXCLUDE_FROM_ALL), TWIST2_SPLIT_CANDIDATE 매크로와 명시적
  --vr-relative-candidate 인자 필요. 기존 --vr-right-arm은 기존 의미 유지.
  아래 과거의 "이식 전" 기록은 당시 상태이며, 이번에 로컬 후보까지만 연결했다.
- 후보 ready: 전신 목표-실측 고정오차 대신 1초 관찰 중 q변화폭 .005rad,
  roll/pitch 변화폭 .01rad, dq .1rad/s, gyro .1rad/s, roll/pitch 절댓값 .15rad 사용.
  이는 관찰로그에서 검토한 연구값이며 물리 안전기준으로 검증되지 않았다.
  발목오차가 하중유지에서 생겼다는 해석은 여전히 가설이다. 보상토크 추가 없음.
- SplitSettleWindow는 deque 대신 고정128표본 배열 사용. 초과 시 거부하며 조용히
  표본을 버리지 않는다. 50Hz의 1초 창을 수용하되 실제500Hz writer 지연은 미측정.
- 후보는 writer 기준 고정을 필수화. 첫 active 직전 최신 완료시도의 active/damping/
  SDK accepted/20ms 신선도와 최신 LowState 검사를 확인하고 오른팔 C0를 고정.
  V0는 첫 active Mink 목표, 이후 C0+(V-V0). 최초 명령은 C0 유지.
  첫 VR-실측 .025rad 정렬, 입력/변환한계 .05margin, ±10도, .08rad/s 유지.
  실측을 곧바로 명령으로 덮어 하중오차를 없애는 방식이 아니다.
- 입력처리/관찰창/추론은 command 잠금 밖. commit 시 command 잠금 아래 최신 frame과
  최초 기준의 오른팔 q/kp/kd/feedforward 및 최초 desired q/feedforward를 재비교한다.
  동일 frame의 새 sequence는 허용, 내용변경은 거부 후 기존 latch 경로로 중단.
  이전 writer_reference_study의 "sequence만 변경돼도 거부" 모델과 이 점이 다르다.
  adapter 잠금 안에서 command 잠금을 취하지 않는다. 다른 관절은 기존 소유구조 유지.
- 정책표본 validate_state 뒤 신선도/damping 결과를 adapter에 전달하고 commit에서 다시
  실제 상태검사. writer의 R1/Select/B/CRC/상태·모드·한계/timeout 검사 유지.
  후보에 한해 SDK Write false면 감사기록 뒤 즉시 latch하여 다음 active 쓰기를 막는다.
  accepted는 모터 ACK가 아니다. SDK 실패에서 damping 전달 성공도 보장할 수 없다.
- 검증: MSVC /W4 /WX 후보 결합시험 및 기존 NativeVrPolicyAdapter 회귀시험 exit0.
  최초기준 필수/정확일치, 동일명령 새sequence 허용, 위치·gain·FF 변경 거부,
  SDK거부/damping/빈기준 거부, 최초명령 점프 거부, 창초과 거부와 기존 속도/
  목표초과 없음/다른축 유지/정렬/JSON/해제·오류·latch·timeout 시험 통과.
  기존진단+새후보 WSL SDK/Torch 컴파일·링크 exit0. SDK/Torch 헤더 경고는 존재.
  증거: logs/test_results/twist2_split_candidate_offline_20260908.json,
  logs/test_results/twist2_split_candidate_build_final_20260908.log.
- 기존 물리원본 twist2_right_arm_trial.cpp SHA E61D8A3C...CC09F 그대로.
  G1 전송/파일변경/실행, DDS 실행/publisher 생성, VR 시험 없음. 로컬 컴파일만 했다.
  원격은 이전2af67725...65ef16 진단버전이며 기존 전송 patch에 이번 변경은 없다.
- 다음 필수 항목: 후보 소스 검토 후 새 전송물 준비 및 승인 범위 안에서 G1 빌드,
  VR engage 전 제한된 전신 settle 시험으로 실제 시간지연/ready/중단 동작 확인.
  그 다음 최초 상대명령 연속성 확인 후 작은 VR 이동. 즉시 무제한조작 가능 판정 아님.
  사용자 AI복귀·안정 확인 상태 유지; 현재 상태를 새로 조회하지 않았다.
  /home/unitree/g1_vr_native_review_20260908 임시폴더 추후삭제는 아직 미완료.

## 실제 Controller 연결 검토와 선행 결함 수정

기존 validate_state는 검사대상 LowState와 다른 최신 snapshot의 나이를 검사했다.
로컬 초안에서 state/received를 state_mutex 아래 함께 복사하고 그 received를 검증하도록 고쳤다.
모든5종 호출 경로와 VR receipt 전달을 수정했으며20ms 한계는 유지한다.
오래된표본을 새callback으로 신선하게 만드는 반례/경계/미래시간 시험 및 로컬Linux빌드 통과.
G1에는 미전송이다. 이 결함이 실제3회차에 발생했다거나 ready실패 원인이라는 증거는 없다.

| 연결 지점 | 검토 결과 / 실제 이식 조건 |
|---|---|
| writer/Poll | 현재 command→adapter 순서. adapter→command 역순을 만들지 않는다. |
| 최초 기준/명령 commit | command→adapter→desired 안에서 짧게 처리. 추론을 이 잠금 안에서 하지 않는다. |
| 상태 검사 | R1/Select/B/모드/유한값/온도·fault/관절·속도·신선도를 실제 Controller로 검사한다. |
| writer 기준 | 최신 SDK완료시도·accepted·active·damping·신선도 확인. SDK성공은 로봇ACK가 아니다. |
| torque/rate/joint 제한 | 최종 writer 검사 유지. 불가능한 교집합은 기존 damping 경로 유지. |
| 연구 관찰 창 | deque 메모리할당과 연구임계값은 그대로 실기 승격하지 않는다. |

현재 경로를 읽어 잠금 역순사이클은 찾지 못했지만 경쟁 조건에 대한 완전한 증명은 아니다.
또한 현재 SDK Write false는 기록만 한다. 기준고정 거부와 실제송신 실패 latch는 다른 기능이다.
split/relative adapter를 실제 native에 연결하는 변경은 아직 없다.
최신 로컬 cpp SHA0FAECDC7...B6CCC1, G1 ELF2af67725...65ef16.
기존패치는 신선도수정을 포함하지 않으므로 그대로 최신버전으로 재배포하지 않는다.

## writer 기준 고정의 오프라인 연결

`WriterReferenceStudy`는 실제송신기 대신 메모리에 최신 SDK완료시도를 모델링한다.
sequence가 요청 버전과 같고 최근20ms 이내이며 accepted/active 조건일 때만
mutex 안에서 BindCommandReference와 최초후보 계산을 수행한다. 최신실패에서 이전성공으로
되돌아가지 않으며 성공 후 기준은 다시 잡지 않는다. 기준확인실패는 bind callback을 호출하지 않는다.
외부안전검사 false나 Stop/damping도 거부한다. callback은 writer모델에 재진입하거나 I/O하면 안 된다.

최신유효 오른팔 명령을 시험용 상대adapter의 C0로 고정해 최초출력과 정확히 일치함을 검증했다.
0..21 소유범위는 바꾸지 않는다. stale version/SDK실패/damping/중단/지연/안전검사실패/재기준화
거부와 기존 JSON/정렬/속도/timeout/해제 시험을 통과했다.
증거 logs/test_results/twist2_writer_reference_study_20260908.json, MSVC /W4 /WX exit0.

이것은 실제 Controller 연결이 아니다. 현재 native는 command_mutex를 잡은 writer에서
adapter Poll을 호출하므로, 이식 시 policy가 adapter잠금 안에서 writer잠금을 다시 얻는
역순을 만들면 안 된다. 외부 writer→adapter 순서와 실제 후보 commit을 함께 설계해야 한다.
기존 시험용 생성자baseline 경로는 아직 존재한다. 실제 연결에서는 명시적 reference 고정이
필수여야 하며, 외부검사true 가정과 관찰임계값을 그대로 실기에 승격하지 않는다.

## 상대 정렬 C++ 시험용 결합 완료

후속 단계에서 split_vr_adapter_study의 상체 목표 부분을 AnchoredUpperStudy로 교체했다.
아래 절대입력 유지 설명은 이전 단계의 이력이다. 실제 native/원래 UpperTargetOffline은 그대로다.
최초 검증된 입력 V0와 생성자 명령 C0를 고정하고 `C0+(V-V0)`를 목표로 쓴다.
최초 active 배치는 모두 검증하지만 명령은 이동하지 않는다. 이후 .08rad/s, dt20ms,
입력변화±10도와 변환후 관절한계 .05rad margin을 검사한다.

저장 simulation 패킷 기반 C++ 결합 시험에서 .03rad 하중offset의 첫명령불변,
상대이동/속도/초과방지/다른관절유지/anchor고정, 변환후한계초과 미갱신 및 기존 latch를 확인했다.
MSVC /W4 /WX 빌드·실행 exit0. 증거 logs/test_results/twist2_relative_cpp_study_20260908.json.
실측 하중오차 보상/실제 힘 연속성/전신안정 검증은 아니다.
실기 이식에는 C0를 실제 writer의 마지막 명령과 일치시켜 원자적으로 고정하는 연결이 필요하다.
아직 외부 안전검사 bool과 실제 Controller를 연결하지 않았으며 물리-ready 기준도 승인하지 않았다.

## SDK없는 C++ 결합 검증 완료

`split_vr_adapter_study.hpp`는 기존 native adapter에서 분리한 시험용 사본이다.
`split_settle_window.hpp`의1초 관찰 결과로 후보 ready를 계산하고,
기존 RawInputWatchOffline/InputValidator/UpperTargetOffline을 재사용한다.
시작15초 및 입력250ms timeout, JSON/세션 검증, 해제 latch는 기존 경로에 남는다.
외부 안전검사 실패는 명시적 bool로 전달하며, false면 latch한다. 실기의 안전검사와 아직 연결하지 않았다.

MSVC /W4 /WX 컴파일과 저장 simulation 패킷 시험 exit0. 고정 .03rad 오차의 정지 후보,
초기 engage 거부/정렬 불일치/JSON 오류/외부검사실패/시작timeout/입력timeout/해제,
오른팔 속도 제한과 다른 축 유지 확인. 증거 logs/test_results/twist2_split_cpp_study_20260908.json.

실제 native는 변경하지 않았다. **이 시험은 기존 절대 관절 목표 의미를 유지**한다.
상대 정렬 C0+(V-V0)는 별도 Python 가설에만 존재하며, 이번 C++ 시험은 첫 입력에서
기존 명령과 실측 사이의 오차를 제거하거나 명령 불변을 보장하지 않는다. 기존 .08rad/s 제한으로 접근한다.
따라서 두 가설을 합친 실제 VR 연결 완료로 표현하지 않는다.

## 분리 준비 판정기 오프라인 구현

`split_ready_study.py`는 native에 연결되지 않은 별도 상태 판정 가설이다.
고정 목표오차 .025rad을 전 관절 정지 기준으로 쓰지 않고, 명시적으로 전달한 관찰 한계로
1초간29관절 각도 변화·dq·gyro·roll/pitch와 자세 변화를 검사한다.
첫 VR 입력은 별도로 최신 오른팔 실측과 .025rad 이내인지 검사한다.
R1/Select/B, 비유한값, 상태20ms 지연, 상체 .25rad/1.5rad/s 초과는 중단 latch한다.
실제 CRC/모드/온도/관절 한계/토크/입력 세션/watchdog 판정은 외부 기존 계층의 책임이며
external_checks_passed=False이면 중단한다. 이 bool이 실기에서 어떻게 생성될지는 아직 연결하지 않았다.
15초 시작 제한 및 VR 입력 timeout/세션 처리는 이 모델에 중복 구현하지 않았고 기존 계층에서 유지해야 한다.

시험 가정: window1초, dq .1rad/s, gyro .1rad/s, roll/pitch .15rad,
roll/pitch 구간 변화 .01rad. 관절 구간 변화 한계를 .002/.005/.01rad 세 가지로 비교했다.
이 수치들은 명시적 연구 설정이며 물리 운전용 기본값/검증된 안전 임계값이 아니다.

| 관절 구간 변화 한계 | 최초 정지 후보 | 후보 표본 수 |
|---|---:|---:|
| .002rad | 6.340초 | 420 |
| .005rad | 6.060초 | 434 |
| .01rad | 6.060초 | 434 |

3회차 저장736표본을 사용했다. 외부 검사 통과는 저장된 정상 policy 표본에서 가정했으며
CRC/모드 등을 별도로 모두 재현하지 않았다. 첫 VR목표=실측으로 합성했으므로 실제 VR 정렬 성공이 아니다.
physical_ready는 보고서에서 false다. 기존 실제 ready는 변경하지 않았다.

테스트10개: 고정하중 오차와 정렬 분리, 느린 drift 검출, R1/중단버튼/외부검사/지연/
NaN/상체추종 한계 latch, 움직임/시간단절 후1초 구간 재시작, 오래된 최초정렬 거부.
증거 logs/test_results/twist2_split_ready_tests_20260908.xml 및
twist2_diag3_split_ready_study_20260908.json.

다음 구현은 이 판정 가설을 SDK없는 C++에서 기존 입력/watchdog와 결합해 검증하는 단계다.
실제 native로 옮기기 전에 외부 검사 연결 누락과 시작 timeout/입력 latch 유지 검증이 필요하다.

## 3회차 gyro 포함 재현 결과

실제 gyro가 포함된487개 blend후 표본에서 현재 applied-feedback 정책 출력의
CPU 재현 잔차는 최대2.44366e-6 action이다. 서로 다른 플랫폼과 CSV 정밀도 범위에서
이번 입력/정책 계산을 매우 가깝게 재현했다. 모터 동작이나 폐루프 안정성 검증은 아니다.
raw-feedback 비교의 하체목표 최대 차이는 .01114984rad(10번),4번 .00086561rad.
이전 gyro0가정은 제거했으며, 두 방식은 동일한 저장상태와 저장 이전action을 사용한다.

ready487표본 통과0, 양쪽 어깨16/23 위치조건은 전부 실패했다.
상체437개 중첩 관찰 구간에서 최대각도변화 .0028882rad, 최대속도 .0720971rad/s,
명령변화0인데 목표 오차는 약 .0319rad이다. R1은 앞서736표본과 중단snapshot에서 유지 확인됐다.
따라서 다음 설계는 계속된 고정 위치오차와 실제 움직임을 분리하는 데 초점을 둔다.
현재까지의 결과로 gain/FF/feedback을 변경하거나 실제 ready를 승인하지 않았다.

비교기 gyro필드 선택·배율·누락/부분/비유한값 처리를 테스트3개로 검증했다.
재현 결과: logs/test_results/twist2_diag3_feedback_20260908.json.

## 최초 중단 snapshot 추가 완료

후속 로컬 수정으로 `native_stop_audit.hpp`를 연결했다. 아래 이전 진단 열 설명의
"별도 오류 snapshot 미구현" 상태는 이 단계에서 대체됐다.
최초 latch에서 상태를 메모리에 복사하고 finish 이후 `<policy CSV>.stop.csv`에 저장한다.
writer/policy가 제공한 상태는 supplied_context=1, 최신 수락 상태를 대신 사용하면0이다.
age_at_snapshot_ms는 획득 시점 나이이며 오류 발생 시점의 정확한 지연 측정이 아니다.
reason/planned와 q/dq/tau/rpy/gyro/전압/온도/버튼/상태 코드를 포함하며 총219열이다.
후속 damping으로 덮어쓰지 않는다. CRC에서 거부한 원문, latch 전 시작 실패,
강제 종료/전원상실에 대한 파일 보존은 지원하지 않는다. RF링크 원인 판정도 아니다.
MSVC snapshot·CSV 검증 및 로컬 Linux SDK/Torch 빌드는 통과했다.
G1 미전송/미실행, 실제 중단 기록과 실시간 영향은 아직 미검증이다.

## 다음 기록용 LowState 진단 열 준비

로컬 native 초안의 policy Sample에 `NativeStateAudit`를 추가했다. 해당 policy 추론에 사용한
동일한 LowState에서 다음124개 열을 복사하며, 기존 writer snapshot과는 별도다.

- state_tick/state_crc/state_mode_pr/state_mode_machine/remote_buttons
- gyro_x_rad_s/gyro_y_rad_s/gyro_z_rad_s
- motor_voltage_i/motor_temperature0_i/motor_temperature1_i/motorstate_i (i=0..28)

R1은 remote_buttons & 0x0001, Select는0x0008, B는0x0200이다.
remote_buttons는 수신 상태의 버튼 비트이며 RF 신호세기/링크 품질은 아니다.
motor_voltage는 SDK MotorState.vol 값이며 BMS 잔량/SOC 또는 배터리 건강 판정이 아니다.
전압·온도·상태 진단을 추가했지만 자동 판정 임계값은 바꾸지 않았다.

CSV는 기존 열 뒤에 진단 열을 추가한다. gyro는 policy state, writer_q는 별도 writer state이므로
writer_state_tick과 state_tick을 구분한다. CRC 값은 원래 수신 CRC이며 새 진단기가 검증한 것은 아니다.
기존 callback이 CRC 유효 상태를 수락하고 policy 검증 후 Sample을 만든다.
따라서 유효 정책 표본만 기록되며, 검증 실패를 일으킨 LowState나 전체500Hz 상태를 보존하지 않는다.
오류 직전 버튼 비트/모터 상태가 CSV에 반드시 남는다고 주장하지 않는다. 별도 오류 snapshot은 미구현이다.

`test_native_state_audit.cpp`를 MSVC /W4 /WX로 빌드·실행 exit0.
SDK 클래스만 추출한 기존 fixture로 29축 열 순서·값·signed 온도·32bit tick·remote bit와
원본 상태 변경 후 snapshot 불변을 확인했다. Linux SDK/Torch 로컬 컴파일·링크 exit0.
G1에는 미전송/미빌드/미실행. 새 기록의 실시간 부하와 실기 값은 아직 확인하지 않았다.
증거 `logs/test_results/twist2_state_audit_build_20260908.log`.

## 하체 및 공식 배포 코드 교차 검토

공식 amazon-far/TWIST2 commit `d5c7108e9ef82d1b8770e5b692f27a1294f3aa8a`의
[g1.yaml](https://github.com/amazon-far/TWIST2/blob/d5c7108e9ef82d1b8770e5b692f27a1294f3aa8a/deploy_real/robot_control/configs/g1.yaml),
[배포 루프](https://github.com/amazon-far/TWIST2/blob/d5c7108e9ef82d1b8770e5b692f27a1294f3aa8a/deploy_real/server_low_level_g1_real.py),
[wrapper](https://github.com/amazon-far/TWIST2/blob/d5c7108e9ef82d1b8770e5b692f27a1294f3aa8a/deploy_real/robot_control/g1_wrapper.py)를 읽고 비교했다.
다운로드한 파일은 logs/test_results/upstream_twist2_*에만 저장했으며 실행하지 않았다.

- joint2motor_idx 0..28, 기본각, Kp/Kd 배열은 로컬 common.hpp와 자동 비교 일치.
  gyro .25, q오차1, dq .05, 발목 속도0 처리, action .5, history10 및 관측 구성도 일치한다.
  공식 파일의 `1402` 주석은 산술 오류이며 식127*11+35는 로컬과 같은1432다.
- 공식은 policy raw output을 last_action에 저장한 뒤 ±10 클립하고29축을 적용한다.
  로컬은 ±2 클립, 하체 출력과 고정/VR 상체를 합친 뒤 그 목표를 action으로 환산해 history에 넣는다.
  기존 프로젝트의 의도적인 hybrid 차이이며 발견만으로 버그/무조건 수정 대상으로 판정하지 않는다.
  2회차 저장 action 최대절댓값1.60294여서 관측된 native action saturation은 없다.
- 2회차 blend 이후 기록에서 정책 출력과 재환산 feedback 차이는 상체 최대 .211045 action단위,
  하체는 float 오차 수준이다. 전신 정책의 상체 출력이 실제 적용되지 않는다는 구조 차이가 남는다.
  공식 배포는 ONNX를 사용하며, 이 비교만으로 로컬 TorchScript의 변환 동등성까지 증명하지 않았다.

`compare_feedback_recorded_offline.py`로 검증된 로컬 정책 SHA를 확인하고 CPU 비교했다.
490개 blend 이후 표본에서 raw/applied previous-action과 그 history만 다르게 구성했다.
gyro는 CSV에 없어 양쪽0, 이전 action은 저장값을 공급한 비교이므로 폐루프 재현이 아니다.
예측 하체 목표 차이는 최대 .013791rad(10번), 4번 .000914rad이었다.
이 가정 아래 입력 의미 차이에 민감함을 보였지만, 실제 .3–.4rad 발목 오차의 단독 원인을
확정하거나 feedback 변경이 안전하다는 결론을 낼 수 없다. 현재 feedback은 변경하지 않았다.

2회차 blend 이후490표본의 하체 전체 구간 q범위 최대 .004892rad,
최대 |dq| .073709rad/s. 같은 writer 시점의 PD+FF 예측 토크 기준으로
4/10번은 최대16.555/12.417Nm, 소프트 한계25Nm까지 표본 여유8.445/12.583Nm이었다.
이는 소프트웨어 계산 여유이며 배터리 전압·실제 토크 용량·접촉 안정 여유가 아니다.
50Hz 표본 밖의500Hz 제한 개입을 배제하지 않는다.

### 실제 연결 전 남은 핵심

1. 전신 정책을 hybrid로 사용하는 현재 previous-action 의미와 상체 명령 경로를 유지할지
   별도 비교로 결정해야 한다. 임의로 공식 raw feedback으로 바꾸지 않는다.
2. 하체/상체의 움직임 관찰과 첫 VR 정렬을 분리하는 것은 타당한 설계 방향이지만,
   관찰 수치만으로 새로운 물리 ready 임계값은 확정되지 않았다.
3. 다음 실기록이 필요하면 상태 gyro·전압/배터리·상태 건강과 명령/입력 진단을 같은 시간축에
   보존해야 한다. 지지대 하중은 별도 현장 조건으로 기록해야 한다.
   같은 조건의 물리 시험을 반복하는 것만으로 위 누락이 해결되지는 않는다.

증거: twist2_lower_policy_review_20260908.json(공식 파일 해시/자동 배열 비교 포함),
twist2_feedback_sensitivity_20260908.json. CPU 비교 exit0, 정책 shape/finite 검증 완료.
NumPy 미설치 경고는 있었지만 이 스크립트는 NumPy를 사용하지 않는다. 원격 실행/제어 수정 없음.

## 하중 후 상체 관찰 결과

`review_loaded_settle.py`는 blend 완료 이후 신선하고 연속된 표본을 약1초 구간으로 묶는다.
구간 내 최대-최소 각도, 최고 속도, 몸체 roll/pitch 변화, 상체 명령 변화 및 목표 오차를
각각 기록한다. 통과 임계값이나 실제 ready 결정은 추가하지 않았다.
최대 표본 간격50ms는 분석용이며 실제 상태 신선도20ms 조건과 구분한다.
구간 길이는 적어도1초이며 시작쪽 표본 간격만큼 길 수 있다. 구간들은 서로 중첩된다.

| 기록 | 완성된 중첩 구간 | 상체 각도 변화 최대 rad | 상체 속도 최대 rad/s | 몸체 자세 변화 최대 rad | 상체 명령 변화 |
|---|---:|---:|---:|---:|---:|
| 1회차 | 322 | .001354 | .042854 | .002735 | 0 |
| 2회차 | 440 | .004266 | .047553 | .001417 | 0 |

구간별 최대 목표 오차는 1회 .032441–.032465rad, 2회 .032142–.032178rad이다.
고정 오차와 실제 각도 변화는 다른 양이며 기존 all29 ready는 전자를 막고 있었다.
이는 지지된 상체의 작은 움직임을 관측한 결과이며, 전신 균형·하중 지지·자유 상태 안전을
검증한 결과가 아니다. 몸체 각속도/접촉 하중/토크 여유 판정은 이번 관찰기에 없다.

검증7개 통과: 정지 오차 분리, 속도값0이어도 느린 drift 검출, 구간 중간 왕복 변위 검출,
지연/NaN/시간 단절/blend 중 표본으로 구간 초기화. 재현:
`py -3.11 -m pytest experiments/twist2_right_arm_manual/test_review_loaded_settle.py -q`
실기록 결과는 `logs/test_results/twist2_trial1_loaded_settle_20260908.json` 및
`twist2_trial2_loaded_settle_20260908.json`. 각 구간의 실제 span도 저장한다.

오프라인에서 확인한 것은 (1) 고정 오차의 존재, (2) 상체의 작은 움직임,
(3) 상대 정렬 시 첫 명령 연속성이다. 다음 실제 연결용 설계에서 이 세 조건을 별도로 표시해야 한다.
현재 자료만으로 하체 안정 기준을 확정하거나 공통 중단 조건을 제거할 수는 없다.

## 어깨 하중 유지 오차의 추가 근거

2회차 writer 표본을 구간 평균으로 비교했다. 아래 오차는 `writer_target-writer_q`이며
P 토크는 기록된 Kp와 같은 writer 시점의 오차로 계산했다.

| 구간 | 왼 어깨16 FF Nm | 왼 어깨 오차 rad | 오른 어깨23 FF Nm | 오른 어깨 오차 rad |
|---|---:|---:|---:|---:|
| capture .2–.9초 | 1.4375 | .000093 | -1.4375 | .000022 |
| blend 1.5–2.5초 | 1.2133 | .002946 | -1.2133 | -.000134 |
| blend 3.5–4.5초 | .2477 | .026287 | -.2477 | -.019541 |
| 정지 구간8–14초 | 0 | .032142 | 0 | -.030618 |

마지막 구간의 P 토크는 +1.286Nm/-1.225Nm이다. 코드에서 전체29축에
`feedforward=(1-alpha)*capture_tau`를 적용하며 상체도 4초 blend 동안 보상이 사라진다.
이 기록은 **FF 감소 뒤 위치 오차로 하중 토크를 만드는 설명과 부합**한다.
접지/지지 하중과 동역학 변화가 분리되지 않았으므로 단독 원인 확정이나 중력 토크 측정은 아니다.
상체 정책 출력은 사용하지 않으므로 상체용 정책이 별도 보상을 만들어 주는 경로도 없다.

### 설계상 결론

- 현재 .025rad 준비 조건은 Kp40에서 P 토크1Nm까지의 오차만 허용한다.
  이번 정지 구간의 양 어깨 P 토크는 이를 넘는다. 상대 입력 정렬만 추가해도
  기존 상체 준비 조건은 그대로 실패하므로 실제 연결용 수정으로 충분하지 않다.
- 최초 capture 추종, 하중 후 정지 상태, 첫 VR 목표 정렬을 분리해 다뤄야 한다.
  정지 상태 판정에는 자세 변화와 속도뿐 아니라 명령/토크 여유와 지지 조건이 필요하다.
  하중 후 자세 기준을 관찰용으로 잡더라도 기존 명령을 그 실측값으로 즉시 덮어쓰지 않는다.
  오차를 없애기 위한 덮어쓰기는 현재 하중 유지 P 토크까지 바꾼다.
- capture_tau는 초기 추정 토크이며 순수 중력 보상이 아니다. 이를 움직이는 팔에 고정 적용하거나
  gain을 높이는 변경은 이 기록으로 정당화되지 않는다. 이번에 FF/게인/ready를 바꾸지 않았다.
- 다음 구현은 실제 제어 변경보다 **하중 후 상체 정지 구간을 별도 관찰하는 상태 진단**으로 제한한다.
  현재 로그를 통과시키도록 허용 오차를 늘리는 수정은 하지 않는다.

증거: `logs/test_results/twist2_trial2_load_transfer_20260908.json`.
실제 로봇 재실행 없이 35/50/50/300 표본의 구간 평균을 계산했다.

## 오프라인 정렬 가설 검증 추가

`anchored_alignment_study.py`는 별도 Python 메모리 모델이다. native C++에 연결하지 않았다.
명령 기준 C0는 진입 직전 명령, 입력 기준 V0는 최초 검증된 VR 관절값으로 한 번만 고정한다.
첫 입력은 신선한 실측 M과 |V0-M|<=.025rad을 검사하되 출력 C0를 유지한다.
이후 후보 목표는 `C0 + (V - V0)`이고 매 새 입력마다 최대 `.08 * min(dt,.02)`만 이동한다.
원래 command 기준 ±10도와 매핑 후 관절 한계를 함께 검사한다. 0..21 값은 메모리 모델에서 유지한다.

이는 **절대 관절값 직접 추종에서 상대 변화량 적용으로 의미가 바뀌는 가설**이다.
Mink/Unity의 절대 목표와 C++ 목표가 계속 같다는 주장을 할 수 없다.
C0-M 하중 오차를 보존하며 보상하거나 없애지 않는다. 첫 위치 명령의 연속성만 확인했고
이후 힘 변화·실제 안정성·상체 유지 문제·몸체 ready를 해결하지 않았다.

2회차 CSV에서 10초 이후 한 표본의 writer 명령/실측을 사용하고 첫 입력은 실측과 같도록
합성했다. body_ready=True도 시험 가정이다. 실제 VR 패킷이나 준비 승인으로 해석하지 않는다.
모델은 기존 JSON 검증, CRC, R1, session 원문 신뢰성, source age 검증을 대신하지 않는다.
호출자는 검증된 입력을 제공해야 하며, 여기서는 세션·순서·실측 신선도·결측 freeze/
250ms timeout·해제/오류 latch·유한값·매핑 한계만 메모리 상태에서 검증한다.
몸체 준비의 물리 기준이 미확정인 동안 이 모델을 실제 adapter에 이식하지 않는다.

재현: `py -3.11 -m pytest experiments/twist2_right_arm_manual/test_anchored_alignment_study.py -q`

2026-09-08. 오프라인 설계 검토이며 제어 코드에 적용하지 않았다.
G1은 사용자 확인상 전원이 꺼져 있다. 두 시험은 어깨 지지 조건이며 2회차 양발 접지는
사용자가 확인했지만 지지대와 발의 하중 분담은 측정하지 않았다.

## 저장 로그 비교

기존 조건을 이전 policy행 목표 기준으로 재계산했다. 후보 body proxy는 기존 arming의
roll/pitch 각 .15rad와 하체 속도 .1rad/s만 조합한 진단용이다. 균형 검증 기준이 아니다.
연속 구간은 50Hz 표본 사이의 관측 구간이며 완전한 실시간 재현이 아니다.

| 구분 | 1회차 | 2회차 |
|---|---:|---:|
| 유효 blend 이후 표본 | 373 | 490 |
| 기존 전 관절 준비 조건 통과 | 0 | 0 |
| body proxy 통과 표본 / 최장 구간 | 369 / 7.36초 | 490 / 9.78초 |
| 허리·왼팔 기존 추종 조건 통과 | 0 | 0 |
| 오른팔 기존 추종 조건 통과 | 373 | 0 |
| body proxy + 기존 상체 조건 통과 | 0 | 0 |

하체 위치 오차를 무시하는 변경만으로는 두 시험 모두 준비되지 않는다.
왼쪽 어깨 roll 16번은 두 시험에서 지속적으로 .025rad을 넘는다.
오른쪽 어깨 roll 23번도 2회차에서 약 .0306rad의 정지 오차를 보인다.
1회차 오른팔 조건 통과가 실제 VR 최초 패킷 정렬 성공을 뜻하지 않는다.

## 제안하는 책임 분리

1. **공통 중단 조건:** R1, Select/B, CRC/진행 tick/상태 신선도, 모드·모터 건강,
   관절 한계, writer/policy watchdog, 명령 제한, 해제 후 latch를 그대로 유지한다.
   준비 판정과 독립적으로 모든 단계에서 적용한다.
2. **몸체 안정 관찰:** 하체 목표와 실제 각도의 일치를 곧바로 균형으로 해석하지 않는다.
   자세·각속도·관절 속도 및 일정 시간의 자세 변화, 토크 여유와 제한 개입을 함께 관찰한다.
   발 접촉과 지지 조건도 명시한다. 현재 CSV는 gyro/접촉 하중/전체 writer 이력을 갖추지 않아
   이것만으로 새 기준을 확정할 수 없다. .15rad/.1rad/s proxy 통과는 진단 정보에 한정한다.
3. **허리·왼팔 유지:** 초기 명령과 하중 후 실측 사이의 정지 오차를 별도 진단한다.
   기존 .25rad/1.5rad/s 상체 중단 기준은 준비를 승인하는 기준으로 전용하지 않는다.
   지지대 고정 상태에서 조용하다는 이유만으로 자유 상태의 안정성을 주장하지 않는다.
4. **오른팔 최초 정렬:** 첫 active VR 목표와 신선한 오른팔 실측의 .025rad 비교를 유지한다.
   최초 capture 명령에 대한 추종 오차와 VR 목표-실측 초기 오차는 서로 다른 검사다.
   현재는 capture 시점 목표를 계속 유지하므로 하중 후 자세와 차이가 날 수 있다.
   실측 기준 재정렬을 도입한다면 명령 연속성, 힘 변화, .08rad/s 제한, 세션별 기준 고정,
   시작 상대 범위가 함께 검토돼야 한다. 매 tick 재기준화나 목표 점프는 제안하지 않는다.

## 구현 순서와 통과 조건

- 우선 위 항목을 독립적인 진단 사유로 계산하는 오프라인 관찰기를 유지한다.
  실제 ready 출력은 아직 기존 조건을 사용한다. 이번 분석기는 publisher/네트워크가 없다.
- 다음 구현 검토 대상은 **최초 capture와 하중 후 실측의 두 기준을 명시하는 정렬 상태 설계**다.
  첫 active 입력을 저장 로그에 합성해 위치 점프 없음, 갱신 속도, 해제·오류 latch,
  잘못된 세션/오래된 실측 거부를 먼저 검증한다. 합성 결과를 live 입력 승인으로 쓰지 않는다.
- 몸체 기준 확정에는 현재 관찰 데이터의 누락과 지지 조건을 해결해야 한다.
  로그를 통과시키기 위한 임계값 맞추기, gain 증대, feedforward 변경은 이번 범위가 아니다.
- 물리 재시험은 별도이며 이번 설계 문서가 실행 승인을 대신하지 않는다.

## 재현

PowerShell에서 프로젝트 루트 기준:

```powershell
py -3.11 -m pytest experiments/twist2_right_arm_manual/test_review_ready_components.py -q
py -3.11 experiments/twist2_right_arm_manual/review_ready_components.py logs/test_results/twist2_writer_trial2_20260908.csv --output logs/test_results/ready_review_new.json
```

출력 파일은 덮어쓰지 않는다. 새 파일명을 사용한다.
분석기는 이전행 목표, 비유한 값/오래된 상태/시간 단절, 팔 오차가 남는 사례를 3개 테스트로 검증했다.
증거는 logs/test_results/twist2_trial1_ready_components_20260908.json 및
twist2_trial2_ready_components_20260908.json이다. 원본 물리 C++와 native adapter는 변경하지 않았다.
