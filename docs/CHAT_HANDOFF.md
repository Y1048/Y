## 2026-09-21 노트북 실행본 이식성 동기화 완료

이 기록이 아래의 "dirty Desktop runtime에 미설치" 안내를 대체한다. 원격을 fetch하고
`codex/g1-laptop-sync-20260917`의 `30dc8a546a1d32cff10a5c4e18e65b42c08ad4ff`와 canonical source가 일치함을 확인했다.
노트북 `C:/Users/user/Desktop/G1_Teleop_Project`에 사용자 승인으로 실행/설치/카메라 관련 13개 파일과 .gitignore 로컬환경 제외 규칙을 반영했다.
기존 파일 백업: `logs/backups/portable_runtime_20260921_170246/manifest.json`.
13개 source 파일 SHA256 일치, 다른 Unity/IK/hardware 코드 181개 SHA256 보존 확인.
Desktop Git branch/reset/clean/pull은 수행하지 않았다. 기존 dirty 수정은 유지한다.

노트북 프로젝트에서 `py -3.11 -B tools/SETUP_G1_VR_TELEOP.py --pc-only` 실행으로
`.venv-teleop` 신규 설치, pip check 및 전체 IK import/model construction 통과.
`cmd.exe /d /c tools\SETUP_G1_VR_TELEOP.bat --check-only`도 통과: Windows 의존성과 WSL camera SDK import만 확인했다.
기존 WSL 전용 camera 환경 재사용, running `wslinfo --networking-mode`=mirrored 확인; 설정/재시작 없음.
오프라인 pytest: test_g1_portable_environment, test_g1_vr_teleop_launch, test_g1_ssh_login,
test_g1_quiet_observation, test_g1_observation_tap 합계 49 passed / 41 subtests passed.

이제 노트북에서도 옵션 없는 START_G1_VR_TELEOP는 유선주소 우선/폐쇄망 fallback이며,
명시적 --host는 해당 주소를 사용한다. WSL 기본 배포판 또는 G1_WSL_DISTRO를 사용한다.
G1 SSH/키등록, SDK/DDS 초기화, 카메라 영상, VR 실착, 모터 실행은 이번 검증에서 하지 않았다.
새 PC도 최신 브랜치 checkout과 최초 setup/device 연결은 필요하다.

## 2026-09-21 Omni 몸 회전의 Unity 반영

`docs/OMNI_UNITY_BODY_HEADING_20260921.md` 참고. Omni yaw를 loopback55072로 별도 전달한다.
XR와 주변환경에 inverse body yaw를 적용해 fixed-base IK 좌표를 유지하며 작업방향 회전을 표시한다.
전체 G1Teleop C# 컴파일, production gate20 assertion, Python28 테스트 통과.
Quest/Omni 실착 및 양팔 목표 유지 체감은 미확인. 실제 로봇 제어/PD 변경 없음.

## 2026-09-21 자동 네트워크 선택 및 설치 검증 완료

`START_G1_VR_TELEOP.bat`은 유선주소 192.168.123.164:22 우선, 불가 시 폐쇄망 192.168.10.165:22를 선택한다.
명시적 --host는 자동 선택을 덮어쓴다. 입력 worker와 카메라에 같은 주소 전달. 두 주소 불가 시 창 생성 전 중단.
최초 `SETUP_G1_VR_TELEOP.bat` 실행: 프로젝트 전용 고정 Windows 패키지 + WSL 전용 카메라 SDK 설치.
.wslconfig mirrored 항목은 원본 백업 후 병합하며 자동 WSL shutdown은 하지 않는다.
Windows/WSL 새 환경 설치와 재실행, check-only, 오프라인 48개 검사 통과. 실제 영상은 미검증.
노트북 네트워크 점검 시 10.1.119.101/172.20.10.5였고 G1 두 주소 TCP22 연결불가. NIC/방화벽 변경 없음.
현재 사용 중인 dirty Desktop runtime에는 설치/덮어쓰기 하지 않았다. source checkout에서 검증했다.

## 2026-09-21 PC 환경 이식성 개선

최신 설치/실행 안내는 `docs/PORTABLE_TELEOP_SETUP.md`다.
`SETUP_G1_VR_TELEOP.bat`으로 PC별 전용 환경을 준비하고 동일 START 배치를 사용한다.
카메라의 노트북 절대경로·Ubuntu 이름·192.168.123.99 고정을 제거했다.
최초 Python/Unity/Meta Link/Omni Connect/WSL 및 mirrored LAN 설정은 각 PC에 필요하다.
아래의 고정 경로 관련 설명은 이전 상태의 기록이다. IK/게인/프로토콜은 변경하지 않았다.

# G1 Teleop Project Chat Handoff

## 2026-09-21 다른 데스크톱 이전 체크포인트

최신 진입 문서는 `docs/DESKTOP_INPUT_HANDOFF_20260921.md`다.
사용자는 FOV/시점/화면배치를 그대로 유지하고 현재작업을 GitHub에 push하도록 요청했다.
현재 범위는 양팔14축3rad/s·3rad/s²와 Omni 입력 전달/관찰이다. 실제PD 변경·모터제어 없음.
양팔실착3회추적·2회재engage·3회복귀와 로컬수신무손실 확인; Omni 실제보행은 미확인이다.
노트북원본logs/설치환경은Git에없으며 카메라 고정경로/WSLvenv는새PC에서확인해야한다.
아래항목들의 '이번commit/push없음'은 각작업당시이력이다. 이번에는 이변경을공용브랜치
`codex/g1-laptop-sync-20260917`에묶어게시한다. main/dirty Desktop실행작업본은건드리지않는다.

## 2026-09-21 다음 단계 — 새 3/3 양팔 + Omni 전달 검사와 로컬 실입력 준비

사용자는 Quest·Omni만 사용할 수 있다고 답했다. G1/카메라는 실행하지 않고
PC localhost127.0.0.1:55070에 동일 관찰 수신기를 열어 send/omni/arm과 연결했다.
모터 제어·실제 PD 변경 없음. 관련 source/runtime14파일SHA 일치, runtime3/3 확인.
원본 복사·Omni 좌표 변환·clocked 검사40개, 실제 계산프로그램→로컬수신기 연결2개 통과.
생성 fixture 양팔419개/Omni415개 표본 정확일치, 수신59.9857Hz·표시100Hz.
생성 입력으로 검증했으며 G1 수신/물리 검증은 아니다. 실제 새3/3 실착 결과는 대기 중이다.

로컬 시작20260921_152630_958214. 수신 로그:
`logs/test_results/input_local_live/20260921_152630_958214/received_observation.jsonl`.
양팔`unity_20260921_152631_628857.jsonl`, Omni`omni_observation_20260921_152631_589019.csv`.
시작 시 두 생산자FRESH_LIVE, Omni calibrated=true, 양팔ready/Unity WAIT 확인.
Unity Play 후 동시 보행·양팔 움직임·pinch복귀·재engage를 요청했다.
현재 네 관찰 창을 유지한다. G1 대상으로 다시 시작하기 전 이 localhost 창을 닫는다.
관찰 창 종료는Ctrl+C/창닫기이며 실제 제어기와 무관하다. 로그자동삭제 없음.

검증증거 `docs/validation/input_limits_integration_20260921/`.
PD연구후보는 여전히 미확정, recommended_hardware_gains=null.
production코드 수정 없음. 기존 pipeline테스트만 검증을 보강했고 소스에 저장했다.
sourceHEAD/origin31a5df6동일,dirty보존,이번commit/push없음.

### 실입력 확인 결과 (2026-09-21 15:31 스냅샷)

사용자는 시험을 완료했다고 알렸다. 실제 Quest/Unity 입력과 MuJoCo 목표값을
로컬 수신 로그에서 대조했다. 양팔 tracking3회, 재engage2회, pinch복귀3/3완료,
최종READY, BLOCKED/solver/return fault0. 최대목표속도1.364523rad/s,
최대목표가속도3.000000000000469rad/s²(수치오차), tracking계산p95 7.882ms,
최대10.860ms, deadline miss0. 실제 G1관절 측정값이 아니다.

로컬수신seq0..15655(15,656개),59.99877Hz,순번누락/역전/reject/로그drop0.
양팔15,544개·Omni15,647개 전달값이 생산자 원본과 정확일치했다.
다만 Omni원본mx=-0.05,my=0.27이전구간고정,armYaw112.37~112.79°,
vx/vy/yaw_rate모두0이었다. **동시 실제보행은 미확인**이며, 사용자에게
실제 Omni보행 여부를 확인 중이다. 잘못된 방향이라고 단정하거나 동시보행PASS로표시하지 않는다.
Omni계산tick60Hz와 새로운원본처리약28.32Hz를구분한다.

원본파일은 계속 기록될 수 있어 증거JSON에 분석 prefix SHA/byte수/cutoff를 기록했다.
`actual_arm_metrics.json`, `actual_local_receive_metrics.json` 참조.
production코드/실제PD/모터출력은 변경하지 않았고 G1접속·카메라도 실행하지 않았다.

## 2026-09-21 양팔 속도·가속도 상한 3 rad/s · 3 rad/s²

사용자 요청으로 양팔14축(왼15~21,오른22~28)을 모두 각속도3.0rad/s,
각가속도3.0rad/s²로 맞췄다. 약171.887°/s·171.887°/s²다.
이전 어깨/팔꿈치90°/s·손목180°/s·가속도60°/s²에서 변경했으므로 손목속도만 약간 내려간다.
설정은 `MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py` 한 곳이다.
추적 QP, 접근·관절한계 제동 계산, checked stopping tail, Ruckig 복귀가 같은 상한을 사용한다.
IK cost/damping, jerk, collision clearance, 모델관절범위, 단독오른팔/실기PD는 바꾸지 않았다.
`START_G1_VR_TELEOP.bat`의 다음 arm 실행부터 적용. 현재는 값 전달·관찰용이며 G1모터 출력 없음.

새 profile로 과거 staged-session 입력을 재생할 때 `return_joint_range` 재시도 실패를 발견했다.
제동의 첫 v=0 tick에는 아직 유한차분 가속도가 남아 Ruckig 재시작이 바깥쪽으로 밀릴 수 있었다.
복귀 재시도 전에 이미 검사된 정지 표본을 한 tick 더 소비해 가속도가 실제로0이 된 뒤 다시 계획한다.
상태값을 임의로0으로 덮거나 관절/충돌 제한을 풀지 않는다.
동일 복귀 시작 상태는6.833333초 후ready/complete; 원본 기록 종료가5.75초였으므로
current-profile regression에만 표시된 생성 clock65ticks를 추가해 완료를 검사했다.
가짜 측정값·입력은 만들지 않았으며 원본 fixture는 변경하지 않았다.

검증: 전체source suite116개 실행에서115PASS, 1개는 위의 짧은 기록창 끝에서home상태라 실패.
그 마지막 test의 생성종료구간 명시 후 단일재실행PASS. 전체 suite를 다시 돌렸다고 주장하지 않는다.
양팔경계/충돌/복귀/손목우선/재engage와 새상한 검사를 포함하며 현재116항목이각각통과했다.
과거두녹화는 test-only 원래profile로 q차이0 exact replay 보존. 새3/3 Quest입력은
두pinch복귀/재engage 통과. 실패중간로그도 삭제하지 않고 검증폴더에 보존한다.
실제runtime13파일동일성/preflightPASS, 새sim인스턴스의14축velocity/acceleration모두3.0확인.
실제 Quest/Omni/G1 동작을 새속도로 시험한 것은 아니다.

run 로그에 `motion_limits`를 추가했다. 보고서는 원본기록당시 상한으로 판정한다.
과거와 현재상한이다른 replay는 `different_motion_limits`, exact_replay_passed=null로표시하고
현재속도/가속도/충돌/복귀검증을별도로판정한다. 과거실패결과를새상한으로PASS로바꾸지 않는다.

문의한 마지막 오른팔PD연구조합:
Kp22..28=[120,300,64,100,20,30,20], Kd22..28=[1,3,1.2,1.4,1,1,1].
26/28은기존20/1유지이며별도최적화가아니다. 근거 `docs/G1_PD_PITCH_WRIST_20260913.md`.
기존12/12,확장15/16;send-clock mix_a에서yaw24 -1.5035593181rad/s로당시1.5gate실패.
20ms명령보간포함연구로최종PD/실기승인/왼팔검증값이아니다.
이번속도변경은과거PD실패를무효화하지않으며PD/실기gain/validator는변경하지않았다.

설치백업 `logs/backups/bimanual_limits_3rad_20260921_151406`.
증거 `docs/validation/bimanual_limits_3rad_20260921/`.
기존보호파일source308개/runtime297개동일, 예상된양팔7파일외변경없음(새limits파일추가).
sourceHEAD/origin31a5df6동일,기존dirty보존. 이번작업commit/push없음.

## 2026-09-21 입력 관찰 + 카메라 통합 배치 설치

현재 통합 진입점은 `tools/START_G1_VR_TELEOP.bat`이다. 새
`tools/G1_VR_TELEOP_LAUNCH.py`가 기존 관찰 launcher의 receive/send/omni/arm
worker와 기존 `START_G1_CAMERA_TO_UNITY.bat`을 재사용한다. 기본 다섯 창이며,
같은 작업본·옵션의 살아 있는 자식 프로세스는 유지하고 빠진 항목만 연다.
서로 다른 설정·중복 생산자·알 수 없는 UDP 점유는 오류로 알리고 종료/kill하지 않는다.
종료 후 Enter를 기다리는 wrapper 창은 실행 중인 생산자로 세지 않는다.
`--host`, `--no-receiver`, `--check-only` 지원. 원래 두 개별 배치도 그대로 유지한다.

우리 범위는 양팔14축·몸 기준 Omni vx/vy/yaw_rate의 입력 전달 및 수신 확인이다.
관찰 경로는 SDK/DDS 없음. 카메라만 기존 SDK2 VideoClient 읽기와 WSL→Unity TCP5011을 사용한다.
모터 명령·제어기·모드 전환·실제 gain 변경은 없다. Unity Play와 Omni Connect는 직접 실행한다.
카메라 최대20fps 요청, IK/Omni계산/관찰송신60Hz, 화면출력100Hz 유지. 자동 로그 삭제 없음.

실행: 프로젝트 루트에서 `.\tools\START_G1_VR_TELEOP.bat`.
receive 창의 SSH 로그인 후 Unity Play. 종료는 각 관찰/카메라 창의 Ctrl+C 또는 창 닫기.
다른 PC/터미널의 G1 수신기를 유지할 때는 `--no-receiver`.

검증: 새 launcher mocked unit tests15개 + 기존 관찰 command-contract1개, 합계16/16 PASS.
실제 Windows runtime BAT `--check-only`도 PASS(WSL 프로세스 조회, dependency/import 검증).
이 통합 배치로 다섯 창을 새로 열거나 실제 카메라 영상을 재검증한 시험은 하지 않았다.
기존 개별 배치는 직전 턴에 실행한 이력과 구분한다. 하드웨어 제어 검증을 주장하지 않는다.
설치: Desktop runtime의 새 BAT/helper와 사용 가이드. 기존 문서는 백업 후 선택 갱신.
백업 `logs/backups/vr_teleop_launcher_20260921_145817`.
소스 증거 `docs/validation/vr_teleop_launcher_20260921/`.
기존 runtime handoff의 다른 내용은 덮어쓰지 않고 이 항목만 추가했다.
fetch 후 source HEAD/origin `31a5df6` 동일. 기존 dirty 유지, 이번 작업 commit/push 없음.

## 2026-09-21 현재 담당 범위 확정 — 입력값 생성·전달

최신 사용자 지시: **우리는 값을 정확히 보내는 데 집중하고, 로봇 제어는 상대가 담당하며
나중에 통합한다.** 이전의 제어기 통합 계획을 현재의 필수 작업으로 다시 확대하지 않는다.

추가 정정: **모드 전환은 없고, 하체·상체를 동시에 제어하는 통합을 전제로 한다.**
우리 송신 측도 Omni와 양팔 값을 함께 제공한다. 팔 조작 후 하체 모드로 바꾸는 식의
상호 배타적 모드 전환 기능을 설계하거나 복구 작업으로 추가하지 않는다.
팔의 ready/tracking/return 같은 입력 상태와 로봇 제어 모드를 구분한다.

- 우리 범위: Quest/Unity → 양팔 IK 14축(왼팔15~21, 오른팔22~28, rad),
  Omni 월드 mx/my → 현재 몸체 기준 vx/vy(m/s), yaw_rate(rad/s)의 생성·송신·수신 확인.
- JSON 필드/단위/축/관절 순서, 원본 시각·순번, stale/누락 표시와 CSV/JSONL 기록을 관리한다.
  계산·송신 목표60Hz와 표시100Hz는 구분하며, 같은 화면 행을 동시 센서 취득으로 해석하지 않는다.
- G1 관찰 수신기는 입력 확인용이다. 실제 관절 초기각 읽기, C++/LowCmd 연결, PD/하체 정책,
  균형·모드 전환·로봇 회전각 추종은 상대의 제어/향후 통합 범위다.
  `initial_g1_q_rad=null`, `cpp_command_sent=false`는 현재 우리 범위의 완료를 막는 TODO가 아니다.

다음 실제 입력 확인은 새 Omni 변환으로 방향을 바꿔도 직진 시 vx 양수·vy≈0인지,
그 값과 양팔14축이 같은 관찰 세션에서 수신 원문과 일치하는지 확인하는 것이다.
변환 코드는 offline 68개를 통과했으나 새 변환의 실제 보행 확인을 완료한 것은 아니다.
이번 범위 확정은 문서만 수정했으며 프로그램 실행·입력값·제어 경로를 변경하지 않았다.
자동 삭제 요청 철회는 계속 유효하다.

## 2026-09-21 Omni 월드 이동 벡터를 현재 몸체 속도로 변환

사용자가 `mx/my`는 월드 기준이며 현재 방향으로 직진하면 기존 JSON의 `vx`에
전진, `vy`에 0이 들어가야 한다고 요청했다. **yaw 0에서 mx→vx, my→vy**라는
이번 입력 계약을 사용하여 기존 `vx←my`, `vy←-mx` 가정을 대체했다.
원점/양의 yaw 축은 사용자 요청에 따른 계약이며, Virtuix 원시 센서 축을 이번에
독립 실측해 확정한 것은 아니다. 과거 문서의 X=오른쪽/Y=앞 가정을 새 코드와 혼용하지 않는다.

`hardware/g1_arm_bridge/g1_omni_velocity_gateway.py`:
`world_movement_to_body`에서 현재 절대 armYaw의 R(-theta)를 적용한다.
`x=mx-zero_x`, `y=my-zero_y`, `forward=c*x+s*y`, `left=-s*x+c*y` 순서이며,
회전 뒤 기존 body 축 deadzone·0.8 m/s scale/상한을 적용한다. 단위벡터 정규화는 하지 않는다.
start yaw를 뺀 상대각만 사용하지 않으므로 시작112°도 처리한다. 원본 mx/my/raw JSON,
CSV 필드, JSON vx/vy, command velocity 배열 순서, yaw_rate와 yaw_diff 처리는 유지한다.
관찰 ClockedOmniProcessor와 기존 event 경로가 같은 mapper를 사용한다.

사용자의 calibration 질문에는 방향 정렬은 불필요하다고 설명했다. **기존 1초 정지
mx/my 오프셋 평균은 유지**하며, yaw_diff의 기준은 첫 표본에서 잡는다.
실제 G1의 초기 관절각·heading 수신 또는 회전각 폐루프 제어를 추가한 것은 아니다.

검증: offline/synthetic 68/68 PASS. 별도 새 방향 테스트16개는 0/45/90/112/-90/180/359°,
전후좌우, 크기 보존, 현재각 vs 이전각/시작각, world bias, wrap, gap/nonfinite,
기존 JSON/CSV/command 값과 실제 receive-audit 검증 함수 통과를 확인한다.
1000개 생성 샘플에서 git HEAD와 비교하여 yaw 결과 및 calibration/timing 상태 동일 확인.
최신 receiver 경유 assertion 추가 후 방향16개도 다시 통과했다.
실제 Omni 재보행·G1 물리 동작 확인은 아직 하지 않았다.

PC runtime은 Gateway와 관찰 가이드만 선택 설치하고, 보호 파일667개의 SHA를 유지했다.
백업 `logs/backups/omni_world_body_20260921_143812`.
Gateway SHA256 `d9172773a493e16935b06be70b4dd6bd29e0607f3e580ba7e4a02b084b7fc79f`.
현재 실행 중인 창을 중지·재시작하지 않았다. 다음 Omni 관찰 창 실행부터 적용:
`tools/START_G1_INPUT_OBSERVATION.bat --worker omni` (기존 Omni 창을 먼저 Ctrl+C).
G1 프로그램/송신기/IK/PD/모터 명령은 변경·실행하지 않았다. 자동 로그 삭제도 다시 넣지 않았다.
소스 protocol memo의 Omni 설명은 갱신했지만 runtime의 다른 내용인 구형 memo는 덮어쓰지 않았다.
상세 사용법은 runtime `docs/G1_LIVE_INPUT_OBSERVATION_20260921.md`에 반영했다.
증거 `docs/validation/omni_world_body_20260921/`. 기존 dirty 유지, fetch 후 HEAD/origin
`31a5df6` 일치 확인. 이 작업에서 commit/push는 하지 않았다.

## 2026-09-21 자동 로그 삭제 요청 철회 및 원복 완료

사용자가 구현 직후 **자동삭제 넣지말자**로 방향을 변경했다. 이 지시가 우선이다.
PC 소스/runtime launcher·수신기·가이드를 기능 추가 전 백업과 같은 SHA로 복원했고,
자동 삭제 helper 및 그 전용 테스트 2개를 제거했다. G1 관찰 수신기도 원복했으며
실행 폴더의 helper가 없는 것을 SSH에서 확인했다. **자동 저장만 유지하고 자동 삭제·압축은 없다.**
실제 사용자 로그는 삭제하지 않았다. 실행 중인 프로세스나 모터 프로그램은 건드리지 않았다.

G1/PC 수신기 SHA256: `acd30b233117b02c4da2bdbb7815264fe29bbbd7b61abc59591641339eb0071b`.
PC launcher SHA256: `db285dd6c137fbdee3dd87a694713bc155dd66e1c1fbe6e5363551fe1e515af5`.
삭제 기능의 구현/시험/설치 기록은 `docs/validation/observation_log_retention_20260921/`에
과거 이력으로 남으며, **현재 상태는 rollback.json**을 기준으로 한다. 구현물을 재적용하지 않는다.
기존 수신 회귀의 실제 Omni 표본 혼입을 막는 임시 포트 격리 수정은 테스트 파일에만 유지했다.
기존 dirty 작업은 보존했고 commit/push는 하지 않았다.

## 2026-09-21 Omni 이동·회전 실입력의 G1 관찰 수신 확인

사용자 Omni 테스트 완료 후 PC omni_observation_20260921_134946_064568.csv와
G1 input_receive_20260921_134949.jsonl을 대조했다. G1원문9,122,470byte를
읽기전용 SCP회수:3364packet/56.04819s/60.00194Hz,순번168..3531 연속,
구간내누락0·순서역행0·reject기록0·logdrop0·packetSHA불일치0.
모든3364개에서양쪽source FRESH_LIVE. 각Omni수신값을 PC raw_sample_sequence로
조인해3364개전부일치(고유Omni표본1748개). 앞선순번0..167 수신은주장하지않는다.

G1 수신 vx[-0.1681,+0.2667]m/s, vy[-0.7786,+0.1171]m/s,
yaw_rate[-1.6,+1.6]rad/s. 세성분모두양·음값확인,2246packet에서이동/회전출력비영.
yaw_diff[-84.57,+83.15]deg. 고유31표본은현재회전상한±1.6rad/s에포화됐다.
이동방향의실제행동라벨/구간이없고양의vy구간이짧으므로6방향물리정확도를완료판정하지않는다.
이번세션은Unity입력WAIT/팔READY였으며, 실제양팔움직임은직전134118세션에서검증했다.
동일패킷으로양팔/Omni값이함께수신됨과두동작의동시수행검증을구분한다.

PC CSV 고정snapshot5710행/179.937초에서계산tick59.999Hz,deadline skip0,
새처리표본31.7278Hz. 원본JSON/CSV값불일치·timestamp역행0. 활성파일의
Get-ChildItem Length가0으로표시됐지만실제내용은정상증가중이므로메타데이터만으로
미기록판정하지않았다. 조회시OmniConnect32123·IK5020은활성,PCsender55071은
없었다. 이후PC원본행을G1수신검증범위에포함하지않는다. 프로세스조작/모터출력없음.

결과 `docs/validation/omni_observation_reconnect_20260921/operator_omni_134946.json`.
원문은로컬 `logs/test_results/input_observation_live_20260921/g1_received_134949.jsonl`,
SHA256 `3ebf05ee07d9235fd0b5a62acd09430e57682733a98e3c04e36eb20f5d4ded8c`.

## 2026-09-21 timeout 수정 후 실제 양팔/Omni → G1 관찰 수신 확인

사용자 완료 후13:41:18 PC 세션과 G1 input_receive_20260921_134120.jsonl을
대조했다. 실제 Quest/Unity/Omni 입력 관찰이며 새 합성 fixture가 아니다.
G1 원문10,012,517byte를 읽기전용 SCP 회수했다.3553packet/59.197834s,
60.0022Hz, 순번136..3688 구간 내 누락0/순서역행0/reject기록0/logdrop0.
두 source 모두3553개 전부FRESH_LIVE. 전체packet SHA256 재구성 일치하고,
수신3553개 각각의 양팔14축 값은 PC IK feedback_sequence와, Omni 값은
PC CSV raw_sample_sequence와 대조하여 전부 일치했다. 첫 기록 이전0..135는
수신했다고 주장하지 않는다. PC ACK 콘솔은 보존되지 않아 ACK 개수는 미확인.

양팔 unity_20260921_134118_416682.jsonl: 전체59.8214Hz, tracking59.4262Hz,
추적 tick p95 11.8769ms/max17.4778ms, deadline skip11회. READY→TRACKING→
RETURNING(pinch)→READY 정상shutdown, BLOCKED0. 입력1257중1256수용,
종료 부근 마지막1개 sender timestamp역행은 거부됐다. source SHA5개가현재
source/runtime과 일치한다. 이번turn에 제어/설정 변경 없이 로그만 조회했다.

Omni CSV omni_observation_20260921_134118_368864.csv:66.313s/1923처리표본,
계산tick 추정59.9897Hz/deadline skip0. 새 표본 기록은28.9838Hz로,60Hz계산
주기와 다르다. rawseq0..6195 중 latest선택으로4273표본이건너뛰어진것이기록됐다.
원본JSON과값전부일치, nonfinite/시각역행0, 최대새표본간격157ms. 영점보정완료.
다만 mx=my=vx=vy=yaw_rate 모두0이고 armYaw112.49~112.86도였으므로
**정지 상태 연결/수신 확인만 완료**, 보행·회전 부호/속도 실동작은 이번에검증하지않았다.
이번operator세션100Hz화면출력로그는없어이전bounded표시시험결과와구분한다.
실제G1관절초기각/SDK/DDS/C++명령/모터출력은여전히미연결.

분석기록 `docs/validation/omni_observation_reconnect_20260921/operator_134118.json`.
G1원문은 로컬 `logs/test_results/input_observation_live_20260921/g1_received_134120.jsonl`;
SHA256 `af12ad5d78a7c5c083df8de74b99a3ae829193b8086e4d903d720774b5e38c83`.

## 2026-09-21 Omni 관찰 startup timeout 수정

사용자가 clocked Omni 창에서 raw_samples_received=0 / 약0.116초 뒤
`TimeoutError: timed out` 종료를 보고했다. 기존 관찰 reader가 WS 연결에도
수신 polling용0.1초 timeout을 사용하고, create_connection 예외를 fatal로
분류한 문제가 확인됐다. 설치 websocket-client1.8.0은 connect에서 원시
TimeoutError를 올릴 수 있고 recv timeout은 별도 WebSocketTimeoutException이다.
13:33:55 KST 읽기전용 조회에서 로컬TCP32123 listener 및 Omni/Virtuix 이름의
프로세스가 없었다. 이는 조회 시점 상태이며 오류 발생 당시 서버 상태까지 단정하지 않는다.

관찰전용 LatestOmniReader에 connect timeout2초 / established recv0.1초를 분리했다.
connect timeout/refusal, socket disconnect는0.5~2초 stop-interruptible backoff로
재접속한다. 정상 수신 중 timeout은 대기만 한다. 원본 sample seq/시각은 재접속
중에도 유지하고 중복 표본을 발행하지 않는다. 잘못된 JSON/필드/nonfinite 오류는
여전히 fatal이다. CONNECTING/RETRY_WAIT/WAIT_SAMPLE/RECEIVING 상태·시도 횟수·
수신 timeout 수를 표시한다. 60Hz 처리/100Hz 외부표시 설정은 그대로다.
기존 비관찰 Gateway mapping/command 송신, IK, G1 수신기/제어파일 변경 없음.

실제 실행 테스트 총38개 PASS:
- `backend.tests.test_g1_observation_tap` + `hardware.g1_arm_bridge.test_g1_omni_velocity_gateway`:22/22(0.107s), 기존 core AST 보존 포함.
- `hardware.g1_arm_bridge.test_g1_omni_clocked_observation`:14/14(1.220s), timeout/refusal→recovery, stale 원문 유지, malformed fatal, 종료/backoff/late connect 포함.
- `backend.tests.test_g1_omni_transport_recovery`:2/2(3.353s). 실제 websocket-client/websockets의 임시 loopback TCP 서버가 handshake300ms 지연 → 수신 idle → 재개, 서버보다 reader를 먼저 켠 뒤 자동 복구를 검증. 생성 데이터이며 실제 Omni/G1 계측이 아니다.

Desktop Gateway+사용설명2파일 이전 설치 SHA 확인 후 백업·반영. 보호파일667개
변경 없음. 백업 `logs/backups/omni_observation_reconnect_20260921_133854`.
Gateway SHA `27f346c09defeee4afae41d8d4332e63ba6a2895d52a9c71bacb43d97499cec0`.
근거 `docs/validation/omni_observation_reconnect_20260921/`.
Omni Connect와Bluetooth 연결을 켠 뒤 launcher 재실행하면 된다. 다른 관찰 창을
이미 실행 중이면 `START_G1_INPUT_OBSERVATION.bat --worker omni`로 Omni만 재시작.
실제 Omni 재연결 확인은 아직이며 G1 접속/모터 출력/프로세스 자동 종료는 하지 않았다.

## 2026-09-21 관찰 계산60Hz / 표시100Hz — PC/G1 반영 완료

사용자가 모든 계산주기를 맞추고 표시를50→100Hz로 변경 요청했다. 계산은 기존
검증된 양팔 IK dt=1/60초에 맞춰 **60Hz**, PC/G1 관찰 콘솔은 별도 **100Hz**로
구현했다. 새 observation launcher가 IK `--compute-hz 60`, Omni dry-run
`--process-hz 60`, send-live `--send-hz 60 --print-hz 100`, receive
`--print-hz 100`을 전달한다. Unity/C#/IK수학·필터·속도·모델·PD·실제 명령 경로는
변경하지 않았다. 관찰 모드에서만 perf_counter 기준 스케줄을 사용하고 과부하 시
밀린 tick을 건너뛴다. target Hz이지 hard-realtime 보장은 아니다.

Omni 원본 WebSocket 수신은 독립 thread, 최신1개 슬롯에서 새 sample만 계산한다.
센서 수신빈도를60Hz로 바꾼 것은 아니다. CSV는 처리한 표본의 부분집합이며 원래
raw JSON/시각/순번 및 raw_samples_skipped를 기록한다. 이전 전용CSV 기록기의
기본 event 경로는 보존했다. IK/Omni/송신이 같은 주기를 쓰더라도 센서 측정 동시성,
프로세스 위상 동기화, PC-G1 clock 동기화는 하지 않는다.

100Hz 표시는 새 sample 생성과 분리했다. 원본 payload/SHA/순번/시각은 유지하며
display_payload만 age를 증가시키고 STALE로 표시한다. G1 age는 PC 보고 age에
G1 수신 후 경과를 더하되, 아직 계측하지 않은 transport delay는 포함하지 않는다.
stdout이 느리면 표시 slot을 건너뛰며 수신/ACK를 막지 않는다.

실제 실행한 검증:
- `py -3.11 -B -m unittest backend.tests.test_g1_observation_tap backend.tests.test_g1_observation_audit backend.tests.test_g1_observation_pipeline`: **26/26 PASS**, 19.330s.
- `py -3.11 -B -m unittest hardware.g1_arm_bridge.test_g1_omni_clocked_observation hardware.g1_arm_bridge.test_g1_omni_velocity_gateway`: **19/19 PASS**, 0.942s.
- 생성 Unity + 가짜 Omni WS를 실제 producer에 넣은 localhost 통합: IK59.9993Hz,
  수신420packet/59.9943Hz, 표시800frame/100.0626Hz, 반복표시380, IK deadline miss0.
- Python3.8 receiver 구문/기존 mapper·UnityCycle·filter·command encoding AST 보존,
  100Hz 독립 출력·느린stdout·오래된 데이터 판정 회귀 포함.
- runtime launcher `--check-only` PASS. 실제 Quest/Omni 센서 및 G1 새 버전 계측 아님.
- 처음 `unittest discover -s hardware/g1_arm_bridge` 호출은 package relative import
  때문에 수집 실패했다. 위 full module 경로로 바로잡아19개 모두 실행·통과했다.

Desktop 실행본6파일을 이전 설치 SHA와 대조한 뒤 백업·설치했다.
백업 `logs/backups/observation_clocked_20260921_132705`; 보호파일666개 SHA 불변.
근거 `docs/validation/input_clocked_observation_20260921/install.json` 및
`verification.json`. 실행 중 Python은 자동으로 바뀌지 않으므로 재시작 필요.

첫192.168.123.164:22 접속은5초 timeout이었으나 사용자가 연결됐다고 알려준 뒤
재접속 성공했다. PC 이더넷4 주소192.168.123.99/24, G1 기존e9b34184... SHA 및
55070 미점유 확인 후 수신전용 파일을 백업·갱신했다. 새 PC/G1 receiver SHA256:
`acd30b233117b02c4da2bdbb7815264fe29bbbd7b61abc59591641339eb0071b`.
경로는 기존 `~/g1_input_audit_20260921_7e83c4/G1_INPUT_RECEIVE_AUDIT.py` 그대로이며
백업은 `G1_INPUT_RECEIVE_AUDIT.before_clocked_20260921.py`다. G1 Python으로
`receive --seconds 1.2 --print-hz 100`을 실행해 WAIT 표시120frame/99.99993Hz,
정상 종료 후55070 비점유 확인. 콘솔 원문을 g1_console_smoke.jsonl로 회수했다.
새 실제 Quest/Omni를G1까지 보낸 시험은 아직이며 다음 사용자 실행에서 확인한다.
다른 프로세스 종료나 SDK/DDS/LowCmd/모터 출력 없음. PC 기존 launcher를 재실행하면
60Hz 계산/전송과100Hz 표시를 사용한다. 수신창을 직접 띄울 때 기존 receive 명령은
이제 기본100Hz이며, PC launcher는 --no-receiver 옵션으로 중복 수신을 피한다.

추가 질문: 사용자는 기존 Quest2를Quest3S로 교체할 수 있는지 물었다. Desktop Unity는
공통 OVRHand/OVRSkeleton 입력을 사용하며 G1Teleop 소스에 Quest2 모델명 분기를
발견하지 못했다. 기존 PC Link+Unity Play 경로는 같은 IK/UDP 구조를 사용할 수 있다.
실제 Quest3S 연결은 미검증. APK standalone은 loopback 주소와 Android target이
현재Quest2/Pro만 포함돼 별도 작업이다. XR설정/패키지는 이번에 변경하지 않았다.

## 2026-09-18 session report and near-hands return v2

Read [near-hands return v2](BIMANUAL_NEAR_HANDS_RETURN_20260918.md) and
[session reporting](BIMANUAL_SESSION_REPORT_20260918.md). The report tool selected the latest
real operator log behind newer headless smokes and exposed a historical return BLOCKED at seq 697.
The preserved fixture now triggers a v2 path: checked stop -> one-arm separation -> existing safe
waypoint -> home -> settle. Original/mirrored cases choose left/right respectively and both finish
in 510 ticks with >=5.696 mm sampled clearance. Existing normal returns keep the old direct route.
Report strict exit propagation, EOF latest scan, malformed-row handling and state/reason counting
are regression-tested. Current new logs must show return_policy=bimanual_staged_return_v2.
Simulation only; 5 mm hard clearance/0.25-degree swept checking remain unchanged.
Final isolated-source and installed-runtime suites both pass 89/89. A trigger-specificity regression
keeps near-hands disabled at 6.769 mm global / 85.631 mm inter-arm clearance. Runtime backup:
`logs/backups/bimanual_near_hands_return_20260918_210946/`; 385 protected files were unchanged.
The headless BAT smoke used loopback port 57287, not production port 5020.
Follow-up retry/fail-closed coverage brings source/runtime suites to 91/91. The recorded fixture's
zero-speed separation probes are left 5.788 mm and right 4.573 mm: if the checked left route is
injected as swept-clearance rejected, the right probe remains below the 5 mm hard limit and the
return fails closed without publishing it. A state-machine test also verifies switching to right
when an opposite candidate is explicitly probe-safe. Runtime test-only backup:
`logs/backups/bimanual_near_hands_retry_20260918_214512/`; 391 protected files unchanged.
UnityCycle integration now replays the near-hands fixture from `tracking_lost` through READY in
510 ticks / 8.5s, minimum sampled clearance 5.696090 mm and <=60 deg/s^2 output acceleration.
Source/runtime suites are 92/92 PASS. Test-only runtime backup:
`logs/backups/bimanual_near_hands_unitycycle_20260918_215424/`; 391 protected files unchanged.
Headless log `unity_20260918_211223_0339097.jsonl` records v2 + MuJoCo 3.12.0 + current return hash.

## 2026-09-18 performance micro-optimization stop point

Read [performance stop point](BIMANUAL_PERFORMANCE_STOP_POINT_20260918.md).
No code after `1e28597` was accepted. Squared sphere masking had zero decision mismatches but
no reproducible full-replay gain; hybrid AABB and small-distmax variants were slower/inconsistent.
Early unsafe-pair exit saved just 0.0133% of exact pair calls. Keep the current sphere broadphase
and safety sampling unchanged. Future performance work must be architectural and independently
prove identical sampled decisions, zero-distance handling, Quest replay and reproducible A/B gain.

## 2026-09-18 conservative sphere broadphase

Read [sphere broadphase validation](BIMANUAL_PERFORMANCE_SPHERE_20260918.md).
Stopping-tail threshold checks now reject certainly distant collision pairs with bounding
spheres enclosing each local geom AABB; surviving pairs still use exact geometry distance.
No clearance/sweep/motion limit changed. Recorded + random exact-distance rechecks found
zero bad exclusions. Quest replay q remains identical at 5.032 mm minimum clearance.
Clean detached suite 77/77 PASS; runtime targeted 16/16 PASS. A/B p95 mean improved
20.902 -> 17.300 ms under the same host load. Parallel session-report work was preserved.

## 2026-09-18 clearance kinematics optimization

Read [second clearance optimization](BIMANUAL_PERFORMANCE_KINEMATICS_20260918.md).
Normal sampled distance checks now use `mj_kinematics`; exact zero distance alone promotes
to `mj_fwdPosition` and the existing robust contact/probe path. All collision margins,
sweep samples and motion limits remain unchanged. Quest replay q is still identical.
Repeated A/B p95 mean: 15.055 -> 12.274 ms; source/runtime suites 76/76 PASS each.
Two files installed with backup, 277 protected files unchanged, BAT smoke passed.

## 2026-09-18 clearance performance optimization

Read [performance/clearance validation](BIMANUAL_PERFORMANCE_CLEARANCE_20260918.md).
Profiling the confirmed Quest replay showed checked stopping-tail clearance checks
were the main tracking cost; QP solve itself averaged about 0.044 ms. Clearance now
uses `mj_fwdPosition` instead of full `mj_forward`, without changing collision samples,
5 mm hard clearance, motion/return policies, or speed/acceleration bounds.
500 random poses matched full-forward distance/pair/contact results exactly. Quest replay
q remained identical. Direct old/new p95: about 16.42 -> 14.63 ms; source/runtime 74/74 PASS.
The user process was left running; the installed optimization loads on next Python start.

## 2026-09-18 Quest pinch/re-engage confirmed

Read [Quest confirmation and replay](BIMANUAL_QUEST_CONFIRMED_20260918.md).
The user confirmed the current Quest behavior works. The same session log shows
two pinch staged returns with one successful re-engage between them. A compact
recorded fixture replays 2,927 state ticks with 0 rad max logged-q difference,
5.032 mm minimum sampled clearance and the 60 deg/s^2 output acceleration bound.
Source and runtime bimanual suites: 73/73 PASS each. This is Quest simulation confirmation,
not physical G1 validation or a claim of continuous host-side 60 Hz timing.

## 2026-09-18 pinch re-engage and startup follow-up

Read [re-engage/startup validation](BIMANUAL_REENGAGE_STARTUP_20260918.md).
A real BimanualSimulation/UnityCycle regression now covers motion, pinch return,
staged waypoint/home/settle, active-only rejection, inactive rearm and re-engage.
Source bimanual suite: 71/71 PASS; return suite: 11/11 PASS.

The existing leave-zone release condition is now a testable production helper;
592 engage/leave combinations and 17 backend-generation/order cases passed after
a full Unity-reference C# compile with zero errors. Unity was open, so this
semantics-preserving C# refactor was not hot-copied into the runtime project.

Fresh MuJoCo 3.12 imports (10) took about 0.201-0.268s and five headless full
startups took about 1.196-1.277s. The earlier intermittent long import delay was
not reproduced and remains unexplained. No new Quest or physical G1 validation.

## 2026-09-18 observed staged-return replay and laptop path deployment

Read [observed run validation](BIMANUAL_OBSERVED_RUN_20260918.md).
Added a selected recorded-input fixture and two regression tests covering
3,433 state ticks through tracking-loss braking and staged return. The source
recording's five Python hashes match `7e74219`; replayed q matches exactly.
Observed return: 6.063s recorded time, 5.75s simulation time, waypoint/home/
0.5s zero-speed settling, no replans. Minimum sampled bilateral clearance was
about 5mm, not generous margin. No new comfort, re-engage, or physical validation.

Installed the nine existing Windows path patches into the laptop Desktop-folder
project after baseline checks and backup; preserved 508 other code/scene files.
Four actual BAT path-only checks passed. No Unity, robot, DDS, APK, or compiler
execution. Separate desktop deployment remains unverified. An auxiliary engine
import stalled again; its interrupted attempt is not counted as a pass.


## 2026-09-18 staged bimanual return restored on the same laptop

Read [return parity and validation](BIMANUAL_RETURN_PARITY_20260918.md).
The reported return regression was a different return implementation, not reduced
speed caps in the preceding boundary fix. Tracking retains the shared QP and
motion policies. Return now uses the original right-arm Ruckig profile/waypoint,
mirrored to the left, then home and 0.5s at zero speed before READY. Every output
keeps bilateral geometry and checked stopping-tail validation.
Source/runtime suites: 68/68 each. Same-start 60Hz durations: 10.733 -> 5.933s,
9.833 -> 5.350s. Latest recorded prefix replay and actual BAT startup passed.
Seven files installed with backup, 363 protected files unchanged. No Unity/C#
edit, user process restart or physical G1 control. New return Quest feel remains
unverified. This is historical v1 parity evidence. Current restarted Python should report return_policy=bimanual_staged_return_v2.

## 2026-09-18 bimanual boundary fixes installed (simulation only)

Read [boundary fixes and verification](BIMANUAL_BOUNDARY_HARDENING_20260918.md).
Short tracking loss now consumes checked braking commands, with output qpos
continuity and zero-speed READY checks. Known solver errors use the tail or
BLOCKED; malformed JSON is rejected before updating the cycle. Engage origins
use the filter's normalized quaternion. New backend identity/start ordering and
feedback sequence reset the C# calibration and reject delayed/old feedback.

Source and installed-runtime suites: 58/58 PASS each. C# compilation with actual
references, 17 backend-order cases and 576 engage combinations passed. Nine
files installed with backup; 604 protected files and the scene/right-arm policy
unchanged. Stop Play and the old Python normally, then restart both together;
check boundary_policy=bimanual_boundary_v1 in the new run log.

Intermittent engine-import delay remains unexplained; stage timestamps are now
logged. A stopped auxiliary test is not counted as passed. Quest feel, full
Unity Play restart and physical G1 behavior have not been tested.

**최신 GPT 인계 요약: [GPT_BIMANUAL_HANDOFF_20260918.md](GPT_BIMANUAL_HANDOFF_20260918.md).**
아래 기록은 역순 작업 이력이며, 과거의 미해결 표시는 이후 수정 결과와 구분한다.

## 2026-09-18 bimanual motion corrections installed on the same laptop

Read [motion correction validation](BIMANUAL_MOTION_CORRECTION_20260918.md).
Per-arm motion preferences now restore target-approach braking, wrist priority,
shoulder comfort, torso projection, elbow assistance and reversible orientation
priority inside the shared 14-DOF QP. The original single-right-arm controllers,
Unity scene/C# and exact checked stopping-tail function remain unchanged.
Paired input filtering and log-only runtime/policy diagnostics were added.

Final installed-runtime suite: 45/45 PASS. Actual BAT headless idle smoke: PASS.
Selected reported-motion replay: 1,404 ticks, 667 tracking ticks, one checked
braking tick, >=19.69mm sampled clearance, return to ready. No Quest verification
of the corrected behavior yet; no physical G1 control. Old user Unity/Python
processes were not restarted: stop/restart normally before comparing behavior.
Backup: laptop runtime logs/backups/bimanual_motion_install_20260918_114658/.

## 2026-09-18 environment clarification and runtime checkpoint

- User clarification: all work from the beginning through now has remained on
  the same laptop. No additional development on a separate desktop PC has started.
- `C:/Users/user/Desktop/G1_Teleop_Project` is the laptop's Windows Desktop-folder
  runtime project. The clean source worktree under `Documents/Codex/.../g1-integration`
  is on the same laptop. Folder names and device hostnames do not establish a PC migration.
- Runtime engine parity fix `d52c2aa` and its 29/29 offline test record are in the
  source worktree; that fix has not been copied into the laptop's runtime folder.
  See [runtime validation](BIMANUAL_RUNTIME_VALIDATION_20260918.md).
- Latest Quest feel remains unverified. Historical desktop-migration instructions
  below are plans/reference material, not evidence that desktop development occurred.

## 2026-09-18 coupled IK checked braking (offline verified)

- Fix previous next-step-only planning: each accepted joint velocity now has
  a discrete stopping tail checked before committing the step. Every tail
  step respects the existing 60 deg/s^2 acceleration, 90/180 deg/s speed,
  joint ranges, frozen non-arm pose, and >=5mm sampled clearance.
- If a subsequent QP is infeasible or its stopping tail invalid, follow the
  previously checked tail instead of resetting velocity or latching BLOCKED.
  At zero velocity retain its checked hold and retry tracking on later input.
  No valid cached tail still fails closed. This assumes fixed kinematic
  geometry; it is NOT a physical braking controller or continuous collision proof.
- World-AABB separation excludes only certainly distant collision pairs;
  remaining pairs still use the existing robust geometry distance. 120 seeded
  poses match the full collision decision. No XML/mesh limits were changed.
- Recorded Quest/Unity fixture committed with provenance: original sequence
  607 QP failure (+2.188s) now passes. 209 ticks, 24 checked-braking ticks;
  joint range/speed/acceleration/clearance checked throughout. This is NOT
  measured G1 data. Original laptop source JSONL preserved.
- Executed: `py -3.11 -m unittest discover -s backend/tests -p "test_bimanual*.py"`
  with isolated MuJoCo 3.12.0 PYTHONPATH: 17 PASS, 13.213s total.
  Replay tick p95 13.34ms / max16.14ms on this run, not a hard real-time guarantee.
- Original project installed selectively with backup. Current Python process
  retains old code: stop simulation/Unity Play and reopen START_BIMANUAL_UNITY_SIM.bat,
  then Play. Quest feel remains unverified. No G1/SSH/DDS/motor execution.


## 2026-09-18 sequential engagement and recorded IK failure

- User finds simultaneous stable hand alignment uncomfortable. Each hand now
  remembers completed stable alignment for 4 seconds. Both current alignment
  gates and tracking must still pass at engage. Pinch, loss, stale feedback,
  return/rearm invalidate memory. Neutral origins are captured together.
- Compiled Unity/Meta references PASS; 576 engage combinations plus memory,
  invalidation, expiry and final current-position gate checks PASS. No Quest
  verification of this UX yet. Runtime selectively backed up and installed.
- Latest laptop recording unity_20260918_094323_0712614.jsonl, session
  2a9d0dc13c574a208a64b4c50f1ab6de: engage sequence 529, then sequence 607
  qp_infeasible at +2.188s. Unity feedback stayed fresh; this was IK BLOCKED,
  not a UDP disconnect. Exact event replay reproduces the same sequence.
- Offline diagnostic removing only 28 acceleration inequalities makes that
  QP feasible. At failure clearance .020925990836630545m; maximum joint
  velocity .9528789799160351rad/s. This does NOT establish collision or
  physical safety and does not justify removing acceleration constraints.
- Solver is unchanged; interrupted tracking REMAINS UNRESOLVED. Next work:
  implement and regression-test checked braking viability for coupled IK,
  preserving range/clearance and using this replay. Do not claim fixed tracking.
- Replay script/report live under logs/test_results/same_scene_bimanual/ in
  source worktree; source recording remains laptop-local, not in GitHub.


## 2026-09-18 camera-attached bimanual status strip

- Replaced paired sender floating TextMesh with a world-space UI strip attached
  to the existing camera PiP bottom edge: 6 canvas-unit gap, 48-unit height.
  Two columns show Korean left/right tracking/alignment/progress/ready status;
  lower row shows concise cycle state. No detailed distances in headset UI.
- Child canvas sorting order is camera order + 1; text is rendered after
  background. No overlap with video rectangle. Headset-relative fallback uses
  camera default geometry if PiP is absent, without creating a camera receiver.
- Hide duplicate preview TextMesh in bimanual mode. Original right-arm mode
  keeps existing display. Engage logic, initial pose and robot paths unchanged.
- Actual Unity/Meta-reference C# compilation PASS; diff whitespace check PASS.
  Installed into original project with selective backup. Quest visual readability
  and occlusion verification remain pending. Stop Play and restart after compile.


## 2026-09-18 marker parity and engage audit (Quest success NOT verified)

- Previous repair was compile-verified only. User reports engage still fails.
- Confirmed cyan wrist diameter mismatch: right .060m, left .025m. Right
  requested target was also cyan, unlike left green. Now both tracked markers
  use .060m and targets .055m, with white/yellow alignment and green active.
- Latest runtime capture unity_20260918_094323_0712614.jsonl and Editor.log
  show tracked hands but no demonstrated simultaneous completed alignment.
  Do not claim a proven single cause for failed engage or a successful fix.
- Remove extra simultaneous .35s timer in existing-scene mode; both binders
  still require their configured stable hold, valid tracking and alignment.
  Fresh ready feedback, released pinch, and rearm conditions remain required.
- Add per-second combined [BIMANUAL ENGAGE] diagnostics for backend freshness,
  pinch, rearm and both alignment errors/progress. Explicit pinch instruction.
- Actual Unity/Meta reference compilation PASS; compiled sender CanEngage
  executed under Mono: 576 boolean/progress combinations PASS. Shared marker
  diameter check PASS. This is not Unity Play/Quest end-to-end verification.
- Installed two C# changes selectively in original project with backup.
  No robot, SSH, SDK/DDS or motor execution.


## 2026-09-18 same-scene engage/left-marker repair

- User capture `unity_20260918_093446_2442044.jsonl`: 800 inputs; 625 had
  both hands tracked, none engaged; backend remained ready. Saved left binder
  had reference_transform=0 and head_camera_alignment=0, unlike the right binder.
- Explicitly wire both references in installer and runtime Awake to repair
  existing scenes on next Play. Add missing left cyan tracked-wrist marker,
  green left target and per-hand alignment distance/hold status.
- Keypad bootstrap now runs AfterSceneLoad so the bimanual marker is present
  before its guard is evaluated; earlier log showed unwanted keypad startup.
- Unity/Meta DLL-reference compilation passed. Quest retest and actual
  runtime bootstrap suppression remain unverified; no G1/robot execution.


## Same-scene bimanual extension (2026-09-18, current)

- User rejected the separate-scene workflow. Use existing SampleScene menu
  `G1 Teleop/Arms/Use Both Arms (Simulation)` or `Use Original Right Arm` with
  Play stopped, then save. No separate project/scene is needed.
- Current right-hand binder settings are reused; left binder clones them.
  Existing preview/head alignment/camera remain. Paired joint feedback now
  drives both arms of the existing official rig, not just a PC MuJoCo window.
- Original right-arm mode bypasses all new preview/input branches. The coupled
  14-axis IK remains a candidate: original one-arm elbow/torso/orientation
  refinements have NOT all been generalized. Do not claim identical IK behavior.
- See `docs/BIMANUAL_SAME_SCENE_20260918.md`. Local source installation is backed
  up; menu/Quest Play is not auto-executed. No physical G1 action.

## 2026-09-18 original laptop Desktop-folder project: bimanual simulation installed

- Selectively copied the paired Unity/MuJoCo simulation files from source commit
  `0a83dc3` into the laptop's existing Desktop-folder project at the user request.
- Backup: `logs/backups/bimanual_install_20260918_090952/`: tracked dirty diff,
  pre-install copies of affected existing files, original SampleScene, hashes.
- Keypad Install/Awake received only the two simulation-scene guards; no broad
  overwrite/reset/pull of this dirty worktree. Original SampleScene hash unchanged.
- Runtime checkout: 13 offline/generated/loopback tests passed on MuJoCo 3.12.0.
  Open Unity recompiled Assembly-CSharp and Assembly-CSharp-Editor; both new types
  were found in the resulting DLLs. Scene creation and Quest Play remain untested.
- Use the existing Unity project menu G1 Teleop -> Create Separate Bimanual
  Simulation Scene, then tools/START_BIMANUAL_UNITY_SIM.bat. G1 is not used.


> **Absolute G1 mutation rule:** Never create, delete, rename, move, or modify any file on the G1; never run a program that can create a log, publish a command, change a service or mode, or otherwise mutate G1 state without the user's explicit approval for that exact action. Inspect source before running diagnostics. Remote-to-local copy is allowed only when it reads existing G1 files and writes exclusively to the Windows project.

Last updated: 2026-09-18

## Unity paired-hand simulation input (2026-09-18)

- Laptop work in clean sync checkout: added `G1BimanualSimulationSender`,
  separate-scene editor menu, `g1_bimanual_unity_sim.py`, and
  `tools/START_BIMANUAL_UNITY_SIM.bat`. See `docs/BIMANUAL_UNITY_SIM_20260918.md`.
- Fixed localhost UDP 5020 by default; distinct simulation-only schema. Both
  hands engage together; either-hand pinch for 0.5s returns both; fresh ready
  and a new inactive/active edge permit re-engage. No G1 connection.
- Added an opt-in scene marker guard to keypad Install/Awake, because the
  existing automatic UDP 5016 sender would otherwise run even in the new scene.
  Existing right-arm IK, original scene, physical paths and dirty runtime stay untouched.
- MuJoCo 3.12.0: 13 generated/unit/loopback tests passed. C# compiled against
  installed Unity/Meta assemblies. Full Unity import/scene generation/Play,
  actual Quest input and runtime bootstrap suppression still need verification.
- The new scene is generated through the menu, not checked in. Logs are PC-local.
  Do not describe this source-level connection as a completed Quest/G1 trial.

## Bimanual simulation candidate (not Unity or G1 connected)

- Added isolated `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py` and
  `tools/START_BIMANUAL_SIM.bat`: coupled 14-axis IK, both hand collision meshes,
  bilateral/body collision constraints, sampled-path guard, constrained home return.
- Existing right-arm controller, runtime checkout, Unity, UDP, G1, gains and model
  assets remain unchanged. This is a new kinematic candidate, not a replacement
  for every right-arm posture refinement or a physical stopping controller.
- Generated tests: 6 passed on MuJoCo 3.11.0 and 6 on 3.12.0. A 1,800-tick demo
  reached ready after return. GUI and live Quest two-hand input remain untested.
- Read `docs/BIMANUAL_SIM_20260917.md` for launcher, paired JSONL schema,
  collision-check limitations, and the remaining Unity two-hand integration.

## Omni raw and mapped time-series CSV recorder

- Run `tools\RECORD_OMNI_TIMESERIES_CSV.bat`. Optional arguments are total
  duration and preparation delay in seconds; defaults are `120 20`.
- Each `g1.omni.timeseries.v1` row records one received Omni sample with the
  same timestamp and sequence: raw `mx`, `my`, `arm_yaw_deg`,
  `omni_yaw_rate_deg_s`; mapped `vx`, `vy`, `yaw_rate`; relative
  `yaw_diff_deg` and per-sample `yaw_step_diff_deg`; calibration state; and the
  exact source JSON in the final column.
- CSV files are written to `logs/test_results/omni_timeseries/`. The launcher
  uses `--dry-run`: no G1 discovery, UDP output, SDK, DDS, or motor command.
- Offline verification passed: 12 mapper/schema unit tests, a fake WebSocket to
  discovery/UDP test with 10 accepted command packets and final zero, and a
  loopback fake-G1 CSV test with 72 rows.
- A user-operated Omni capture was subsequently recorded on the laptop at
  `C:\Users\user\Desktop\G1_Teleop_Project\logs\test_results\omni_timeseries\omni_timeseries_20260917_171846.csv`
  (10,344 rows; 7,880 calibrated rows). The raw CSV and its generated interactive
  visualization are laptop-local artifacts and are not tracked by Git, so a
  desktop checkout of this branch will not contain them. Copy them separately
  if the desktop must inspect the exact same recording. Code, tests, schema and
  these handoff notes are in Git.
- The default mapped yaw-rate ceiling was raised from `0.8 rad/s` to
  `1.6 rad/s` (about `91.7 deg/s`) after the user-operated recording showed
  sustained clipping in both turn directions. The limit remains finite; this
  is a PC Gateway setting change and was not run against a physical G1.

## Current method audit: neither current behavior nor priority prototype accepted

- User requested a rigorous review instead of further tuning followed by VR
  feedback. Read `docs/IK_WRIST_ARM_METHOD_REVIEW_20260917.md` before more edits.
- Source/runtime remain at the `6c32983` tracking implementation, SHA256
  `fe0ab3273bb6a470fe5d982aa9d00faa7b106e25358ff5d610b7f806444b5ba3`.
  No controller, launcher, model, gain, or hardware file was changed this turn.
- Latest16:39 CSV: inferred wrist penalty disabled for654/669 active samples
  (97.8%) because remaining position error>=8mm. At17.50-18.50s target position
  range1.56mm/rotation10.25deg nevertheless recruits shoulder roll/yaw6.04/6.43deg,
  with>=36.5mm clearance. Earlier position backlog also requires some valid
  proximal motion; do not freeze the arm based on stationary input alone.
- Independent generated hold test: current posture objective causes4.74/6.80deg
  proximal motion during2s of an unchanged nonneutral wrist target, still moving
  at2.05/2.97deg/s afterward. This masks fine-motion intent and was missing from
  the previous neutral-pose regression suite.
- Local model FK confirms pitch-to-yaw offset46mm; neutral wrist pitch origin
  translation Jacobian norm=.046m/rad. Fixed arm plus30deg wrist pitch moves the
  tracked origin23.8mm. Do not silently change the task frame to hide this error.
- New OFFLINE ONLY `prototype_mink_task_priority.py` is a research comparison:
  wrist6D primary, then minimize proximal velocity while preserving linear Jv.
  It greatly improves some precise rotations but regresses cumulative shoulder
  spread/elbow lift on full records. NOT approved for launcher/runtime use.
- New `audit_mink_precision.py` fixes31 generated scenarios and predeclared
  engineering criteria. Final matching-engine MuJoCo3.12.0 results:
  current24pass/7fail; prototype27pass/1fail/3inconclusive. accepted=false BOTH.
  Each run9,660test+3,720prelude ticks with no geometric, frozen-joint, velocity
  or acceleration violations. Data are simulated; no measured G1 validation.
- Complete reports/hashes are committed under
  `docs/validation/ik_method_review_20260917/`.3.11 exploratory results remain in
  ignored logs. Generated scenario comparisons have controller-dependent prelude
  poses; same-CSV replay is separately labeled. No failed results were removed.
- Next implementation must preserve fine task motion and assess cumulative
  posture/continuity, not just instantaneous proximal speed. Do not request
  another VR trial for the rejected prototype or raise thresholds to pass it.
  More precise release criteria/remaining coverage are listed in the review.

## Current excessive elbow spread correction (after the 16:30 simulation)

- User clarified the problem is excessive sideways/upward elbow spread, not
  failure to lift. The newest closed CSV is
  `mink_v5_right_arm_20260917_163007_600.csv` (601 active samples). Recorded
  shoulder yaw reaches 90 degrees, shoulder roll reaches -58.2 degrees, and
  final wrist position error is 15.9 cm. These are simulated model values,
  not actual G1 measurements or evidence of the human elbow position.
- Tested removing/weakening the fixed elbow Y/Z preference. Alone this did
  not eliminate the 90-degree yaw excursion. A global posture penalty reduced
  excursion but could suppress the useful front lift. Those sweep candidates
  were not copied to the runtime; local reports remain under `logs/test_results`.
- Added `ShoulderComfortTask`: a soft squared excess-angle objective, with
  zero error/Jacobian within engage-relative roll +/-20 and yaw +/-45 degrees.
  Cost is 0.6 and gain follows the scheduled wrist task gain. Beyond those
  bands the solver prefers less shoulder roll/yaw but can still cross them
  to reach the target. This is not a new hard joint limit or a motor PD gain.
  Existing +/-90 yaw envelope, collision constraints, wrist priority, velocity,
  acceleration, elbow reference, return logic and model limits are unchanged.
- Same-input A/B replay versus `8921f42`, newest CSV, 1,158 ticks:
  shoulder yaw max 90.0 -> 77.98 degrees; roll excursion max 37.98 -> 34.95
  degrees; final elbow lift 6.81 -> 5.15 cm. Peak elbow lateral distance from
  shoulder decreases only 19.86 -> 19.39 cm; final lateral distance increases
  10.70 -> 10.94 cm. Do not claim every pose is less spread. Wrist position
  p95 remains 13.87 cm and final two-second rotation error 14.76 -> 14.72
  degrees. Two checked braking steps, no hard holds or acceleration violations.
- Earlier front-target CSV (15:58), 1,529 ticks: shoulder yaw max 90 -> 80.28
  degrees, roll excursion 53.65 -> 40.79 degrees, maximum elbow lift
  11.72 -> 7.96 cm. Position p95 20.38 -> 19.39 cm; final rotation error
  2.98 -> 2.93 degrees. All steps accepted, no acceleration violations.
  Reports: `logs/test_results/elbow_comfort_latest_20260917.json` and
  `logs/test_results/elbow_comfort_front_20260917.json`.
- Added a finite-difference Jacobian and neutral-band regression. Existing
  tests preserve the front-lift, non-ratcheting, return and stationary wrist
  behavior. Executed five regression suites: **51 tests +21 subtests passed**.
  This is a preference candidate, not an optimal/naturalness proof:
  the input has wrist pose but no measured human elbow/swivel target. User
  visual acceptance after restarting Input remains necessary. No G1 execution,
  SDK/DDS, motor output, or gain changes were performed.

## Current stationary wrist rotation correction

- User confirmed the front-elbow change improved motion, but observed arm
  recruitment during stationary wrist rotation. The newest 16:19 CSV was still
  zero bytes when inspected; do not describe this as an analysis of that run.
- The active upstream tracking QP used the standard proximal/wrist damping
  costs 0.25/0.015. The legacy banner's proximal cost 100 refers to the other
  task path and does not describe this QP. A reachable fixed-position synthetic
  30-degree local roll rotation recruited up to 6.12 degrees of proximal motion.
- Added a finite proximal velocity penalty in `UpstreamMinkTracking`. It is an
  IK objective, not motor Kd or a hard joint lock. Maximum extra cost is 5.
  Its weight fades with position error (full <=2 mm, zero >=8 mm), rotation
  error (full >=3 degrees, zero at zero error), wrist joint margin (full >=28
  degrees, zero <=5 degrees), and clearance (full >=25 mm, zero <=5 mm).
  Reset and BeginReturn clear it. Elbow assistance, yaw envelope, original
  rotation target, speed/acceleration, exact geometry, and hardware files stay
  unchanged. Finite cost allows proximal compensation for offset wrist axes.
- Reproducible synthetic experiment:
  `python experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py --baseline-ref a709874 --output logs/test_results/wrist_stationary_priority_20260917.json`.
  Initial-pose wrist position stays fixed; rotate 30 degrees over 2 seconds,
  hold 4 seconds, separately around each local axis. Baseline -> candidate
  maximum proximal joint excursion: roll 6.12 -> 0.33 degrees, pitch 3.73 ->
  3.44 degrees, yaw 1.83 -> 0.10 degrees. Final orientation errors <=0.29 degrees.
  Pitch compensation is necessary for this model's offset wrist pivot; do not
  promise absolutely fixed shoulders for every wrist rotation. Maximum pitch
  position error increased from 0.70 to 5.60 mm; regression requires final
  position error below 2 mm. Other two axes stay below 0.1 mm throughout.
- Replayed the 15:58 recorded simulation targets (789 samples, 1,529 ticks)
  against a709874. Final elbow lift remains +4.18 cm, final rotation error
  remains 2.98 degrees, position p95 remains 20.38 cm. Rotation p95 changed
  75.06 -> 76.01 degrees; this is not a global tracking improvement. All replay
  steps accepted; no acceleration violations. Report:
  `logs/test_results/wrist_priority_front_replay_20260917.json`.
- Tests include generated three-axis stationary rotations with position,
  orientation, proximal excursion, exact geometry, frozen joints, velocity,
  and inter-step acceleration checks, plus existing straight reach, front
  elbow, return and simulation boundary regressions. Executed five suites:
  **50 tests and 21 subtests passed**. Reports identify the tested source hash;
  only explanatory comments were added to tracking code afterward. No live G1 validation;
  user must restart Input to assess appearance in VR. No robot execution.

## Current front-of-torso elbow correction (after the 15:58 simulation)

- `mink_v5_right_arm_20260917_155826_842.csv` contains 789 active samples.
  During the front-of-torso plateau, yaw reached the added 45-degree envelope,
  elbow joint coordinate was at its 5-degree bound, and projection disabled the
  old elbow-assist trigger. Joint coordinate 5 degrees must not be equated with
  a human-visible elbow bend angle; use FK elbow height to judge elevation.
- Front-face proximity is now checked against the model's expanded torso
  boxes. When the effective wrist position error exceeds 2 cm and elbow joint
  coordinate is below 20 degrees, a lateral/vertical elbow preference can
  activate even for a projected goal. It releases outside the front area,
  within 2.5 cm of the captured wrist target, on reset, or on pinch return.
- The old `FrameTask` Z cost acted in a rotating local frame, not world height.
  `ElbowClearanceTask` uses actual world Y/Z position error and `mj_jacBody`.
  It anchors lateral position to the engage elbow and vertical target to
  engage elbow +8 cm, capped 4 cm below the shoulder. Re-entry recomputes from
  the same engage reference rather than adding height to the current elbow.
  This is a soft pose preference, not an absolute 8 cm bound on every motion.
- The added yaw envelope is now +/-90 degrees from engage (previously +/-45).
  The 45-degree restriction prevented the required repositioning; increasing
  elbow cost alone worsened wrist reach. This change is an IK pose-envelope
  adjustment, not a velocity or hardware joint-limit change. Model/XML,
  velocity/acceleration limits, and original wrist rotation targets remain intact.
- A/B replay against `0be2f4c`, same target timestamps, 1,529 ticks:
  final elbow height relative to engage was -1.39 -> +4.18 cm (5.57 cm higher);
  final two-second wrist direction error 2.77 -> 2.98 degrees;
  position error p95 19.12 -> 20.38 cm (a regression, not an overall accuracy gain);
  minimum clearance 5.50 -> 31.74 mm; no rejected/braking steps or acceleration
  violations. Earlier 15:38 replay also retained rotation recovery (final error
  10.35 -> 9.83 degrees), with no rejected steps or acceleration violations.
- Added a recorded simulation snapshot test: fixed front target raises the
  elbow by 4-10 cm, maintains wrist rotation within 5 degrees and effective
  position error below 8 cm, and preserves non-arm joints/checked geometry.
  Forced repeated re-entry proves the assist target cannot ratchet upward.
  A finite-difference test checks the world-frame Jacobian; original return
  position/orientation tolerances remain unchanged.
- Validation executed: five focused suites, 48 tests +18 subtests passed;
  after adding constructor initialization, the initialization and front-target
  regressions passed (2 tests). Earlier assertions forbidding all projected
  elbow assistance were replaced by the bounded-lift requirement intentionally.
- Replay reports: `logs/test_results/elbow_front_final_ab_20260917.json` and
  `logs/test_results/wrist_elbow_final_ab_20260917.json`. These reports precede
  the constructor-only initialization addition; their source hashes identify
  that tested source. That addition does not change the Reset-based replay.
- Natural appearance still needs user confirmation after restarting Input.
  These are simulation/replay results, not measured G1 validation. No G1 SSH,
  SDK/DDS initialization, publisher, motor output, PD changes or model changes.

## Current wrist-orientation correction (after the 15:38 simulation)

- Torso projection now changes only the position target. The original user
  wrist rotation remains the QP target, including while the position lies
  inside the torso exclusion volume. `collision_orientation_relaxed=false`
  no longer conceals an overwritten rotation target.
- Position-priority orientation cost scale is now 0.5 rather than 0.1.
  Mink squares cost-weighted residuals, so the orientation term retains 25%
  rather than 1% of its normal strength. Projected goals retain full cost.
- Velocity/acceleration limits, the current +/-45 deg shoulder-yaw envelope,
  collision checks, and return behavior were not changed in this correction.
- A/B replay against `51b9035` used the same 840 active targets from
  `mink_v5_right_arm_20260917_153809_875.csv`, held according to recorded
  send timestamps at the fixed IK timestep (1,629 ticks per variant).
  Rotation median: 50.24 -> 20.11 deg; p95: 96.83 -> 78.83 deg;
  final two seconds median: 96.79 -> 10.35 deg. Position p95:
  18.59 -> 17.75 cm. Both variants had no rejected/braking steps or
  acceleration violations, minimum clearance >=5.49 mm, and yaw <=45 deg.
- A recorded final-pose fixture, initialized at rest for a static regression,
  reduces >90 deg rotation error to <5 deg within 600 ticks while remaining
  collision checked, rate limited, and preserving other joints. This fixture
  is derived from simulated joint values, not measured G1 state.
- Remaining: fast rotation still produces a maximum ~119.58 deg transient
  in both A/B runs. This change corrects sustained orientation abandonment;
  fast transient response is not solved. Live Quest retesting remains pending.
- Executed validation: upstream tracking, standard Mink, virtual-center
  trajectory, simulation handoff boundary, and runtime compatibility suites:
  **46 tests and 18 subtests passed**. The static fixture finished at 1.50 deg
  rotation error, 5.50 mm clearance, and 45 deg shoulder yaw. Local simulation
  runtime receives the identical tracking source; restart Input to load it.
- Reproduce from the repository root (Python with the existing Mink dependencies):

  ```powershell
  py -3.11 experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py <simulation.csv> --baseline-ref 51b9035 --output logs/test_results/wrist_rotation_ab.json
  ```

  The script rejects multi-episode input, uses no transport, and includes
  source/CSV hashes in the report. Original logs are preserved. Timing between
  logged targets is reconstructed; this is not exact replay of unlogged IK ticks
  or hardware validation. No G1 SSH, SDK/DDS initialization or output occurred.

- The current Unity scene and sender now require a continuous 1.0 s
  thumb-index pinch before emitting `pinch_disengaged` (previously 0.5 s).
  This follows a recorded false/accidental sustained-pinch disconnect; it does
  not alter tracking-loss handling or any G1 output path.
- Raw Quest tracking loss is now distinct from a wrist-pose speed outlier.
  A pose outlier holds the last valid target without clearing calibration or
  starting the return cycle; a real loss of tracked/high-confidence input for
  0.35 s still emits `tracking_disengaged`. This addresses a recorded run where
  raw tracking stayed valid but computed wrist speed jumped to 9.18-12.01 m/s.
- User clarification established that the triggering motion was intentional and
  fast. The wrist input gate is therefore 5.0 m/s instead of 1.1 m/s, and its
  diagnostic speed uses consecutive observed frames instead of distance from
  the last accepted frame. Joint velocity/acceleration limits remain unchanged.
- A subsequent run retained 69 mm position error with elbow joint 25 at its
  5-degree lower limit while orientation error fell to 5.65 degrees. The
  position-priority state originally ramped orientation cost to zero instead
  of 25%; subsequent corrections used a 10% floor and now use a 50% cost
  floor (see current correction above). Its original rotation goal is retained and restored after
  positional recovery. Runtime packets record the priority flag and scale.
- The next replayed live run exposed a separate hysteresis gap: position error
  settled near 33 mm with elbow 25 at its 5-degree limit, below the old 80 mm
  entry threshold, so position priority never activated. Entry is now 25 mm
  while constrained, and full orientation cost returns only below 10 mm or
  after leaving the constrained region.

## 2026-09-17 IK/Omni time-series capture

- Added a receive-only Mink logger for `g1.mink.right_arm.state.v1` on Windows loopback UDP 5008. It validates the complete 29-joint order and the duplicated right-arm indices 22-28, then records the seven targets in radians before any G1 relay/controller.
- The final IK CSV column, `raw_json_text`, preserves the complete UTF-8 UDP JSON plaintext alongside the parsed fields.
- Extended the existing Omni read-only CSV with raw `movementXY`/arm yaw, yaw relative to the first sample, wrapped per-sample yaw difference, raw yaw rate, and mapped `vx/vy/yaw_rate` with explicit units.
- Operator instructions and field definitions are in [IK_OMNI_TIMESERIES_20260917.md](IK_OMNI_TIMESERIES_20260917.md).
- No G1 SSH, SDK, DDS, publisher, relay, or motor output was used. Tests use generated fixtures only; Quest/Omni hardware capture remains an operator step.
- Restored the selected fast Quest-following limits in the standard virtual-center path: shoulder/elbow 90 deg/s, wrist 180 deg/s, and all right-arm joints 60 deg/s^2. This source change is not physical-G1 validation.
- Restored the user-confirmed simulation v5 path for IK CSV capture. It now
  separates the raw Quest wrist target from a model-derived collision-effective
  target. A wrist target inside the torso exclusion volume is projected to the
  nearest outside face using the torso mesh bounds, wrist collision radius and
  configured clearance. While projection is active, position continues moving
  along that outside boundary so an operator can route the hand around the
  torso. The old behavior replaced raw wrist orientation with the current
  wrist orientation; the current correction above removes that substitution.
  The front-of-torso correction above now permits bounded elbow assistance
  for projected targets. When the
  raw target leaves the exclusion volume, normal position and orientation
  tracking resume. Raw/effective positions, projection distance and the
  orientation-relaxed flag remain in runtime and raw-JSON CSV diagnostics.
  Recorded-problem regression coverage bounds elbow lift below 3 cm. This is
  MuJoCo/offline validation only.

## Laptop migration checkpoint

This integration branch combines the latest published continuation with the laptop source. Read [migration status](migration/20260917/README.md) and [two-PC synchronization rules](migration/20260917/TWO_PC_SYNC.md) first. Local historical notes are preserved in [LAPTOP_CHAT_HANDOFF.md](migration/20260917/LAPTOP_CHAT_HANDOFF.md). Conflicting temporary-worktree work is stored as patches, not enabled in this checkout. This is source synchronization, not hardware validation.

### 2026-09-17 scope change and last locomotion evidence

- GitHub-to-desktop continuation was the 2026-09-17 migration plan; see the
  2026-09-18 clarification above. Current work remains on the laptop.
- Lower-body policy development in this repository is stopped. Another developer will provide that policy; later work only integrates it with the Unity/Mink upper-body target and the single LowCmd owner.
- Do not repeat the preserved velocity 12DoF physical trial. In the last `+vx=0.05` axis trial, the policy transition reached approximately roll `-0.19 rad` and pitch `+0.34 rad`, then the controller stopped on `RuntimeError: IMU roll/pitch limit` and retained the last valid full-body position command.
- The robot was reported stable in its support rig after that event. This observation is not policy validation.
- Existing locomotion sources, MuJoCo results and logs remain historical evidence. Their presence is not authorization to deploy or run them on G1.


## 1. Start here

For every new project conversation:

1. For current laptop bimanual work and any later desktop migration, use `codex/g1-laptop-sync-20260917`. `main` remains the canonical branch after review and merge.
2. Read this file, [`ARCHITECTURE.md`](ARCHITECTURE.md), and [`REVIEW_LATEST.md`](REVIEW_LATEST.md).
3. Read the relevant review/remediation log before changing a reviewed defect.
4. Read [`CODE_GUIDE.md`](CODE_GUIDE.md) before changing a control path.
5. Inspect current HEAD and working-tree state before edits or cleanup.
6. Keep review findings, production changes and physical tests separately labeled.

Do not remove safety checks, loosen limits or change gains merely to make a test pass. Do not treat unit/static/simulation/transport tests as physical validation.

## 2. Repository checkpoint

```text
Repository : Y1048/Y
Primary branch : main
Old main archive : archive/old-main-20260820
```

`main` contains the former `refactor/teleop-architecture` work. The old refactor branch has been retired by the user. Do not target it in new automation or Codex instructions.

The default launcher remains:

```text
START_VR_HAND_TO_MUJOCO.bat
```

It launches the provenance-marking virtual-center entrypoint; `--baseline` uses the corresponding prototype entrypoint.

## 3. Current remediation/review state

The precision review records R1-R67 and remains incomplete. `REVIEW_LATEST.md` is authoritative for current status.

Key state:

- **R15/R35/R65** supported command provenance/freshness paths are source-mitigated and current-checkout CI is green.
- **R21/R51** supported LowState startup paths use per-run forward tokens and provenance/state/raw-odometry-bound prechecks.
- **R1/R3/R34/R64** have source fixes with offline regression coverage.
- **R2/R33/R41/R42** supported Gate 7/Jog collision/acquisition guards have offline regression coverage.
- **R46** is integrated into `g1_right_arm_jog.py`; planned/fault release share the SDK-neutral finalizer and incomplete evidence is fail-closed.
- **R40** supported physical paths bind current 29-joint/model/config evidence and raw `rt/odommodestate` position/quaternion back to startup, while requiring live base stability. Connected-G1 validation is still not done.
- **R50** supported paths supervise LowState IMU roll/pitch, motor temperature/fault/tau finiteness, and runtime base/odometry stability. Remote/deadman and CRC/integrity remain open until actual read-only SDK fields are verified.
- **R20/R24/R27/R32** remain open. Latest full-text review reconfirmed R20 benchmark/replay exit semantics, extended R24 to remaining stale velocity tests, retained R27 as the generic SE(3) matrix-validation boundary, and left R32 as direct V1 protocol integer coercion versus strict V2.
- **R53** remains open. Camera validation and inspection-scene tests add shared generated-MuJoCo-XML writer surfaces to the existing model/evidence provenance finding.
- The bounded 308-file source inventory is fully read. This closes the review queue only; it does not close any R-number or authorize physical output.

## 4. Reconciled review coverage

Current canonical ledger:

```text
total current scoped files : 311
full_text_review           : 311
static_only                : 0
static check failures      : 0
```

Use:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

Latest review batches:

```text
docs/REVIEW_20260904_BACKEND_CORE.md
docs/REVIEW_20260904_BACKEND_SUPPORT.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_2.md
docs/REVIEW_20260904_BACKEND_DIAGNOSTICS_3.md
docs/REVIEW_20260904_LAUNCHERS.md
docs/REVIEW_20260904_CONFIG_AND_FRAME.md
docs/REVIEW_20260904_RECOVERY_MULTISTRATEGY.md
docs/REVIEW_20260904_REMAINING_EXPERIMENTS_AND_HARDWARE_HELPERS.md
```

The current bounded inventory has no remaining `static_only` files. This is
full-text review coverage, not a correctness or physical-validation claim.

## 5. Offline regression evidence

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

These workflows are robot-offline and create no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection.

## 6. Immediate next work

```text
1. Keep R20/R24/R27/R32 remediation separate from completed review bookkeeping.
2. Preserve the experimental TWIST2 R43-R45/R49 block before any further physical use.
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first.
4. Plan simulation/WSL integration checks with hardware output locked.
5. Reconcile CODE_INDEX/source_checks whenever scoped files change.
```

The first explicitly approved right-shoulder-pitch sign/response trial completed
on 2026-09-04. `Q` increased raw q and moved the arm backward; `Z` decreased raw
q and moved it forward. The run also included an absolute-zero `A` input, so it
is not a strict +/- one-step acceptance test. See
[`PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md`](PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md).
Do not expand physical testing without a new exact approval.

The captured 1,538-row full-body CSV now has a local-only visual replay at
`experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat`. It maps
measured `q_0..q_28` directly to the canonical MuJoCo motor order and creates no
Unitree SDK, DDS, socket, publisher or robot command. Automated schema/model
validation passes; the human visual sign comparison is still pending.

## 6A. Rejected Mink collision-boundary experiment

The temporary split-clearance experiment was rejected after the first
Quest/MuJoCo visual test. It allowed the torso/right-shoulder-yaw pair to reach
12.0018 mm and produced an abnormal arm posture. The rejected 20/12 mm split is
not active and the policy identifier remains `checked_local_lookahead_v1`.
Collision settings are selected explicitly. Local Unity/MuJoCo launchers now
default to Mink's 5/10 mm distances. The Gate 7 hardware launcher passes
`--hardware-display`, which always forces the guarded 20/40 mm profile. The
physical adapter still applies its independent 12 mm hard stop.

Do not reapply the rejected 20 mm QP / 12 mm post-QP split. Evaluate the
MuJoCo-only 5/10 mm profile before changing planner merit or tangent behavior,
and do not use it as an implicit physical-output policy. See
`docs/REMEDIATION_20260904_MINK_COLLISION_PROGRESS.md`.

A 2026-09-04 automatic wrist-only preference experiment was rejected and
removed after the first Quest test. Per-frame hand-motion classification
latched during ordinary motion; the 51.08-second active trace drove the elbow
from 55 to its 5-degree lower limit, reported collision limiting for 738 frames,
and produced 16.19 cm position-error p95. Do not restore that detector or its
target-position latch. The pre-existing wrist/proximal redundancy issue remains
open and needs a continuous objective or explicit operator mode, not this
discarded heuristic.

The first retest after this rollback did not exercise the local 5/10 mm
profile: PID 35608 was still bound to UDP 5005/5012 with the old explicit
`--collision-profile hardware-guarded` command. Runtime status showed the
torso/right-shoulder-yaw pair stopped at 20.0005 mm. The local stale process was
identified and closed; the next ordinary launcher run starts with 5/10 mm.

The subsequent 5/10 mm retest reached the true local boundary at 5.0011 mm.
Local simulation now uses `mink_local_detour_checked_v1`: a 5.5 mm QP reserve with
a 5.0 mm nonlinear validation floor, and geometry-safe tangent steps do not
need strict per-frame merit decrease. `hardware-guarded` remains monotone and
unchanged. Reconstructed first-step evidence changed the saved boundary pose
from zero motion to a 0.0764 degree maximum joint step without dropping below
5.0011 mm. This is local avoidance, not a global path planner; APF or a broader
path layer is still required if the short waypoint reaches another local minimum. The first
local detour is an 8 cm outward waypoint, held for at most 30 frames before the
unchanged operator target is retried. A measured-pose 180-frame offline
regression requires at least 120 moving frames, lower final target error and a
5 mm minimum checked clearance.

## 7. Hardware boundary

- Repository hardware authorization remains locked.
- Do not assume G1 Ethernet, WSL DDS, Unity, Quest or any publisher is currently running.
- No physical command, G1 file mutation, service/mode change or administrator network change is authorized by this handoff.
- Runtime-base changes add only read-only `rt/odommodestate` subscriptions on supported physical paths; they have not been executed against G1 in this remediation session.
- Preserve calibration and intentional local work; inspect Git state before cleanup/reset/restore.

## 8. Historical handoff

Historical detail remains in [`CHAT_HANDOFF_HISTORY_20260903.md`](CHAT_HANDOFF_HISTORY_20260903.md). Use this current handoff and `REVIEW_LATEST.md` first.

## 9. 2026-09-14 main-baseline continuation

Fetched `origin/main` and confirmed it exactly matched
`0da866f7833c21ee1898c3e3ccf7932cdb401475`. The older dirty
`codex/g1-regular-handoff-20260910` worktree was left untouched; continuation
uses a clean branch from current main.

Phase 1 of `G1_REAL_SYSTEM_ID_NEXT_20260913.md` now has an offline foundation:
`real_response_log.py` supplies a versioned, strict, asynchronous local trace
sink, while `real_response_identification.py` supplies a gap-refusing low-order
offline fitter skeleton. Neither module imports Unitree SDK/DDS, creates a
publisher/socket, emits `LowCmd`, modifies gains, or connects to G1. See
`G1_REAL_RESPONSE_LOGGER_20260914.md` for schema, tests, limits and remaining
integration work. This is offline infrastructure, not measured-G1 evidence or
a hardware gain recommendation. The five new focused tests and the existing
recorded-target parser regression pass on Windows Python 3.14.

The same branch now integrates a passive `real_response.jsonl` sink at the
existing single LowCmd owner's completed 500 Hz writer frame. It separates the
original joints 22..28 target from the final shaped command and pairs both with
the LowState, estimated torque, IMU, temperature and status values already read
by that writer. Two focused C++ offline tests pass with strict warnings enabled.
The Unitree/ARM controller has not been linked, deployed or run, so the next
step is an ARM compile-only review followed by a separately authorized small
measurement—not immediate gain optimization.

## 2026-09-14 read-only system-identification foundation, isolated continuation

Current user priority supersedes earlier PD48/5 and mode-research plans:
measurement -> real model identification -> unused-episode validation -> PD
optimization. Mode research stays HOLD. Later clarification permits data
acquisition, but no robot connection/actuation was needed or performed here.

Fetched remote and compared local branches/worktrees. origin/main0da866f,
origin/codex/g1-main-continuation-20260914=5de8586; main is an ancestor.
The former isolated worktree contains uncommitted unrelated shutdown/diagnostic
work; it is preserved. New initially clean independent working copy:
C:/Users/user/AppData/Local/Temp/g1_sysid_offline_20260914, same continuation branch.
The dirty live tree remains on05d4ebf with423status entries at initial inventory.

Added sysid_capture.py (29-axis v2 immutable-byte queue/file sink and parser),
sysid_model.py (training-only delay/first-order fit and separate recursive
validation), test_sysid_pipeline.py and G1_SYSID_OFFLINE_PIPELINE_20260914.md.
No inherited controller/hook, v1 logger, launcher, gains, model, IK or transport
files changed. New module is not connected to the existing writer. v1 files are
legacy, not automatically converted or used by this v2 identification pipeline.

Actually executed: Windows Python3.14 unittest,21new generated-fixture tests plus
5existing v1 tests =26passed,0failed. Known fixture40msdelay and first-order lag
recovered; independent session validation passes; changed-delay validation fails
without retuning. Preservation test, ordering, malformed/nonfinite, clock/gap,
exact bytes, queue/file failure and leakage cases covered. No new MuJoCo runs,
ARM/C++ build, SDK/DDS, SSH, physical output, hardware gains or mode switching.

actual parameter identification is data-blocked: no suitable excited and held-out
real v2 episodes available. Earlier handoff-only trace has constant arm commands.
Effective delay/lag are fixture-only closed-loop estimates, NOT motor latency or
inertia; physical damping/friction/inertia/load require additional identifiable
models/data and remain null. recommended_hardware_gains=null always.
Uniform aligned-clock fitter deliberately rejects asynchronous real frames;
future timestamp-aware fitting/adapter timing validation remains separate work.
Current task delivers the offline foundation, not a deployed hardware recorder.

## 2026-09-14 next data-readiness check

User explicitly permits data acquisition and reports powered-on ZeroTorque.
Read-only SSH inventory only (no controller launch/setter/SDK/DDS): known response
build/cycle directories contain only the already retrieved real_response.jsonl
under trial1789346113063495_6812; PID6812 is absent at this observation.
No new trace copied and no physical state changed. Does not prove no other PID.
Local v1 inspection:2500records,4.997848125s,0sequence gaps,2repeated states,
0conflicting repeats; all7command excursions0rad. Report in
validation/g1_sysid_20260914/legacy_readiness.json, raw source hash retained.
Added reusable sysid_inspect_legacy.py; it does NOT fabricate29-axis fields,
write-begin timestamps, missing clock metadata or receipts. fit_ready=false.
23tests actually passed (2new inspector+21v2 pipeline); preservation scope still
excludes only explicitly new file-only sysid modules/tests. No hardware gains.

Next meaningful implementation is a reviewed native observer adapter that
captures all required existing writer values without changing control decisions,
plus timestamp-aware fitting. Actual excited training and separate validation
captures remain missing. More stationary ZeroTorque samples alone cannot fill
that gap. No new motion authorized/executed by this data-inventory step.

## 2026-09-14 native observer hook candidate (not deployed)

Added sysid_native_observer.hpp: SDK/transport-free fixed-size2048-slot SPSC ring,
POD29-axis snapshot and worker-only JSON/file encoding. Lock-free index assertion,
nonthrowing Offer, overflow/failure receipt, exclusive file creation. Producer
makes no allocations, file writes or queue waits in Offer; actual callback timing
is not benchmarked/guaranteed. A native receiver/publisher is NOT created by it.

Existing Controller start_response_log optionally starts v2 only when
G1_SYSID_CAPTURE_V2=1. Defaults and launchers are unchanged. Records include actual
write-begin/end steady-clock nanoseconds, original full target, post-limiter
command/dq/gains/feedforward, paired29-axis q/dq/torque/temperature/status and
IMU rpy/gyro/acceleration. Mode is null (no extra RPC), acceptance unknown.
Output is real_response.jsonl.v2.jsonl with SHA-bound receipt on explicit finish.
Native Finish detaches under writer mutex, then drains/hashes outside it; native
setup/finish failure only reports incomplete recording. Existing v1 logger code
and its exception/lifecycle semantics are inherited, not repaired by this patch.
A killed process/destructor-only cleanup has no completion receipt: reject it.

Actually executed:2 SDK-free C++/Python tests in WSL using g++17 mode and
-Wall -Wextra -Werror (ring full/empty, exact29-axis mapping through Python parser,
exclusive output, nonfinite encoding/worker failure), plus21Python v2 tests on
Windows. All passed. Source comparison confirms motor equation block unchanged
and no added publisher Write call. Preservation test now explicitly excludes the
reviewed observer hook cpp; its command equations are checked separately.
Full Controller ARM compile, SDK field compatibility, callback timing, real v2
capture and asynchronous fitter integration remain unverified. No G1 SSH,
deployment, mode or gain change this turn. Do not run the candidate yet.

### 2026-09-14: asynchronous offline identification and compile-only check

Added sysid_async_model.py and generated tests: shared-host-clock asynchronous
command/state integration, frozen delay/lag grid, independent episode validation,
leakage/gap/invalid-model rejection. See G1_SYSID_OFFLINE_PIPELINE_20260914.md for
commands and interpretation limits. Actual parameter identification is data-blocked;
recommended_hardware_gains=null. No PD optimization or hardware recommendation.

Full local WSL x86_64 controller compile/link passed with Torch header warnings;
controller binary was not executed or deployed. Windows numerical/schema tests32
and WSL SDK-free native tests2 passed (native suite initially failed under Windows
because g++ was absent, then rerun in WSL). Fixtures are generated, not measured.
Existing motor equations, gains, model and launch paths remain unchanged this turn.
No SSH, SDK/DDS initialization, motor output, mode work or live worktree changes.
ARM/runtime timing/real v2 capture remain pending; do not interpret compilation as
hardware approval. Prior ZeroTorque/hold data is insufficient for dynamic fitting.

### 2026-09-14: standalone read-only DDS capture on G1

Added `sysid_readonly_dds.cpp`, a subscriber-only aarch64 logger for `rt/lowcmd`
and `rt/lowstate`, plus strict parser, quiet-summary utility and tests. Static
checks require zero `ChannelPublisher`, motion client and command-write symbols.
It uses an asynchronous heap ring. An initial pre-fix launch segfaulted before
creating a file because the large ring was on the stack; moving it to the heap
fixed the issue. That failed attempt produced no command and no measurement file.

The corrected ARM binary SHA is
`80d854e0492a6adadfef329d9447ae66f26bec994c4d7109aa9cd91646f4a1ad` in
`/home/unitree/g1_sysid_observer_437db16`. Three 5 s subscriber-only runs in the
user-reported ZeroTorque state produced 15,742 LowState records, zero observed
LowCmd records and zero ring drops. No actuation or mode change was performed.
Raw logs/receipts are durably copied to
`C:/Users/user/Documents/G1_SysID_Data/20260914_zerotorque_readonly`; Git contains
only their hashes/statistical summary and deployment receipt. Repeated state tick
values occurred 263/262/264 times while data changed, so tick is diagnostic, not
treated as a unique sequence number.

Actual state data now exists, but actual dynamic parameter identification remains
blocked on controlled command excitation and an unused validation capture.
`recommended_hardware_gains=null`. Do not use the existing PD sweep: it changes
Kp 40/48/56 and reaches the deferred mode-handoff path. Next code task is a fixed
current-gain, bounded per-joint identification trajectory with an explicit
termination/ownership contract; physical execution requires separate review.

### 2026-09-14: offline excitation-plan contract

Implemented the next code task as `sysid_excitation_plan.py`, an offline-only
plan generator with no execution/SDK/DDS/network/controller path. It requires a
SHA-bound controller, exact29-axis start/soft-limit/Kp/Kd vectors and explicit
seven-axis amplitudes, speed and acceleration limits. It produces sequential
one-joint quintic moves; analytic peak velocity/acceleration are bounded and
training/validation reverse joint order and initial sign. Output explicitly says
`command_capable=false`, `execution_authorized=false` and
`recommended_hardware_gains=null`.

The termination owner is an explicit unresolved/reviewed contract in the input.
Current status remains unresolved because handoff research is on hold, so this
plan is not connected to LowCmd and is not a physical-run instruction. See
`G1_SYSID_EXCITATION_PLAN_20260914.md`. Generated tests cover order, limits,
analytic bounds, deterministic hash binding, malformed/nonfinite inputs and
absence of transport imports. No G1 connection or output was performed.

Added `sysid_excitation_readiness.py` as the next offline gate. It compares the
plan against a strict completed `g1.sysid.readonly-dds.v1` capture and reports
tail pose error, right-arm velocity, observed modes, command coverage and gain
agreement. Pose/velocity tolerances are mandatory caller inputs so no unmeasured
physical threshold is invented. Missing LowCmd produces unknown gain agreement;
it is never relabelled as a match. The output always keeps
`physical_execution_authorized=false` and `recommended_hardware_gains=null`.
Generated tests cover matching evidence plus pose, motion, gain and unresolved-
owner blockers. The three existing ZeroTorque captures were not converted into
an excitation plan because they have no commands and their posture is not an
approved controlled start. No G1/DDS/controller execution occurred.

Added `sysid_excitation_request.py` to remove manual29-vector transcription.
It extracts literal gains/soft limits from the chosen C++ common header, derives
a median start pose only from a caller-bounded stable tail, and hash-binds the
capture plus common/controller sources. All motion limits and ownership text
remain required in a separate draft spec; there are no physical defaults. It
rejects moving, short or variable-mode captures and validates the resulting
request through the plan builder. The output receipt remains explicitly
non-authorizing. Generated tests verify the current right-arm gain extraction,
hash binding, motion rejection, malformed-source refusal and absence of command
imports. Existing ZeroTorque data was not promoted to an approved start pose.

Added `G1_SYSID_EXCITATION_DRAFT_SPEC_20260914.json`. It reuses the existing
joint22 small-signal shape (±8deg,20deg/s,60deg/s²,3cycles) across seven
sequential axes only as a review draft. The extension to joints23..28 is marked
unvalidated, tail thresholds are not claimed as measured noise, and termination
ownership remains unresolved. Draft receipts now hash and retain a mandatory
human-readable parameter basis. This does not authorize or implement motion.

Fixed an ambiguity in the offline plan: every post-move hold now carries the
active joint index/name and exact held offset. Added `sysid_excitation_preview.py`
to expand plans to sample-level training/validation CSV plus a hash-bound summary.
It rejects discontinuities, off-grid segments and nonzero final offsets and has
no command path. The current draft shape computes to169segments and116.252s per
episode (232.504s combined), but no actual start pose has been selected and no
physical run is authorized or claimed.

Added `sysid_excitation_reference.hpp` as an SDK-free C++ implementation of the
same grid-rounded quintic waveform used by the offline Python plan/preview. It is
pure trajectory math and is not included by any LowCmd writer, DDS process or
robot controller. The native C++ test checks the complete 2 ms grid, endpoint
clamping, monotonic position and the draft 20 deg/s and 60 deg/s² bounds; a Python
test checks constants/formulas and the expected 0.878 s move duration. This is an
offline integration reference only. No G1/DDS/controller was run, command-owner
and termination behavior remain unresolved, physical execution is unauthorized,
and `recommended_hardware_gains=null`.

Added `sysid_excitation_sequence.hpp`, an SDK-free deterministic C++ sequence
core over the reference quintic. It consumes an explicit 29-axis start vector and
in-memory hold/move segments, rejects nonfinite/off-grid/discontinuous/non-returning
plans and only permits active joints 22..28. Its native test sequentially moves all
seven right-arm joints and proves every inactive joint is held exactly, targets do
not overshoot, and the final 29-axis vector equals the start. The sequence core
has no writer integration, DDS, publisher or robot executable; its separate
offline saved-plan adapter is recorded below. Command-owner and termination work
remain on hold.

Added `sysid_excitation_plan_adapter.hpp` and the file-only
`sysid_excitation_plan_check.cpp`. The adapter refuses executing/authorized plans,
non-null hardware recommendations, wrong 29-axis/right-arm identity, soft-limit
breaches, discontinuities, nonfinite values and altered analytic peak metadata.
It constructs training and validation sequences without any SDK, DDS, network,
publisher or controller path. The compiled checker successfully opened a plan
produced by the Python generator and reported matching 47,906-tick episodes at
2 ms. Native malformed-plan tests and static dependency tests passed. Nothing was
connected to the robot runtime; physical acquisition and gain selection remain
blocked pending a reviewed procedure, and `recommended_hardware_gains=null`.

Added the file-only C++ `sysid_excitation_plan_dump.cpp` and Python
`sysid_excitation_crosscheck.py`. The native dumper expands a saved episode while
the Python checker independently compares every time, segment, active-joint,
seven-offset, velocity and acceleration field. An executed generated-fixture run
matched all 47,907 rows in both training and validation; maximum numeric error was
`8.526512829121202e-14`. Tests reject changed, missing and nonfinite samples and
statically exclude transport/robot dependencies. This is generated evidence, not
measured G1 data, and no physical execution or gain recommendation follows.

Added detached `sysid_excitation_writer_hook.hpp` after confirming the existing
policy loop is 50 Hz while LowCmd construction is 500 Hz. Passing the 2 ms plan
through the policy loop would drop nine of ten samples, so the candidate models
the later writer boundary but is not included by the physical controller. It
returns only seven right-arm targets, holds the final start pose and rejects
unarmed use, wrong writer period, start-pose mismatch, current Kp/Kd mismatch and
nonfinite inputs. The adapter now retains/validates planned 29-axis Kp/Kd for this
check. Native and static tests passed; the physical controller SHA remains
`aa38a2e7d7e1686493b9c535ee2d13636856025f1a67928ef4c9290da5e01359`.
No CLI option, SDK/DDS execution, publisher, gain change or G1 access was added.
Actual integration still requires reviewed arming tolerances and completion/fault
ownership. `recommended_hardware_gains=null`.

Added detached `sysid_excitation_runtime.hpp` with explicit disarmed, running,
complete-hold and fault-hold states. Each sample carries plan/request hashes,
contract, termination-owner status, episode, tick, segment and active joint. A
latched fault after the first valid sample freezes the last seven targets, reports
zero planned velocity/acceleration, preserves the first reason and stops tick
advance; normal completion holds the original arm start. The adapter now validates
and retains request/contract/owner provenance. Tests cover both hold paths, bad
hashes and pre-sample fault rejection. This remains detached from the observer and
physical controller, which is still unchanged. No G1/DDS/publisher/gain action was
performed and `recommended_hardware_gains=null`.

Added detached `sysid_excitation_observer_bridge.hpp` and an optional fixed-size
excitation tag to `sysid_native_observer.hpp`. It preserves plan/request/contract/
episode provenance and records runtime state, tick, segment, active joint, seven
planned arm positions, velocity/acceleration and bounded fault reason through the
existing asynchronous ring. Existing observer callers remain source-compatible
and emit the prior schema shape when no excitation context is supplied. The bridge
does not assign target/command/measured/gain/torque arrays; native tests compare
those arrays before/after and exercise the asynchronous file worker. Focused
Python tests 28 and SDK-free C++ bridge/runtime tests passed; the existing native
observer's two tests also passed when rerun with the WSL worktree Git path supplied.
The first native rerun had one environment-only Git worktree-path error while its
ring/schema test passed; the corrected rerun passed both. The physical controller
is still not connected or changed. No G1, DDS, publisher, gain or motor action was
performed; `recommended_hardware_gains=null`.

Final bridge verification also ran the full 73-test Python regression set, every
SDK-free excitation C++ test/tool, and a complete local x86_64 compile/link of
`g1_twist2_mink_cycle_trial` using the existing Unitree SDK/Torch files. All
completed successfully; the controller binary was not executed. Third-party SDK
and Torch warnings remain. This is compile/offline evidence only, not ARM timing,
hardware validation or execution authorization.

Connected the excitation runtime to the actual 500 Hz writer source as a dormant
integration seam. `twist2_mink_cycle_trial.cpp` has no CLI/launcher caller and its
runtime pointer defaults null, so existing executable behavior is unchanged. A
future installation is rejected unless it precedes writer start, capture is ready,
the owner contract says `reviewed`, current gains/start pose match and V2 logging
is enabled. The checked-in draft remains `unresolved` and cannot install. When
installed, only desired joints22..28 come from the 2 ms sequence; the existing
slew/range/torque clamps and single `publisher_->Write(command)` remain unchanged,
and the observer separates plan target from actual constructed command. Static
tests confirm there is exactly one installation method definition and no caller or
`--sysid-excitation` option. Focused Python28, native C++ runtime/bridge, native
observer2 and full local x86_64 controller compile/link passed. The binary was not
executed. New controller source SHA is
`af9f8e7bf988766b42210e75c9f909826bba0d2d0d369531d1f11b65a07c75a6`.
No G1/SSH, DDS initialization, deployment, publisher execution, motor output or
gain change occurred. Termination ownership and a physical caller remain blocked;
`recommended_hardware_gains=null`.
## 2026-09-17 position-priority posture correction (simulation only)

- The latest simulation CSV `mink_v5_right_arm_20260917_150853_846.csv` showed that the apparent excessive elbow bend was not elbow flexion: joint 25 reached its 5 deg extension limit while right shoulder yaw reached its 150 deg upper limit and wrist pitch approached -80 deg.
- Root cause: the position-priority fallback reduced wrist orientation cost to zero, leaving the redundant 7-DOF solution free to wind shoulder yaw toward its limit.
- Position priority now retains 10% of the normal orientation cost and temporarily raises only the right shoulder-yaw posture cost to 8.0, referenced to the captured engage posture. Normal orientation and posture costs are restored when priority ends, on pinch return, and on reset.
- Offline replay of the 1,238 active targets from that CSV reduced maximum shoulder yaw from the recorded 150 deg to 79.98 deg. This replay does not reproduce Unity timing exactly and is simulation evidence only.
- Verification: `backend/tests/test_upstream_mink_tracking.py` and `backend/tests/test_standard_mink_live.py` passed (35 tests, 2 subtests). No G1 SDK/DDS, publisher, SSH, or physical output was used.

### Follow-up: remove the perceived slowdown

- The temporary shoulder-yaw posture cost of 8.0 reduced not only winding but also requested shoulder-yaw velocity (recorded-target replay: about 79.5 deg/s at cost 2 versus 65.9 deg/s at cost 8). The user's slower-motion observation was therefore plausible even though the configured 90/180 deg/s caps had not changed.
- Replaced that cost penalty with a checked shoulder-yaw tracking envelope of +/-65 deg from the captured engage posture. It is expressed as acceleration-aware QP velocity bounds, so no posture penalty is applied inside the envelope; return behavior remains unchanged.
- The same 1,238-target offline replay held shoulder yaw at 65.0 deg, preserved the configured velocity limits, and reduced replay position-error p95 from 0.1795 m with the cost-8 experiment to 0.1571 m. Replay timing differs from Unity and is simulation evidence only.
- Verification: 45 tests and 18 subtests passed across upstream tracking, standard live Mink, virtual-center trajectory, simulation handoff boundary, and runtime refactor compatibility. No G1 output was used.

### 2026-09-17 follow-up simulation result and second correction

- The next simulation CSV `mink_v5_right_arm_20260917_153207_224.csv` confirmed the 65 deg envelope exactly: shoulder yaw stayed in 0..65 deg, with no tracking stop and only two acceleration-limited braking samples. Compared with the preceding cost-8 run, shoulder pitch/roll p95 speeds increased from 4.8/13.5 to 11.8/19.0 deg/s; the perceived whole-arm slowdown was not present, although shoulder yaw was intentionally constrained.
- The pose was still visually excessive because the solver repeatedly reached the 65 deg envelope and shoulder roll reached -62.7 deg. Recorded-target replay favored a 45 deg shoulder-yaw envelope: position-error p95 was 15.67 cm at 45 deg versus 16.12 cm at 65 deg.
- The QP approach-rate braking allowance was also changed from a 4x to the standard 2x acceleration-distance factor, without changing the configured 60 deg/s2 acceleration or 90/180 deg/s velocity caps. On the same replay, position-error p95 improved to 14.17 cm and most shoulder/wrist p95 speeds rose by roughly 15-30%.
- Verification after both changes: 45 tests and 18 subtests passed. Evidence remains simulation/replay only; no G1 output was used.

## 2026-09-20 Bimanual Unity-free preflight

Quest/Unity operator 테스트 전에 실행할 one-click gate를 추가했다:
`tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat`.

이 gate는 source/runtime parity, runtime SampleScene bimanual 설정, UDP 5020 free,
isolated MuJoCo 3.12.0과 simulation-only provenance를 검사한 뒤,
near-hands 12mm 경계 safe-pose 320개 sweep과 ephemeral-port 실제 UDP E2E를 실행한다.

최종 결과:
- preflight PASS, source/runtime parity 9 files.
- near-hands 160 + ordinary 160, false/missed trigger 0, min clearance 5.063977mm.
- 대표 return 4개 READY, max accel 50.557419deg/s².
- UDP: READY→TRACKING→RETURNING(pinch)→READY→TRACKING, accepted 9,
  min clearance 40.372503mm, max accel 33.886225deg/s².
- full bimanual suite source/runtime: 94/94 PASS.

preflight 과정에서 runtime `G1BimanualSimulationSender.cs`가 source의 commit
`45146f4` helper extraction을 놓친 동일동작 구버전임을 잡아냈다. runtime 원본을
`logs/backups/bimanual_sender_sync_20260920_134512`에 백업하고 source와 동기화했다.

상세: `docs/BIMANUAL_QUEST_PREFLIGHT_20260920.md`.
Unity/Quest 최신 operator feel은 아직 검증하지 않았다. 실제 G1, SSH, DDS, motor
output 및 물리 안전 검증은 범위 밖이다.

## 2026-09-20 post-session Quest verifier

Unity/Quest 테스트 후 수동 로그 해석을 줄이기 위해
`tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat`를 추가했다.
최신 operator session을 찾아 static safety/integrity report와 current-code replay를 수행하고,
engage → pinch return 완료 → re-engage가 없으면 strict failure로 반환한다.

report는 pinch return, re-engage, near-hands recovery, separation side를 직접 집계한다.
user-confirmed historical Quest fixture에서 cycle/replay 모두 PASS했다.

또한 원격 Unity launch 때 UPM 9.x가 필요로 하는 `PROGRAMDATA` /
`ALLUSERSPROFILE` / `TMP` 누락을 `RESOLVE_UNITY_EDITOR.bat`가
현재 CMD process에만 보강한다. machine/user 환경은 변경하지 않는다.

preflight parity는 12 files로 확장되어 PASS했고,
source/runtime bimanual suite는 각각 95/95 PASS,
runtime Windows tool-path contract는 23/23 PASS다.

## 2026-09-21 Quest operator acceptance 완료

최신 operator session `unity_20260921_091420_0176388.jsonl`에서 normal bimanual flow를 실제 Quest로 확인했다.

자동 verifier 결과:
- Quest cycle PASS.
- replay PASS.
- tracking starts 2 / re-engage 1.
- pinch return 2회 모두 complete.
- final READY.
- failures 0 / BLOCKED 0.
- replay min clearance 30.914499mm.
- max speed 43.090153deg/s.
- replay max accel 60.000000000005deg/s².
- tracking p95/max 12.360040 / 13.328100ms.

사용자도 re-engage 1회 정상 동작을 확인했다. 로그 sequence 491에서 두 번째 TRACKING으로 기록됐다.
원본 로그 SHA-256:
`d091391676a2603c88c7e7d501e5163e22cc92e02a6b22ce2a506650f2eacd21`.

첫 09:07 세션의 `quest_cycle_no_reengage`는 re-engage를 수행하기 전에 종료한 세션이라 발생한 범위 미완료이며,
09:14 세션이 최종 acceptance evidence다.

report의 acceleration comparison만 기존 controller regression과 같은 `+1e-4 rad/s²` numerical tolerance로 정렬했다.
60deg/s² 설정 limit은 변경하지 않았다.

near-hands recovery는 이번 실착 세션에서 발동하지 않았으며 기존 offline/replay 검증으로 남는다.
fixed-base Quest→Unity→MuJoCo normal operator flow는 이 checkpoint에서 완료로 본다.

## 2026-09-21 오른팔 단독/양팔 IK 비교 확장

`docs/BIMANUAL_SINGLE_ARM_COMPARISON_20260921.md`와 재현 도구
`backend/tools/compare_bimanual_single_arm.py`를 추가했다.
왼팔 home 유지, 오른팔 3축 ±45도 회전 및 3축 ±50mm 이동을 각 360틱 실행했다.
12개 모두 단독/양팔 관절 궤적 최대 차이 1.48744e-10도, 왼팔 변화 0도,
BLOCKED 0, 전체 최소 sampled clearance 12.3465mm였다.
다만 Y -45도 회전(14.898mm), Y -50mm 이동(13.822mm), Z -50mm 이동(37.716mm)은
두 방식 모두 6초 후 위치 오차가 남았다. 동등성은 확인했지만 추종 정확도 합격을
주장하지 않는다. 다음은 이 세 목표의 활성 제약/정착/도달 가능성 분석이다.
synthetic offline 데이터이며 새 Quest 또는 G1 검증이 아니다.
제어기/runtime/gain 변경 없음. 12사례 비교 및 결과 검사를 실행했고,
기존 전체 96개 회귀는 이번 작업에서 다시 실행하지 않았다.

## 2026-09-21 양팔 초록 목표 표시 수정

**이 최초 수정은 아래의 IK 입력 목표 표시 수정으로 대체됐다. 사용자가 초록원이
손목에 붙어 목표로 보이지 않는다고 지적했으며, FK 표시를 요구 충족으로 취급하지 않는다.**

사용자가 초록원/파란원이 함께 움직인다고 보고했다. 양팔 Unity 표시가 raw binder
target을 초록원에 사용하고 있었고, 기존 upstream 오른팔 경로는 수락된 IK 관절
자세의 FK 손목 위치를 사용했다. 이번에는 양팔 feedback에
`accepted_target_valid`, `left_accepted_target_operator_delta`,
`right_accepted_target_operator_delta`를 추가하고 양팔 초록 표시에 연결했다.
delta는 `BASIS.T @ (accepted_wrist_position - home_wrist_position)`이며 단위는 m이다.
Unity는 engage 기준 위치와 OperatorHeading으로 world 위치를 복원한다.
파란색/하늘색은 실제 추적 손목, 초록색은 수락된 IK 위치다. 이 위치를 최종 목표에
대한 도달 가능성 예측 또는 실제 G1 측정 위치로 해석하면 안 된다.
inactive/returning/blocked/braking, 오래된 feedback 또는 필드 누락 시 추종 초록원을
숨기며 raw 목표로 대체하지 않는다. engage 전 안내 표시는 유지한다.

source marker tests 2/2, protocol/loopback tests 8/8, Unity 참조 Roslyn 컴파일
exit 0/error 0, runtime marker tests 2/2를 실제 실행했다. 전체 96개 회귀는 미실행.
제어 solver/gain/trajectory는 변경하지 않았고 feedback의 q/velocity/tail 불변을 검사했다.
Play 정지 사용자 확인 후 runtime 4파일을 백업/설치하고 SHA-256 일치를 확인했다.
백업: `logs/backups/bimanual_markers_20260921_093535/`.
설치 및 컴파일 증거: `docs/validation/bimanual_markers_20260921/`.
새 Python Input 재시작 및 Unity 재컴파일 후 Quest 화면 확인은 남아 있다.
앞선 단독/양팔 비교에서 공통 오차가 컸던 3방향의 원인 분석도 다음 항목으로 유지한다.

## 2026-09-21 초록원을 IK 입력 목표로 정정

FK 기반 첫 수정은 사용자가 요구한 목표 표시가 아니었다. 현재 소스는
`ArmMotionPolicy.effective_target_position`을 사용한다. 이는 PairedHandFilter와
몸통 내부 목표 투영을 거쳐 실제 wrist task에 설정한 위치다. 현재 손목 위치나
checked look-ahead의 FK가 아니며, 최종 도달 가능성을 보장하지 않는다.
파란원은 측정 손목, 초록원은 처리된 IK 요청 목표다. 자유 공간에서 느리게 움직이면
둘이 겹치는 것이 정상이며, 지연 중에는 로봇 손목과 목표가 분리된다.
목표는 몸통 투영 때 raw 손 위치와 달라질 수 있지만 팔 간 충돌/관절 제한 때문에
실제로 도달하지 못할 수도 있다. 이 한계를 사용자에게 명시했다.

feedback 필드는 `ik_target_valid`, `left_ik_target_operator_delta`,
`right_ik_target_operator_delta`로 변경했다. 정상 입력으로 목표를 갱신했지만 QP가
감속 중인 경우에도 목표 표시를 유지한다. 입력 소실 감속, 복귀/blocked/ready에서는
추종 목표를 제공하지 않는다. 오래된 FK 버전 feedback을 새 표시로 해석하지 않는다.
source 테스트 3개 PASS: 5cm 요청 목표와 1틱 후 손목 분리, torso 투영,
상태별 무효 처리, feedback 생성의 제어상태 불변. 실제 Unity 참조 C# 컴파일 exit 0.
실행 프로젝트 반영 및 사용자 화면 확인 상태는 후속 기록 참조.

Play 정지 확인 후 이전 설치 hash와 runtime 4파일이 일치하는 것을 검사하고 설치했다.
백업 `logs/backups/bimanual_ik_goal_20260921_094014/`, 설치/컴파일 증거
`docs/validation/bimanual_ik_goal_20260921/`. runtime marker 3/3 및 source protocol
8/8 PASS. 새 Python 프로세스와 Unity 재컴파일 이후 Quest 시각 확인은 아직 남아 있다.

## 2026-09-21 양팔 손목-목표 연결선과 좌표 오차 진단

사용자가 도달 가능한 곳에서도 raw 파란 손목과 초록 IK 목표 사이에 오차가 있고
손목-목표 선이 사라졌다고 보고했다. 양팔 경로의
`SetActualTrackingObjectsActive(visible, false)`가 연결선을 끄는 것을 확인했다.
현재 소스는 양팔 각각 실제 표시 robot wrist → backend IK goal 연결선을 표시한다.
target 누락/stale/비tracking 때 숨기며 단독 표시 경로는 유지한다.

좌표 오차의 구조적 원인은 raw wrist와 engage 상대 목표의 기준점 차이가 가능하다는 점이다.
`CalibratedWristPosition`과 `EngagementTargetPosition`은 같은 위치로 강제되지 않는다.
따라서 도달 가능한 목표라도 raw 실제 손과 green target의 일치를 보장하지 않는다.
sender에는 movement scale/몸 이동 보정이 있고 backend에는 60ms 위치 필터와 몸통
투영이 있다. 사용자의 이번 오차에 각 요인이 얼마나 기여했는지는 아직 실측 미확정.
좌표를 임의로 바꿔 오차를 숨기지 않고 `[BIMANUAL TARGET]`에 calibration,
input_processing, backend_processing 3D 벡터(cm)와 전체 gap 크기를 기록하도록 추가했다.
세 벡터의 합은 green minus raw이며 벡터 크기끼리의 합으로 해석하지 않는다.

Unity 실제 참조 Roslyn 컴파일 exit 0/error 0. 제어/IK/필터 값 변경 없음.
runtime 반영과 정지 상태 사용자 확인은 후속 기록을 따른다.

사용자는 손을 멈추고 기다려도 오차가 남는다고 확인했다. 필터 지연만으로는 설명되지
않으며 기준점/몸 이동 보정/목표 투영의 실제 기여를 다음 로그로 구분해야 한다.
Play 정지 확인 후 이전 설치 hash 보존을 확인하고 C# 2파일을 runtime에 설치했다.
`docs/validation/bimanual_marker_lines_20260921/install.json`에 백업/설치 hash 기록.
화면 확인 및 새 `[BIMANUAL TARGET]` 로그 계측은 남아 있고 오차 해결 완료를 주장하지 않는다.

## 2026-09-21 실제 진단 후 engage 위치 잔여 보정

사용자 재시험 Editor 로그에서 고정 engage 차이를 계측했다: L 6.1634cm / R 5.3988cm.
마지막 실제 green/raw 간격은 L 6.12cm / R 5.30cm였으며 input_processing=0이었다.
`docs/BIMANUAL_ENGAGE_OFFSET_20260921.md`에 원인/실제 표본/수정 의미를 기록했다.
Unity hand packet에 `engage_offset_m`를 추가하고 Python이 engage 시 한 번 포착하여
실제 IK 위치 목표에 더한다. 단순 marker 이동이 아닌 simulation 위치 매핑 변경이다.
누락 필드는 0으로 이전 fixture/클라이언트 동작을 유지한다. 원점 변경을 임의의
후속 packet이 유발하지 않도록 cycle 동안 offset을 고정한다. 복귀 home/한계는 유지한다.

source 전체 bimanual suite **102/102 PASS** (93.713s), runtime 신규 관련 tests **6/6 PASS**,
Unity 참조 C# 컴파일 exit 0/error 0. 이전 recorded replay의 관절값 최대 차이는 0 rad.
Play 정지 사용자 확인 후 runtime 3파일을 백업/설치하고 hash를 대조했다.
백업 `logs/backups/bimanual_engage_offset_20260921_095215/`.
시험/설치 증거 `docs/validation/bimanual_engage_offset_20260921/`.
수정 후 Quest 화면 정착 오차 확인은 아직 필요하다. Python 재시작과 Unity 재컴파일이
모두 필요하며, 기존 프로세스는 새 mapping을 적용하지 않는다. 실제 G1 실행 없음.

## 2026-09-21 보정 후 operator 로그 확인

`unity_20260921_095254_4149346.jsonl`에서 READY → TRACKING → RETURNING(pinch) → READY, BLOCKED 0. Unity 최신 7개 marker 진단 쌍 중 6쌍은 각 손 0.06~0.30cm, 마지막 L 0.21cm/R 0.06cm. 기존 지속적인 기준점 차이는 크게 감소했다. 다만 중간 1쌍에서 L 5.90cm/R 5.96cm 일시 간격이 있으며 원인은 확정하지 않았다. 모든 순간 오차가 해결됐다고 주장하지 않는다. `docs/validation/bimanual_engage_offset_20260921/operator_check.json` 참조. 이번 확인은 기존 로그 분석이며 테스트 재실행/실제 G1 계측은 하지 않았다.

## 2026-09-21 일시적 목표 간격의 필터 재구성 분석

동일 operator 세션의 tracking 908 state를 accepted input sequence로 결합하고,
engage 시 position을 원점으로 포착한 뒤 dt=min(sender delta,0.1),
alpha=1-exp(-dt/0.060)로 위치 필터를 재구성했다.
재구성 목표와 실제 기록된 IK 목표의 최대 차이는 양손 모두 6e-17m 미만
(assert <1e-12m 통과). 해당 구간 target_projected는 양손 모두 0이다.
따라서 이 세션의 backend raw-to-goal 위치 차이는 60ms 필터로 설명된다.
raw 대비 목표 간격 중앙값 L0.573mm/R0.458mm, 최대 L49.227mm/R43.870mm.
tracking 입력 최대 간격은 41.021ms였다. 전체 세션의 1.25s 입력 간격을
tracking 중 gap으로 잘못 해석하지 않는다.

Unity의 5.90/5.96cm 표본에는 대응 sequence/time이 없어 정확한 단일 화면
표본까지 원인을 확정할 수 없다. 렌더링/피드백 지연 기여도 미계측이다.
정지 기준점 오류와 이동 중 필터 지연은 구분해야 한다. 이번 단계에서는
필터/IK/속도/실행 프로젝트를 변경하지 않았다. 기존 전체 회귀 재실행 없음;
실측 입력의 오프라인 수학 재구성만 실행했다. 실제 G1 검증 아님.
증거: docs/validation/bimanual_engage_offset_20260921/filter_gap_audit.json.

## 2026-09-21 양팔 잔여 오차 장시간 정착 진단

3개 synthetic 목표를 20초, baseline 및 posture 비용 제거로 총 7200 ticks 실행했다. 단순 정착시간 연장/자세 비용 제거로 잔여 오차가 해결되지 않았다. 상세 표와 재현은 `docs/BIMANUAL_SETTLING_AUDIT_20260921.md`, 원본 결과는 `docs/validation/bimanual_settling_20260921/`. 진단 도구만 추가했으며 실행 IK/Unity/runtime은 변경하지 않았다. 다음은 고정 방향에서의 운동학적 도달 가능성과 QP 활성 제약 분리 확인. 실제 G1 실행 없음.

## 2026-09-21 도달 가능성/QP 분리 진단

`docs/BIMANUAL_REACHABILITY_AUDIT_20260921.md` 참조. 144회 synthetic endpoint 탐색, 대조군 성공 검증. 3개 실패 목표는 요청 위치/방향을 동시에 만족하는 해를 못 찾았다. Y/Z 이동은 방향을 제거해도 각각 약10.7/34.6mm 잔여오차, 다수 미수렴이므로 전역 도달불가로 단정하지 않는다. 저장된 정착 q/속도0의 QP 부등식 slack은 모두 양수. 따라서 충돌/속도 한계만 완화하는 변경은 근거가 없으며 controller/runtime은 그대로 유지했다. 기존 잘되는 사용자 흐름은 유지하고, 이 synthetic 목표들은 일반적인 추종 정확도 합격조건으로 쓰지 않는다. 실제 G1 실행 없음.

## 2026-09-21 도달 가능한 양팔 목표 12조건 확인

`docs/BIMANUAL_KNOWN_TARGETS_20260921.md` 참조. FK witness로 생성한 왼팔5/오른팔5/동시2조건, 총7200ticks 실행, 사전 기준 12/12 PASS. 10초 후 최대 위치0.894mm/회전0.058도, 최저 sampled clearance40.015mm, BLOCKED0. 3초 위치 최대5.926mm. 작은 고정목표 정착 결과이지 빠른 VR 추종/물리검증은 아니다. 실행 IK/runtime 설정은 보존. 앞선 arbitrary 목표의 잔여오차만으로 추가 비용 튜닝을 하지 않는다. 진단 도구 `backend/tools/audit_bimanual_known_targets.py`, 결과 `docs/validation/bimanual_known_targets_20260921/baseline.json`.

## 2026-09-21 양팔/Omni 50Hz 콘솔 표시

사용자는 기존7축 relay가 아닌 현재 양팔14개 값을 선택했다. `tools/PRINT_G1_INPUTS_50HZ.bat` 및 Python 모니터 추가. 기존 bimanual JSONL/Omni CSV를 읽기만 하며 50Hz 최신값/단위/sequence/age/freshness 표시. 실제송신/수신과 구분하도록 G1_RX UNVERIFIED 상시 표시. G1 수신 검증은 미완료이며 새 양팔 전송경로는 만들지 않았다. 4개 unittest 및 과거 로그2초96줄49.843Hz smoke 통과. 문서 `docs/G1_INPUT_CONSOLE_50HZ.md`. 새 Quest/Omni 입력/실제G1 실행 없음. 기존 제어 파일 보존.

## 2026-09-21 G1 측 수신 출력 요청

사용자가 G1에서도 양팔/Omni 수신값을 보고 싶다고 요청. UDP55070 observation-only 전용 링크 및 seq/SHA256 ACK 구현. `tools/G1_INPUT_RECEIVE_AUDIT.py receive`는 G1 표준Python만 사용, send는 기존 PC로그 복사. 기존5014/5017 제어경로/SDK/DDS/모터에 연결하지 않는다. `SEND_G1_INPUT_AUDIT.bat` 준비. 4개 unittest/loopback UDP tests 통과. 실제192.168.123.164:22는 2회 timeout으로 전송/실행 불가, 연결 확인 질문 pending. 실제 G1 수신확인은 미완료. 실행법/구분은 `docs/G1_OBSERVATION_RECEIVE_AUDIT.md`.

## 2026-09-21 사용자 재연결 후 G1 observation 수신 확인

G1 192.168.123.164 / PC192.168.123.99 접속 성공. Python3.8.10, UDP55070 미점유 확인. 새 `/home/unitree/g1_input_audit_20260921_7e83c4`에 수신전용 단일파일 배포, SHA256 일치. 30초 bounded receiver +5초 PC send에서 247송신/247 G1수신, 순번0..246 누락0, PC ACK246개 확인. 마지막은 PC 종료 전 송신후 ACK polling이 없어 집계되지 않았지만 G1 로그 수신확인. 모든 저장 ACK hash를 회수한 G1 로그와 대조. 원본 양팔/Omni 모두 HISTORICAL이라 새로운 센서입력 검증은 아님. 모터 수신/실행은 NOT_CHECKED. 실제 제어포트5014/5017과 SDK/DDS 미사용. 증거 `docs/validation/input_receive_audit_20260921/g1_network_check.json`.

사용자 관찰용 지속실행: G1 SSH receiver unified session13859, PC sender13027. G1 log `input_receive_20260921_110559.jsonl`. 수신창 표시 요청은 Codex UI queued 반환. 종료는 각 관찰터미널 Ctrl+C; 실제 제어프로그램과 무관하다. 새 Quest/Omni 로그가 생성되면 1초내 최신 파일로 전환하되 source buffering 지연 가능. 기존 dirty runtime에는 새 수신도구만 설치했으며 원래 제어파일은 변경하지 않았다.

## 2026-09-21 동시 실물통합 보류

사용자가 오늘 Omni+양팔 실물통합을 요청했으나, 적용할 외부 하체정책/제어기 경로 확인 질문에 "이건 일단 보류"라고 답했다. 하체정책 확인/실물통합 작업을 중단했다. 코드/정책/SDK/DDS/모터출력 변경 또는 실행 없음. 읽기전용 SSH 목록 조회만 수행. 기존5014 relay7축과 bimanual sim14축은 직접 호환되지 않고 관찰55070은 과거자료도 ACK하므로 제어입력으로 사용하지 않는다.

지속관찰 stdout backpressure 가능성: remote ss에서55070 Recv-Q213248 확인. PC sender13027은 Ctrl+C로 종료. SSH receiver13859는 Ctrl+C 뒤 connection reset으로 종료상태가 불명확하며, 이후 ss에서55070이 남아 있었다. 자신이 생성한 정확한 receiver command만 대상으로 정리하려고 SSH 재접속했으나 인증 중 connection reset되어 G1 측 종료 확인을 못했다. 다른 제어프로세스에는 손대지 않았다. 차후 연결 시 해당 observer만 상태 확인/정리할 것. 관찰용 출력 비동기화는 검토만 했고 user hold에 따라 구현하지 않았다.

## 2026-09-21 GROOT 확인 후 외부제어기 입력 모사로 범위 변경

사용자가 하체 실행본을 `~/groot_onboard_runtime/build/groot_balance_actuator --normal ...`
이라고 제공했다. SSH로 소스/문서를 읽어 복사했으며 실행·SDK/DDS 초기화·모터 출력은
하지 않았다. 실제 구조는 GR00T lower15(다리+허리), 별도 upper14이며 단일 LowCmd다.
이후 사용자가 통합을 중지하고 Omni+양팔 값만 실시간 수신하는 일을 우선 요청했다.
GROOT 파일/모델/gain/원래 실행본은 수정하지 않았다.

사용자 확정 방향: 향후 G1 내부 Python 외부제어기가 통신 시작 시 실제 G1 초기각을
읽고 Windows Arm Relay/Omni Gateway 입력을 받아 C++ 실제 제어기에 UDP 명령을 보낸다.
이번 완료 범위는 **외부제어기 입력 수신부 모사**이며 실측 초기각 및 C++ 송신은 미연결이다.
`initial_g1_q_rad=null`, `initial_g1_q_status=NOT_MEASURED`, `cpp_command_sent=false`를
출력/로그에 명시한다. IK 목표를 실제 G1 관절값으로 취급하지 않는다.

기존 로그 tail 관찰과 별도로 `send-live` 추가. 양팔 IK 계산 직후·Omni WebSocket
수신 직후 opt-in localhost55071 observation tap → PC 최신값 snapshot50Hz → G1
UDP55070 → exact SHA256/seq ACK. old `send`는 과거 로그도 표시하는 별도 모드다.
원본 시각/순번을 유지해 중단 후 STALE로 바뀐다. IK-loop freshness와 Unity 입력
freshness를 별도로 표시한다. 양팔/Omni 동시센서시각 정렬·보간은 하지 않는다.
50Hz는 최신값 표시/송신 주기이며 서로 다른 생성시각의 두 값을 함께 표시한다.

G1 stdout blocked에도 수신/ACK가 진행되도록 pending1개 비동기 출력, queue256개
비동기 JSONL 기록을 적용했다. display/log drop 수를 기록하며 ACK는 디스크 영속화나
모터 수신을 증명하지 않는다. 기존 옛 receiver3588은 이번 SSH 조회 시 없어졌고
55070도 비점유였다. 무관한 프로세스를 종료하지 않았다.

실제로 실행한 검증: 기존 bimanual102/102 PASS(116.954s), Omni mapper12/12 PASS,
기존 synthetic WebSocket/discovery e2e PASS10packets, tap9/9 PASS, audit10/10 PASS,
새 실제 producer→loopback pipeline2/2 PASS(최종12.156s). 새 pipeline은 생성한
Unity pose와 가짜 Omni WebSocket을 사용해 실제 IK/Gateway 프로그램을 실행했다.
현재 실제 Quest+Omni 사용자 입력을 이용한 동시시험은 하지 않았다.

G1 Python3.8 수신전용 실제 네트워크 시험: 생성 fixture 200송신/200수신, 순번0..199
누락0, 회수 로그 전체 SHA256 일치, PC ACK199(마지막 송신 후 PC 종료), log drop0.
입력 중단 후 양쪽 STALE 확인. 이는 실제 네트워크 수신 검증이지 물리제어 검증이 아니다.
소스/로그 증거: `docs/validation/input_live_observation_20260921/`.

처음 별도 `~/g1_input_live_observation_20260921`에서 시험 후, 사용자 요청 기존 명령에
맞춰 `~/g1_input_audit_20260921_7e83c4/G1_INPUT_RECEIVE_AUDIT.py`를 백업/갱신했다.
백업 `G1_INPUT_RECEIVE_AUDIT.before_live_20260921.py`. 최종 receiver SHA256:
`e9b34184ca0a52b36ba2d14a3ff513654e0909ad3785792189663f7fcca56267`.
첫 PC 설치 백업 `logs/backups/live_observation_20260921_114415`.
새 `tools/START_G1_INPUT_OBSERVATION.bat`가 source/sender/SSH수신창을 연다.
G1 수신창을 직접 열었으면 `--no-receiver`로 PC3개 창만 실행한다.
기존 Python 양팔 프로세스는 닫고 새 launcher로 재실행해야 tap이 켜진다.
Unity/C# 수정 없음. Omni Connect(32123)가 이 작업 시점에는 열려 있지 않았으므로
사용자가 연결 후 실제 센서입력을 확인해야 한다. 명령/해석은
`docs/G1_LIVE_INPUT_OBSERVATION_20260921.md`에 모두 기록했다.


## 2026-09-21 Quiet teleop launcher
START_G1_VR_TELEOP now hides newly started local send/Omni/arm consoles by default and writes output to logs/test_results/teleop_background/<session>/*.log. SSH receive authentication remains visible, then its console is hidden after remote stdout begins; failures restore it. A small manager console remains: Enter/Ctrl+C stops only workers started by that invocation. Camera window is unchanged. Existing processes are reused, not hidden or terminated. --show-consoles restores legacy diagnostic windows. Do not close the manager with X; use Enter so child cleanup runs. No motor-control changes. Offline tests: 19 passed plus 17 subtests; no live SSH/camera/VR run, Windows terminal-host hide behavior still needs operator verification. Laptop runtime patched narrowly with backup; unrelated portability differences preserved.


## 2026-09-21 Per-PC SSH enrollment
Integrated START_G1_VR_TELEOP verifies dedicated per-user SSH key before spawning a new receiver. First-run OpenSSH password prompt registers only public key, then verifies BatchMode login; no password persistence. check-only skips enrollment. Details: docs/G1_SSH_AUTO_LOGIN.md. Offline: 36 tests + 41 subtests passed. Actual G1 enrollment not run. Laptop runtime patched with backups preserving unrelated changes.


## 2026-09-21 Windows venv duplicate-worker false positive fixed
Live inventory showed Omni venv redirector PID14424 parenting base Python PID11440 with identical arguments/CSV. Process inventory now retains PID/PPID/executable and collapses only the exact project .venv-teleop redirector and its identical base-Python child. Independent duplicate workers still fail closed. 20 tests / 17 subtests passed. Runtime launcher backed up and installed; read-only live recognition passed without starting/stopping workers. No robot commands.
