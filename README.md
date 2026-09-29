# G1 VR Bimanual Teleoperation

현재 기본 경로는 **Quest/Unity → 양팔 Mink/MuJoCo → Omni/LowState/camera observation**이다.
`tools/START_G1_VR_TELEOP.bat`이 통합 진입점이며 기본 실행은 G1 motor publisher를 만들지 않는다.

## 기본 실행

```bat
tools\START_G1_VR_TELEOP.bat
```

검사만 하려면:

```bat
tools\START_G1_VR_TELEOP.bat --check-only
```

새 PC 설치는 [docs/PORTABLE_TELEOP_SETUP.md](docs/PORTABLE_TELEOP_SETUP.md)를 따른다.

## 현재 데이터 흐름

```text
Quest both hands
  -> Unity G1BimanualSimulationSender
  -> UDP 127.0.0.1:5020
  -> g1_bimanual_runtime.py
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
  -> tools/g1_camera_ssh.py
  -> TCP 127.0.0.1:5011
  -> Unity PiP on G1 RobotRoot
```

## 양팔 IK

왼팔 IK는 오른팔 IK를 단순 반전한 별도 solver가 아니다. 하나의 MuJoCo configuration에서 좌/우 hand task를 만들고 같은 QP로 동시에 푼다.

핵심 파일:

- `MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py`
- `MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py`
- `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py`
- `MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py`
- `MuJoCo_G1_Controller/scripts/g1_bimanual_return.py`
- `MuJoCo_G1_Controller/scripts/g1_mink_shared.py`
- `MuJoCo_G1_Controller/scripts/g1_arm_common.py`

현재 controller-side profile:

- proximal arm joints: 90 deg/s
- wrist joints: 180 deg/s
- joint acceleration: 90 deg/s^2
- IK tracking rate constant: 1.0 s
- compute/send: 60 Hz
- observation display: 100 Hz

## Camera

현재 실제 실행 target은 **1920×1080 JPEG / 15 fps / 16:9**이다.
`g1_camera_ssh.py`는 JPEG를 재인코딩하지 않고 전달하며 Unity PiP는 1920×1080을 320×180으로 표시한다.

30 fps 실험은 G1 `videohub_pc4`의 임시 `/tmp` 복사본으로만 수행했다. stock service는 변경하지 않았다.

## 현재 포트

| 포트 | 용도 |
|---|---|
| 5020/UDP | Unity bilateral input / backend feedback |
| 55071/UDP | observation tap |
| 5011/TCP | G1 camera -> Unity PiP |
| 32123/WebSocket | Omni Connect |
| 5010/UDP | read-only G1 state display |

`5005/5006` 호환 wiring 일부는 기존 SampleScene/replay 경계 때문에 남아 있으나 기본 bilateral runtime에는 사용하지 않는다.

## 검증

```bat
.venv-teleop\Scripts\python.exe -B -m unittest discover -s backend\tests -p "test_*.py"
.venv-teleop\Scripts\python.exe -B -m unittest discover -s hardware\g1_arm_bridge -p "test_*.py"
```

`G1.zip` 실제 세션은 `g1_bimanual_session_report.py --replay --strict`로 재현 가능해야 한다.

상세 문서:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PROTOCOL.md](docs/PROTOCOL.md)
- [docs/CODE_GUIDE.md](docs/CODE_GUIDE.md)
- [docs/CHAT_HANDOFF.md](docs/CHAT_HANDOFF.md)
- [docs/OMNI_WORLD_UPPER_BODY_20260922.md](docs/OMNI_WORLD_UPPER_BODY_20260922.md)
- [docs/PORTABLE_TELEOP_SETUP.md](docs/PORTABLE_TELEOP_SETUP.md)
