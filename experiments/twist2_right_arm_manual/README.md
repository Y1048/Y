# TWIST2 오른팔 수동조작 실험본

현재 상태: **2026-09-04 오른쪽 어깨 pitch 한 축의 첫 물리 부호·응답 시험 완료.**
이 결과는 오른팔 7축 전체나 반복 실물 시험의 승인이 아니다.

## 목적

2026-09-07: TWIST2를 다음 VR 통합 경로로 선택했다. 기존 물리 C++/정책/게인은
변경하지 않았고 Python/C++ 오프라인 후보 계산과 Windows 수신 전용 shadow를 추가했다.
기존 Mink 입력 파서를 재사용하되 Arm SDK의 Regular 복귀/weight 제어는
사용하지 않는다. 오른팔22..28의 절대 관절각을0.08rad/s로 갱신하는 오프라인
upper_target 후보이며, 아직 TWIST2 정책/물리 C++에 연결되거나 G1에 배포되지 않았다.
프로젝트 루트에서 다음 명령으로 가짜 입력 테스트를 실행할 수 있다.

```powershell
py -3.11 -B experiments/twist2_right_arm_manual/test_vr_input_offline.py
```

이 테스트는 소켓/WSL/SDK/정책 실행 없이 메모리에서 수행한다. 테스트의
0.2rad 시작범위와0.25초 timeout은 합성 사례 조건이며 물리 승인값이 아니다.
세션 변경/연동해제/타임아웃 후 자동 재연동은 없고 새 study 생성이 필요하다.
기존 허리/왼팔 캡처 목표 유지와 하체 정책 합성 지점은
`docs/TWIST2_INTEGRATION.md`에 정리했다.

기존 왼팔 조작 구조를 오른팔로 옮겨, VR/IK를 제외하고
키보드 명령 → 실제 관절값 → PC 모델의 부호와 움직임을 비교하기 위한 실험본이다.
기존 Unity/Mink 및 Arm SDK 실행 경로는 변경하지 않는다.

## 현재 해석 및 실행 경계

- Arm SDK weight1.0 실제 상체 기울어짐 문제는 해결되지 않았으며 보류 상태다.
- 최종 TWIST2는 하체 정책+상체 목표를 단일 `rt/lowcmd` 작성자가 합친다.
  Regular를 유지하는 오른팔 전용 SDK 방식이 아니다. 현재 Windows C++는 미연결이다.
- Quest shadow/저장 재생은 첫 active Mink 가상 baseline을 사용한다. 최신 C++도
  첫 active 캡처 또는 config의 명시적 가상 baseline을 선택한다. 실제 LowState 초기화는 없다.
- Unity/MuJoCo는 기존 Mink 화면이며 새 C++ 후보의 시각화가 아니다.
- UDP5008은 다른 shadow/Gate7 dry-run과 동시 사용하지 않는다. 점유 PID와
  명령줄을 확인하고 무관한 프로세스는 종료하지 않는다.
- 로컬 VR는 simulation 표시로 실행한다. 프로젝트 루트 PowerShell 명령:
  `.\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback`.
- 최신 Unity 컴파일/assembly reload 로그와 사용자의 손목 표시 정상 확인을 받았다.
  `wrist_limit_margin_unknown`의 분기별 화면 비교나 C++ 후보 시각화 검증은 아니다.
  로컬 테스트 성공을 물리 안전성 검증으로 표현하지 않는다.

## 파일

### 첫 active 가상 baseline 및 Quest 시험 (2026-09-07)

현재 세션의 시작 자세를 사용할 때는 명시적 baseline 배열 대신 다음 config를
사용한다. `baseline` 키는 함께 지정하지 않는다:

```json
{
  "schema": "g1.twist2.cpp_receive_shadow.v1",
  "baseline_source": "first_active_mink_simulation_not_g1",
  "maximum_delta_rad": 0.17453292519943295,
  "queue_capacity": 64
}
```

아래 빌드 절의 큐 harness와 수신기를 재빌드한 뒤 새 config/로그 경로로 실행한다:

```bat
logs\test_results\receive_target_shadow.exe 5008 180 logs\test_results\cpp_quest_config.json logs\test_results\cpp_quest_new.jsonl
```

실행 전5008 점유를 확인한다. Mink는 프로젝트 루트 PowerShell에서
`.\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback`로 실행한다.
수신기 READY 후 Unity Play→초록색 engage→작은 손 움직임→pinch로 시험한다.

캡처 전 로그의 q/baseline은 null이다. 형식이 정상인 이전 비활성 상태도
첫 active까지 기다리되 malformed/overflow는 즉시 중단한다. 첫 active 검증과
관절 범위를 통과하면29축 baseline을 한 번만 캡처한다. 이후 해제/오류 뒤
자동 재캡처하지 않는다. baseline과 candidate는 로그에 별도로 기록한다.

실제 Quest 시험150530:2079패킷,152 active tick, pinch 중단. 최대 속도
0.07989rad/s, 비대상22축/비활성 후보 유지 위반0. 전체 tick 최대79.10ms,
active 구간 최대20.98ms로 실시간50Hz 보장은 아니다. 사용자가 기존 Mink
손목 표시 정상도 확인했다. 원시 목표는 이 로그에 없으므로 해당 실제 세션의
오버슈트 대조는 미완료다. 기록은 `logs/test_results/twist2_cpp_quest_20260907_150530/`.
전체 관련 시험59 tests /230 subtests 통과, 결과 XML은
`logs/test_results/twist2_cpp_quest_regression_latest.xml`이다.

### 입력 필드 계약 비교 (2026-09-07)

C++는 Python 순수 Mink 파서와 timestamp, workspace/collision bool, 충돌 이름
배열, idle 메타데이터 및 mode/state/active 조합을 대조한다. 추가 검증 오류는
후보를 유지하고 latch한다. ASCII session 앞뒤 공백은 정규화한다.
Arm SDK controller/Regular 복귀 정책을 이 경로에 가져오는 작업이 아니다.

아래 harness를 재빌드한 후 소켓 없는 회귀시험:

```bat
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_input_contract.py experiments/twist2_right_arm_manual/test_cpp_queued_input.py experiments/twist2_right_arm_manual/test_cpp_input_tick.py experiments/twist2_right_arm_manual/test_cpp_upper_target.py experiments/twist2_right_arm_manual/test_cpp_validator.py experiments/twist2_right_arm_manual/test_vr_input_offline.py --junitxml=logs/test_results/twist2_cpp_contract_regression_latest.xml
```

결과46 tests /214 subtests 통과. C++는 숫자 문자열/bool의 수치 변환, 중복 키,
raw NaN/Infinity, uint64 초과 sequence를 계속 거부한다. Python과 의도적으로
다르며 완전 동등성을 주장하지 않는다. Unicode 공백 session의 trim 차이도 남아 있다.
새 헤더 반영 후 두 수신기는 빌드만 했으며 이번에 소켓/VR 실행은 하지 않았다.

### Windows 수신 전용 C++ 큐/tick shadow (2026-09-07)

`receive_target_shadow.cpp`는 `queued_input_offline.hpp`와 기존 목표 갱신
로직을 연결하는 별도 Windows 실행파일이다. **127.0.0.1 수신과 로컬 후보
로그만 수행**한다. 기존 raw 수신 probe 및 물리 C++는 그대로다.

- 큐 용량1..64개, datagram최대16,384bytes. overflow/과대 패킷은 latch 중단.
- 수신/큐/tick/로그를 한 스레드가 처리한다. 이 큐는 다중 스레드용이 아니다.
- 큐의 모든 패킷을 순서대로 검증하고 tick당 한 번만 후보를 갱신한다.
- 20ms high-resolution waitable timer와 Winsock event 사용. 지연 후 catch-up
  갱신 없음. 시스템 전역 설정 변경 없음. Windows 실시간 주기 보장은 아니다.
- 해제/timeout/검증/transport/log 오류 후 후보 갱신 중단. 출력 파일은
  Windows CREATE_NEW로 생성하며 기존 파일을 덮어쓰지 않는다.

프로젝트 루트의 **VS x64 Developer Command Prompt**에서 빌드:

```bat
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_queued_input.exe /Fo:logs\test_results\test_queued_input.obj experiments\twist2_right_arm_manual\test_queued_input.cpp
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\receive_target_shadow.exe /Fo:logs\test_results\receive_target_shadow.obj experiments\twist2_right_arm_manual\receive_target_shadow.cpp
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_queued_input.py experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py
```

실행 예시의 `logs/test_results/cpp_shadow_config.json` 내용:

```json
{
  "schema": "g1.twist2.cpp_receive_shadow.v1",
  "baseline_source": "explicit_simulation_baseline",
  "baseline": [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
  "maximum_delta_rad": 0.17453292519943295,
  "queue_capacity": 64
}
```

baseline은 설명용 가상29축이다. 시험할 가상 자세를 명시해야 하며 실측 G1
자세로 해석하지 않는다. 실행 인자는 포트(1024..65535), 제한시간(1..180초),
config 경로, 존재하지 않는 새 로그 경로다:

```bat
logs\test_results\receive_target_shadow.exe 55018 5 logs\test_results\cpp_shadow_config.json logs\test_results\cpp_shadow_new.jsonl
```

위 실행만으로 입력이 생기지는 않는다. 자동 시험은 임시 loopback 포트에
합성 JSON만 보낸다. 프로그램은 datagram을 송신하거나 화면/로봇에 후보를
적용하지 않는다. 종료코드0은 해제 또는 패킷을 받은 뒤 제한시간 종료이며,
2는 오류/timeout/무입력 종료다. 실제 장애 시 마지막 로그가 없을 수 있으므로
stderr와 종료코드를 함께 확인한다. 큐/과대 패킷 중단은 즉시, JSON 의미 검증은
다음 tick에서 수행한다. OS UDP buffer 유실과 kernel 대기 시간은 검출하지 않는다.

통합 회귀시험(아래 기존 harness도 빌드되어 있어야 함):

```bat
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_queued_input.py experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py experiments/twist2_right_arm_manual/test_cpp_input_tick.py experiments/twist2_right_arm_manual/test_cpp_upper_target.py experiments/twist2_right_arm_manual/test_cpp_validator.py experiments/twist2_right_arm_manual/test_vr_input_offline.py --junitxml=logs/test_results/twist2_cpp_queued_shadow_latest.xml
```

결과44 tests /91 subtests 통과. 약1.2초 연속 합성 시험은61개 전부 수신,
tick 중앙값20.086ms/최대20.446ms, 최대 후보 속도0.0798rad/s, 해제 중단.
기록은 `logs/test_results/twist2_cpp_receive_stream_20260907_144501/`에 있다.
Quest 실제 입력, 장시간 부하, 물리 정책/실측/충돌/종료 동작은 미검증이다.

### C++ 메모리 전용 목표 갱신 (2026-09-07)

`upper_target_offline.hpp`는 `InputValidator`를 통과한 오른팔22..28 목표를
0.08rad/s, 최대 dt0.02초로 갱신한다. baseline29축과 최대 시작 대비 범위는
생성자가 명시적으로 받는다. 나머지22축은 baseline을 그대로 보존한다.
관절 한계/시작범위를 모두 검사한 뒤 적용하며, 목표를 넘지 않는다.
첫 engage 전 idle 대기, 무패킷 즉시 유지, engage 후0.25초 초과 timeout 및
해제/오류 latch를 적용한다. 중단 후 새 객체 생성 전에는 갱신하지 않는다.

프로젝트 루트의 **Windows VS x64 Developer Command Prompt**에서:

```bat
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_upper_target_offline.exe /Fo:logs\test_results\test_upper_target_offline.obj experiments\twist2_right_arm_manual\test_upper_target_offline.cpp
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_input_validator.exe /Fo:logs\test_results\test_input_validator.obj experiments\twist2_right_arm_manual\test_input_validator.cpp
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_upper_target.py experiments/twist2_right_arm_manual/test_cpp_validator.py experiments/twist2_right_arm_manual/test_vr_input_offline.py --junitxml=logs/test_results/twist2_cpp_upper_target_latest.xml
```

실행 전 `logs/test_results` 폴더와 Python pytest가 필요하다. 위 시험은
stdin/stdout만 사용한다. 결과:19 tests 및51 subtests 통과. 아래의 기존
`TEST_OFFLINE.bat`은 WSL을 사용하므로 이 메모리 전용 검증 명령과 구별한다.
이 메모리 로직은 위 수신 전용 shadow에서 재사용하며 정책/물리 제어기에는
연결하지 않았다. 호출 시각은 같은
단조 시계이며 기존 `Step(payload, now)`는 즉시 수신용이다. 큐 지연을
포함한 가상 tick 검증은 다음 절을 사용한다. 실측 피드백, 전신 충돌,
물리 종료 정책은 별도 작업이다.

### 수신 배치와 가상50Hz tick 재생 (2026-09-07)

`Tick(vector<ReceivedInput>, now)`에 해당 tick까지 수신한 패킷 전체를
수신 순서대로 전달한다. 각 패킷은 원문 `payload`와 같은 단조 시계의
`received_at`을 갖는다. 예: 수신0.011초, tick0.02초, source age0.24초이면
합산 age0.249초다. 0.25초를 넘으면 갱신하지 않고 중단한다.
유효한 배치의 마지막 목표로 tick당 한 번만 움직이며, 중간 해제/오류도
반드시 검사한다. 무패킷 tick은 유지한다. 이전 receipt 이후0.25초를 넘긴
tick 정체는 쌓인 정상 패킷이 있어도 중단한다. 이 API 자체에는 큐가 없으며
위 수신 전용 shadow의 단일 스레드 큐에서 호출한다.

위 두 harness를 다시 빌드한 후 프로젝트 루트에서:

```bat
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_input_tick.py experiments/twist2_right_arm_manual/test_cpp_upper_target.py experiments/twist2_right_arm_manual/test_cpp_validator.py experiments/twist2_right_arm_manual/test_vr_input_offline.py --junitxml=logs/test_results/twist2_cpp_input_tick_latest.xml
py -3.11 experiments/twist2_right_arm_manual/replay_cpp_input_tick.py logs/test_results/twist2_vr_shadow_20260907_140851_282afca4/samples.jsonl --output-dir logs/test_results/twist2_cpp_tick_replay_new
```

`--output-dir`는 존재하지 않는 새 경로여야 한다. 재실행 시 다른 이름을 쓴다.
재생기는 현재 송신 순수 함수와 fake sink로 옛 진단 Infinity만 호환 변환하며
저장 원문은 수정하지 않는다. baseline은 첫 active **가상** 자세, 시작범위10deg.
각 tick의 후보/상태는 `ticks.jsonl`, 입력·실행파일 해시와 검사 결과는
`result.json`에 저장한다. 실제 소켓/정책/G1/WSL/DDS 실행은 없다.

검증 결과29 tests 및70 subtests 통과. 저장476패킷 재생에서 active115회,
해제 중단 후16 tick 유지, 최대0.08rad/s, 관절 불변/오버슈트/중단 위반0회.
재생은 가상 시간이며 실제 정책 실행이나 물리 제어기 연결 검증이 아니다.

### 로컬 VR 소켓 확인 (2026-09-07)

1. `tools/START_TWIST2_VR_INPUT_SHADOW.bat` 실행, LISTENING 확인.
2. 프로젝트 루트의 다른 터미널에서 아래 명령 실행.

```bat
START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback
```

3. Unity Play에서 engage 후 오른손을 조금 움직이고 pinch로 해제.

수신기는127.0.0.1:5008에만 bind한다. 기존 기본 실행기의 Regular 복귀
수신기와 포트가 겹치므로 반드시 `--external-feedback`을 사용한다.
첫 정상 active Mink 자세는 **가상 baseline**이며 실제 G1 캡처값이 아니다.
시작 대비10deg 범위,0.08rad/s 후보 갱신,0.25초 입력 timeout은 이번 로컬
비교 조건이다. 정책50Hz tick을 구동하지 않고 수신 시점에서 후보를 계산하며
계산 dt는 최대0.02초다. 수신 간격에 따라 후보의 실효 속도가 더 느릴 수 있다.

180초 또는 연동해제/입력오류/timeout/Ctrl+C까지 기록한다. 중단 뒤 자동
baseline 재설정/재연동은 없다. 다시 비교하려면 수신기를 재실행한다.
PC logs/test_results/twist2_vr_shadow_날짜_시간_ID에 result.json과
samples.jsonl(원본 datagram base64/후보)이 저장되며 정확한 경로가 출력된다.
`input_observed`는 후보 갱신 유무일 뿐 안전 시험 PASS가 아니다.

Unity/MuJoCo 화면은 기존 Mink 결과다. 수신 후보를 화면/로봇에 반영하거나
패킷을 다른 주소로 전달하지 않는다. SDK/DDS/WSL/C++ 정책 실행 없음.
카메라 및 Gate7 물리 실행기를 함께 시작하지 않는다.

- `twist2_right_arm_trial.cpp`: 기존 static stand의 오른팔 파생본.
- `CMakeLists.txt`: 원본 빌드 설정 기반. 오른팔 실행파일 이름과 공통 헤더 경로만 분리.
- `verify_offline.py`, `TEST_OFFLINE.bat`: 로컬 원본 보존 검사 및 C++ 계산 검사.

공통 헤더는 기존 `references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp`를
참조한다. 원본 C++와 공통 헤더는 수정하지 않았으며, 검증 스크립트에 SHA-256을 고정했다.
원본이 바뀌면 자동으로 받아들이지 않고 재검토를 요구한다.
해시는 Windows CRLF와 Linux LF checkout을 같은 소스로 판정하도록 줄바꿈을 LF로
정규화한 뒤 계산한다.
파생본은 비교하기 쉽도록 원본의 코드 스타일을 유지했다.

## 바꾼 부분과 유지한 부분

| 항목 | 실험본 |
| --- | --- |
| 수동 제어 대상 | 왼팔 15~21 → 오른팔 22~28 |
| 제어하지 않는 상체 | 시작 시 측정한 허리·왼팔 목표 유지 |
| 관절 제한 | 공통 29관절 배열의 오른팔 인덱스 사용. 좌우 roll 범위 다름 |
| 부호 | 키보드 +는 해당 q 증가, -는 감소. 임의 좌우 부호 반전 없음 |
| 로그 | 오른팔 이름과 별도 CSV 접두사 사용 |
| 하체 정책 | 기존 TWIST2 `.pt` 사용, 재학습·변경 없음 |
| 송신 구조 | 기존 단일 전신 `rt/lowcmd` 작성자, 500 Hz 유지 |
| 정책·키 입력 | 기존 50 Hz, 속도·토크 제한 유지 |
| 보호 기능 | R1 유지, 추적 오차·상태 유효성·watchdog·damping 유지 |
| 실행 경로 | 원본 인자 검사, --enable-actuation 및 P 확인 유지. 추가 잠금 없음 |

사용자 요청에 따라 추가했던 실행 잠금·수동 전용 제한은 제거했다.
원본의 일반 기립·자동 어깨 동작·키보드 모드를 그대로 유지하며,
팔 관련 옵션 이름만 right로 바뀐다. 자동 어깨 동작도 오른팔을 대상으로 하므로
실물 실행 전 확인이 필요하다. 이 수정은 G1에서 실행하라는 승인이 아니다.

PD 게인은 기존 작성자가 임의로 설정한 값이라는 사용자 설명을 기록한다.
이번 비교에서는 값을 바꾸지 않았으며, 최적값으로 검증된 것이 아니다.
게인 튜닝은 이후 별도 작업이다.

## 원본에서 가져온 키

| 관절 번호 | 오른팔 관절 | 증가 | 절대 0 rad | 감소 |
| --- | --- | --- | --- | --- |
| 22 | shoulder pitch | Q | A | Z |
| 23 | shoulder roll | W | S | X |
| 24 | shoulder yaw | E | D | C |
| 25 | elbow | R | F | V |
| 26 | wrist roll | T | G | B |
| 27 | wrist pitch | Y | H | N |
| 28 | wrist yaw | U | J | M |

키보드 P는 damping 요청, `?`는 도움말, 숫자 1~9는 속도 배율이다.
**우리 기존 Jog와 키가 다르다. 여기서 Q는 종료가 아니라 어깨 증가다.**
키보드 B는 손목 감소이고, 조종기 B는 damping 입력이다.

증감은 0.02 rad(약 1.146도), 기본 목표 변화율은 0.08 rad/s(약 4.58도/s)다.
9배속은 0.72 rad/s(약 41.25도/s)이며 최종 명령에는 원본의 추가 제한이 적용된다.
0 rad 키는 **시작 자세/Regular 복귀가 아니다.**
원본의 300초 수동 모드와 넓은 관절 범위도 그대로이므로, 처음 물리 시험에
적절하다는 의미가 아니다. 첫 실물 시험 시간·증감·범위·속도는 별도로 검토해야 한다.

## 지금 실행할 수 있는 것

이 폴더의 `TEST_OFFLINE.bat`은 G1/Quest 없이 실행한다.
Windows Python 3.11, 노트북의 WSL Ubuntu와 g++가 필요하다.
결과와 컴파일된 독립 검사 프로그램은
`logs/test_results/twist2_right_arm_offline_날짜_시간/`에 저장되고 경로가 출력된다.

검사 범위:

- 원본 해시와 허용된 소스 변경만 존재하는지 검사.
- 공통 헤더의 실제 키 계산·속도 제한 함수를 추출해 C++로 컴파일 및 실행.
- 오른팔 22~28, 나머지 관절 목표 불변, 오른팔 roll 범위, +/-/0, 포화, 속도·오버슈트 검사.
- 원본 대비 전체 소스 diff를 결과 폴더의 `source_changes.diff`로 저장.

**이 오프라인 스크립트가 검사하지 않는 것:** 전체 Torch/SDK2 제어 프로그램 컴파일, 정책 실행,
실제 DDS 통신·모터 동작·신체 충돌 회피·안정성·실측 부호 일치.

## 전체 C++ 빌드 검증 (2026-09-03)

별도로 전체 오른팔 C++ 프로그램의 컴파일과 링크에 성공했다.
제어 소스는 변경하지 않았으며, 실행파일은 실행하지 않았다.

- 환경: 노트북 WSL Ubuntu 26.04, x86_64, g++ 15.2.0, CMake 4.4.2.
- LibTorch: 별도 Python 3.11.16 환경의 PyTorch 2.8.0+cpu, CXX11 ABI=1.
- 공식 Unitree SDK2 commit: `9754cd153af3da471b0fe5f3aa535e426fb11db3`.
- 의존성/빌드 폴더: WSL `/home/user/.local/share/g1-right-arm-build/`.
- 결과: `logs/test_results/twist2_right_arm_build_20260903_164053.json`.
- 라이브러리 헤더 경고가 있었으나 컴파일·링크 종료 코드는 0이다.

이것은 **노트북 x86_64 빌드 검증**이다. G1용 실행파일이나 실물 동작 검증이 아니다.
G1 환경의 SDK/Torch 버전·아키텍처 호환성은 따로 확인해야 한다.
현재 제어용 Python 가상환경과 G1 내부에는 설치하거나 수정하지 않았다.

## 첫 물리 부호·응답 시험 (2026-09-04)

사용자의 명시적 승인 후 G1에서 오른쪽 shoulder pitch를 조작했다.

- `Q`: 관절값 증가, 실제 팔은 뒤쪽으로 이동.
- `Z`: 관절값 감소, 실제 팔은 앞쪽으로 이동.
- 1,538개 CSV sample에서 측정 관절값이 명령 방향을 추종했다.
- LowCmd 평균 전송률은 500.003 Hz였고 torque limiter 동작 비율은 0이었다.
- 실제 입력에는 `Q 4회 -> Z 8회 -> A 1회 -> Q 1회`가 포함됐다.

`A`는 시작 자세 기준 이동이 아니라 절대 `0 rad` 목표이므로, 이번 실행은 엄격한
작은 `+/- 1 step` 시험이 아니다. 상세 수치, CSV 해시 및 아직 확인하지 않은
안전 범위는 [`../../docs/PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md`](../../docs/PHYSICAL_TEST_20260904_TWIST2_RIGHT_SHOULDER_PITCH.md)에 기록했다.

물리 CSV를 PC의 G1 MuJoCo 모델에 같은 관절 순서로 재생하려면
`VIEW_PHYSICAL_CSV_MUJOCO.bat`을 실행한다. 이 재생기는 CSV의 실측
`q_0..q_28`만 읽으며 Unitree SDK, DDS, 소켓과 로봇 명령을 사용하지 않는다.
MuJoCo에서 `Q` 구간이 뒤쪽, `Z` 구간이 앞쪽으로 보이는지 확인하면 실제 G1과
PC 모델의 shoulder-pitch 부호가 같은지 시각적으로 판정할 수 있다.

## 다음 물리 시험 전 남은 단계

1. `R43`, `R44`, `R45`, `R49`의 실험 경로 제한을 유지하고 변경 시 별도 검토.
2. 다음 시험은 정확한 관절·범위·시간·속도·키 잠금 및 정지 절차를 별도 승인.
3. 오른팔 나머지 관절은 한 축씩 실제 LowCmd, LowState, PC 모델의 부호를 비교.
4. 엄격한 작은 증감 시험에서는 절대 0 rad 및 속도 배율 키를 비활성화.
5. 이후 같은 전신 작성자 안에 수신 전용 소켓부터 추가. VR/IK 연결은 그 다음.

이 프로그램은 `rt/arm_sdk` 경로가 아니다. AI 제어권을 넘겨받고 하체까지
명령하며, 끝에는 damping으로 전환한다. **damping은 서 있는 자세 유지가 아니다.**
다른 LowCmd/Arm SDK 작성자와 함께 실행하지 않는다.
원본처럼 CSV를 생성하므로 G1에서 실행하면 파일이 생긴다.
빌드 성공이나 왼팔의 과거 동작만으로 오른팔의 안전성이나 사용 승인이 확보되는 것은 아니다.

## 원문 로그의 오프라인 재생 (2026-09-07)

Windows receiver는 `g1.twist2.receive_replay.v1` 로그에 전체 datagram hex와
receipt 시각, enqueue 결과, tick의 검증된7축 목표를 기록한다. 목표는 active
성공 tick에만 있고 waiting/stopped에는 null이다. 입력 허용 크기는16384바이트다.
잘못된 UTF-8 원문도 보존하며 parser 오류 사유는 ASCII `parse_error`다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py logs/test_results/cpp_raw_replay_dw9v_jyy/ticks.jsonl
```

미리 빌드한 `logs/test_results/test_queued_input.exe`를 사용하며 소켓을 열지 않는다.
원문/시각/순서를 재생해 후보와 목표를 정확히 비교하고 속도·오버슈트·비대상
관절 고정·중단 시 유지를 검사한다. 누락/불완전/구형 로그는 거부한다.
transport 오류에 의한 외부 stop은 정확히 재현했다고 처리하지 않는다.
합성 loopback 및 새 형식 실제 Quest 캡처 재생 검증을 완료했다.
실제 캡처1127패킷/active240tick, pinch 중단과 정확한 후보 재생·오버슈트 검사를
통과했다. 근거: `logs/test_results/twist2_cpp_quest_raw_20260907_152430/result.json`.
기존150530 Quest 로그의 원문은 복구할 수 없고 물리 안전성 검증도 아니다.

## Snapshot 초기화 및 위치 합성 초안

`measured_composition_offline.hpp`는 transport 없이 q29/dq29/sequence/receipt를
받아 연속 정지 조건에서 캡처하고 첫 active VR 목표와 현재 오른팔을 비교한다.
`CompositionLimits`의7개 양수 임계값을 호출자가 명시해야 한다. 시험 임계값은
실물 설정이 아니다. 입력 좌표는 motor순서 rad/rad/s, 시각은 동일 monotonic 초다.
각 Tick에는 새 snapshot이 필요하다. 초기 settling 중 VR 입력은 적용/저장하지 않는다.

하체 입력12축은 이미 action→위치 변환된 절대 rad다. 후보는 하체0..11 +
캡처12..21 + rate-limited 오른팔22..28이다. 중단 시 Candidate()는 null이며
null을 이전 명령 계속 송신으로 해석하면 안 된다. 실제 writer/damping 연결은 미구현이다.

```powershell
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_measured_composition.exe /Fo:logs\test_results\test_measured_composition.obj experiments\twist2_right_arm_manual\test_measured_composition.cpp'
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_measured_composition.py
```

실제 LowState subscriber/policy/SDK 연결은 없다. CRC·IMU·모드·온도·전축 한계,
정책 freshness, blend/토크/게인/전신 경로 검증은 별도이며 기존 물리 C++는 유지한다.

## Health 및 정책 action 검사 wrapper

`GuardedCompositionOffline`은 상태 health와 `OfflinePolicySample`을 검사한 뒤
기존 합성 모듈을 호출한다. policy는 `Policy::infer` 이후 clipped[-2,2] motor순서
29축 action이며 현재 snapshot sequence와 일치해야 한다. 하체 default+0.5*action
및 clamp는 reference float 연산을 유지한다. 최종 상체 한계 초과는 중단한다.
CRC 필드는 어댑터 assertion일 뿐 실제 DDS CRC 계산/출처 검증이 아니다.

```powershell
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_guarded_composition.exe /Fo:logs\test_results\test_guarded_composition.obj experiments\twist2_right_arm_manual\test_guarded_composition.cpp'
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py experiments/twist2_right_arm_manual/test_cpp_measured_composition.py
```

임계값은 명시적 합성 시험 설정이다. policy 실행/파일 identity 확인, raw LowState
검증, 전신 충돌, blend/torque/gain/writer 연결은 아직 없다. 기존 수신기와 분리돼 있다.

## 저장 Quest 입력으로 guarded 합성 검증

`test_guarded_replay.cpp`는 synthetic fixture 전용 stdin harness다.
`replay_guarded_quest_fixture.py`가 기존 Quest 원문 검증 후 기록된 수신/tick을
연결하고 정상·단절·tilt·policy stale·state stale·초기 불일치6종을 검사한다.
상태는 가상 baseline 고정, policy는 sine action, CRC는 합성 assertion이다.
이는 실제 정책 또는 전신 동역학 시험이 아니다.

```powershell
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_guarded_replay.exe /Fo:logs\test_results\test_guarded_replay.obj experiments\twist2_right_arm_manual\test_guarded_replay.cpp'
py -3.11 experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py --output logs/test_results/guarded_quest_new_run
```

output은 새 디렉터리여야 한다. 기존 `test_queued_input.exe`와 저장152430 Quest
로그도 필요하다. 결과는 `twist2_guarded_quest_fixture_20260907_v2/result.json`에
보존했다. 실제 LowState/SDK/policy runtime/물리 송신 연결은 없다.

## CRC 코어와 정책 array 어댑터

`offline_word_crc.hpp`는 little-endian uint32 word CRC 계산만 제공한다.
DDS/CDR decoder가 아니며 hg LowState layout/CRC field 위치를 가정하지 않는다.
`offline_policy_adapter.py`는 로컬 정책의 고정 SHA256 확인 및 [1,29] raw array의
float32/finite/clip/time 검증을 제공한다. Torch를 import하거나 모델을 실행하지 않는다.
반환된 array만으로 실제 inference 출처를 증명할 수 없다.

```powershell
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_offline_word_crc.exe /Fo:logs\test_results\test_offline_word_crc.obj experiments\twist2_right_arm_manual\test_offline_word_crc.cpp'
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_offline_input_adapters.py
```

실제 decoder에는 배포와 일치하는 hg SDK 정의/layout 및 raw CRC 표본이 필요하다.
현재 프로젝트에는 그 정의가 없고 확인한 py3.11에는 Torch도 없다. 실제 상태 decode/
inference 연결은 미완료다. Go LowCmd 예제의 구조체를 G1 LowState에 대입하지 않는다.

## 고정 공식 hg 정의 기반 native-memory decoder

`vendor/unitree_hg_reference/manifest.json`에 공식 SDK commit과 파일 SHA256을
보존했다. G1 배포 버전과의 일치는 확인하지 않았다. decoder 입력 profile은
`hg_native_le2092_9754cd15`: little-endian, native 메모리2092바이트, trailing CRC다.
DDS/CDR 패킷을 직접 넣으면 안 된다. 첫29 motor 상태와 IMU/remote/mode/tick을
읽으며35 motor 전체 및 나머지 바이트는 CRC 계산 범위에 포함된다.
온도는 motor의 두 센서 중 큰 값이다. robot_tick은 추출만 하고 순서/재시작
처리는 향후 수신 어댑터가 해야 한다. CRC 통과는 송신자 인증이 아니다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/prepare_hg_class_fixture.py
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Ilogs\test_results /Fe:logs\test_results\test_hg_native_decoder.exe /Fo:logs\test_results\test_hg_native_decoder.obj experiments\twist2_right_arm_manual\test_hg_native_decoder.cpp'
.\logs\test_results\test_hg_native_decoder.exe
```

시험은 해시 확인한 공식 class 선언만 추출하여 DDS traits/runtime 없이 컴파일한다.
그 객체로 만든 합성 byte fixture와 대조한 것이며 실제 로봇 raw 표본 검증은 아니다.

## 격리 CPU 정책 실행

공식CPU wheel을 hash 확인한 뒤 `logs/diagnostics/twist2_cpu_venv`에 설치했다.
전역Python 변경 없음. 패키지 버전은 `logs/test_results/twist2_cpu_requirements_20260907.txt`,
출처와 wheel 해시는 `twist2_cpu_install_20260907.json`에 기록했다.

```powershell
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_policy_cpu_offline.py --output logs/test_results/cpu_policy_new.json
```

output은 새 파일이어야 한다. 고정 SHA256 검증한 동일 bytes를 TorchScript에 로드한다.
zero 및 synthetic home 관측 각각10회 CPU 추론은 통과했다. 이는 실제 정책 파일 실행이지만
실제 LowState/history feedback/물리 제어 시험은 아니다. 첫 호출29.7ms로50Hz 보장 없음.
NumPy 미설치 및 jit.load deprecation 경고는 관찰됐고 tensor-only 실행은 통과했다.
결과: `logs/test_results/twist2_cpu_policy_smoke_20260907.json`.

## CPU 정책/history/후보 feedback 반복 시험

`offline_observation_history.hpp`는 reference1432 관측 및10-frame history를 구현한다.
Build 후 승인 후보가 있을 때만 Commit하고, 후보 없으면 Discard, 중단은 Stop이다.
feedback은 raw policy action이 아니라 후보 위치를 target_as_action으로 변환한 값이다.
Stop 후 새 인스턴스를 만들기 전까지 Build할 수 없다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/prepare_observation_reference.py
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Ilogs\test_results /Iexperiments\twist2_right_arm_manual /Fe:logs\test_results\test_observation_history.exe /Fo:logs\test_results\test_observation_history.obj experiments\twist2_right_arm_manual\test_observation_history.cpp && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_policy_history_loop.exe /Fo:logs\test_results\test_policy_history_loop.obj experiments\twist2_right_arm_manual\test_policy_history_loop.cpp'
.\logs\test_results\test_observation_history.exe
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_policy_history_offline.py --output logs/test_results/policy_history_new_run
```

output은 새 디렉터리. 기존 Queue replay harness와152430 Quest 로그가 필요하다.
정상1801 inference/240 active/386 commit, tilt 중단 경로 통과; native reference200frame
정확 비교 통과. 결과: `logs/test_results/twist2_policy_history_20260907_v1/result.json`.

상태는 frozen virtual baseline, 시각은 가상 tick, health는 합성이다. mimic은 이전
승인 upper+default legs로 구성하며 물리 코드의 현재 upper/blend 순서와 다르다.
writer/blend/모터 적용/dynamics 시험이 아니며 first inference30.1ms로50Hz 보장 없음.

## 현재 upper → 추론 → blend → feedback

GuardedCompositionOffline의 Prepare는 복사된 상태에 현재 VR 목표를 적용한다.
PreparedUpper는 관측용 임시 값이며 Candidate가 아니다. 정책 결과를 받은 Finish가
시간/sequence/action 검사 후에만 commit한다. 중복 Prepare/추론 중 expiry/Abort는
중단하고 staged 상태를 버린다. 기존 Tick wrapper도 유지한다.

history loop는 현재 PreparedUpper로 mimic을 만들고 Finish 결과를 float blend한
위치로 feedback한다. blend 미완료 active VR은 이 harness에서 중단한다.
기존 first-active 이전 후보 null gating 때문에 실물 takeover 전체 흐름은 미구현이다.
토크 fade/게인/500Hz writer/damping/실측 applied feedback도 아직 없다.

```powershell
cmd /d /c 'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul && cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs\test_results\test_policy_history_loop.exe /Fo:logs\test_results\test_policy_history_loop.obj experiments\twist2_right_arm_manual\test_policy_history_loop.cpp'
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_policy_history_offline.py --output logs/test_results/preinfer_blend_new
```

결과 `logs/test_results/twist2_preinfer_blend_20260907_v2/result.json`:
정상active240/commit386, tilt/early-blend 차단.601시점 수식/6종 Prepare-Finish
시험도 통과했지만 상태/시각은 가상이며 실제 로봇 안전성 검증은 아니다.


## 현재 500Hz writer 계산 오프라인 검토 (2026-09-07)

- 기존 변경사항을 먼저 확인하고 물리 C++의 rate → joint → torque → joint
  순서를 검토했다. 기존 물리 C++와 reference 원본은 변경하지 않았다.
- 새 `offline_writer_study.hpp`는 소켓/SDK/LowCmd 직렬화 없는 메모리 진단이다.
  2ms당 하체 2.0rad/s, 상체 0.8rad/s writer 상한을 사용한다.
  VR 목표의 0.08rad/s 제한과는 별도 단계다. kp/kd/torque 상수는 로컬
  reference와 drift-test로 대조했다.
- 합성 입력으로 기존 순서의 충돌 2개를 재현했다. 관절27에서 last=desired=0,
  measured q=0.2/dq=0/ff=0이면 torque clamp가 목표를 0.075rad까지 옮겨
  0.0016rad writer 변화량을 넘는다. 같은 관절이 soft upper bound에 있고
  dq=1.5/ff=-2.5이면 최종 joint clamp 뒤 예측 torque=-4Nm로 2.5Nm를 넘는다.
  이는 소스 수식의 합성 반례이며 Arm SDK 기울어짐의 원인 진단이 아니다.
- 새 모델은 rate/joint/torque 구간의 교집합으로 제한한다. 교집합이 없으면
  전체 target commit 취소 후 damping 진단으로 latch한다. 따라서 충돌 시
  기존 물리 계산과 의도적으로 다르며 실제 controller에 적용된 수정이 아니다.
- health/20ms state watchdog, 60ms command watchdog(250ms grace), R1/비상정지,
  gains, capture torque clamp/fade, 중단 후 재개 금지와 35슬롯 damping을 검증했다.
  damping 진단의 predicted_torque=0은 미계산 placeholder다. 실제 토크가
  0이라는 의미가 아니다. damping 지속시간/종료 lifecycle은 아직 모델링하지 않았다.
- 모델 추가 규칙: 호출 간격 최소2ms, 긴 간격에도 고정2ms 변화량만 허용,
  desired 생성시각은 activation 이후여야 한다. 실제 scheduler/clock 측정은 아니다.
- `test_offline_writer_study.cpp`: 500tick×29축 정상 reference 일치/변화율/
  overshoot/gain/예측torque, 오른팔만 목표 변경 시 0..21 유지, 오류12종
  atomic 취소/latch, 충돌2종, watchdog/grace/명시 stop/누락desired,
  torque fade101단계 및 잘못된 alpha 거부 통과.
- MSVC C++17 /W4 /WX 빌드 통과. 관련 pytest **14 passed /110 subtests passed**.
  로그: `logs/test_results/twist2_writer_study_latest.txt`,
  `logs/test_results/twist2_writer_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  G1/WSL/DDS/publisher/물리 출력은 실행하지 않았다.
- 다음: 저장 Quest→CPU 정책→blend의 desired를 이 모델에 연결하여
  50Hz/500Hz 다중 주기와 추론 지연·해제 전파를 파일 재생으로 검증한다.
  현재 writer 테스트는 합성 입력 단독이며 그 전체 경로 연결은 아직이다.
  실제 LowState/배포 ABI/동역학/실시간성 및 로봇 안전성은 미검증이다.

재실행(Windows 로컬, 빌드된 메모리 전용 테스트):
```powershell
.\logs\test_results\test_offline_writer_study.exe
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_offline_input_adapters.py experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py experiments/twist2_right_arm_manual/test_cpp_measured_composition.py
```


## 현재 정책 trace→500Hz 다중 주기 재생 (2026-09-07)

- 현재 변경사항과 CHAT_HANDOFF/정책 history/writer 코드를 확인한 뒤 진행했다.
  다른 작업과 물리 C++는 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_writer_trace_loop.cpp`는 stdin/stdout 전용 C++ probe다.
  `replay_writer_policy_trace.py`가 실제 CPU 정책/blend trace를 읽고 기록된
  inference_ms를 단일 worker 결과 도착 지연으로 반영하여 2ms writer를 호출한다.
  같은 시각에는 stop을 completion보다 먼저 처리하고 중단 후 completion은 폐기한다.
- CPU 정책 원본 재생을 새로 실행했다: 정상 1800 inference/386 commit/active240,
  tilt/blend_gate 포함 3종 통과. 첫 CPU 추론 36.1463ms, 중앙값 0.45805ms.
  전체 시작 구간을 포함한 실시간성 보장은 아니다. writer 재생은 첫 유효
  candidate 이후 구간만 사용하므로 초기 warm-up 지연은 포함하지 않는다.
- 입력은 alpha=1인 완료된 blend만 허용하며 feedforward=0 합성 fixture다.
  writer state는 직전 target q/zero dq로 매 tick 갱신한 이상화된 입력이다.
  정책 관측은 원본 frozen virtual baseline을 그대로 사용한다. writer 결과가
  정책 관측/history로 돌아가지 않는 open-loop trace 재생이며 동역학 모델이 아니다.
- 4종 통과:
  - 기록 inference 지연: 3931 writer tick, input_disengaged 중단.
  - 100ms까지 결과 도착 정체 주입: 223 tick 뒤 command_timeout, 이후 결과366개 폐기.
  - state receipt 갱신 중단: 209 tick 뒤 state_timeout, 이후 결과365개 폐기.
  - 마지막 candidate 40ms 추가 지연: 해제 후 결과1개 폐기, 재개 없음.
- 해제는 source의 검증된 stop tick 36.6105804초를 사용한다.
  writer 중단 36.6121153초, 전달 지연1.5349ms(모의 시계).
  실제 pinch/UDP 수신부터의 지연 또는 Windows 스케줄러 실측이 아니다.
- 성공 tick마다 rate/overshoot/waist·왼팔12..21 유지, 실패 첫 tick의 전체
  commit 취소, 이후 target 불변/damping 진단을 독립 비교했다.
  하체0..11은 정책대로 변경되므로 이 full-body writer에서 유지 대상이 아니다.
  최대 step 0.00400000066rad는 float 반올림을 포함한 하체2rad/s×2ms다.
  VR0.08rad/s와 writer 상체0.8rad/s는 별도 상한이다.
- 첫 release_pending 시험은 마지막 candidate가 해제20.24ms 전이어서 20ms
  주입 구간에 포함되지 않아 검사 실패했다. 30ms 선택 구간으로 수정하여
  실제 지연 completion이 존재하는 것을 확인했다. 최종 결과는 v3다.
- C++17 /W4 /WX 빌드 및 writer 단독 테스트 통과.
  pytest **14 passed /110 subtests passed**, skip0.
- 증거:
  `logs/test_results/twist2_writer_policy_source_20260907/result.json`,
  `logs/test_results/twist2_writer_multirate_20260907_v3/result.json` 및 4종 trace,
  `logs/test_results/twist2_multirate_regression_latest.xml`.
  입력 normal trace SHA256:
  `9e231b7eae74bfb9e8d2989b98747df1db234467770df0f11f6ce30317ed301b`.
  물리 C++ SHA256은 이전 기록 E61D8A3C…CC09F와 동일하다.
- 남은 다음 단계: Prepare→실제 추론 완료→Finish→writer를 하나의 모의
  이벤트 시계로 연결하여 stale 추론 폐기와 history commit 순서를 검증한다.
  현재는 precomputed 후보 전달 시험이므로 upstream freshness 검증의
  실제 추론 지연 반영 및 writer 중단의 upstream 전파는 아직 통합되지 않았다.
  실제 LowState/배포 ABI/동역학/물리 안전성은 계속 미검증이다.

재실행(프로젝트 루트, 출력 폴더는 새 이름 사용):
```powershell
py -3.11 experiments/twist2_right_arm_manual/replay_writer_policy_trace.py --source logs/test_results/twist2_writer_policy_source_20260907 --output logs/test_results/twist2_writer_multirate_rerun
```
MSVC 개발자 셸에서 probe 빌드:
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs/test_results/test_writer_trace_loop.exe /Fo:logs/test_results/test_writer_trace_loop.obj experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp
```


## 현재 단일 이벤트 시계 통합 검증 (2026-09-07)

- 현재 변경사항과 인계/GuardedComposition/ObservationHistory/writer를 확인했다.
  기존 물리 C++/다른 작업은 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_event_clock_loop.cpp`, `run_event_clock_offline.py`:
  raw Quest 파일을 기존 Replay로 검증하고 Prepare→실제 CPU 추론→Finish→
  desired/history→2ms writer를 하나의 모의 이벤트 시계에서 실행한다.
  source tick은 기록된 약50Hz cadence, writer는 첫 candidate 후2ms 간격이다.
  Python heap 순서는 같은 시각 stop→writer→finish→packet→build다.
- Prepare 시각을 Finish 시각으로 재사용하던 방식과 달리 실제 측정 inference
  duration을 더한 완료 시각을 Finish에 전달한다. 정책 created_at은 완료 시각이며
  inference 중 snapshot30ms age 만료를 GuardedComposition에서 검사한다.
  단일 추론만 pending으로 허용하고 그동안 build는 건너뛰며 packet은 다음 build까지 보관한다.
- writer 실패가 guard.Abort/history.Stop/desired 제거로 전파된다. stop은
  pending observation과 준비 중인 upper를 취소한다. 이후 finish는 폐기되며
  target/history/previous_action은 유지된다. 정상 history feedback은 writer의
  rate-clipped q가 아니라 기존 규약대로 성공 Finish의 blend desired다.
- 모델은 검증된 같은 bytes TorchScript를 CPU로 실행한다. 초기 warm-up1회는
  모의 작업 밖에서 수행했고 cold-start/실시간성 검증으로 표현하지 않는다.
  이번 정상 최대 inference9.5081ms. NumPy 미설치/jit.load deprecated 경고가
  있으나 tensor-only 실행은 성공했다.
- 4종 통과:
  - 정상: inference1800/history386/writer3931, input_disengaged.
  - 40ms 지연 Finish: history13/writer152 후 state_expired_during_inference.
    해당 Finish는 후보/history에 commit하지 않았다.
  - 추론 pending 중 writer state age30ms 주입: history13/writer132에서
    state_timeout; 이후 완료 결과1개 폐기.
  - 마지막 추론40ms 지연 중 해제: history385/writer3931, 결과1개 폐기.
- 매 이벤트 history1270개/previous_action29개/commit count를 독립 비교했다.
  성공 writer의 rate/overshoot/12..21 유지, stop 최초·이후 target 불변과
  desired 제거/pending 취소도 확인했다.
- 해제는 raw 파일의 검증된 stop tick36.6105804초를 외부 stop 이벤트로 주입한다.
  이 이벤트에서 즉시 메모리 latch되며 그 뒤 writer 갱신은 없다.
  raw packet을 추론 중 별도 validator로 처리한 시험이나 실제 pinch 지연 실측은 아니다.
- 상태 경계: 정책 state는 frozen virtual baseline, writer state는 직전 target/
  zero velocity fixture다. history 연결과 stop 전파는 통합됐지만 두 단계가
  동일한 실제 LowState를 사용하거나 writer 위치가 다음 policy q 관측으로
  돌아가는 동역학 closed-loop는 아니다. 실로봇 안전성은 계속 미검증이다.
- C++17 /W4 /WX 빌드 통과. 기존 writer 단독 검사와 관련 pytest
  **14 passed /110 subtests passed**, skip0.
  결과: `logs/test_results/twist2_event_clock_20260907/result.json` 및4종 trace,
  `logs/test_results/twist2_event_clock_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 다음 단계: 추론 pending 동안 raw 입력의 해제/오류/timeout을 별도
  검증해서 stop으로 전달하는 로컬 경로. 현재 외부 stop tick 주입을 대체하고
  packet FIFO/재참여/중복 sequence와 동시 완료 우선순위를 검증한다.
  실제 LowState/배포 ABI/동역학/콜드 스타트/실시간성/물리 실행은 미완료다.

재실행(프로젝트 루트, 새 출력 폴더 사용):
```powershell
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --output logs/test_results/twist2_event_clock_rerun
```
MSVC 개발자 셸 빌드:
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs/test_results/test_event_clock_loop.exe /Fo:logs/test_results/test_event_clock_loop.obj experiments/twist2_right_arm_manual/test_event_clock_loop.cpp
```


## 현재 raw 입력 감시와 pending 추론 중단 (2026-09-07)

- 현재 변경사항과 인계/validator/queue/event harness를 읽고 기존 작업을 유지했다.
  물리 C++/G1/WSL/DDS/publisher/UDP 실행·수정 없음.
- 신규 `raw_input_watch_offline.hpp`: 단일 이벤트 소유자가 raw 도착 시
  InputValidator로 즉시 검증한다. 유효 active만64개 FIFO에 보관하고 Prepare가
  한 번 drain한다. 완전히 검증된 pre-engage inactive는 대기하며 보관하지 않는다.
  bootstrap validator는 drain과 무관하게 session/sequence를 유지한다.
- payload16384bytes/queue64 제한, 전체 스키마/해제/중복sequence/250ms
  receiver timeout을 검사한다. 오류 시 FIFO를 지우고 latch한다.
  timeout은 이벤트에서 Poll하므로 별도 실시간 timer/독립 thread 구현은 아니다.
- `test_event_clock_loop.cpp`의 선택적 raw_input 모드:
  packet/poll을 추론 pending 동안 처리하고 guard/history/writer/desired를
  함께 중단한다. raw 모드 build에 외부 packet batch를 섞으면 거부한다.
  기존 batch 모드는 유지한다. Finish/다른 이벤트 앞에서도 timeout을 확인한다.
- `run_event_clock_offline.py --raw-input`은 외부 stop tick 주입을 제거하고
  raw packet을 동일시각 writer/finish보다 먼저 처리한다.
  동일시각 packet 간에는 원본 FIFO 순서를 유지한다.
- 신규 `test_raw_event_clock.py` **9종 통과**: 해제=완료 시각 및 재engage,
  pending malformed JSON, drain 뒤 duplicate,250ms 경계와 timeout,
  oversized, pending65번째 queue overflow, FIFO 중간 역순sequence,
  engage 전 idle 장기대기, 유효 batch drain1회.
  합성 zero-action 정책 입력이며 실제CPU 정책 시험과 구분한다.
  중단 최초 및 늦은 Finish/재engage 이후 history/previous/target/write 불변,
  desired 제거/pending 취소/FIFO 제거를 검사했다.
- **실측 duration 재생은 통과하지 못했다.** warm-up1회로2회 시도했으나
  active 이전 state_expired_during_inference로 중단됐다. warm-up10회 후에도
  동일하게 실패했으며 v3 failure.json에 최대52.0336ms window가 기록돼 있다.
  window는 tensor 생성/model/clamp/list 변환을 포함한다. 지연 원인은 미진단이다.
  30ms state freshness 제한을 완화하지 않았다. 첫2회는 콘솔 오류만 남고
  v3부터 failure.json으로 trace를 저장하도록 개선했다.
- 입력 스케줄 검증을 분리하기 위해 `--fixed-inference-ms 1` 옵션을 추가했다.
  실제 CPU action은 계산하되 완료 시각만 명시적1ms 모의 값으로 사용한다.
  이 모드 **정상 재생 통과**: inference1800/history386/writer3921,
  raw 해제 도착36.591642초에서 input_disengaged 중단.
  다음 policy tick36.6105804초를 기다리지 않는다. 실제 물리 지연 측정이 아니다.
  이 실행의 실제 측정 최대40.8206ms도 별도 보고하며 실시간 통과로 해석하지 않는다.
- 상태는 정책 frozen virtual baseline/writer previous-target zero-velocity
  fixture로 유지한다. G1 LowState/동역학/로봇 안전성 검증이 아니다.
- C++17 /W4 /WX 빌드 통과. 관련 회귀 **23 passed /110 subtests passed**.
  증거:
  `logs/test_results/twist2_raw_event_regression_latest.xml`,
  `logs/test_results/twist2_raw_event_clock_20260907_v3/failure.json`,
  `logs/test_results/twist2_raw_event_clock_fixed_20260907/result.json` 및 trace.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 다음: 로컬 CPU 측정 window의 지연 구간을 tensor 준비/model/후처리로
  분리해 원인을 조사하고, 실측 시계에서 정상 종료까지 가능한지 확인한다.
  raw 입력 로직의 결정적 시험은 완료했지만 이번 실측 시간 전체 재생은 실패다.
  실제 로봇 실행 및 LowState/배포 ABI/동역학 검증은 미완료다.

프로젝트 루트에서 재실행(출력은 새 폴더):
```powershell
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_raw_event_clock.py
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --fixed-inference-ms 1 --output logs/test_results/twist2_raw_fixed_rerun
```
실측 시간 시험은 `--fixed-inference-ms 1`을 생략한다. 현재 실측 시험은
state_expired_during_inference 실패 기록이 있으므로 고정시간 시험과 구분한다.


## 현재 CPU 지연 분리 측정·정책 worker 격리 (2026-09-07)

- 인계/현재 변경사항/측정 코드를 읽고 로컬 파일 재생만 수행했다.
  기존 물리 C++/G1/WSL/DDS/UDP/publisher/물리 출력은 변경·실행하지 않았다.
- `run_event_clock_offline.py`에 tensor/model/output 시간, 호출 thread CPU 시간,
  GC callback의 시작/종료·generation을 기록했다. 성공/실패 모두
  `normal_timing.json`에 매 추론 구간을 저장한다.
- 직접 실행 실패를 재현했다: total40.9698ms, tensor0.0506ms,
  model40.8806ms, output0.0386ms. 이 model 구간에 generation2 GC가
  40.5913ms 실행됐다. 따라서 이번 재현에서 GC가 지연 대부분을 차지했다.
  이전52.03ms 건은 당시 세부 계측이 없어 동일 원인으로 단정하지 않는다.
  thread_time 값은 Windows의 거친 해상도로0/46.875ms 등이 나와 세부 분해에 사용하지 않는다.
- 신규 `policy_cpu_worker_offline.py`: 해시 검증한 동일 bytes 모델을
  별도 로컬 Python 프로세스에서 CPU 실행한다. stdin/stdout JSON만 사용,
  소켓/SDK 없음. 부모는 이 모드에서 torch/model을 로드하지 않는다.
  GC를 끄거나 임계값을 바꾸지 않고 policy heap과 replay/log heap을 분리했다.
- `--raw-input --isolated-policy`는 JSON 인코딩/pipe 왕복/worker 실행/
  응답 decode까지 포함한 실제 경과시간을 모의 Finish 시각에 더한다.
  worker 내부 세부시간도 별도 기록한다. 고정 완료시간 옵션은 사용하지 않았다.
  기존 직접 실행/고정시간 옵션은 비교용으로 남아 있다.
- 초기 model 로드/warm-up10회는 모의 시계 밖이다. 부모 event processing/
  전체 OS scheduler의 모든 지연을 모의 시계에 더하는 구조는 아니다.
  실제 asynchronous robot control이나 실시간성을 입증한 것은 아니다.
- 분리 실행2회 정상 종료:
  - 첫 실행1800 inference/history386/writer3921, 최대왕복1.8442ms,
    중앙값0.7393ms, worker 내부 최대0.9748ms. 측정 window에서 부모/worker
    generation2 GC event는0개였다.
  - worker 정리 경로 보강 후 최종v2도1800 inference/writer3921,
    최대왕복2.0556ms. history385/해제 뒤 completion1개 폐기.
    마지막 Finish와 raw release의 측정시간 순서에 따른 차이이며 재개 없음.
  - 두 실행 모두 raw release36.591642초에 input_disengaged.
  30ms state freshness 기준은 그대로다. 최대치의 장기 상한을 보장하지 않는다.
- 신규 `test_policy_worker_offline.py`는 합성1432차원8입력에 대해
  직접 실행과 worker의 clip 후29축 출력을 exact 비교해 통과했다.
  별도 unittest1개/내부8case이며 관련 pytest는 **23 passed /110 subtests passed**.
  syntax/diff check 및 worker 정상 종료 확인. 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 증거:
  `logs/test_results/twist2_timing_split_20260907/failure.json` 및 timing,
  `logs/test_results/twist2_timing_isolated_20260907/result.json`,
  `logs/test_results/twist2_timing_isolated_20260907_v2/result.json` 및 timing/trace,
  `logs/test_results/twist2_policy_worker_equivalence_latest.txt`,
  `logs/test_results/twist2_cpu_isolation_regression_latest.xml`.
- 남은 다음 단계: worker 응답 누락/비정상 종료/잘못된 응답에 대한 제한시간과
  stop 전파를 파일·합성 worker로 검증한다. 현재 readline은 응답을 동기 대기하며
  worker hang에 대한 응답 deadline은 없다. 정상 종료/예외 정리의5초 대기는 별도다.
  실제 LowState/배포 ABI/동역학/물리 안전성 및 live 동시성은 계속 미검증이다.

프로젝트 루트에서 재실행(출력은 새 폴더):
```powershell
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --isolated-policy --output logs/test_results/twist2_isolated_rerun
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/test_policy_worker_offline.py
```
직접 실행의 GC 비교는 `--isolated-policy`를 생략한다.


## 현재 worker 응답 제한시간·실물 전환 우선순위 (2026-09-07)

- 사용자 요청에 따라 실물 연결의 필수 장애 처리부터 진행했다.
  현재 변경사항/인계/worker를 읽고 기존 물리 C++와 다른 작업은 유지했다.
  G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `policy_worker_client_offline.py`: 자신이 만든 로컬 worker에만 접근하는
  단일 요청 client다. daemon I/O thread가 pipe write/read를 수행하며 부모는
  초기 ready10초/요청응답30ms deadline으로 대기한다. 최대응답65536bytes,
  newline/UTF8 JSON/중복key/NaN/응답ID/finite29축[-2,2]를 검증한다.
  오류는 latch되며 worker를 종료하고 늦은 결과로 재개하지 않는다.
- `policy_cpu_worker_offline.py`는 request_id를 응답에 되돌린다.
  기존 list 입력은 출력 동등성 비교용으로 유지한다. 실제 client는 ID 포함 dict를 사용한다.
- `run_event_clock_offline.py`는 새 client를 사용하고 오류를 worker_failure
  이벤트로 C++ Stop에 전달한다. 무응답을 무기한 readline으로 기다리던 경로를 제거했다.
  모의 큐에서는 elapsed 이후 Stop 이벤트이며 live 비동기 제어 구현은 아니다.
- deadline은 OS 실행 상한 보장이 아니다. timeout 감지 후 소유 worker
  terminate/wait/kill 및 thread join의 정리 시간이 추가된다(각1초 제한).
  시험에서 오류 호출은 정리 포함1초 미만이고 프로세스/thread 종료를 확인했다.
  현재 메모리 재생의 C++ stdin 응답 자체에 대한 장애 처리는 별도다.
- 신규 client 테스트5개/내부14case: 응답timeout/EOF/깨진JSON/ID불일치/
  boolean action/oversized, 시작timeout,NaN/중복key,정상ID응답,
  장애6종→C++ pending Stop→늦은Finish·재engage 후 history/target 불변.
  합성 worker는 모두 로컬 테스트 프로세스이며 무관한 PID를 종료하지 않았다.
- 전체 관련 회귀 **28 passed /124 subtests passed**.
  직접 정책과 worker 출력 exact8입력 비교도 unittest1개 통과.
- 실제CPU/저장Quest 정상 재생 통과: inference1800/history385/writer3921,
  최대왕복4.9294ms, 해제36.591642초, 늦은completion1개 폐기.
  fixed_inference_ms=null. warm-up10회는 모의 시계 밖이며 실시간/물리 안전성 보장은 아니다.
- 증거:
  `logs/test_results/twist2_worker_deadline_regression_latest.xml`,
  `logs/test_results/twist2_worker_deadline_20260907/result.json` 및 timing/trace,
  `logs/test_results/twist2_worker_deadline_equivalence_latest.txt`.
  물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.

### 실물 VR까지의 필수 순서 — 부가 오프라인 시험보다 우선

| 단계 | 현재 상태 | 통과에 필요한 증거 |
|---|---|---|
| 입력/정책/목표/중단 로컬 준비 | 합성·저장파일 재생 통과 | 위 테스트·trace; 실제 로봇 안전성과 구분 |
| 실제 LowState 초기화 | 미완료 | 실제 배포 SDK/LowState 형식 확인, fresh CRC/모드/관절/속도/IMU 상태와 정지구간 캡처, VR 첫 목표 정렬 |
| 단일 full-body owner 연결 | 미완료 | 기존 물리 C++를 유지한 별도 검토 가능한 연결안, 0..11 정책·12..21 할당·22..28 VR 통합, 송신자1개와 fail-stop |
| 제한된 실물 비VR 시험 | 미승인/미실행 | 실행 파일·대상·모드 전환·중단/종료 동작을 사전에 특정하고 승인 후 확인 |
| 최초 실물 VR 시험 | 미승인/미실행 | 앞 단계 통과, 작은 목표 범위·0.08rad/s·해제/오류 중단 확인 |

- 다음 작업은 실제 LowState 입력과 단일 owner의 연결 준비다. 동일한 정상
  오프라인 검사를 반복하는 것으로 실제 초기화/물리 시험을 대체하지 않는다.
- 기존 physical writer의 순차 clamp 충돌 반례는 아직 물리 원본에 수정되지 않았다.
  새 owner 연결 때 해결/검토해야 하며 Arm SDK 사고 원인으로 단정하지 않는다.
- 현재 금지된 G1/WSL/DDS/publisher 실행은 별도 구체적 범위의 승인이 필요하다.
  기존 Arm SDK 기울어짐은 해결이 아닌 보류이며 새 C++의 Unity 시각화도 별개다.


로컬 재실행:
```powershell
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --isolated-policy --output logs/test_results/twist2_deadline_rerun
```
출력 폴더는 새 이름을 사용한다.


## 현재 native LowState→초기화→전신 후보 연결 (2026-09-07)

- 현재 변경사항/인계/native decoder/초기화 코드를 검토했다. 기존 물리 C++와
  다른 작업은 유지했고 G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `native_composition_offline.hpp`는 native bytes를 DecodeOfflineHgNative에
  통과시켜 실제 입력 형태의 sample/health를 GuardedComposition Prepare에 전달한다.
  JSON/Mink를 measured state로 대체하지 않는다. Finish가 유효 policy를 받은
  뒤에만 후보를 노출한다. 초기 정지1초→VR 첫 목표 정렬→정책 하체와 캡처 상체
  결합까지 기존 개별 단계를 연결했다.
- CRC/ABI profile/health/age 외에 receipt 증가와 robot tick 연속성을 검사한다.
  tick duplicate/backward/reset은 latch중단, uint32 max→0 rollover는 serial
  arithmetic으로 허용한다. tick 단위/최대 허용 jump는 배포 확인 전 미검증이다.
- profile은 여전히 `hg_native_le2092_9754cd15`라는 Windows native fixture
  layout이다. 실제 G1 배포 ABI 확인도 DDS/CDR 디코딩도 아니다.
- `test_native_composition.cpp`: pinned SDK class accessor로 만든 합성 LowState
  bytes→CRC→1초 settle→VR align→policy legs/캡처 upper를 검증했다.
  waist12를 모델 default와 다른0.1rad로 설정해 실측 입력 역할의 capture를
  사용하는지 확인했다. Prepare 중 후보null, 정상Finish 후0번 정책 반영/
  12..28 캡처 유지,중복tick 후후보제거/재개금지 통과.
  CRC/profile/stale/R1/mode/motor fault/tilt7종 거부, rollover/backward,
  Finish state 만료도 통과했다.
- 초기 시험은 strict20ms 간격 경계에서 실패했다. fixture cadence를10ms로
  하여 경계 반올림을 피했다. strict age/receipt gap20ms 비교의 부동소수 경계
  처리는 변경하지 않았으므로 정확히20ms cadence에 대한 허용을 주장하지 않는다.
- MSVC C++17 /W4 /WX 및 관련 회귀 **14 passed /110 subtests passed**.
  증거: `logs/test_results/twist2_native_composition_latest.txt`,
  `logs/test_results/twist2_native_composition_regression_latest.xml`.
- 로컬 기존 상태 자료도 확인:
  `logs/runtime/g1_hardware_lowstate.json`은2026-09-07 14:42:30 저장된
  read_only_lowstate 상태 요약으로 당시 mode_pr0/mode_machine5와29축q/dq가 있다.
  native bytes/CRC/시간 연속 sample이 없어 이번 native 초기화 입력으로 사용할 수 없다.
  내부 last_packet_age_s는 저장 당시 값이며 현재 fresh 상태로 해석하면 안 된다.
  `logs/review/20260903/saved_lowstate_review_fixture.json`은29축0값 fixture다.
- 실물 전환에 필요한 다음 입력: 배포 SDK/native layout 확인과 최신 연속
  LowState 원본 및 local receipt 시각. 현재 로컬 자료만으로 실측 초기화
  완료를 선언할 수 없다. G1/WSL/DDS 실행 금지는 유지한다.
- 단일 송신자 연결은 아직 후보 계산 단계다. 0..11 정책/12..21 캡처/
  22..28 VR 소유권을 구성할 수 있지만 실제 lowcmd writer/모드 handoff/
  종료 lifecycle과 배포 ABI는 미연결이다. native 후보 연결 통과는 물리 안전성 검증이 아니다.
- 기존 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.


MSVC 개발자 셸의 로컬 빌드(기존 생성 fixture header 필요):
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Ilogs/test_results /Fe:logs/test_results/test_native_composition.exe /Fo:logs/test_results/test_native_composition.obj experiments/twist2_right_arm_manual/test_native_composition.cpp
```
테스트 stdin은 `test_cpp_upper_target.Packet()`의 JSON 한 줄이다.


## 현재 실제 tick 중복 분석·연속성 어댑터 수정 (2026-09-07)

- 저장된 실제6000sample을 Windows에서만 재생했다. 신규 WSL/DDS/로봇 접속/
  publisher/물리 출력 없음. 현재 변경사항과 인계 및 기존 어댑터를 읽고 수정했다.
- 같은tick291쌍 전부 IMU/motor/CRC 영역이 달랐고 header/remote/reserve는
  같았다. 전체bytes 동일쌍0,중복쌍receipt 간격0.329115~5.589701ms.
  따라서 tick을 패킷별 unique sequence로 해석한 기존 규칙이 관측자료와 맞지 않는다.
  실제 firmware의 tick 단위/갱신 구현까지 확인한 것은 아니다.
- 신규 offline_state_continuity.hpp: local receipt 단조 증가/20ms freshness와
  receipt gap을 유지한다. 동일robot tick은 허용하되 마지막tick 전진 이후20ms
  초과 시robot_tick_stalled. 역행/reset은 거부, uint32 rollover는 허용한다.
  중단은 latch되고 나중 전진으로 자동 복구되지 않는다. tick의 정상 주기 가정은 없다.
  이 검사는 Check 호출 시 동작하며 독립 타이머가 아니다.
- native_composition_offline.hpp는 이 검사를 사용한다. local sequence는
  유효상태마다 증가하므로 반복robot_tick을 local sequence로 대체하지 않는다.
  CRC/health/pose/alignment/deadman 조건은 완화하지 않았다.
- decoder에 hg_sdk_crc_le2092_b95a5304를 별도 profile로 추가했다.
  설치SDK CRC source 해시/패킹을 확인한 representation이며 native G1 ABI/
  CDR원본으로 명명하지 않는다. 기존native fixture profile도 유지한다.
- 신규 test_real_state_continuity.cpp:
  수집metadata CRC source/representation 확인→6000CRC/receipt/tick 연속성 통과,
  duplicate291허용, 합성stall/receipt재사용/stale/latch 검사 통과.
  실제 첫sample은 원본buttons0 상태로 native composition에 전달하여
  operator_stop/nullcandidate를 확인했다. R1값을 조작하지 않았다.
- 기존 native composition 테스트는 짧은중복 허용→지속정체중단으로 갱신했고
  capture/정책하체/캡처상체/health7종/rollover/역행/Finish만료까지 통과.
  MSVC C++17 /W4 /WX 빌드 통과. 회귀 **14 passed /110 subtests passed**.
- 증거:
  logs/test_results/twist2_real_state_continuity_latest.txt,
  logs/test_results/twist2_real_state_continuity_review.json,
  logs/test_results/twist2_native_composition_tick_latest.txt,
  logs/test_results/twist2_state_continuity_regression_latest.xml.
- 다음은 실측 캡처 자세와 VR 최초목표의 정렬 준비다. 현재 자료는 R1 off이며
  실제 제어초기화가 성공한 자료가 아니다. 실제single lowcmd owner/모드전환/
  비VR 물리시험/VR 물리시험은 여전히 미실행·미승인이다.
  코드의20ms 부동소수 경계 비교 문제는 이번 변경으로 별도 보정하지 않았다.
- 기존 물리 C++ SHA256 불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.


로컬 재생:
```powershell
.\logs\test_results\test_real_state_continuity.exe logs/test_results/twist2_hg_readonly_capture_20260907.jsonl
```


## 현재 저장 실측 자세↔VR 최초목표 정렬 검사 (2026-09-07)

- 현재 변경사항/인계와 MeasuredComposition의 기존 initial_arm_error0.025rad
  조건을 읽고 유지했다. 새로운 WSL/DDS/로봇 실행이나 물리 C++ 변경 없음.
- 신규 audit_saved_alignment.cpp는 실제 CRC-packed 상태에서1초 정지구간을
  확인한 뒤(1011samples) 저장Quest 첫 active 목표를 pose-only 검사에 전달한다.
  다른 시각에 수집한 세션이므로 packet receipt를 비교시각으로 재지정했다.
  따라서 동시수집 live 정렬 시험이 아니며 health/R1 arming 시험도 아니다.
- 결과 initial_arm_mismatch, 후보null. 오른팔7축 중6축이0.025rad를 초과했다.
| 관절 | 실측 rad | 저장 VR rad | 차이 ° | 허용 |
|---|---:|---:|---:|---|
| 22 right_shoulder_pitch | 0.16053 | 0.17453 | 0.80 | 통과 |
| 23 right_shoulder_roll | -0.05057 | -0.38397 | -19.10 | 초과 |
| 24 right_shoulder_yaw | -0.06134 | 0.00000 | 3.51 | 초과 |
| 25 right_elbow | 1.39617 | 0.95993 | -24.99 | 초과 |
| 26 right_wrist_roll | -0.10733 | 0.00000 | 6.15 | 초과 |
| 27 right_wrist_pitch | 0.28316 | 0.00000 | -16.22 | 초과 |
| 28 right_wrist_yaw | -0.07005 | 0.00000 | 4.01 | 초과 |

- 양성 대조군으로 동일 실측q를 목표로 만든 합성packet은 정렬 검사를 통과했다.
  합성packet은 테스트 안에서만 사용했고 runtime 파일/Unity/VR에 보내지 않았다.
  로봇을 기존 VR 기본자세로 이동하거나 관절 offset을 더하지 않았다.
- 공통 Mink 코드 g1_right_arm_common.py의 DEFAULT_RIGHT_ARM_READY_DEGREES는
  [10,-22,0,55,0,0,0]이며 저장VR 첫 목표와 일치한다.
  G1_USE_HARDWARE_INITIAL_STATE=1이면 별도 right_arm_q_rad를 읽는 기존 경로가
  있지만 freshness/동일세션/CRC를 이 loader가 확인하지 않으며7축만 초기화한다.
  이번에 환경변수/공용초기화파일/기존 hardware-sync launcher는 변경·실행하지 않았다.
- 다음 구현 대상: 최신 LowState와 동일세션에 묶인 Mink 초기 자세/기준 프레임
  동기화. 필요하면 full29축 기구학 자세까지 반영하고 collision/첫 goal 정렬을
  다시 검사해야 한다. 오래된 저장 snapshot을 현재 로봇 상태로 재사용하면 안 된다.
- MSVC C++17 /W4 /WX 빌드와 실제 mismatch 거부/합성 matched 허용2경로 통과.
  증거 logs/test_results/twist2_saved_alignment_review.json(입력hash/관절별오차 포함).
  pose-only 정지구간 검사 통과를 제어 초기화/물리안전성 통과로 해석하지 않는다.


## 현재 Mink29축 LowState seed 초기화 경로 (2026-09-07)

- 현재 변경사항/인계/기본 초기화 함수를 확인하고 기존 변경분을 보존했다.
  기존 물리 C++/G1/WSL/DDS/publisher 실행·변경 없음. VR 프로세스도 시작하지 않았다.
- 신규 MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py:
  schema g1.mink.lowstate_seed.v1,명시적session ID,29관절 이름 순서,
  received_at_unix_s의0..250ms age,reviewed SDK CRC-packed2092bytes를 검증한다.
  CRC 독립검사,mode0/5,finite q/dq/IMU,abs dq<=0.1,roll/pitch<=0.15,
  온도<=75/motorfault0 조건을 확인한다. 부정확한 관절값을 clamp해서 숨기지 않는다.
  이것은 시뮬레이션 초기 seed 검사이며 R1/실제제어arming 판정이 아니다.
- 기존 run_mink_g1_right_arm_virtual_center_live.py에 opt-in
  --initial-lowstate-seed PATH / --initial-lowstate-session ID를 추가했다.
  두 옵션은 함께 필요하며 없으면 기존 기본자세로 시작한다.
  model joint qpos 주소로29축을 모두 적용하고 태스크/목표 프레임을 그 자세에서
  초기화한다. 소켓 생성 전 age를 재검사하고 기존 planner의 CheckConfiguration
  충돌/범위 검사를 통과해야 한다. loader실패 시기본자세로 fallback하지 않는다.
- 적용은 joint29축에 한정된다. free-base 위치/방향은 model 초기값을 유지하며
  metadata base_pose_measured=false다. 실제 월드 프레임 정렬까지 완료된 것이 아니다.
  session은 seed와명시적실행값을 대조하며 아직Unity/수신기세션전달 전체계약은 미연결이다.
- 신규 backend/tests/test_lowstate_mink_seed.py:
  실제 저장 q를 테스트 시계로만 seed fixture화하여29축exact 적용/다른qpos유지/
  입력불변,stale/future/session/order/CRC/length/schema/representation 거부,
  관절범위오류의atomic거부10tests 통과. 오래된상태를live로 승인하거나runtime에 쓰지 않았다.
- 기존standard Mink24tests 포함 **34 passed**.
  XML logs/test_results/twist2_mink_seed_latest.xml.
  최종계약재검사10passed: logs/test_results/twist2_mink_seed_contract_latest.xml.
  syntax/diff 검사 통과. 새로운옵션으로 전체GUI시작/VR사용자확인은 아직이다.
- 다음 필수 연결: 명시적동일세션의최신LowState→seed파일을atomic갱신하는
  읽기전용공급기,플랫폼간wall-clock timestamp 확인,simulation launcher인자전달.
  현capture로그는wallclock/session envelope가없으므로live seed로바로사용할수없다.
  seed유효시간은완화하지않는다. 소켓전검사이후live첫engage freshness/일치 여부는
  C++정렬gate와동일세션상태로다시검증해야한다.
- 기존공유초기화파일/G1_USE_HARDWARE_INITIAL_STATE/BAT는변경하지않았다.
  실물초기화·single rt/lowcmd owner·물리안전성은계속미검증이다.
- 기존물리C++ SHA256:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.


seed envelope 예시 구조(실행용 실제데이터 아님):
```json
{"schema":"g1.mink.lowstate_seed.v1","session_id":"explicit-session",
 "joint_names":["29 ordered names required"],
 "received_at_unix_s":0,
 "representation":"sdk_crc_packed_le2092_b95a5304","packed_hex":"2092 bytes required"}
```
현재 공급기 미연결이므로 위 예시는 loader에서 거부된다. 직접 timestamp를 고쳐
과거기록을 fresh 상태로 사용하지 않는다.


## 현재 LowState→atomic seed 공급기 준비 (2026-09-07)

- 현재 인계/capture/seed loader를 검토하고 로컬 코드를 작성했다.
  신규 WSL/DDS/로봇 실행/VR 시작/publisher/물리 출력 없음.
- 신규 lowstate_seed_writer.py: 세션별 새 폴더의 seed 경로를 소유한다.
  임시파일에 기록/fsync→기존 ReadSeed 검증→os.replace 순서로 교체한다.
  잘못된CRC/health/age/receipt 또는교체실패 시이전seed와임시파일을제거한다.
  기존다른파일을 인수하지 않으며 timestamp는새수신값일때만전진한다.
- 신규 supply_lowstate_seed_readonly.py: 승인 후 Domain0/eth2/rt/lowstate만
  최대30초 구독한다. 새run폴더를exclusive생성,약50Hz로 SDK CRC-packed seed를 갱신.
  msg수신 직후Unix wall-clock을부여하고CRC는수신마다검사한다.
  timeout/오류/종료시seed삭제. 강제종료로남아도consumer250ms만료로거부한다.
  외부45초timeout으로시작정체도제한할계획이다.
- 신규 observe_seed_file_offline.py: Windows에서35초동안seed파일만읽어
  동일session/CRC/health/250ms유효시간과종료후삭제여부를기록한다.
  WSL↔Windows wall-clock/DrvFs파일교체의실제동작은아직미검증이다.
- backend/tests/test_lowstate_seed_writer.py의6tests:
  교체/수신중단뒤만료/삭제,CRC/stale/receipt/replace오류시정리,
  다른소유파일보존 통과. 기존seed loader10개포함 **16 passed**.
  logs/test_results/twist2_seed_supply_latest.xml.
  합성시계+저장bytes fixture만사용했으며runtime seed파일은작성하지않았다.
- 기존물리C++ SHA256불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
- 다음승인요청:30초읽기전용DDS seed공급과Windows 파일검증만실행.
  session=twist2-seed-check-20260907,새폴더=logs/test_results/twist2_seed_live_20260907.
  Unity/Mink 실행이나모터명령/모드변경은포함하지않는다.
  실제제어arming/세션별VR프레임/전체base pose동기화는계속미완료다.

실행 범위(프로젝트 루트, 아직 실행하지 않음):

WSL 공급기:
```powershell
wsl -d Ubuntu -- timeout --signal=TERM --kill-after=2s 45s /home/user/.venvs/g1-teleop/bin/python -B /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py --directory /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results/twist2_seed_live_20260907 --session twist2-seed-check-20260907
```

동시에 Windows 파일 검증:
```powershell
py -3.11 experiments/twist2_right_arm_manual/observe_seed_file_offline.py --seed logs/test_results/twist2_seed_live_20260907/seed.json --session twist2-seed-check-20260907 --output logs/test_results/twist2_seed_live_observer_20260907.json
```
DDS discovery/상태 수신 트래픽은 발생한다. publisher·모드 변경·G1 파일작업은 없다.
