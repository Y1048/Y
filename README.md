# G1 Quest 3S Teleoperation

Quest 3S의 오른손 hand tracking 데이터를 Unity에서 받아 UDP로 전송하고,
MuJoCo의 G1 29DoF 오른팔 IK를 구동하는 프로젝트다.

## 바로 실행

1. Meta Horizon Link에서 Quest Link를 연결한다.
2. 프로젝트 루트의 `START_VR_HAND_TO_MUJOCO.bat`을 실행한다.
3. 열린 Unity에서 `Assets/Scenes/SampleScene`을 확인하고 Play를 누른다.
4. Quest에서 청록색 손목 마커를 흰색 시작점에 맞춘 채 약 0.55초 유지한다.
5. 마커가 초록색으로 바뀌면 오른손 이동과 회전이 MuJoCo에 전달된다.

메인 실행 파일:

```text
C:\Users\user\Desktop\G1_Teleop_Project\START_VR_HAND_TO_MUJOCO.bat
```

## 폴더 구조

| 경로 | 용도 |
| --- | --- |
| `Unity_G1_Quest3S` | Quest 3S hand tracking과 VR 표시를 담당하는 Unity 6000.5.4f1 프로젝트 |
| `MuJoCo_G1_Controller` | G1 모델, 오른팔 UDP IK, 테스트 데이터와 Unitree MuJoCo 참고 코드 |
| `backend` | 카메라 프레임, 좌표 변환, 캘리브레이션, watchdog 공통 Python 모듈 |
| `config` | 시뮬레이션 및 실제 D435i 전환 설정 |
| `tools` | 빌드, 진단, 가짜 입력, 카메라 검증용 보조 실행 파일 |
| `docs` | 설계 및 카메라 전환 문서 |
| `logs/camera` | 카메라 검증 이미지와 JSON 결과 |
| `logs/unity` | Unity 컴파일 및 APK 빌드 로그 |
| `archive` | 현재 주 경로에서 사용하지 않는 이전 실행 파일과 임시 메모 |

## 보조 도구

| 실행 파일 | 용도 |
| --- | --- |
| `tools/TEST_FAKE_VR_TO_MUJOCO.bat` | Quest 없이 가짜 오른손 좌표를 UDP로 전송 |
| `tools/BUILD_AND_INSTALL_QUEST3S_APK.bat` | Quest용 APK 빌드 후 연결된 기기에 설치 |
| `tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat` | 카메라 변환, 프레임, 공유메모리 경로 자동 검증 |
| `tools/START_HEAD_CAMERA_SIMULATION.bat` | MuJoCo G1 머리 카메라 시뮬레이션 실행 |
| `tools/CAPTURE_HEAD_CAMERA_PREVIEW.bat` | 머리 카메라 검증 화면을 BMP로 저장 |

카메라 구성은 `docs/CAMERA_SIMULATION_GUIDE.md`에 정리되어 있다.

## 현재 데이터 흐름

```text
Quest 3S right wrist tracking
-> Unity calibration and target mapping
-> UDP JSON 127.0.0.1:5005
-> MuJoCo G1 right-arm position/orientation IK
```

MuJoCo에서는 손목 베이스 위치와 손 자세를 분리해 푼다. 위치는 어깨/팔꿈치 4축,
자세는 손목 3축이 담당하며, 몸통 안전영역과 접촉 기반 스텝 거부를 적용한다.

## 파일 관리 규칙

- 평소 실행은 루트의 `START_VR_HAND_TO_MUJOCO.bat`만 사용한다.
- 새 진단용 BAT는 `tools`에 둔다.
- 실행 결과는 각각 `logs/camera` 또는 `logs/unity`에 둔다.
- Unity의 `Library`, `Temp`, `Logs`, `obj`는 Unity가 관리하는 캐시이므로 직접 작업 파일을 넣지 않는다.
- `archive`의 파일은 현재 실행 경로가 아니며, 필요성이 확인되기 전까지 보관만 한다.
