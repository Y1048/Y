# Project Tools

`tools/`에는 실제 사용자 운용에 필요한 BAT 4개만 남긴다. 모두 프로젝트에 포함된 CPython Embedded runtime을 호출하는 **3줄짜리 double-click shim**이다.

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

## 남겨둔 BAT shim

| BAT | Python subcommand | 용도 |
|---|---|---|
| `START_G1_VR_TELEOP.bat` | `teleop` | 기본 통합 실행/재실행 |
| `BUILD_AND_INSTALL_VR_APK.bat` | `build-install-apk` | Quest APK 빌드·설치 |
| `CONFIGURE_G1_ETHERNET.bat` | `ethernet-configure` | G1 Ethernet 설정 |
| `RESTORE_G1_ETHERNET_DHCP.bat` | `ethernet-restore` | PC Ethernet DHCP 복구 |

camera 단독 실행, bimanual demo, report/replay, runtime check, Unity path 확인은
일상 사용자 진입점이 아니므로 별도 BAT를 두지 않는다. 필요한 경우
`runtime\python\python.exe -I -B tools\G1_PORTABLE.py <subcommand>`를 직접 사용한다.

전체 캡처 archive의 오프라인 회귀는 `archive-validate` subcommand를 사용한다.

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py archive-validate "C:\Users\user\Desktop\G1.zip" --strict
```

## Network administration

`CONFIGURE_G1_ETHERNET_ADMIN.ps1`, `RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1`, `G1_ETHERNET_DNS.ps1`, `G1_ETHERNET_TRANSACTION.ps1`은 Windows 관리자 NetTCPIP/DNS transaction을 위해 유지한다.

이 PowerShell 파일들은 Python dependency가 아니라 Windows 자체 네트워크 관리 API 경계다.

## Runtime policy

- system Python 사용 금지
- `py -3.11` 사용 금지
- `.venv-teleop` 사용 금지
- operator PC에서 pip repair 금지
- bundled runtime 이상 시 `runtime/python` 폴더 전체 복원
