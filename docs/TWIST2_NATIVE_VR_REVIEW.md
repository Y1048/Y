# 네이티브 VR 통합 초안 — 실행 전 검토용

## 우선순위 정정

기존 `twist2_right_arm_trial.cpp`에는 이미 네이티브 정책, SDK LowState 수신,
단일 rt/lowcmd writer, MotionSwitcher ReleaseMode와 damping 처리가 있다.
이를 새로 만드는 대신 별도 `twist2_vr_native_draft.cpp`에 VR 입력을 연결했다.
원본 물리 C++와 기존 CMake는 변경하지 않았다. 이 초안은 Ubuntu WSL x86_64에서
SDK/Torch 컴파일·링크를 완료했다. 제어 바이너리는 실행하지 않았고 G1 대상 빌드와
배포/실제 시험 준비 완료가 아니다.

## 이번에 연결한 부분

- `native_vr_udp.hpp`: 명시된 bind IPv4/port에서 UDP를 받고 지정 source IPv4만
  허용한다. SO_REUSEADDR를 사용하지 않는다. 최대64개 batch, 초과/수신 오류는 중단.
- `native_vr_policy_adapter.hpp`: 기존 JSON 검증/FIFO/0.08rad/s 목표 로직 재사용.
  blend 뒤 이전 정책 목표와 측정 q 오차0.025rad, 속도0.1rad/s 이내1초를 요구한다.
  초기 오른팔 정렬0.025rad, 시작 상대10도, 상체 추종 오차0.25rad를 검사한다.
  값은 기존 오프라인 실험 기준이며 로봇 승인값은 아니다.
- 기존 네이티브 policy loop의 키보드 처리 대신 UDP와 VR target을 사용한다.
  `hybrid_target`이 하체0..11 정책과 상체 목표를 합친다. 허리/왼팔은 capture 유지.
- 기존 SDK writer에서 VR watchdog도 호출한다. pinch는 계획된 damping tail,
  오류/timeout은 기존 오류 damping 경로로 연결했다. 둘 다 AI 자동 복귀가 아니다.
- `native_vr_build/CMakeLists.txt`: 기존 reference의 SDK/Torch 빌드 설정을 사용하며
  새 초안 target만 구성한다. 원본 물리 실행파일을 덮어쓰지 않는다.

환경변수 `G1_VR_BIND_IPV4`, `G1_VR_SOURCE_IPV4`, `G1_VR_UDP_PORT`,
`G1_VR_RELAY_TOKEN`은 필수다. token은 기존 relay의 `--relay-token`과 일치하는
16..128 ASCII 영숫자다. 네이티브 입구에서 live_mink 및 token을 검사하고
simulation_only/recorded_replay/replay-session을 거부한다.
현재 네트워크 값이나 Windows 송신 목적지를 추측해서 설정하지 않았다.
Windows shadow의 loopback5008을 그대로 G1 수신 주소로 취급해서는 안 된다.
IP 제한은 암호학적 인증이 아니므로 배포 네트워크 검토가 필요하다.

2026-09-08 후속: 기존 relay 직렬화와 C++ 검사 호환성은 메모리 sink로 확인했다.
저장 Quest는 simulation_only이므로 실제 중계 입력으로 사용할 수 없다. 별도 합성
live fixture가 검사를 통과했으며 실제 네트워크/장비 시험은 아니다. native 콘솔은
vr_wait_tracking / vr_ready / vr_active로 구분한다. ready 후 engage하며 ready 취소도
반영한다. owner pytest7개 및 WSL 재빌드 성공. 최신 ELF SHA256은
ec356caef23b0adc908ddb1c0c689f35d368a6f8166996b656c27c4b0a413bd6.
아래 WSL 최초 빌드 해시는 이력이며 최신 소스와 다르다.

## 지금 확인된 것과 아직 필요한 것

Windows MSVC /W4 /WX로 입력 어댑터를 빌드하고 early engage 거부, 초기 정렬
거부,22번만0.08rad/s 갱신, 다른 축 보존, pinch 및 writer-side timeout을 검증했다.
owner 관련6개 pytest 통과. 후속 WSL x86_64 통합 빌드는 완료했고 실제 송수신은 미검증이다.

사용자가 WSL 환경 확인과 컴파일을 승인하여 빌드만 진행했다. 장비를 사용할 수
있을 때에는 대상 SDK/Torch/아키텍처, 실제 송신자/모드/신선한 LowState와
Windows→G1 입력 목적지를 먼저 확인한다. WSL의 ELF를 G1용으로 간주하지 않는다.

실제 실행 전에 반드시 검토할 핵심:

1. 기존 Controller는 생성자에서 publisher를 초기화한다. 실행 자체가 publisher
   생성을 포함하므로 검토만 하려면 바이너리를 실행하지 않는다.
2. ReleaseMode 실패/응답 유실은 UNKNOWN으로 명시하고 VR loop/active 진입을
   차단한다. 자동 재시도나 별도 damping publisher는 만들지 않는다. 실제 로봇의
   모드가 복구됐다는 의미는 아니며, 대상 장비에서 인계 실패 대응을 확인해야 한다.
3. native 경로의 기존50Hz 정책/45ms 추론 제한/60ms command watchdog을 그대로
   두었다. Windows harness의10ms 기한 실패를 이 경로의 해결 증거로 쓰지 않는다.
4. 초안 writer는 rate/joint/torque 교집합을 사용하도록 수정했다. 한 축에서라도
   교집합이 없으면 전체35슬롯을 damping으로 다시 작성하고 이전 목표를 보존한다.
   stop latch와 최종 Write를 같은 recursive mutex로 직렬화한다. 이미 시작한
   SDK Write를 취소하는 기능은 아니며, SDK Write 블로킹과 최대 중단 지연은 미측정이다.
5. 종료는 damping이며 AI 자세 유지로의 복귀는 구현하지 않았다. 실제 정지와
   이후 제어권 인계를 확인하기 전에는 복귀 완료로 보고하지 않는다.

이번 우선순위는 이 한 개 네이티브 통합 경로의 빌드·검토다. Windows CPU 재시험이나
새 합성 시나리오는 위 연결부의 구체적인 문제를 해결할 때만 추가한다.

후속 검증: native_command_limits.hpp를 MSVC /W4 /WX로 빌드해 rate/torque
충돌2종, 정상 rate 제한, 잘못된 gain 거부를 확인했다. owner 관련6개 pytest 통과.
이 결과는 SDK를 포함한 전체 초안 빌드를 대체하지 않는다. 저장된 과거 WSL inventory는
Python SDK만 확인했고 당시 확인 경로에는 C++ 헤더가 없었다. 현재 설치 상태를
재확인한 결과 시스템에 CMake/Torch/C++ SDK가 없었다. 승인 범위에서 별도 로컬
환경을 구성해 아래 빌드를 완료했다.

## WSL 빌드 결과

- Ubuntu26.04 x86_64, GNU15.2.0, CMake4.4.3/Ninja1.13.2,
  전용 Python3.12.14 venv의 Torch2.10.0+cpu, C++11 ABI=1.
- [Unitree 공식 SDK](https://github.com/unitreerobotics/unitree_sdk2)의 commit
  `9754cd153af3da471b0fe5f3aa535e426fb11db3`를 별도 폴더에 clone했다.
  SDK 예제나 라이브러리의 DDS 초기화 코드는 실행하지 않았다.
- 전용 환경 `/home/user/.venvs/twist2-vr-build`, SDK/build 폴더
  `/home/user/twist2-vr-build-20260907`. 기존 Python 환경/시스템 패키지는 변경하지 않았다.
- 빌드 성공 후 `file`/`readelf`로만 ELF와 의존성을 확인했다. 제어 바이너리 미실행.
  SHA256 `82e5e55b39cd83840b1cc645e4afb6c7db39629cb7e079edbd519c4c9073cf33`.
- 경고200건: 대부분 SDK/Torch/DDS, 기존 twist2_common.hpp의 ignored-attributes1건.
  Torch의 maybe-uninitialized 경고도 포함한다. 경고를 삭제하거나 런타임 무해함을
  증명한 것은 아니다. 컴파일/링크 성공과 실제 동작 검증을 구분한다.
- 증거: `logs/test_results/twist2_native_wsl_build_20260907.log` 및 같은 이름의 `.json`.
  JSON에는 SDK commit, 주요 소스 해시, ELF 해시와 실행하지 않은 범위를 기록했다.
