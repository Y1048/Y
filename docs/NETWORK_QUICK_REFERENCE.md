# G1 Teleoperation Network Quick Reference

현재 코드 기준: 2026-09-02

## 가장 짧은 암기법

```text
5005~5006 : Quest/Unity <-> Mink 텔레오퍼레이션
5007~5008 : 실제 G1 상태 확인과 안전 검증
5009~5010 : 실제/저장 G1 상태 시각화
5011      : G1 카메라 JPEG -> Unity PiP (TCP)
5012      : Gate 7 후보 자세 -> MuJoCo 표시 전용 피드백
5013      : Windows 검증 릴레이 -> WSL Gate 7 물리 어댑터
5014      : VR 기록 proxy -> Gate 7 dry-run 전달
```

## UDP 포트

| 포트 | 방향 | 역할 | 실제 G1 명령 여부 |
| ---: | --- | --- | --- |
| `5005` | Unity -> Mink/MuJoCo | Quest 오른손 위치·회전 target 전송 | 아니오. 시뮬레이션 IK 입력 |
| `5006` | Mink/MuJoCo -> Unity | Mink가 계산한 29관절 자세와 IK·충돌·workspace 상태 반환 | 아니오. 제어 피드백 |
| `5007` | WSL G1 subscriber -> Windows | 실제 `rt/lowstate`를 초기 동기화, Gate 5, 시작 전 검사에 전달 | 아니오. 읽기 전용 |
| `5008` | Mink -> locked Gate 7 | 순번·원본 해제 원인·최소 충돌 여유가 포함된 Arm SDK 후보를 검사 | 아니오. 오프라인 테스트 전용 |
| `5009` | WSL G1 subscriber -> Windows MuJoCo | 실제 G1 29관절과 상대 base pose를 MuJoCo에 실시간 표시. 저장 JSON 재생에도 사용 | 아니오. 읽기 전용 |
| `5010` | LowState viewer -> Unity | `5009`에서 검증한 실제/저장 29관절과 선택적 상대 base pose를 Unity 공식 G1 모델에 표시 | 아니오. 표시 전용 |
| `5012` | locked Gate 7 -> Mink/MuJoCo | 연동 해제 후 HOLD와 Regular 복귀 후보를 기존 MuJoCo 창에 표시 | 아니오. localhost 시뮬레이션 전용 |
| `5013` | Windows validated relay -> WSL Gate 7 | 검증된 UDP 5008 packet을 WSL live 어댑터에 전달 | 자체 명령 없음. 이후 어댑터만 잠금 해제 시 DDS 출력 가능 |
| `5014` | Mink capture proxy -> Gate 7 dry-run | UDP 5008 원본을 JSONL에 기록하면서 dry-run에 전달 | 아니오. 기록/회귀 전용 |

## TCP 포트

| 포트 | 방향 | 역할 | 실제 G1 명령 여부 |
| ---: | --- | --- | --- |
| `5011` | WSL camera bridge -> Unity | SDK2 `VideoClient`가 반환한 완전한 JPEG를 시야 고정 PiP에 표시 | 아니오. 카메라 읽기 전용 |

### 핵심 구분

- `5005`와 `5006`은 **VR 텔레오퍼레이션 시뮬레이션 왕복 경로**다.
- `5007`은 **실제 G1 상태 검사와 초기 동기화**에 쓴다.
- `5008`은 **실제 로봇에 보내기 전 후보값만 검사하는 locked Gate 7 입력**이다.
- `5009`는 **실제 G1 -> MuJoCo 전신 미러**다.
- `5010`은 **실제 G1 -> Unity 전신 미러**다.
- `5011`은 **실제 G1 카메라 -> Unity 영상 PiP**다. UDP가 아니라 TCP다.
- `5012`는 **Gate 7 -> MuJoCo Regular 복귀 표시**다. 패킷은
  `simulation_only=true`, `hardware_output_authorized=false`를 강제하며
  `REGULAR_RETURN/REGULAR_HOLD` 상태만 MuJoCo 자세에 적용한다.
- `5013`은 **Windows -> WSL Gate 7 물리 어댑터**의 내부 전달 포트다.
  Windows relay가 UDP 5008의 schema와 순서를 먼저 검사하며 relay 자체에는
  Unitree SDK, DDS publisher 또는 로봇 명령 기능이 없다.
- `5014`는 **VR 입력 기록 중에만 쓰는 Gate 7 대체 입력 포트**다. recorder가
  UDP 5008을 독점 수신하므로 Gate 7 dry-run은 5014에서 전달본을 받는다.
- `5006`과 `5010`을 합치면 안 된다. `5006`은 Mink 제어 피드백이고,
  `5010`은 실제/저장 상태의 시각화 전용이다.

## 전체 흐름

### VR 텔레오퍼레이션

```text
Quest hand tracking
  -> Unity
  -> UDP 5005
  -> Mink + MuJoCo IK
  -> UDP 5006
  -> Unity G1 preview/HUD
```

### 실제 G1 상태 확인

```text
G1 rt/lowstate + rt/odommodestate
  -> WSL Unitree SDK2/CycloneDDS
  +-> UDP 5007 -> 초기 동기화 / Gate 5 / startup precheck
  `-> UDP 5009 -> MuJoCo 전신/base 미러
                   -> 실제 표시 자세 + 오차 계측 UDP 5010
                   -> Unity 전신/base 미러
```

### Safety dry-run

```text
Mink 후보 관절값
  -> UDP 5008
  -> schema/sequence/watchdog 검사
  -> active이면 오른팔 후보 추종
  -> 의도적 pinch이면 Regular 양팔 복귀 후보
  -> 추적/네트워크/workspace/collision fault이면 현재 목표 HOLD
  -> 실제 G1 출력 없음
```

### 잠금된 실제 팔 출력 경로

```text
Mink 후보 관절값
  -> Windows localhost UDP 5008
  -> schema/session/sequence 검증 relay
  -> WSL UDP 5013
  -> Gate 7 + direct DDS rt/lowstate 재검증
  -> locked rt/arm_sdk adapter
```

현재 `config/g1_gate7_live_hardware_output.json`의
`hardware_output_authorized=false` 때문에 마지막 publisher는 생성될 수 없다.
어깨 authority 시험 승인 후에만 별도로 잠금을 검토한다.

### 실제 G1 카메라

```text
G1 front camera / videohub
  -> Unitree SDK2 VideoClient.GetImageSample (CycloneDDS domain 0)
  -> WSL read-only JPEG bridge
  -> TCP 127.0.0.1:5011
  -> Unity G1HeadCameraPiP
```

## DDS 항목

UDP 포트와 DDS 토픽은 서로 다른 개념이다.

| 항목 | 역할 | 현재 정책 |
| --- | --- | --- |
| DDS domain `0` | Unitree SDK2/CycloneDDS 통신 영역 | 현재 기본값 |
| `rt/lowstate` | 실제 G1 29관절 위치·속도 상태 | subscribe/read-only |
| `rt/odommodestate` | 실제 G1 base 위치·IMU 방향·속도. 첫 sample 기준 상대 pose로 사용 | subscribe/read-only |
| `rt/arm_sdk` | Regular Mode를 유지하며 팔 명령을 혼합하는 공식 상체 경로 | Gate 6 승인 시에만 사용, 평소 잠금 |
| `rt/lowcmd` | 전체 저수준 모터 명령 경로 | 이 프로젝트에서는 사용하지 않음 |

Unitree DDS 자체에는 이 프로젝트가 직접 정한 `500x` 포트가 없다. 코드에서는
DDS domain, network interface, topic을 지정하고 CycloneDDS가 통신을 처리한다.

## IP와 주소 표기

| 값 | 의미 |
| --- | --- |
| `192.168.123.99/24` | 노트북/WSL의 G1 전용 Ethernet 주소. `/24`는 `255.255.255.0`과 같음 |
| `127.0.0.1` | 현재 런처가 쓰는 로컬 loopback 목적지 |
| `0.0.0.0` | 해당 포트의 모든 로컬 interface에서 수신한다는 bind 주소 |

`192.168.123.99`는 G1의 IP가 아니라 **우리 PC 쪽 주소**다. G1 내부 주소를
변경하지 않는다. Windows 방화벽 예외는 현재 읽기 전용 수신 포트 `5007`과
`5009`에만 만들어져 있다.

## 실행 파일별 사용 포트

| 실행 파일 | 사용하는 포트/토픽 |
| --- | --- |
| `START_VR_HAND_TO_MUJOCO.bat` | UDP `5005`, `5006`; UDP `5008` safety mirror; G1 연결 시 TCP `5011` 카메라 브리지 |
| `START_G1_GATE7_LIVE_DRY_RUN.bat` | 위 경로 + localhost UDP `5012` Gate 7 Regular 복귀 시각화; 실제 G1 출력 없음 |
| `START_MINK_G1_HARDWARE_SYNC.bat` | UDP `5007`, DDS `rt/lowstate` |
| `START_G1_GATE5_READ_ONLY.bat` | UDP `5007`, DDS `rt/lowstate` |
| `CHECK_G1_TELEOP_STARTUP.bat` | UDP `5007`, DDS `rt/lowstate` |
| `START_G1_GATE7_LIVE_DRY_RUN.bat` | UDP `5008` |
| `TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat` | UDP 계약 `5008 -> 5013` 정적/loopback 검증; DDS/로봇 출력 없음 |
| `TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat` | 실제 UDP `5008 -> 5013`, 가상 LowState, Gate 7 frame/fault lifecycle; DDS 없음 |
| `ANALYZE_G1_GATE7_LATEST_CAPTURE.bat` | 가장 최근 UDP 5008 캡처의 raw IK/Gate 7 품질 JSON+HTML; 네트워크 없음 |
| `VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat` | 가장 최근 캡처의 engage 구간 MuJoCo 반복 재생; 네트워크 없음 |
| `START_G1_GATE7_VR_RECORDING.bat` | UDP `5008 -> 5014`, JSONL 원본 기록, Gate 7 dry-run; DDS 없음 |
| `TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat` | 임시 UDP 기록/재생과 deterministic trace 검증; DDS 없음 |
| `START_G1_GATE7_LIVE_HARDWARE.bat` | UDP `5008`, `5013`, DDS `rt/lowstate`, 잠금 해제 시 `rt/arm_sdk` |
| `TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat` | 저장 자세와 합성 UDP `5008` packet만 사용; 네트워크/DDS 없음 |
| `VIEW_G1_LIVE_MUJOCO.bat` | UDP `5009`, `5010`, DDS `rt/lowstate`, `rt/odommodestate` |
| `VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat` | UDP `5009`, `5010`; G1/DDS 없음 |
| `PREPARE_G1_GATE6_HOLD.bat` | DDS `rt/lowstate`; 출력 준비검사만 수행 |
| `START_G1_CAMERA_TO_UNITY.bat` | DDS `rt/api/videohub/request`, `rt/api/videohub/response`; TCP `5011` |

## 로봇 통신과 무관한 포트

Unity Meta XR DevAgent 설정에는 `48735`, `48736`이 있지만 현재 비활성화되어
있고 G1 텔레오퍼레이션 데이터 경로가 아니다. Meta Quest Link도 이 프로젝트의
`5005~5011` 계약과 별개다.

## 포트 충돌 시

Windows의 `WinError 10048`은 보통 같은 UDP 포트를 다른 프로세스가 이미 듣고
있다는 뜻이다. 같은 역할의 BAT를 중복 실행하지 말고 먼저 기존 창을 닫는다.
