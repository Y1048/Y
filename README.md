# G1 VR Bimanual Teleoperation

현재 기본 경로는 **Quest/Unity → bilateral Mink/MuJoCo → Omni/LowState/camera observation + onboard GROOT actuation**이다.
`START_G1_VR_TELEOP.bat`이 사용자 진입점이다. 현재 실기 개발 경로는 **Quest Link hand tracking 지원을 위해 Unity Editor를 자동 실행하고 Play mode도 자동 시작**하므로 사용자가 Editor를 조작하거나 Play를 누를 필요는 없다. 새 GROOT supervisor를 시작할 때 local console에서 `ACTUATE`를 확인한 뒤 onboard heading controller와 external balance actuator를 함께 실행한다. `--no-groot-actuation`은 motor output 없이 Editor/observation 경로를 유지한다. Windows standalone player는 `--standalone` 진단용으로만 남긴다. 최종 제품 경로는 Quest APK가 HMD/양손 tracking을 직접 수행하고 PC Portable로 pose를 전송해 **운영 PC의 Unity Editor 의존성을 제거**하는 것이다.

## Portable Python runtime

프로젝트는 Windows x64용 **CPython Embedded 3.11.9**와 필요한 Python 패키지를 폴더 안에 포함한다.

```text
runtime/python/python.exe
runtime/python/Lib/site-packages/
runtime/python/RUNTIME_MANIFEST.json
```

다른 Windows PC로 옮길 때 시스템 Python 설치, `py -3.11`, venv 생성, `pip install`이 필요하지 않다.
프로젝트 폴더 전체를 복사하면 Python runtime도 같이 이동한다.

남겨둔 사용자용 BAT 4개에는 환경 설정 로직이 없다. 모두 3줄짜리 shim으로 bundled Python의 `tools/G1_PORTABLE.py`를 호출한다.

BAT는 Quest 카메라 pan·tilt 추종기도 자동 시작한다. 실행 순서와 부호 옵션: [실시간 UDP 카메라 안내](docs/QUEST_CAMERA_PAN_TILT_20261001.md).

## 기본 실행

```bat
START_G1_VR_TELEOP.bat
```

검사만:

```bat
START_G1_VR_TELEOP.bat --check-only
```

GROOT actuation 없이 기존 관측/Unity 경로만 실행:

```bat
START_G1_VR_TELEOP.bat --no-groot-actuation
```

bundled runtime 자체 검사:

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py check-runtime --pc-only
```

별도 setup BAT는 유지하지 않는다. 통합 실행 검사는 `START_G1_VR_TELEOP.bat --check-only`,
Python runtime만 검사할 때는 위 dispatcher 명령을 사용한다.

## 현재 데이터 흐름

```text
Quest both hands
  -> Unity G1BimanualSimulationSender
  -> UDP 127.0.0.1:5020
  -> bundled Python g1_bimanual_runtime.py
  -> one bilateral Mink/QP solve for 14 arm joints

Omni Connect ws://127.0.0.1:32123
  -> g1_omni_velocity_gateway.py --dry-run
  -> observation only

G1 LowState
  -> SSH read-only
  -> observation / Unity display

Insta360 Link 2 Pro
  -> G1 UVC video-index0 MJPEG 1920x1080@30
  -> SSH stdout
  -> g1_camera_ssh.py
  -> TCP 127.0.0.1:5011
  -> Unity HMD-follow PiP

Integrated onboard GROOT
  -> SSH unitree@G1
  -> g1_omni_heading_controller.py --yaw-sign -1
  -> groot_balance_actuator --external-controller --interface eth0
  -> 300 s actuation window
```

## Omni 이동 방향 기준각

Omni의 `movementXY`/`armYaw`는 WebSocket으로 PC gateway에 들어온다.
통합 실행은 Unity/Quest initial alignment 전과 alignment heartbeat가 stale인 동안
이동 출력을 **zero-hold**한다. Unity가 초기 HMD 얼라인을 완료하면 그 순간의
raw Omni yaw를 `omni_origin_yaw_deg`로 저장해 UDP 55074 heartbeat에 반복 전송한다.

새 Unity session이 READY가 되면 gateway는 이 캡처값을 yaw origin/offset으로 사용하고
movement bias calibration도 다시 수행한다. 구버전 Unity처럼 origin 필드가 없으면
READY heartbeat를 받은 순간의 현재 Omni yaw로 fallback한다. Quest pitch는
`quest_pitch_deg`로 같은 heartbeat에 전달되지만 locomotion readiness와는 분리된
카메라 PTZ 관측값이다.

## 양팔 IK

왼팔 IK는 오른팔 IK를 단순 반전한 별도 solver가 아니다. 하나의 MuJoCo configuration에서 좌/우 hand task를 만들고 같은 QP로 동시에 푼다.

핵심 파일:

- `MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py`
- `MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py`: packet/state cycle only
- `MuJoCo_G1_Controller/scripts/g1_bimanual_target.py`: current absolute world-frame target mapping
- `MuJoCo_G1_Controller/scripts/g1_bimanual_legacy_input.py`: historical relative-frame filter/mapping only
- `MuJoCo_G1_Controller/scripts/g1_bimanual_profile.py`: read-only effective upper-body tuning profile
- `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py`: bilateral QP orchestration
- `MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py`: soft IK preferences/heuristics
- `MuJoCo_G1_Controller/scripts/g1_bimanual_safety.py`: hard limits, collision bounds, acceleration/braking bounds, checked stop-tail
- `MuJoCo_G1_Controller/scripts/g1_bimanual_return.py`
- `MuJoCo_G1_Controller/scripts/g1_mink_shared.py`
- `MuJoCo_G1_Controller/scripts/g1_arm_common.py`

현재 controller-side profile:

- proximal arm joints: 90 deg/s
- wrist joints: 180 deg/s
- joint acceleration: 90 deg/s²
- IK tracking rate constant: 1.5 s⁻¹
- wrist-rotation proximal damping scale: 14.0
- compute/send: 60 Hz
- observation display: 100 Hz

## Camera

현재 target은 **Insta360 Link 2 Pro / 1920×1080 MJPEG / 30 fps / 16:9**이다.
`g1_camera_ssh.py`는 `/dev/v4l/by-id/*Insta360*video-index0`을 자동 탐색하고
JPEG를 재인코딩하지 않고 기존 G1CM/TCP 5011 경로로 전달한다.
Unity PiP는 HMD에 고정된다. Quest yaw/pitch는 Unity loopback UDP 55075에서 시작하는
카메라 전용 SSH bridge를 통해 G1 loopback UDP 15103의 PTZ follower로 전달된다.
이 경로는 GROOT heading controller/UDP 55070/Omni calibration과 독립이며, follower는
`--no-camera-stream --port 15104 --quest-port 15103`으로 영상 device를 소유하지 않는다.

## 외부 dependency

Python dependency는 프로젝트 안에 포함하지만 다음은 외부 환경이다.

- 현재 Quest Link 양손 실기 경로에는 Unity Editor가 필요하며 launcher가 프로젝트 선언 버전을 자동 탐색한다 (`UNITY_EXE` override 지원)
- `Builds/Windows/G1Teleop.exe`는 HMD/카메라 standalone 진단용이며 Quest Link hand tracking의 기본 경로가 아니다
- 최종 운영 목표는 Quest APK on-device hand/HMD tracking + PC Portable transport로 Unity Editor를 운영 dependency에서 제거하는 것이다
- Meta Quest/Link 및 드라이버
- Omni Connect
- working OpenSSH client: Windows OpenSSH 또는 Git for Windows OpenSSH (`SSH_EXE`로 명시 가능)
- G1 network access
- APK 설치 시 Meta Quest Developer Hub ADB

## 테스트

```bat
runtime\python\python.exe -B -m unittest discover -s backend\tests -p "test_*.py"
runtime\python\python.exe -B -m unittest discover -s hardware\g1_arm_bridge -p "test_*.py"
```

`G1.zip` 전체 오프라인 세션 검증은 다음 명령으로 수행한다.

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py archive-validate "C:\Users\user\Desktop\G1.zip" --strict
```

이 gate는 bimanual exact replay와 함께 Quest/Unity trace, Omni mapper, LowState clock, PC→G1 observation, G1→GROOT telemetry를 교차 검증하며 네트워크나 로봇 명령을 사용하지 않는다.

상세 문서:

- `docs/ARCHITECTURE.md`
- `docs/PROTOCOL.md`
- `docs/CODE_GUIDE.md`
- `docs/CHAT_HANDOFF.md`
- `docs/PORTABLE_TELEOP_SETUP.md`
