# G1 Teleop Architecture

## 1. Runtime boundary

현재 기본 시스템은 bilateral-only다. Python 실행 환경은 project-local CPython Embedded runtime에 고정된다.

```text
tools/START_G1_VR_TELEOP.bat
  -> runtime/python/python.exe
  -> tools/G1_PORTABLE.py teleop
  -> tools/g1_teleop_dependencies.py
  -> tools/G1_VR_TELEOP_LAUNCH.py
       -> observation send worker
       -> Omni dry-run worker
       -> bilateral arm simulation worker
       -> LowState read-only worker
       -> camera SSH worker
       -> Unity Editor open/reuse
```

system Python, venv, pip repair는 operator runtime에 사용하지 않는다.

## 2. BAT policy

남겨둔 사용자용 BAT 4개는 3줄짜리 compatibility/double-click shim이다. BAT 내부에 Python 탐색, dependency 설치, 날짜 생성, child BAT chaining, Unity resolution 같은 로직을 두지 않는다.

실제 Windows orchestration의 source of truth는 `tools/G1_PORTABLE.py`다.

## 3. Embedded runtime

- CPython Embedded 3.11.9 x64
- exact packages: `tools/requirements-teleop.txt`
- installed packages: `runtime/python/Lib/site-packages`
- manifest/core hashes: `runtime/python/RUNTIME_MANIFEST.json`
- isolated path config: `runtime/python/python311._pth`

runtime 검증 실패 시 PC에서 pip install로 수리하지 않는다. 정상 `runtime/python` 폴더를 복원한다.

## 4. Bilateral backend

`g1_bimanual_runtime.py`가 실행 wrapper다. MuJoCo 기본 package root도 `runtime/python/Lib/site-packages`로 고정된다.
`g1_bimanual_unity_sim.py`가 UDP 5020 packet과 state cycle을 관리하고, `g1_bimanual_sim.py`가 하나의 configuration에서 좌/우 task를 동시에 푼다.

## 5. Motion policy

- 14 arm joints
- proximal velocity 90 deg/s
- wrist velocity 180 deg/s
- acceleration 90 deg/s²
- jerk limit 1.28 rad/s³
- compute 60 Hz
- staged return: `g1_bimanual_return.py`

## 6. Unity world-frame contract

current SampleScene:

```text
schema      = g1.bimanual.unity.sim.v4
input_frame = unity_display_world_v1
port        = 5020
```

저장된 regression fixture 재생을 위해 v1/legacy-relative decode만 compatibility boundary로 유지한다.

## 7. Omni / observation / camera

- Omni Connect: `ws://127.0.0.1:32123`, default `--dry-run`
- observation sender: 60 Hz
- observation display: 100 Hz
- LowState: read-only
- camera: G1 VideoClient → SSH → TCP 5011 → Unity PiP

## 8. Windows-native external boundaries

Embedded Python으로 해결하지 않는 항목:

- Unity installation
- OpenSSH executable
- Quest/ADB/driver
- Omni Connect process
- privileged Windows NetTCPIP/DNS administration

Ethernet 관리자 변경은 Embedded Python dispatcher가 UAC elevation을 요청하고 기존 PowerShell transaction helper를 호출한다.

## 9. Portability gate

원래 checkout이 아닌 별도 경로로 프로젝트를 복사한 뒤에도:

```bat
tools\START_G1_VR_TELEOP.bat --check-only
```

가 system Python/venv 없이 PASS해야 한다.
