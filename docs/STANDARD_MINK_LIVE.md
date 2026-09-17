# Standard Mink 공통 제어 경로

## 목적

Unity 입력과 G1 통신은 유지하고 IK만 교체한다. `vanilla`는 G1에 맞춘
일반 Mink 가중 QP다. upstream 예제 파일을 그대로 실행한다는 뜻은 아니다.
관절 제한, collision pair, 속도 제한, 연동 상태, 출력 검증은 프로젝트 것을 쓴다.

```text
Unity 손목 목표 UDP 5005
  -> 공통 입력/연동/캘리브레이션 루프
  -> --ik-solver vanilla | hierarchical
  -> 공통 경로 검사 + Ruckig 궤적 제한
  -> 관절 목표 UDP 5008
  -> 기존 Gate 7 relay -> WSL 5013 -> rt/arm_sdk
실제 rt/lowstate -> 기존 실측 표시 경로 -> Unity
```

위 물리 흐름은 지원된 live entrypoint에 해당한다. 아래 3.12 로컬 실행기는
`simulation_only` provenance를 사용하므로 물리 릴레이 단계에서 거부된다.

## IK 선택

- `vanilla`: wrist-yaw 링크 위치/회전을 하나의 6D FrameTask로 계산한다.
  PostureTask와 DampingTask는 기존 prototype 비용을 사용한다.
  계층형 2단계 QP, 근위축 assist, local detour는 사용하지 않는다.
- `hierarchical`: 기존 위치 wrist-roll / 회전 wrist-yaw 계층형 방식을 유지한다.
- 두 방식 모두 `Plan(full_qpos, world_goal, position_target)` -> `FeasiblePlan`을
  반환한다. vanilla의 position_target은 wrist-yaw 위치여야 한다.
  engage 기준도 해당 프레임에서 잡으므로 roll/yaw 오프셋을 섞지 않는다.
- 세션 중 변경하지 않는다. 기존 제어기를 종료하고 새 방식으로 engage한다.
  로컬 기본 BAT는 vanilla를 선택한다. Python 직접 실행 기본값과
  hardware-display의 기본값은 기존 hierarchical을 유지한다.

## 실행파일

- `START_VR_HAND_TO_MUJOCO.bat`: 기본 Mink 6D를 사용하는 로컬 기준선.
  비교하려면 `START_VR_HAND_TO_MUJOCO.bat --hierarchical`로 실행한다.
  로컬 공통 루프는 격리된 MuJoCo 3.12를 사용한다. 비용, 속도, 충돌 제약은 유지한다.
- `START_VR_STANDARD_MINK.bat`: 공통 피드백 루프의 vanilla 시뮬레이션.
  이제 격리된 MuJoCo 3.12를 사용한다. G1 카메라 감지와 WSL 실행은 건너뛴다.
  하드웨어 Gate 7 프로세스가 없는 상태에서 로컬 테스트한다.
- `tools/START_G1_GATE7_STANDARD_MINK.bat`: 물리 경로 준비용.
  기존 first-live 프로파일과 명시적 출력 잠금을 그대로 사용한다.
  이번 작업에서 실행하거나 잠금을 해제하지 않았다.
- 기존 `START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat`는 이전 prototype 비교용이다.
  새 공통 루프 버전과 구분한다.

물리 런처는 `--hardware-display`를 유지하여 20/40 mm 프로파일을 선택한다.
로컬 프로파일은 5/10 mm이며 기존 QP 여유 0.5 mm도 유지한다.
vanilla라고 충돌 검사를 생략하지 않는다. 경로 검사 실패 시 HOLD할 수 있으며,
장애물을 전역적으로 우회하는 경로계획기는 아니다.

## 확인 범위

새 테스트는 두 프로파일의 첫 결과와 직접 mink.solve_ik 결과 일치,
경로 거부 시 HOLD, 입력 오류, 기본 IK 선택 유지, 물리 프로파일 잠금을 검사한다.
관련 기존 IK/궤적/피드백 단위 테스트와 import/compile도 확인한다.
VR 착용, WSL/DDS, 실제 G1 출력 검증은 하지 않았다.

MuJoCo 3.11의 알려진 wrist-roll 거리 부호 문제는 해결되지 않았다.
`DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md`를 참고한다. 이 준비만으로
물리 시험 가능 또는 vanilla의 모든 자세 성공을 의미하지 않는다.

## 3.12 로컬 실행

기존 제어기와 Unity Play를 종료한 후 `START_VR_STANDARD_MINK.bat`를 실행한다.
기본 `START_VR_HAND_TO_MUJOCO.bat`도 로컬 공통 루프에서는 3.12를 사용한다.
물리 런처와 이전 prototype 비교 경로의 엔진 선택은 유지한다.
`--mujoco311`은 설치된 기존 엔진으로 비교하는 진단용 선택이다. 알려진 거리
회귀 실패가 있으므로 정상 동작의 기준선으로 사용하지 않는다.

- 엔진 경로: `logs/diagnostics/mujoco_versions/3.12.0`.
- 경로가 없거나 버전이 다르면 중단한다. 전역 설치로 자동 대체하지 않는다.
- 실행 프로세스의 sys.path만 바꾼다. Windows 기본 3.11/WSL 설치는 그대로다.
- 패킷에 `command_provenance=simulation_only`를 지정한다. 기존 Windows
  릴레이와 WSL 하드웨어 검증기가 거부한다. 이 표시는 명령의 진위를 증명하는
  암호학적 인증이 아니라 기존 소프트웨어 경로의 오접속 방지다.
- `--hardware-display`와 함께 선택하면 BAT가 중단한다. Python 실행기도
  `hardware-guarded` 프로파일을 허용하지 않는다.

장비 없이 import만 확인:

```powershell
py -3.11 MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py --validate-only
```

2026-09-06: 기존 설치 3.11에서 거리 회귀 1 failed / 4 passed / 2 subtests.
격리 3.12에서 관련 회귀 38 passed / 3 subtests. BAT 선택 및 standard 검사
38 passed. 두 검사 묶음에는 중복이 있으며 합산하지 않는다.
Windows 전역 설치는 그대로다. Unity Play나 네트워크 제어 루프는 실행하지 않았다.
