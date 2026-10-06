## 2026-10-02 Quest PTZ intermittent 원인 및 분리 수정

기존 PTZ는 `Unity -> Omni gateway -> UDP 55070 -> g1_omni_heading_controller.py -> localhost 15102 -> camera follower`에 의존했다. 따라서 GROOT heading controller가 없는 camera-only/`--no-groot-actuation` 세션, heading controller 시작 전, Omni WebSocket/보정이 준비되지 않은 구간에서는 follower가 살아 있어도 Quest pose `rx=0` 또는 rejection이 되어 카메라가 움직이지 않았다. 이 시작 순서 의존성이 "될 때도 있고 안 될 때도"의 소프트웨어 원인이었다.

수정 후 Unity는 initial HMD alignment 이후 orientation tracked+valid만으로 camera-only schema를 `127.0.0.1:55075`에 20 Hz 전송한다. 위치 tracking이나 Omni readiness는 PTZ에 필요하지 않다. 카메라 pose는 55074 Omni heartbeat와 별도 `UdpClient`를 사용해 camera-only 세션의 닫힌 55074 포트 오류에도 영향받지 않는다. `G1_CAMERA_FOLLOW_LAUNCH.py`가 이를 검증하고 SSH stdin을 통해 G1 `127.0.0.1:15103`으로 전달하며, onboard `receive_mink_ik_udp.py`는 `--camera-follow --pan-sign 1 --no-camera-stream --port 15104 --quest-port 15103`으로 실행된다. 기존 non-camera Mink receiver는 보존/공존하고, manual keyboard PTZ나 다른 camera-follow 옵션은 계속 fail-closed한다. locomotion의 UDP 55070/55074 READY·STALE zero-hold는 변경하지 않았다.

별개로 2026-10-02 16:00:39 G1 kernel에 `uvcvideo: Non-zero status (-75) in video completion handler`가 실제 기록됐다. 따라서 USB/UVC 불안정은 두 번째 독립 원인이며, 기존 Link 2 Pro device rediscovery/set_ctrl retry 로직을 유지한다.

## 2026-10-02 G1 live Insta360 / SSH 검증

G1 closed network `192.168.10.165`에서 실기 확인했다. Insta360 Link 2 Pro는
`/dev/v4l/by-id/...video-index0 -> /dev/video6`, metadata `video-index1 -> /dev/video7`이며
D435i는 `/dev/video0..5`로 분리된다. index0은 1920x1080 MJPEG 30/60 fps를 지원하고
30 fps 설정 실캡처에서 camera-side 약 30.3~31 fps를 확인했다. PTZ receiver는
`--camera-follow --pan-sign 1 --no-camera-stream --dry-run`으로 정상 기동하고 영상 장치를
점유하지 않은 채 Quest 입력 전 `WAIT_ZERO`로 대기한다.

현재 PC의 `C:\Windows\System32\OpenSSH\ssh.exe`는 `ssh -V`도 정상 동작하지 않는
실행 불능 상태였지만 G1/키 문제는 아니었다. `tools/g1_ssh_login.py`가 OpenSSH를 실제
health-check한 뒤 자동 탐색에서 깨진 Windows OpenSSH를 건너뛰고
`C:\Program Files\Git\usr\bin\ssh.exe`를 선택하도록 수정했다. `SSH_EXE`가 있으면
그 경로를 엄격히 사용한다. 현재 자동 선택값으로 G1 key probe PASS, 통합
`--check-only --no-groot-actuation --no-unity` PASS.

카메라 전송 성능은 closed-network Wi-Fi에서 camera 자체 30 fps와 분리해 기록한다.
직접 MJPEG->SSH는 약 27.7 fps, 현 G1CM->SSH->PC 경로는 약 24.6 fps였다. G1 wlan0은
-37 dBm / 1.2 Gbps PHY였고 eth0은 1 Gbps Full Duplex link-up이지만, PC Realtek Ethernet은
당시 Disconnected였다. 따라서 정확한 30 fps end-to-end 검증은 유선 `192.168.123.164`
경로 연결 후 다시 측정한다. 15 fps 이상이라는 기존 최소 체감 목표는 현재 무선에서도 넘는다.

## 2026-10-01 BAT 카메라 추종 자동 시작

기본 BAT의 launcher가 camera_follow worker도 시작한다. Ubuntu 수신부는
--camera-follow --pan-sign 1 --no-camera-stream 옵션이다. Insta360 Link 2 Pro 영상은
별도 camera worker가 /dev/v4l/by-id/*Insta360*video-index0을 단독 소유해 1920x1080
MJPEG 30 fps를 재인코딩 없이 기존 G1CM/TCP 5011로 보낸다. Unity PiP는 HMD-follow다.
동일한 원격 프로세스는 재사용, 다른 옵션/수동 키보드는 보존하고 오류 표시.
SSH stdin 종료 시 이번에 생성한 카메라 자식만 정리한다. 로봇/GROOT 동작은 변경 없음.
--check-only는 기존대로 실행 없이 계획 검사. 2026-10-02 실기에서 Insta360 discovery/capture, PTZ dry-run, SSH transport 및 통합 check-only까지 검증함.

## 2026-10-01 Quest 카메라 pan/tilt 실시간 UDP

압축 대기 시간 이후 Windows HMD pitch heartbeat와 gateway passthrough를 추가.
위쪽 양수 elevation → quest_pitch_deg → unity_quest_pitch_deg. 기존 yaw/이동/팔
계산은 유지. Ubuntu receive_mink_ik_udp.py는 별도로 pan/tilt 구현 및 테스트 완료.
BAT의 위임 경로 launcher에 실행 명령을 표시하며 자동으로 카메라 추종을 시작하지 않는다.
실행 순서는 docs/QUEST_CAMERA_PAN_TILT_20261001.md 참조. Unity/gateway 재시작 필요.

# G1 Teleop Current Handoff

최종 갱신: 2026-10-02

## 현재 실행

```bat
START_G1_VR_TELEOP.bat
```

BAT는 bundled `runtime/python/python.exe`로 `tools/G1_PORTABLE.py teleop`을 호출하는 3줄짜리 shim이다.

일반 실행은 기존 PC/Unity/camera worker와 함께 onboard GROOT pair도 통합한다. 새 GROOT supervisor를 시작할 때만 local console에서 `ACTUATE` 확인을 요구하며, 이후 사용자가 별도 SSH 창 두 개를 열 필요는 없다.

2026-10-01 실제 G1 로그에서 첫 통합 버전의 원격 실행 실패 원인을 확인했다. 기존 launcher가 `ssh -T`와 remote background child를 사용해 두 프로그램 모두 interactive-terminal 검사에서 종료됐다: actuator는 `walk keyboard requires an interactive terminal`, heading controller는 `controller requires an interactive terminal`이었다. Portable Python 자체의 문제가 아니다.

현재 contract는 예전에 성공했던 수동 SSH 2개 구조를 자동화한다.

```text
SSH/PTTY A (-tt), foreground:
  cd ~/groot_onboard_runtime
  python3 -u tools/g1_omni_heading_controller.py --yaw-sign -1

SSH/PTTY B (-tt), foreground:
  cd ~/groot_onboard_runtime
  ./build/groot_balance_actuator --normal --enable-actuation --acknowledge-harness --accept-handoff-risk --supervisor-off --external-controller --interface eth0 <duration-mode>
```

각 remote process는 통합 세션 owner ID로 태그된다. 정상 종료는 main manager 또는 GROOT console에서 **Enter**를 눌러 요청한다. supervisor가 자신이 시작한 actuator에 먼저 SIGINT를 보내고 controlled damping 완료를 최대 12초 기다린 뒤 heading controller에 SIGINT를 보낸다. 정상 종료를 위해 창의 X 버튼으로 강제 종료하지 않는다.

Actuator duration은 remote binary capability를 자동 검사한다. `--unlimited-duration`을 지원하면 무제한을 사용하고, 아직 지원하지 않으면 현재 binary 호환을 위해 `--duration 300`으로 fail-compatible 동작한다. G1 onboard source용 패치는 `tools/GROOT_ONBOARD_UNLIMITED_DURATION.patch`에 있다. 이 패치는 NORMAL 모드에만 unlimited를 추가하며 signal/emergency damping은 유지한다.

`--check-only`은 remote login/actuation을 하지 않는다. 기존 observation-only 동작이 필요하면 `START_G1_VR_TELEOP.bat --no-groot-actuation`을 사용한다. exact existing remote process는 보존하고 다른 옵션/duplicate는 자동 종료하지 않고 fail closed한다.

## Portable Python

- CPython Embedded 3.11.9 x64 bundled
- exact 16 package pins bundled
- no system Python
- no `py -3.11`
- no `.venv-teleop`
- no runtime pip repair
- `RUNTIME_MANIFEST.json`으로 base/core/package contract 검증

다른 Windows PC로 옮길 때 프로젝트 폴더 전체를 복사하면 Python 환경도 같이 이동해야 한다.

## Bilateral IK

- 14 arm joints
- one MuJoCo configuration
- left/right tasks solved in the same QP
- proximal 90 deg/s
- wrist 180 deg/s
- acceleration 90 deg/s²
- IK tracking rate 1.5 s⁻¹
- wrist-rotation proximal damping scale 14.0; 1.5 tracking의 translation 응답성을 유지하면서 bilateral wrist-dominance motion-quality gate를 복구
- compute 60 Hz

## Camera

```text
Insta360 Link 2 Pro UVC MJPEG
1920x1080 / 30 fps target
stable by-id video-index0 auto-discovery
PiP parent = HMD CenterEyeAnchor
PTZ follower uses --no-camera-stream
SSH transport only
```

## Regression gates

- backend current regression
- hardware Omni/Ruckig regression
- `G1.zip --replay --strict` exact replay
- portable relocation check from a different directory
- 남은 사용자용 BAT 4개 전수 embedded-shim 감사
- operator runtime source의 machine-local Python 경로 금지

2026-09-29 전체 archive validator 추가 후 재검증: backend 219/219 PASS, hardware 38/38 PASS,
code index PASS, no-system-Python startup check PASS. Backend 회귀는 `.git` 없는 export에서도 실행 가능하다. `G1.zip`은 bimanual exact replay뿐 아니라 Quest/Unity, Omni, LowState, PC→G1 observation, G1→GROOT까지 전체 offline strict validation PASS했다.
상세 근거: `docs/G1_ARCHIVE_FULL_OFFLINE_VALIDATION_20260929.md`.

2026-09-30 R1a 재검증: backend 223/223 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` PASS, bimanual exact replay state/reason/accepted mismatch 0, max q difference `2.00062189037453e-13 rad`. 변경 C# 3개는 Roslyn syntax error 0. Unity batch validator는 코드 오류가 아니라 기존 Package Manager IPC startup failure로 실행 전 종료되었고, 오래된 `.csproj` 직접 build는 이미 삭제된 과거 C# 파일 4개를 참조해 유효한 semantic compile gate가 아니다.

2026-09-30 R1c 재검증: backend 226/226 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` exact PASS, accepted/state/reason mismatch 0, max q difference `2.00062189037453e-13 rad`. `g1_bimanual_safety.py`가 hard geometry clearance, Mink collision bound, acceleration/joint-limit/yaw braking bounds와 checked stop-tail을 소유한다. `g1_bimanual_sim.py`에는 기존 테스트/진단 호환용 `limits`, `clearance()`, `checked_stop_plan()` proxy/alias만 남긴다.

## External dependencies

Unity Editor, working OpenSSH, Quest tooling/driver, Omni Connect, G1 network는 외부 dependency다. Unity launcher는 하드코딩된 버전 상수 대신 `Unity_G1_VR/ProjectSettings/ProjectVersion.txt`의 `m_EditorVersion`을 자동 탐색하며 `UNITY_EXE` override를 지원한다. OpenSSH는 Windows/Git 구현을 health-check해 선택하며 `SSH_EXE` override를 지원한다. Python package dependency만 project-local로 완전히 고정한다.

## Upper-body simplification discussion

상체 제어 구조를 수정하거나 gain/limit를 재튜닝하기 전에 `docs/G1_UPPER_BODY_CONTROL_SIMPLIFICATION_AUDIT_20260929.md`를 먼저 읽는다. 2026-09-30 R1a에서 dead Python members를 제거하고, current `unity_display_world_v1` target mapping을 `g1_bimanual_target.py`, historical relative input을 `g1_bimanual_legacy_input.py`, 현재 tuning을 `g1_bimanual_profile.py`로 분리했다. R1b에서는 dormant right-arm sender/preview 분기를 제거했고, R1c에서는 hard safety 계산을 `BimanualSafetyEnvelope`로 이동했다. 이후 heuristic ablation을 완료했다. torso target projection은 연속 입력에서 약 296 mm hidden target jump를 만들면서 hard safety와 역할이 중복되어 제거했다. elbow assist, wrist priority, shoulder comfort, dynamic orientation priority는 제거 시 posture/clearance/braking 또는 joint allocation이 악화되어 유지한다. shoulder-yaw envelope는 ordinary trajectory 영향은 없었지만 independent fallback이라 SafetyEnvelope 안에 유지한다. 실제 replay profile에서는 QP solver 자체보다 checked stop-tail/geometry 검증이 지배적인 계산비용이다. 다음 단계는 gain 재튜닝이 아니라 safety hot path를 하나씩 offline ablation하는 것이다. checked stop-tail은 마지막 안전 gate로 유지한 상태에서 앞단의 겹치는 constraint가 실제로 무엇을 추가하는지 측정한다. Safety ablation에서는 collision stopping-headroom과 joint-limit stopping bound 제거를 REJECT했고, MuJoCo 3.11-era zero-distance QP witness repair는 current 3.12 runtime에서 G1.zip/5,000 synthetic posture 모두 0 activation이며 제거 후 exact replay PASS라 제거를 ACCEPT했다.

## 작업 원칙

1. BAT는 shim 외 로직 금지.
2. 새 Python dependency가 필요하면 bundled runtime과 manifest를 같이 갱신.
3. 기존 dirty/untracked를 reset/clean하지 않는다.
4. 변경 후 embedded runtime에서 회귀 실행.
5. relocation test 없이 portable 완료로 판정하지 않는다.
