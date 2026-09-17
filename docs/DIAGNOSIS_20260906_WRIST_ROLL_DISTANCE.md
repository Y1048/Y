# 손목 roll 거리 부호 불일치

## 검토

`backend/tests/test_virtual_center_kinematics_regression.py`를 다시 실행했다.
결과는 4 passed, 2 subtests passed, 1 failed (wrist_index=4), 13.30초다.
실패는 200 step, 3.35초에서 19.5mm 이상이어야 하는 거리가 -133.205482mm로 계산된 경우다.

충돌 쌍:
- mink_collision_right_shoulder_yaw_link_0_32
- mink_collision_right_wrist_yaw_link_0_36

## 코드 수정

제어기/시험 기준/비용/충돌 거리 수정 없음. 실패를 그대로 유지한다.

## 추가 검사

MuJoCo 3.11.0, 임시 XML, operational joint limits 적용.
기존 `diagnose_mink_distance_invariance.InspectPose`에 아래 qpos와 위 쌍을 전달했다.
뷰어/네트워크/SDK/G1 실행 없이 수행했다.

```json
[-2.6115719829744588e-17,-7.386127300057499e-19,0.78,1.0,7.530592547149907e-17,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,4.423306966596688e-19,-2.1193049717613925e-19,-6.687900009098426e-19,0.17453292519943295,0.3839724354387525,0.0,0.9599310885968813,0.0,0.0,0.0,0.1745427036881762,-0.3837495223593823,-0.0006811409589186536,0.9598789920305901,0.24764952907196308,9.193757257260879e-05,0.0001907919616838155]
```

| 전체 X 이동(m) | raw/guard 거리(mm) | 정점 투영 하한(mm) |
|---|---:|---:|
| 0 | -133.205482 | 130.025710 |
| +1e-12 | +133.205482 | 133.204482 |
| -1e-12 | +133.205482 | 133.204482 |
| +1e-9 | -133.205482 | 130.025710 |
| -1e-9 | -133.205482 | 130.025710 |
| +1e-6 | -133.205482 | 130.025710 |
| -1e-6 | +133.205482 | 133.204482 |

판정: DISTANCE_INCONSISTENT, separation_sign_contradiction=true.
raw/guard span은 모두 0.2664109649150599m다.
이 전체 평행이동은 두 geom의 상대 배치를 바꾸지 않는다.
따라서 이 결과를 곧바로 실제 133mm 관통이라고 해석할 수 없다.
정점 투영 검사는 해당 두 메쉬의 분리 근거이며, 전체 로봇의 안전성이나
움직이는 경로의 충돌 안전 인증은 아니다.

## 남은 항목

### 2026-09-06 확대 호환성 검증

- 검토: 격리 3.12에서 standard IK, 기존 계층형 IK, 거리/충돌, 궤적,
  입력 stream, 분리 모듈 공개 심볼 호환성을 확인했다.
- 코드 수정: 없음. 기본 Python/WSL 설치, IK 비용, 충돌 제한 변경 없음.
- 테스트: 11개 테스트 파일에서 **83 passed / 26 subtests passed** (94.14 s).
  `logs/test_results/mujoco312_expanded_20260906.xml`에 저장.
  비교 도구 6종 입력 각 120프레임 headless 실행 및 960x720 렌더 성공.
  `logs/diagnostics/mujoco_versions/render312.png`를 열어 모델/바닥 렌더를 확인.
  별도 passive viewer 5프레임 실행 후 정상 종료(exit 0).
- 남은 항목: 기본 환경 전환은 하지 않았다. Windows 기본 모듈 경로와
  버전 3.11.0을 재확인했고 Gate 7 프로파일 6개 모두 잠금 상태다.
  이 결과는 3.12 로컬 전환 후보의 근거이며 전체 프로젝트/WSL/VR/실물
  검증은 아니다. WSL 하드웨어 런처는 아직 3.11을 명시적으로 요구한다.

비교 도구의 headless 결과는 20초 입력 주기의 처음 2초만 시험한 값이다.
최종 프레임의 표준 QP 위치 오차는 0.004~0.719 mm, 회전 오차는
0.005~0.065도였다. 전체 작업범위나 최대 오차로 해석하지 않는다.
렌더링 비교 도구는 별도의 direct QP 비교기이며 새 StandardMinkPlanner
전체 실행 루프의 시각 검증을 대신하지 않는다. 새 planner는 위 pytest에서 검증했다.
`logs/ik_visual_comparison/latest.json`은 마지막 viewer smoke 결과로 갱신된다.

### 격리 버전 비교

PyPI wheel을 `--no-deps --target logs/diagnostics/mujoco_versions/<version>`로
설치했다. 기본 site-packages 3.11.0은 변경하지 않았고, 각 버전은 별도
Python 프로세스의 sys.path 앞에만 추가했다. 모듈 경로와 버전을 확인했다.

| 버전/native 기본 옵션 | 7표본 거리 부호 | 판정 |
|---|---|---|
| 3.10.0 | 음수/양수 혼재 | DISTANCE_INCONSISTENT |
| 3.11.0 | 음수/양수 혼재 | DISTANCE_INCONSISTENT |
| 3.12.0 | 모두 +133.205482mm | NO_INCONSISTENCY_OBSERVED |

격리 3.12.0에서 `test_virtual_center_kinematics_regression.py` 실행:
4 passed, 3 subtests passed (5.26 s). 동일 시험 기준이며 threshold 수정 없음.

추가 격리 3.12.0 시험: test_mink_feasible_target, test_mink_collision_diagnostics,
test_mink_virtual_center_trajectory, test_virtual_center_orientation_policy,
test_recorded_reach_bound, test_mink_distance_invariance:
43 passed, 12 subtests passed (36.58 s).

이 fixture와 회귀에서의 결과다. 전체 동작 안전이나 Unity/실물 호환성을
인증하지 않는다. 공식 changelog의 특정 수정 커밋을 원인으로 확정한 것은 아니다.
버전 확인 출처: https://pypi.org/project/mujoco/3.12.0/

재실행 방법: 독립 Python 프로세스에서 아래를 pytest import 전에 실행한다.

```python
sys.path.insert(0, str(Path('logs/diagnostics/mujoco_versions/3.12.0').resolve()))
```

사이트 전역 환경변수나 기본 설치를 변경하지 않는다.

### 2026-09-06 거리 엔진 비교

같은 qpos/메쉬/operational limits에서 임시 모델의 옵션만 바꿔 InspectPose를 실행했다.
기존 파일과 실시간 제어 설정은 변경하지 않았다.

| 옵션 | disableflags | 반복/허용오차 | 7개 이동 표본 |
|---|---:|---|---|
| 현재 native | 0 | 35 / 1e-6 | -133.205482 또는 +133.205482mm |
| native 명시 | 0 | 35 / 1e-6 | 현재와 동일 |
| legacy 비교 | 131072 | 35 / 1e-6 | 모두 +133.205498mm |
| native 정밀도 증가 | 0 | 200 / 1e-9 | 현재와 동일 |

native 세 경로는 DISTANCE_INCONSISTENT, legacy는 NO_INCONSISTENCY_OBSERVED다.
반복 부족이나 이 허용오차 설정만의 문제라는 설명은 이번 결과를 설명하지 못한다.
legacy가 전체적으로 안전하거나 정확하다는 결론은 아니다.

공식 문서의 Geom distance 항목은 MPR 기반 legacy의 일반 거리 계산 한계를 경고한다:
https://mujoco.readthedocs.io/en/latest/computation.html#geom-distance
native/legacy 알고리즘 설명:
https://mujoco.readthedocs.io/en/latest/computation.html#convex-collisions

다음 검증은 동일 fixture의 다른 엔진 버전 또는 최소 재현 모델 비교다.
기존 Python 환경을 직접 업그레이드/다운그레이드하지 않고 격리해서 수행해야 한다.

- 동일 fixture에서 거리 엔진 설정/구현 차이를 격리해 비교할 필요가 있다.
- 현재 모델과 계산 경로에서의 관측이며 MuJoCo 일반 결함으로 단정하지 않는다.
- 양수 결과 선택, abs(distance), 제한 완화로 테스트를 통과시키지 않는다.
- 실시간 계층형 planner와 이 단일 QP probe를 동일한 제어 경로로 간주하지 않는다.
