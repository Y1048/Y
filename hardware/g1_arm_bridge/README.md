# G1 Runtime Hardware Helpers

이 폴더는 현재 integrated teleop에서 사용하는 **Omni observation/discovery와 joint motion limiting**만 포함한다.

이 폴더의 Omni gateway 자체는 통합 실행에서도 `--dry-run`이며 motor output을 만들지 않는다. `tools/START_G1_VR_TELEOP.bat`의 실제 motor output은 이 폴더가 아니라 별도 onboard GROOT supervisor가 담당한다.

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

PC-side `hardware/g1_arm_bridge`에는 여전히 direct physical arm publisher가 없다. 실제 integrated motor authority는 G1 onboard `/home/unitree/groot_onboard_runtime`의 `groot_balance_actuator --external-controller`에 있으며, Windows launcher는 SSH supervisor 역할만 한다. bilateral IK의 안전/limit contract와 onboard actuator의 실제 hardware authority를 같은 코드 경계로 취급하지 않는다.
