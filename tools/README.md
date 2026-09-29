# Project Tools

`tools/`에는 current integrated runtime과 setup/maintenance에 필요한 파일만 둔다.

## 기본 실행

```bat
START_G1_VR_TELEOP.bat
```

구성:

- bilateral arm worker 60 Hz
- Omni dry-run worker 60 Hz
- observation send 60 Hz / display 100 Hz
- LowState read-only
- front camera 15 fps target
- Unity open/reuse
- no motor output

## Camera

```text
START_G1_CAMERA_TO_UNITY.bat
 -> G1_CAMERA_LAUNCH.py
 -> g1_camera_ssh.py
```

현재 camera transport는 SSH 하나다. WSL fallback은 제거했다.

## Setup

```text
SETUP_G1_VR_TELEOP.bat
SETUP_G1_VR_TELEOP.py
requirements-teleop.txt
g1_teleop_dependencies.py
```

Python 3.11 x64와 `.venv-teleop`을 사용한다.

## Network maintenance

- `CONFIGURE_G1_ETHERNET.bat`
- `CONFIGURE_G1_ETHERNET_ADMIN.ps1`
- `RESTORE_G1_ETHERNET_DHCP.bat`
- `RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1`
- `G1_ETHERNET_DNS.ps1`
- `G1_ETHERNET_TRANSACTION.ps1`

## Unity build

- `RESOLVE_UNITY_EDITOR.bat`
- `BUILD_AND_INSTALL_VR_APK.bat`

## Bimanual utilities

- `START_BIMANUAL_SIM.bat`
- `START_BIMANUAL_UNITY_SIM.bat`
- `REPORT_LATEST_BIMANUAL_SESSION.bat`
- `VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat`

## Observation

- `G1_INPUT_OBSERVATION_LAUNCH.py`
- `G1_INPUT_RECEIVE_AUDIT.py`
- `g1_lowstate_view.py`
- `g1_observation_tap.py`
- `PRINT_G1_INPUTS_50HZ.py`

과거 Gate/MJLab/PD/right-arm trial wrapper는 제거했다.
