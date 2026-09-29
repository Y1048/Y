# Project Tools

`tools/`의 BAT 파일은 더 이상 실행 로직을 갖지 않는다. 모두 프로젝트에 포함된 CPython Embedded runtime을 호출하는 **3줄짜리 double-click shim**이다.

## Embedded runtime

```text
runtime/python/python.exe
tools/G1_PORTABLE.py
tools/g1_embedded_runtime.py
```

`G1_PORTABLE.py`가 현재 Windows orchestration의 source of truth다.

## 기본 실행

```bat
START_G1_VR_TELEOP.bat
```

내부적으로:

```text
runtime\python\python.exe -I -B tools\G1_PORTABLE.py teleop
```

구성:

- bilateral arm worker 60 Hz
- Omni dry-run worker 60 Hz
- observation send 60 Hz / display 100 Hz
- LowState read-only
- front camera 15 fps target
- Unity open/reuse
- no motor output

## BAT shim -> Python command

| BAT | Python subcommand |
|---|---|
| `START_G1_VR_TELEOP.bat` | `teleop` |
| `START_G1_CAMERA_TO_UNITY.bat` | `camera` |
| `START_BIMANUAL_SIM.bat` | `bimanual-demo` |
| `START_BIMANUAL_UNITY_SIM.bat` | `bimanual-unity` |
| `REPORT_LATEST_BIMANUAL_SESSION.bat` | `report-latest` |
| `VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat` | `verify-latest-quest` |
| `SETUP_G1_VR_TELEOP.bat` | `check-runtime` |
| `RESOLVE_UNITY_EDITOR.bat` | `resolve-unity` |
| `BUILD_AND_INSTALL_VR_APK.bat` | `build-install-apk` |
| `CONFIGURE_G1_ETHERNET.bat` | `ethernet-configure` |
| `RESTORE_G1_ETHERNET_DHCP.bat` | `ethernet-restore` |

## Network administration

`CONFIGURE_G1_ETHERNET_ADMIN.ps1`, `RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1`, `G1_ETHERNET_DNS.ps1`, `G1_ETHERNET_TRANSACTION.ps1`은 Windows 관리자 NetTCPIP/DNS transaction을 위해 유지한다.

이 PowerShell 파일들은 Python dependency가 아니라 Windows 자체 네트워크 관리 API 경계다.

## Runtime policy

- system Python 사용 금지
- `py -3.11` 사용 금지
- `.venv-teleop` 사용 금지
- operator PC에서 pip repair 금지
- bundled runtime 이상 시 `runtime/python` 폴더 전체 복원
