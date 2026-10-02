# G1 Teleop Protocol

## 1. Current bilateral input

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
simulation_only = true
UDP         = 127.0.0.1:5020
```

packet은 양손 tracking pose, engage/return flags, base yaw, world diagnostics를 포함한다.

## 2. Validation

backend는 packet size, JSON depth, duplicate key, schema/frame pair, simulation provenance, session/sequence monotonicity, finite pose/base-yaw, tracked flag, peer ownership/freshness를 fail-closed로 검사한다.

## 3. Replay compatibility

저장된 2026-09 bilateral regression fixture는 `g1.bimanual.unity.sim.v1 / legacy_relative` packet을 포함한다. 이 decode path는 회귀 재생용 compatibility boundary다. 새 SampleScene traffic은 v4 world-frame을 사용한다.

## 4. Feedback

backend feedback은 같은 UDP cycle로 Unity에 반환된다. 주요 항목은 backend/session/feedback sequence, state, 14 joint positions, effective IK targets, world diagnostics, base yaw다.

## 5. Timing

- bilateral compute: 60 Hz
- Omni processing: 60 Hz
- observation sender: 60 Hz
- observation display: 100 Hz
- freshness: local monotonic clock

## 6. Omni observation

Omni Connect는 `ws://127.0.0.1:32123`을 사용한다. 통합 launcher에서는 gateway를 `--dry-run`으로 실행한다.

## 7. LowState

LowState는 G1에서 read-only로 읽고 observation/Unity display에 전달한다. 현재 measured-state display port는 `5010/UDP`이다.

## 8. Camera

```text
Insta360 Link 2 Pro
 -> /dev/v4l/by-id/*Insta360*video-index0
 -> UVC MJPEG 1920×1080@30 on G1
 -> SSH stdout (G1CM framing)
 -> PC g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity G1HeadCameraPiP
```

현재 target은 1920×1080 / 30 fps / 16:9이며 G1과 PC 모두 JPEG를 재인코딩하지 않는다. PTZ follower는 `--no-camera-stream`으로 실행되어 영상 device를 소유하지 않는다.

## 9. Compatibility scene wiring

SampleScene에는 과거 5005/5006 component reference 일부가 남아 있다. current bimanual sender가 5005 sender를 비활성화하고 5020 path를 사용한다. 새 코드에서 5005/5006을 current protocol로 사용하지 않는다.

## 10. Motor-output boundary

PC bilateral IK/Omni worker 자체는 계속 observation/simulation-only이며 motor publisher를 만들지 않는다. 다만 `START_G1_VR_TELEOP.bat`의 기본 통합 실행은 별도 역할인 onboard GROOT supervisor를 포함한다. 새 supervisor를 시작할 때 local `ACTUATE` 확인이 필요하고, 이후 G1에서 다음 두 프로세스를 실행한다.

- `g1_omni_heading_controller.py --yaw-sign -1`
- `groot_balance_actuator --normal --enable-actuation --acknowledge-harness --accept-handoff-risk --supervisor-off --external-controller --interface eth0 --duration 300`

`--check-only`에서는 remote login/actuation이 없고, `--no-groot-actuation`은 GROOT supervisor 시작을 생략한다. observation protocol과 motor-output process는 코드/테스트상 분리된 상태를 유지한다.
