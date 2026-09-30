# G1 VR Bimanual Teleoperation

현재 기본 경로는 **Quest/Unity → bilateral Mink/MuJoCo → Omni/LowState/camera observation**이다.
`tools/START_G1_VR_TELEOP.bat`이 사용자 진입점이며 기본 실행은 G1 motor publisher를 만들지 않는다.

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

## 기본 실행

```bat
tools\START_G1_VR_TELEOP.bat
```

검사만:

```bat
tools\START_G1_VR_TELEOP.bat --check-only
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

G1 front camera
  -> Unitree VideoClient JPEG
  -> SSH stdout
  -> g1_camera_ssh.py
  -> TCP 127.0.0.1:5011
  -> Unity PiP on G1 RobotRoot
```

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
- IK tracking rate constant: 1.0 s
- compute/send: 60 Hz
- observation display: 100 Hz

## Camera

현재 target은 **1920×1080 JPEG / 15 fps / 16:9**이다.
`g1_camera_ssh.py`는 JPEG를 재인코딩하지 않고 전달하며 Unity PiP는 1920×1080을 320×180으로 표시한다.

## 외부 dependency

Python dependency는 프로젝트 안에 포함하지만 다음은 외부 환경이다.

- Unity 6000.5.4f1
- Meta Quest/Link 및 드라이버
- Omni Connect
- Windows OpenSSH client
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
