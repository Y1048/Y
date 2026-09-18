# Windows 실행기 설치 경로 이식성 — 2026-09-18

기준: `Y1048/Y`, `codex/g1-laptop-sync-20260917`, 출발 커밋 `5844d2d`.
사용자가 데스크톱 Codex의 Unity 설치 경로 문제를 전달했다. 이전 인계의
“별도 데스크톱 작업 없음”은 그때의 이력이며, 이번 사용자 보고보다 우선하지 않는다.
이번 소스 수정과 검증은 연결된 노트북에서 했다. 별도 데스크톱의 설치·실행을
이 세션에서 직접 확인한 것은 아니다.

## Unity 검색 순서

공통 `tools/RESOLVE_UNITY_EDITOR.bat`는 실행 파일의 존재 여부만 검사한다.
Unity나 Hub를 실행하거나 레지스트리/설치 환경을 변경하지 않는다.

1. 호출 전에 설정된 **존재하는 파일** `UNITY_EXE`.
2. `%ProgramFiles%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe`.
3. `%USERPROFILE%\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe`.
4. 어느 곳에도 파일이 없으면 실패한다. 일반 실행은 기존 오류 분기로 간다.

존재하지 않는 override나 `Unity.exe`라는 이름의 폴더는 무시하고 다음 후보를
검사한다. 기본 탐색 버전은 계속 `6000.5.4f1`이다. 다른 설치 버전을 자동으로
선택하지 않는다. 명시적 `UNITY_EXE`는 사용자가 지정한 위치를 존중한다.
이 검사는 바이너리 진위·내부 버전·라이선스·설치 모듈의 검증이 아니다.

공통 탐색을 연결한 실행기:

| 파일 | 변경 |
| --- | --- |
| `START_VR_HAND_TO_MUJOCO.bat` | 요청 대상; 환경변수 우선 및 두 Hub 위치 탐색 |
| `tools/BUILD_AND_INSTALL_VR_APK.bat` | 요청 대상; 동일 탐색 |
| `tools/TEST_CAMERA_REPLAY_TO_UNITY.bat` | 같은 고정 Unity 경로 제거 |
| `tools/TEST_G1_MINK_FK_PARITY.bat` | 같은 고정 Unity 경로 제거 |

네 BAT 모두 첫 인수 `--check-unity-path`를 지원한다. 경로와 선택 출처만 출력하고
즉시 종료한다. Python/WSL/네트워크 검사, 빌드 ID 생성, 로그 폴더 생성, Unity,
카메라, G1/DDS, APK 빌드·설치 또는 `adb devices`에 도달하지 않는다.
성공 종료 코드는 0, 찾지 못한 경우는 1이다. 이 모드에서는 pause도 하지 않는다.
기존 `--check`는 이런 최소 경로 검사 모드가 아니므로 혼동하지 않는다.

## 함께 수정한 하드코딩

- APK 실행기의 `ADB_EXE`: 기존 환경변수는 보존한다. 미설정 시
  `%ProgramFiles%\Meta Quest Developer Hub\resources\bin\adb.exe`를 사용한다.
  다른 MQDH/Android SDK 위치는 `ADB_EXE`로 명시한다.
- `tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat`,
  `tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat`,
  `experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1`: `VCVARS64` override를
  지원한다. 기본은 `%ProgramFiles%` 아래의 기존 Visual Studio 18 Community
  `VC/Auxiliary/Build/vcvars64.bat`다. 버전·에디션을 자동 변경하지 않는다.
- `START_MUJOCO_ONLY.bat`: 특정 노트북 사용자 폴더를 요구하던 안내문을 실제
  `%PROJECT_ROOT%`로 바꿨다. 실행 로직은 변경하지 않았다.

루트 BAT, `tools`의 BAT/CMD/PowerShell, 위 실험 디렉터리의 Windows 실행기에서
고정 `C:\Users\...` / `C:\Program Files\...` 형태가 재등장하지 않도록 검사한다.
과거 로그·검증 기록·마이그레이션 문서의 실제 경로는 증거이므로 치환하지 않았다.
로봇 주소, 안전 한계, 고정 SDK 프로토콜 값, IK·복귀 동작도 변경하지 않았다.

## 데스크톱에서 받기와 경로 검사

기준 브랜치의 작업본이 깨끗한지 먼저 확인한다. 미커밋 작업이 있으면 보존·대조한
뒤 통합하며 reset/clean이나 강제 덮어쓰기를 사용하지 않는다. 원격 변경을 받을 때는
두 BAT만 복사하지 말고 **공통 resolver도 함께** 받는다.

```powershell
# 기준 브랜치이고 작업본이 깨끗한 경우
 git fetch origin
 git pull --ff-only origin codex/g1-laptop-sync-20260917

# 아래 두 명령은 경로만 검사하고 종료한다.
 .\START_VR_HAND_TO_MUJOCO.bat --check-unity-path
 .\tools\BUILD_AND_INSTALL_VR_APK.bat --check-unity-path

# 별도 설치 위치를 명시하는 예시; 실제 존재하는 경로로 지정한다.
 $env:UNITY_EXE = 'D:\Unity Editors\6000.5.4f1\Editor\Unity.exe'
 .\START_VR_HAND_TO_MUJOCO.bat --check-unity-path
```

CMD에서는 `set "UNITY_EXE=D:\Unity Editors\6000.5.4f1\Editor\Unity.exe"`처럼
설정한다. 변수 값 자체에 바깥 따옴표를 넣지 않는다.

## 수행한 오프라인 검증

`backend/tests/test_windows_tool_paths.py`: **21/21 PASS**.
복사한 실제 네 BAT의 경로 전용 분기를 Windows cmd.exe로 실행했다. 가짜 설치
파일은 실행 가능한 바이너리가 아니며, Unity·adb·컴파일러를 실행하지 않았다.
환경변수 우선, ProgramFiles 우선, 사용자 설치, 잘못된 override fallback,
전부 없음, 다른 버전 무시, 파일 대신 폴더, 공백·한글·특수문자와 delayed expansion을
검사했다. ADB/VCVARS64는 실제 소스에서 경로 대입 구문만 추출해 검사했고,
PowerShell 파일은 전체 구문 분석과 경로 선택 부분만 실행했다.

관련 기존 `test_unity_display_mode_launcher.py`: **2/2 PASS**.
이는 임시 복사본에 대한 표시 설정 검사이며 실제 프로젝트 표시 모드를 바꾸지 않는다.
노트북의 실제 네 BAT도 `--check-unity-path`로만 실행해 모두 종료 코드 0을 확인했다.
ProgramFiles 설치가 선택됐다. 사용자 설치 fallback은 임시 폴더에서 검증했다.

초기 테스트 작성 중 Python의 cmd.exe 인용 방식 때문에 테스트 복사본을 못 찾는
실패가 있었다. 테스트 호출의 인용을 수정한 뒤 위 최종 검사를 통과했다. 초기 실패를
통과 횟수에 합산하지 않는다.

검증 기록은 [결과 JSON](validation/windows_tool_paths_20260918/verification.json),
[새 경로 테스트](validation/windows_tool_paths_20260918/path_tests.txt),
[관련 기존 테스트](validation/windows_tool_paths_20260918/related_tests.txt)에 있다.
실제 Unity 실행/빌드·Quest 설치·로봇/DDS·C++ 컴파일은 수행하지 않았다.
양팔 68개 테스트는 이 경로 수정에서 재실행하지 않았다. 해당 제어 소스는 변경하지 않았다.
이번 수정은 Git 소스에 반영하며 별도 노트북 실행 폴더나 데스크톱 파일을 직접 덮어쓰지 않는다.
