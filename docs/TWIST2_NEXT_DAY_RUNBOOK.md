# 2026-09-08 Quest → G1 준비 상태

현재 실행 가능한 범위는 읽기 전용 LowState → Mink simulation → 로컬 C++ 후보 검증이다.
실제 rt/lowcmd 송신 경로는 준비 완료가 아니다. 이 문서에 물리 실행 명령은 없다.
Arm SDK 상체 기울어짐 문제는 보류 상태이며 이 경로로 우회 실행하지 않는다.

**현재 우선순위:** 기존 물리 C++의 SDK/네이티브 정책을 재사용하는 별도
`twist2_vr_native_draft.cpp`를 만들었고 승인된 WSL x86_64 SDK/Torch 통합 빌드를
완료했다. 제어 바이너리 미실행이며 G1 대상 빌드는 미검증이다. 다음은 대상 환경과
실제 입력/상태 연결 확인이다. Windows 합성 시험을 계속 늘리는 것이 우선은 아니다.
정확한 구현/미검증 범위는 `docs/TWIST2_NATIVE_VR_REVIEW.md`를 따른다.
아래 표의 미연결은 새 VR 경로 기준이며 기존 물리 프로그램에 SDK가 없다는 뜻이 아니다.

## 오늘 완료한 로컬 검증

프로젝트 루트 PowerShell에서 다음 명령으로 다시 실행할 수 있다.

```powershell
Set-Location C:\Users\user\Desktop\G1_Teleop_Project
powershell -NoProfile -ExecutionPolicy Bypass -File experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1
```

이 명령은 물리 C++ 해시 확인, MSVC C++17 /W4 /WX 빌드, watchdog/writer 진단,
Python 회귀, 저장 Quest 재생만 수행한다. WSL/SDK/네트워크/Unity를 실행하지 않는다.
결과가 통과해도 실제 출력 허가가 되지 않는다.

## 실제 송신 전 남은 연결부

2026-09-08 현재: 아래 표는 이전 오프라인 경로의 잔여 목록이다. 새 native 초안에는
SDK LowState callback/독립 writer/정책 합성이 소스상 연결돼 있고 WSL 빌드가 완료됐다.
이를 미구현으로 다시 만들지 않는다. 실제 연결·주기·정지는 미검증이다.
Windows G1 전용 주소가 현재 없으므로 장비 연결부터 필요하다.

입력 배선: Windows Mink127.0.0.1:5008 → 기존 relay → 확정할 Linux bind주소:5013 →
NativeVrUdp → NativeVrPolicyAdapter. relay source IPv4와 실행별 token을 양쪽에 맞춘다.
simulation_only 출력은 이 물리 중계 경로에서 거부된다. 저장 패킷 재표기로 우회하지 않는다.
LowState는 해당 실행 호스트의 SDK rt/lowstate callback에서 얻는다. Windows 초기 seed와
별개이며 실제 초기 정렬 검사가 필요하다. 실행 호스트(G1 내부/WSL DDS)를 먼저 확정한다.

| 연결부 | 현재 상태 | 필요한 검증 |
|---|---|---|
| LowState ABI | SDK CRC-packed 2092 bytes를 로컬 해석 | 배포 대상 SDK와 메모리/직렬화 형식 확인. CDR와 혼동 금지 |
| 상태 중단 | NativeCompositionOffline.Poll 추가 | 실제 독립 주기에서 호출해야 함. 아직 timer/thread 연결 없음 |
| 정책/상체 합성 | 메모리 전용 검증 | 하나의 소유자가 0..11 정책, 12..21 지정 자세, 22..28 VR을 원자적으로 전달 |
| engage 전 ready | 오프라인 측정 상태 gate 구현 | blend 후 q 오차 0.025 rad, 속도 0.1 rad/s 이내 1초 지속. 실험값이며 실제 기준 미승인. 이탈 시 ready 취소 |
| 실제 500Hz 송신 | 미연결 | SDK 직렬화/CRC, 단일 송신자 소유, 스케줄링과 명령 만료 검증 |
| 해제·오류 대응 | 후보 latch/damping 진단 | 송신 중단과 실제 모터 damping/모드 복귀의 의미는 다름. 실장 중단 동작과 인계 절차 검토 필요 |
| seed 초기화 | Quest 첫 engage와 초기 seed 오차0 확인 | 실시간 관절 추종 아님. 공급기 종료 뒤 simulation은 계속 동작 |
| 속도 기준 | 단일 샘플 0.1 초과 시 거부 유지 | 시간창 후보는 탐색 결과뿐. 21번 관절 초과 원인 미확정 |

기존 twist2_right_arm_trial.cpp는 변경하지 않는다. 배포/실제 publisher 생성은
위 연결부가 구현·검토되고 장비 상태를 확인한 후 구체적인 실행 범위로 승인받는다.
기존 물리 프로그램을 새 VR 경로에 연결된 것처럼 실행하지 않는다.

## 내일 장비에서 시작할 순서

1. G1 연결 상태와 실제 명령 송신자/모드를 읽기 전용으로 확인한다.
   이전 세션의 모드, deadman 상태, 정지 상태를 현재 사실로 재사용하지 않는다.
2. 로컬 포트를 확인한다. 점유 PID의 명령줄을 확인하고 무관한 프로세스를 종료하지 않는다.

```powershell
Get-NetUDPEndpoint | Where-Object LocalPort -in 5005,5008,5012,5013 |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

3. 새로운 세션/출력 폴더로 승인된 읽기 전용 seed 공급기와 파일 observer를 실행한다.
   공급기는30초 후 종료하고 seed를 삭제한다. 매 시험의 새 seed를 사용한다.
   오류 시 통과로 처리하거나 과거 timestamp를 갱신하지 않는다.
4. 공급 중 simulation 초기화를 시작한다. 두 환경변수는 같은 세션을 가리켜야 한다.

```powershell
# 아래 두 값은 새 공급기가 실제 갱신 중인 경로/세션으로 지정한다.
$env:G1_MINK_INITIAL_SEED = '<fresh seed.json 절대경로>'
$env:G1_MINK_INITIAL_SESSION = '<동일 session>'
.\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback
```

5. 5008 로컬 수신기를 준비한 뒤 engage → 작은 움직임 → pinch를 수행한다.
   화면은 Mink이며 C++ 후보 시각화가 아니다. 단일 rt/lowcmd 송신자 연결 전에는 실제 팔을 움직이지 않는다.
6. 입력·LowState·C++ 후보를 동일 시험으로 묶어 첫 목표 오차, 비대상 축, 속도,
   초과 목표, 해제/timeout latch를 확인한다. 과거 seed 정렬과 현재 상태 정렬은 구분한다.
7. 시험에서 생성한 프로세스만 종료하고 seed 삭제/포트 해제를 확인한다.

```powershell
Remove-Item Env:G1_MINK_INITIAL_SEED -ErrorAction SilentlyContinue
Remove-Item Env:G1_MINK_INITIAL_SESSION -ErrorAction SilentlyContinue
```

## 진행을 멈추는 경우

CRC/형식/세션 불일치, 상태 만료, 모터 fault, 초기 목표 불일치, 송신자 중복,
검토되지 않은 모드/출력 경로가 있으면 다음 단계로 넘어가지 않는다.
관절 속도 한 샘플 초과는 현재 seed 기준의 거부이며 로봇 고장의 증명은 아니다.
다만 이를 자동으로 무시하는 코드도 적용하지 않는다.

아래 후속 기록은 시간순 이력이며 최신 상태는 마지막 기록을 따른다.

로컬 후속: offline_owner.hpp에서 합성 상태/VR/정책/writer 연결과 7가지 중단 검증 완료. 실제 thread/수신 cache/초기 blend/CPU 정책 연결은 아직 없다.

후속 갱신: 상태 cache는 ReceiveState/BeginPolicy로 분리했고 정책 계산 중 상태 오류 중단을 검증했다. 실제 수신 thread/CPU worker/독립 VR 검증 연결은 아직 없다.

후속 갱신: owner에 VR즉시검증/FIFO와1432차원관측/history를 연결했다. 실제 CPU worker IPC와초기blend/실제scheduler는 아직 미연결이다.

후속 갱신: run_owner_cpu_offline.py에서 실제CPU모델과owner를local pipe로연결해 정상/pinch/지연3경우통과. 합성event clock이며실제scheduler/초기blend/연속cycle은미검증. 실행 결과는새 --output 경로로저장한다.

후속 갱신: 실제CPU100연속cycle/history100commit/wallclock요청기한 통과. writer간격2.30~5.43ms로500Hz입증아님. 초기blend단계와VR전writer생성은아직미연결이다.

후속 갱신: OfflineOwner(true)의settle/blend/awaiting_alignment/active 단계와VR전writer진단을합성정책으로검증했다. 기존CPU runner는default false다. 실제CPU blend/실측tracking ready/torque fade/물리모드인계는남아있다.

후속 갱신: 실제CPU startup-blend600cycle 재시험통과(history509). 첫시험은469cycle후12.89ms policy deadline중단. 지연원인미확정이며물리실시간보장아님.

최신 갱신: blend 시간만으로 ready를 허용하던 동작을 제거했다. 측정 q가 desired와
writer 목표 양쪽에 가깝고 속도 조건을 1초 연속 만족해야 한다. startup 8개 시나리오를
포함한 회귀 34개/하위검사 50개 통과. 실제 CPU + 고정 합성 상태는 600 cycle 처리했으나
verifying_tracking에서 대기하여 active 미도달(exit 1). 현재 전체 경로 통과 증거는 아니다.
후속 완료: 1차 지연 합성 추종 fixture에서 ready/engage 진입을 검증했고, 첫 유효
상태부터 active까지 15초 대기 제한을 추가했다. settle/추종 실패와 engage 미입력도
기한에 포함한다. timeout은 latch되며 재시도는 새 owner가 필요하다. startup 시험은
12개 시나리오이며 회귀 34개/하위검사 50개 통과. G1 동역학 검증은 아니다.
후속 완료: offline_dispatch.hpp에 메모리 전송 계약을 추가했다. owner Tick 성공
snapshot만 순번/상태 순번/시간과 함께 전달한다. 2ms 이전 호출은 생략하고 6ms 초과
공백, 시계 역행, sink 거부, owner 중단 뒤에는 전달을 latch한다. catch-up 재전송은 없다.
6개 전송 시나리오 포함 회귀 35개/하위검사 50개 통과. 실제 CPU runner에는 아직
연결하지 않았으며 독립 scheduler, SDK 송신, 실제 damping/모드 인계는 미구현이다.
HandoffRequired는 인계 필요 표시이며 인계 완료가 아니다.

최신 CPU 통합 결과: --dispatch 옵션으로 C++ memory dispatch를 연결했다.
기본 경로는 12/100 cycle 후6.474ms tick 공백, startup 경로는581/600 cycle 후
8.980ms 공백으로 dispatch_deadline 중단(exit 1). 중단 후 후속 전달 없음 확인.
6ms 기준을 완화하지 않았으며, 현재 Python/pipe 주기는 기준을 항상 만족하지 못한다.
재실행 예시(출력 파일은 새 경로 사용):

```powershell
py -3.11 experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py --dispatch --output logs/test_results/new_dispatch_run.json
```

후속 완료: --autonomous-tick으로 독립 C++ 스레드와 동일 owner mutex를 연결했다.
Windows 고해상도 대기 타이머를 사용하며 Python state/tick 요청은 필요 없다.
합성 상태를 생성하는 시험 전용 코드이며 실제 LowState 수신을 대신하지 않는다.
stdin 60ms 중단 중에도 policy_deadline 검출 및 늦은 결과 차단을 검증했다.
실제 CPU 일반 경로100/100 완료(최대 전달 간격4.032ms), startup600/600 처리
(최대4.411ms, ready/active 미도달로 exit 1). 이전 sleep_for 시험의15.164ms 실패도
로그에 보존했다. 500Hz 또는 장시간 실시간성 검증 완료를 뜻하지 않는다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py --autonomous-tick --startup-blend --output logs/test_results/new_autonomous_run.json
```

후속 완료: 실제 CPU 모델 + 1차 지연 합성 추종을 연결해 settle/blend/ready/engage/
22번 목표 +0.02rad/pinch 해제까지544cycle에 완료했다. 최대 전달 간격3.735ms,
해제 뒤 frame/history 증가 없음. 다른 상체 목표 유지 및 기록 목표의 초과 없음 확인.
합성 측정22번 변화는0.008861rad이며 실제 G1 동역학/Quest 입력 시험은 아니다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py --tracking-fixture --output logs/test_results/new_tracking_run.json
```

후속 완료: --torque-fade로 첫 writer 생성 시 합성 측정 토크를 캡처하고 한도50%로
제한해1초 동안0으로 감소시킨다. 정책 유효 시간은 연장하지 않는다. 회귀37개/
하위검사50개 통과. 실제 CPU 시험은 fade 완료 뒤498cycle에서 policy_deadline
(요청~Finish12.530ms)으로 중단됐다. 이번 시험은 전구간 성공이 아니다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py --torque-fade --output logs/test_results/new_torque_fade_run.json
```

다음 로컬 작업은 반복된 정책 지연의 분리 계측과 중단/모드 인계 계약이다.
실제 SDK/500Hz 송신과 물리 중단 인계는 여전히 미구현이다.
장비 연결 즉시 조작 가능한 상태는 아니다.
