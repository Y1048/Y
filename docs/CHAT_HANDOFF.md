# G1 Teleop Current Handoff

최종 갱신: 2026-09-29

## 현재 실행

```bat
tools\START_G1_VR_TELEOP.bat
```

BAT는 bundled `runtime/python/python.exe`로 `tools/G1_PORTABLE.py teleop`을 호출하는 3줄짜리 shim이다.

## Portable Python

- CPython Embedded 3.11.9 x64 bundled
- exact 16 package pins bundled
- no system Python
- no `py -3.11`
- no `.venv-teleop`
- no runtime pip repair
- `RUNTIME_MANIFEST.json`으로 base/core/package contract 검증

다른 Windows PC로 옮길 때 프로젝트 폴더 전체를 복사하면 Python 환경도 같이 이동해야 한다.

## Bilateral IK

- 14 arm joints
- one MuJoCo configuration
- left/right tasks solved in the same QP
- proximal 90 deg/s
- wrist 180 deg/s
- acceleration 90 deg/s²
- compute 60 Hz

## Camera

```text
1920x1080 JPEG
15 fps target
16:9 PiP
PiP parent = G1 RobotRoot
SSH transport only
```

## Regression gates

- backend current regression
- hardware Omni/Ruckig regression
- `G1.zip --replay --strict` exact replay
- portable relocation check from a different directory
- 남은 사용자용 BAT 4개 전수 embedded-shim 감사
- operator runtime source의 machine-local Python 경로 금지

2026-09-29 portable 정리 후 재검증: backend 213/213 PASS, hardware 38/38 PASS,
code index PASS, no-system-Python startup check PASS. Backend 회귀는 `.git` 없는 export에서도 실행 가능하다.
상세 근거: `docs/PORTABLE_EMBEDDED_PYTHON_AUDIT_20260929.md`.

## External dependencies

Unity 6000.5.4f1, OpenSSH, Quest tooling/driver, Omni Connect, G1 network는 외부 dependency다. Python package dependency만 project-local로 완전히 고정한다.

## 작업 원칙

1. BAT는 shim 외 로직 금지.
2. 새 Python dependency가 필요하면 bundled runtime과 manifest를 같이 갱신.
3. 기존 dirty/untracked를 reset/clean하지 않는다.
4. 변경 후 embedded runtime에서 회귀 실행.
5. relocation test 없이 portable 완료로 판정하지 않는다.
