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
G1 VideoClient.GetImageSample()
 -> JPEG
 -> SSH stdout
 -> PC g1_camera_ssh.py
 -> TCP 127.0.0.1:5011
 -> Unity G1HeadCameraPiP
```

현재 target은 1920×1080 / 15 fps / 16:9이며 JPEG는 PC에서 재인코딩하지 않는다.

## 9. Compatibility scene wiring

SampleScene에는 과거 5005/5006 component reference 일부가 남아 있다. current bimanual sender가 5005 sender를 비활성화하고 5020 path를 사용한다. 새 코드에서 5005/5006을 current protocol로 사용하지 않는다.

## 10. Motor-output boundary

`START_G1_VR_TELEOP.bat`은 motor publisher를 만들지 않는다. physical bilateral motor control은 별도 승인과 별도 contract가 필요하다.
