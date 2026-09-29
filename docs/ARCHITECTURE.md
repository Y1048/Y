# G1 Teleop Architecture

## 1. 원칙

현재 기본 시스템은 **bilateral-only**이다. `tools/START_G1_VR_TELEOP.bat`이 유일한 통합 진입점이며 default path는 motor publisher를 만들지 않는다.

## 2. Launcher

```text
START_G1_VR_TELEOP.bat
  -> g1_teleop_dependencies.py
  -> G1_VR_TELEOP_LAUNCH.py
       -> observation send worker
       -> Omni dry-run worker
       -> bilateral arm simulation worker
       -> LowState read-only worker
       -> camera SSH worker
       -> Unity Editor open/reuse
```

정상 worker가 이미 실행 중이면 재사용하며 다른 host/옵션의 사용자 프로세스를 임의 종료하지 않는다.

## 3. Bilateral backend

`g1_bimanual_runtime.py`가 실행 wrapper다. `g1_bimanual_unity_sim.py`가 UDP 5020 packet과 cycle state를 관리하고 `g1_bimanual_sim.py`가 하나의 MuJoCo configuration에서 좌/우 task를 동시에 푼다.

공용 model/collision/math helper는 `g1_mink_shared.py`와 `g1_arm_common.py`에 있다.

## 4. Motion policy

- 14 arm joints
- proximal velocity 90 deg/s
- wrist velocity 180 deg/s
- acceleration 90 deg/s^2
- jerk limit 1.28 rad/s^3
- compute 60 Hz
- staged return: `g1_bimanual_return.py`

## 5. Unity world-frame contract

현재 SampleScene은 `G1BimanualSimulationSender.useExistingScene = true`이며 다음 packet을 사용한다.

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
port        = 5020
```

저장된 regression fixture 재생을 위해 v1/legacy-relative decode만 호환 경계로 유지한다. 새 runtime traffic은 v4 world-frame이다.

## 6. Omni

`g1_omni_velocity_gateway.py`는 Omni Connect WebSocket을 읽는다. 통합 launcher에서는 `--dry-run`으로 실행되며 motor output이 없다.

## 7. Observation

- arm source: 60 Hz
- Omni processing: 60 Hz
- observation display: 100 Hz
- LowState: read-only
- camera: SSH read-only transport

## 8. Camera

```text
G1 VideoClient
 -> JPEG 1920x1080
 -> SSH stdout
 -> g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> G1HeadCameraPiP
```

현재 target은 15 fps, native 16:9이며 PiP parent는 HMD가 아니라 G1 RobotRoot다.

## 9. Compatibility boundary

SampleScene에는 과거 5005/5006 component wiring 일부가 남아 있다. current bimanual sender는 기존 5005 sender를 비활성화하고 5020 bilateral path를 사용한다. 새 기능의 기준으로 5005/5006을 사용하지 않는다.

## 10. Source of truth

1. `tools/START_G1_VR_TELEOP.bat`
2. `tools/G1_VR_TELEOP_LAUNCH.py`
3. `MuJoCo_G1_Controller/scripts/g1_bimanual_*.py`
4. current backend/hardware regression
5. 이 문서
