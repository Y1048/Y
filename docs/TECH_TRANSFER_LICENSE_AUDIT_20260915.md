# 기술이전 준비: IK 라이선스 및 독립 하체 정책 방향

확인일: 2026-09-15. 설치 패키지의 메타데이터·동봉 라이선스와 공식 upstream을
확인했다. 전체 제품의 법률 검토나 배포 적합성 승인은 아니다.

## 설치된 IK 구성

| 구성 | 확인 버전 | 확인 라이선스/검토 사항 |
|---|---|---|
| Mink | 1.3.0 | Apache-2.0 |
| MuJoCo 기본 Python | 3.11.0 | Apache-2.0 및 동봉 third-party 고지 |
| MuJoCo live overlay | 3.12.0 | 동봉 라이선스 원문 별도 보존 |
| qpsolvers | 4.13.0 | LGPLv3; 배포 형태에 따른 준수 검토 필요 |
| DAQP | 0.9.1 | MIT |
| NumPy | 2.4.6 | BSD-3-Clause 등 복합 고지; 원문 보존 |
| SciPy | 1.17.1 | BSD 및 wheel 내 번들 라이브러리 고지; 원문 보존 |
| Ruckig | 0.19.4 | 설치 배포본 MIT 고지 |

`run_mink_g1_right_arm_prototype.py`는 daqp를 우선 선택한다. 실제 실행 중의
solver 선택을 이번 감사에서 계측하지는 않았다. 최신 live launcher는 MuJoCo
3.12.0 overlay를 지정하므로 기본 Python의 3.11.0만 조사하면 누락된다.

`logs/license_audit/20260915_ik/inventory.json`에 8개 배포본의 버전, 요구 의존성,
라이선스 필드, 원본 파일 경로, SHA-256 및 고지 사본 경로를 기록했다.
원문 사본은 같은 폴더의 `notices/`에 있다. 메타데이터에 담긴 모든 의존성을
재귀 감사한 것은 아니다. 라이선스 고지 사본만으로 대응 소스 제공 의무가
충족됐다고 해석하면 안 된다.

재실행 예시(매번 새로운 출력 폴더 사용):

```powershell
py -3.11 -B tools/audit_ik_licenses.py --output logs/license_audit/next_ik --mujoco-overlay logs/diagnostics/mujoco_versions/3.12.0
```

LGPL은 상업 사용 금지가 아니다. 실제 납품 방식에 맞춰 라이브러리 고지,
라이선스 사본, 해당 라이브러리와 수정본의 대응 소스, 사용자 교체/재결합 및
라이브러리 수정 디버깅 권리 등을 검토해야 한다. Python 패키지를 분리해서
배포하는 것만으로 준수가 자동 완료되지는 않는다. 라이브러리를 사용한다는
이유만으로 자체 애플리케이션 전부를 공개해야 한다고 단정해서도 안 된다.

로컬 `OfficialG1/Unitree_LICENSE.txt` 및 `unitree_mujoco/LICENSE`에는 BSD-3-Clause가
있다. 그러나 개별 XML/mesh의 출처, 수정 이력, 데이터 라이선스까지 확인한 것은
아니다. Unity/Meta/Omni SDK, C++ SDK/LibTorch, 정책 가중치도 이번 감사 범위 밖이다.

## 독립 학습 기반 선정

1차 후보는 **Unitree RL Lab + Isaac Lab**이다. 공식 G1 velocity 학습/배포 구성이
있고, 확인한 RL Lab 저장소 LICENCE는 Apache-2.0, Isaac Lab LICENSE는 BSD-3-Clause다.
Isaac Sim 런타임, 로봇 자산, 학습 의존성에는 별도 조건이 있을 수 있다.
이번에는 설치·학습하지 않았으며 로컬/WSL 전체의 설치 여부도 아직 확정하지 않았다.

HOMIE 논문에서 얻은 기능 요구를 우리 코드로 구현하고 처음부터 학습한다.
HOMIE 코드, 설정 파일, 가중치를 복사하거나 변환하여 출처를 지우는 방식을 쓰지 않는다.
이는 독립 구현 방향이며 특허/FTO 검토 완료를 의미하지 않는다.

독립 학습 환경 초안:

- 관측: IMU, 정확한 순서의 전신 q/dq, 이동 명령, 상체 목표, 이전 action과
  필요한 이력. 실제 하드웨어에서 얻지 못하는 상태는 actor 입력에서 제외한다.
- action: 하체 12축. 허리와 상체의 목표 생성 방식은 학습 중부터 실제 운영과
  같게 정의한다. 전신 policy를 학습한 후 팔 출력만 덮어쓰지 않는다.
- 상체 입력: 고정 자세 → 완만한 다양한 자세 → 출처가 확인된 Mink 움직임 순으로
  난이도를 높인다. 팔의 질량·관성과 제한도 로봇 모델에 반영한다.
- 명령: zero, 전후/좌우/회전 및 시작·정지 전환을 포함한다. 모든 축 +/-0.8은
  기존 UI 범위일 뿐, 새 정책의 검증된 동작 범위로 간주하지 않는다.
- 보상/종료: 속도 추종과 함께 자세, 발 미끄러짐, 접촉, 토크, 관절 범위,
  action 변화 및 넘어짐을 고려한다. 가중치는 자체 실험으로 정하고 기록한다.
- 평가: 학습에 사용하지 않은 seed와 팔 궤적을 고정한다. 장시간 zero command,
  시작/정지 반복, 좌우/회전, 팔 뻗기에서 낙상·자세·추종·토크를 비교한다.
  시뮬레이션에서 기준을 미리 정하고 평가한 뒤 실제 적용을 검토한다.

다음 실제 구현 작업은 학습 환경 설치 여부/GPU 확인 및 원본 G1 학습 baseline
재현이다. 이후 위 상체 조건부 12축 task를 별도 구현한다. 새 모델은 아직 없다.

## 확인한 공식 출처

- https://github.com/kevinzakka/mink/blob/main/LICENSE
- https://raw.githubusercontent.com/qpsolvers/qpsolvers/main/LICENSE
- https://raw.githubusercontent.com/unitreerobotics/unitree_rl_lab/main/LICENCE
- https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/LICENSE
- https://github.com/unitreerobotics/unitree_rl_lab
- https://github.com/InternRobotics/Homie (비상업 제한 확인, 구현물 재사용 안 함)

## 검증 범위

- Python 3.11에서 감사 스크립트 실행 성공; 선택한 8개 배포본 누락 없음.
- 수집 파일의 원본/사본 SHA-256 일치 검사를 수행한다.
- SDK/DDS 초기화, G1 접속, 모터 출력, gain/IK/launcher 변경 없음.
- 전체 라이선스 감사, 대응 소스 패키징, 학습/시뮬레이션 검증은 미완료다.
