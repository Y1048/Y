# G1 Teleop Code Guide

## Portable entry layer

- `runtime/python/python.exe`: bundled CPython Embedded 3.11.9
- `runtime/python/RUNTIME_MANIFEST.json`: runtime identity/core hashes/package pins
- `tools/G1_PORTABLE.py`: BAT 전체의 Python dispatcher
- `tools/g1_embedded_runtime.py`: project-relative runtime path/identity helper
- `tools/g1_teleop_dependencies.py`: install 없이 bundled runtime 검증
- `tools/START_G1_VR_TELEOP.bat`: 3-line double-click shim

## Integrated launcher

- `tools/G1_VR_TELEOP_LAUNCH.py`: worker/Unity/camera orchestration
- `tools/G1_INPUT_OBSERVATION_LAUNCH.py`: send/receive/Omni/arm worker command
- `tools/g1_quiet_observation.py`: background worker lifetime
- `tools/g1_process_lifetime.py`: process reuse/lifetime helpers

모든 Python child process는 현재 `sys.executable`, 즉 bundled `runtime/python/python.exe`를 이어받는다.

## Bilateral IK

- `g1_bimanual_runtime.py`
- `g1_bimanual_unity_sim.py`
- `g1_bimanual_sim.py`
- `g1_bimanual_motion_policy.py`
- `g1_bimanual_return.py`
- `g1_bimanual_limits.py`
- `g1_mink_shared.py`
- `g1_arm_common.py`

MuJoCo default engine root는 `runtime/python/Lib/site-packages`다.

## Camera

- `tools/G1_CAMERA_LAUNCH.py`
- `tools/g1_camera_ssh.py`
- `tools/START_G1_CAMERA_TO_UNITY.bat`
- `Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs`

camera BAT도 별도 로직 없이 `G1_PORTABLE.py camera`를 호출한다.

## Network administration

- `CONFIGURE_G1_ETHERNET.bat` → `G1_PORTABLE.py ethernet-configure`
- `RESTORE_G1_ETHERNET_DHCP.bat` → `G1_PORTABLE.py ethernet-restore`
- `*_ADMIN.ps1`, `G1_ETHERNET_DNS.ps1`, `G1_ETHERNET_TRANSACTION.ps1`: Windows 관리자 transaction helper

## Runtime policy

1. system Python을 호출하지 않는다.
2. `.venv-teleop`을 사용하지 않는다.
3. operator PC에서 pip install/repair를 하지 않는다.
4. BAT 안에 orchestration 로직을 넣지 않는다.
5. relocation test가 통과해야 portable로 인정한다.
6. physical motor output은 별도 승인 전 추가하지 않는다.
