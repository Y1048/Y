# G1 Portable Embedded Python 전환 감사 — 2026-09-29

기준 구현: `2eb8f43 - Bundle portable embedded Python runtime`

## 결론

Windows operator-side Python 환경은 project-local CPython Embedded 3.11.9 x64로 고정되었다.
프로젝트 폴더를 다른 Windows 경로로 복사한 뒤에도 system Python, `py -3.11`,
`.venv-teleop`, runtime `pip install` 없이 startup check가 통과한다.

단, 이것은 Python dependency의 portability 판정이다. Unity, OpenSSH, Quest/ADB,
Omni Connect, G1 network와 G1 robot-side `python3`은 별도 외부 조건이다.

## BAT 전수 감사

embedded runtime 전환 직후에는 11개의 3줄 shim이 있었지만, 사용자 운용과 직접 관련 없는
개발/QA wrapper 7개를 제거했다. 현재 Git이 추적하는 `*.bat`는 아래 4개가 전부다.

| BAT | dispatcher command | 유지 이유 |
| --- | --- | --- |
| `START_G1_VR_TELEOP.bat` | `teleop` | 기본 통합 실행/재실행 |
| `BUILD_AND_INSTALL_VR_APK.bat` | `build-install-apk` | Quest APK 빌드·설치 |
| `CONFIGURE_G1_ETHERNET.bat` | `ethernet-configure` | G1 Ethernet 설정 |
| `RESTORE_G1_ETHERNET_DHCP.bat` | `ethernet-restore` | PC Ethernet DHCP 복구 |

삭제한 wrapper는 camera 단독 실행, bimanual demo/unity simulation, report/replay,
runtime check, Unity path 확인이다. 기능 자체는 `G1_PORTABLE.py` subcommand로 남아 있다.

남은 BAT에는 venv 생성, pip 설치/복구, system `py` 탐색, PowerShell 환경 구성 로직이 없다.
Ethernet BAT도 Python bootstrap은 embedded runtime이며, 실제 관리자 권한 네트워크 변경만
Windows PowerShell helper에 위임한다.

## runtime contract

- interpreter: CPython Embedded 3.11.9 x64
- package pins: 16개 exact version
- package location: `runtime/python/Lib/site-packages`
- identity/integrity: `runtime/python/RUNTIME_MANIFEST.json`
- child Python: embedded `sys.executable` 또는 `g1_embedded_runtime.python_command()`
- failure policy: operator PC에서 pip repair하지 않고 `runtime/python` 전체를 복원

## 2026-09-29 검증

현재 source checkout에서 embedded interpreter만 사용해 실행했다.

- runtime manifest/package probe: PASS, errors 0
- backend regression after BAT cleanup: 214/214 PASS
- hardware Omni/Ruckig regression: 38/38 PASS
- code index check: PASS
- project-owned tracked text의 `C:\Users\...` hardcode: 0건

시스템 Python이 PATH에서 사용되지 않는 조건에서도 다음이 PASS했다.

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py check-runtime --pc-only
tools\START_G1_VR_TELEOP.bat --check-only --host 192.168.123.164
```

별도 `C:\Temp\G1PortableRelocationTest` 복사본에서는 `.git`, `.venv-teleop`,
로그와 Unity cache를 제외하고 프로젝트를 다른 경로로 옮겼다.
그 복사본의 bundled `runtime/python/python.exe`로 위 두 check가 다시 PASS했다.
이 relocation test 임시 폴더는 검증 후 삭제했다.

실제 데스크톱 실행 복사본 `C:\Users\user\Desktop\G1_Teleop_Project`에도
동일 runtime과 핵심 portable source를 복사했고 runtime tree와 reachable Python source의
해시 일치를 확인한 뒤 `START_G1_VR_TELEOP.bat --check-only`가 PASS했다.

## 의도적으로 남는 외부 dependency

- Unity 6000.5.4f1
- Windows OpenSSH client
- Meta Quest/Link 및 APK 설치용 ADB
- Omni Connect
- G1 Ethernet/closed network
- G1 robot-side SSH 명령이 호출하는 `python3`

마지막 항목은 Windows host의 system Python이 아니다. G1 내부에서 read-only observation/camera
helper를 실행하기 위한 robot-side dependency이므로 embedded Windows runtime으로 치환하지 않는다.

## 로컬 legacy venv

source checkout에는 ignored `.venv-teleop`가 남아 있을 수 있다.
이는 현재 runtime에서 읽거나 실행하지 않으며 Git에도 포함되지 않는다.
dirty/untracked 보존 원칙 때문에 자동 삭제하지 않는다.

## 회귀 방지

`backend/tests/test_g1_portable_environment.py`는 남은 4개 BAT의 3줄 embedded shim 계약과
operator runtime source의 machine-local Python 경로 금지를 검사한다.
새 Python dependency가 필요하면 `runtime/python`, requirements pin, manifest를 함께 갱신해야 한다.
