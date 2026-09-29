# G1 Runtime Hardware Helpers

이 폴더는 현재 integrated teleop에서 사용하는 **Omni observation/discovery와 joint motion limiting**만 포함한다.

`tools/START_G1_VR_TELEOP.bat` 기본 경로는 motor output을 만들지 않는다.

## 현재 파일

- `g1_omni_velocity_gateway.py`: Omni Connect WebSocket 입력을 읽고 body-relative velocity observation을 계산한다. 통합 launcher에서는 `--dry-run`으로 실행한다.
- `g1_velocity_discovery.py`: G1 velocity endpoint discovery packet parser/listener.
- `ruckig_joint_motion_limiter.py`: bilateral return/motion shaping에 사용하는 online joint limiter.

## 현재 Omni 정책

- processing: 60 Hz
- initial-yaw-relative heading
- fixed alignment offset
- body-forward / body-lateral projection
- bounded yaw output
- stale/reconnect handling

통합 launcher에서는 이 결과를 motor command로 publish하지 않는다.

## 테스트

```bat
runtime\python\python.exe -B -m unittest discover -s hardware\g1_arm_bridge -p "test_*.py"
```

검증 범위:

- body-frame mapping
- clocked observation
- WebSocket reconnect/timeout
- discovery contract
- Ruckig joint limiter

## Physical control boundary

현재 저장소의 기본 runtime에는 physical arm actuation contract가 없다.
향후 실제 G1 motor control을 추가하려면 bilateral 14-joint contract, collision/limit validation, fault HOLD/return, 별도 authorization을 새로 설계하고 승인받아야 한다.
