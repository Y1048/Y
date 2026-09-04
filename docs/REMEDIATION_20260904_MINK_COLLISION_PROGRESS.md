# Rejected Mink collision-boundary progress experiment

## 결론

20/12 mm 분리 실험은 첫 Quest/MuJoCo 시각 시험에서 **기각하고 롤백했다.**
팔 자세가 이상해졌고 최종 상태에서 `torso_link`와
`right_shoulder_yaw_link`의 거리가 12.0018 mm까지 감소했다.

후속 수정에서는 충돌 목표와 후단 검사 거리를 다시 동일하게 유지하되 실행
목적별 프로필을 분리했다. Mink 1.3.0 기본값인 5/10 mm는 로컬 Unity/MuJoCo
실행에 사용하고, Gate 7 물리 후보 경로만 20/40 mm를 강제한다.
실제 출력 어댑터의 12 mm hard stop과 하드웨어 출력 잠금은 변경하지 않았다.

## 검토

생산 시뮬레이션 경로는 vanilla Mink의 `solve_ik -> integrate_inplace` 뒤에
`FeasibleTargetPlanner`의 merit/backtracking/중간 FK 검사를 추가한다. 기존
구현은 QP의 목표 충돌 여유 20 mm와 후단 실행 중단선도 모두 20 mm로 사용했다.
따라서 QP가 충돌면을 따라 우회하려고 만든 유한하고 관절 제한 내의 스텝도
중간 샘플이 20 mm보다 작으면 전부 폐기하고 현재 `q`를 유지했다.

저장된 경계 자세를 사용한 120프레임 재현 결과:

```text
기존 20 mm/20 mm : 이동 1프레임, local_limit 120회, 위치 오차 1.726 cm
분리 20 mm/12 mm : 이동 120프레임, following 120회, 위치 오차 1.188 cm
분리 경로 최소 여유: 19.399 mm
```

## 시험했던 코드 수정

- `CollisionAvoidanceLimit`의 목표 여유는 20 mm로 유지했다.
- `FeasibleTargetPlanner`에 별도의 `validation_clearance_m`을 추가했다.
- 활성 virtual-center 경로는 기존 Gate 7 hard-stop 값인 12 mm를 후단
  비선형 샘플 중단선으로 전달한다.
- 시험 중에는 정책 식별자를 `checked_local_lookahead_v2_split_clearance`로
  구분했지만 롤백 후 v1으로 복구했다.
- 기본 인자를 생략하는 기존 진단은 종전처럼 목표/검증 여유를 동일하게
  사용하므로 호출 계약이 깨지지 않는다.
- G1 출력 허가, Unity, UDP, DDS, WSL, SDK 코드는 변경하지 않았다.

## 테스트

- 변경 Python 4개 파일 `py_compile`: PASS
- 15 mm 후보는 진행하고 11 mm 후보는 거부하는 회귀시험: PASS
- 저장 경계 자세 120프레임 비교: PASS
- 저장 경계 자세 600프레임: 최소 19.399 mm, hard floor 12 mm 미침범

기존 전체 `test_mink_feasible_target`에는 이번 수정과 무관하게 손목 단독
회귀의 proximal excursion 기대값 실패가 남아 있다. 이 실패는 단독 실행에서도
재현되며 이번 clearance 인자의 기본값을 사용하지 않는 경로에서도 동일하다.
`test_mink_step_acceptance_comparison`에도 기존 limit-avoidance detail key 실패가
단독으로 남아 있다. 두 실패를 이번 충돌 경계 수정의 성공으로 숨기지 않는다.

## 후속 프로필 분리

- `START_VR_HAND_TO_MUJOCO.bat`: 로컬 기본은 `mink-default`; 물리 표시
  `--hardware-display`가 들어오면 `hardware-guarded`를 강제한다.
- `START_MUJOCO_ONLY.bat`: `mink-default`를 명시한다.
- 상태 패킷과 runtime status에 프로필명, 최소 거리, 감지 거리를 기록한다.
- 2026-09-04 Quest 시각 시험에서 5/10 mm는 정체를 푸는 대신 최종 오른팔을
  `[0.96, -25.36, 28.88, 5.00, -16.28, 11.94, -6.38] deg`로 이동시켰다.
  충돌 최소거리는 45.04 mm였으므로 이 이상 자세는 충돌 경계가 아니라 현재
  weighted IK의 관절해 선택 문제로 분류한다.

## 남은 항목

- MuJoCo 5/10 mm 실기록 재생과 Quest 시각 시험에서 정체율, 최소 거리,
  팔 자세를 확인한다.
- 후단 검사를 12 mm로만 낮추는 기존 분리 방식은 다시 사용하지 않는다.
- merit 감소 조건과 국소 관절 한계에 의한 `local_limit`도 별도로 구분한다.

## 저장 기록 direct Mink 비교

`quest_motion_20260903_153321_session.jsonl`의 첫 active 구간에 대해 같은
virtual-center task와 속도 제한을 유지하고, 추가 merit/backtracking/중간
샘플 승인을 제거한 `direct_mink_default` 진단을 실행했다. 이는 오프라인
ablation이며 활성 제어기가 아니다.

| 항목 | 현재 20/40 planner | direct Mink 5/10 |
| --- | ---: | ---: |
| 기록 구간 정체 | 1.133 s | 0.017 s |
| 최소 충돌 여유 | 20.001 mm | 13.075 mm |
| 위치 오차 p95 | 17.682 cm | 18.571 cm |
| 회전 오차 p95 | 95.577 deg | 90.774 deg |

direct 방식은 정체를 줄였지만 위치 추종을 개선하지 않았고 12 mm 물리 중단선
근처까지 접근했다. 따라서 활성 경로로 채택하지 않는다. 다음 개선은 충돌
거리만 낮추는 것이 아니라 팔꿈치/어깨 관절 한계에 따른 중복자유도 비용을
명시적으로 설계하고 동일 기록으로 다시 비교해야 한다.

## 폐기한 자동 손목 우선 실험

2026-09-04 손 위치의 프레임간 변화와 손목 회전량으로 자동 모드를 판정하고,
모드 중 목표 위치와 근위 관절 자세를 붙잡는 방식을 시험했다. 첫 Quest 시험에서
일반 팔 동작 중에도 모드가 잘못 유지되어 폐기하고 코드를 제거했다.

- active 구간: 51.08 s
- 팔꿈치: 55 deg에서 5 deg 하한까지 이동
- collision limited: 738 frames
- 위치 오차 p95: 16.19 cm

이 판정기, 목표 위치 latch, wrist-only 상태 필드는 현재 활성 코드에 없다.
손목과 근위 관절의 중복자유도 문제 자체는 미해결이며, 다음 설계는 프레임간
입력 임계값이 아닌 연속 비용 또는 사용자가 명시하는 모드로 검토한다.

## 2026-09-04 재시험에서 확인한 실행 프로필 오류

재시험 직후 runtime status는 `hardware-guarded`, 최소 여유 20.0005 mm,
최근접 쌍 `torso_link`/`right_shoulder_yaw_link`를 기록했다. 이는 vanilla
Mink 5/10 mm 시험이 아니라 기존 PID 35608이 UDP 5005/5012를 계속 점유한
상태였다. BAT은 포트가 이미 사용 중이면 기존 프로세스를 유지하므로 새 설정이
적용되지 않았다. 해당 로컬 MuJoCo 프로세스를 확인 후 종료했고 두 포트가 해제된
것을 검증했다.

## 로컬 접선 진행 복구

5/10 mm 프로필 재시험에서도 마지막 active 자세는 5.0011 mm에서 멈췄다.
최근접 쌍은 `torso_link`와 `right_shoulder_yaw_link`이며 두 body 사이에는
shoulder pitch/roll 링크가 있어 3단계 구조적 이웃이다. 이 쌍은 상완의 실제
몸통 관통을 막기 위해 유지한다.

정지 원인은 Mink QP 뒤의 단조 merit 및 이산 FK 검사였다. 로컬
`mink-default` 경로에 한해 다음 정책을 적용했다.

- QP 최소거리는 5.5 mm로 두어 이산 적분 오차에 0.5 mm 여유를 둔다.
- 후단 실제 configuration 검사는 5.0 mm를 그대로 유지한다.
- 한 프레임 동안 목표 오차가 감소하지 않아도 중간 자세가 모두 안전하면
  충돌면 접선 스텝을 허용한다.
- direct QP가 다시 막히면 오른팔 바깥쪽 8 cm waypoint를 최대 30프레임
  추적하고 원래 operator target을 다시 시도한다. 첫 방향이 막힐 때만
  위쪽/앞쪽 대각선 후보를 순서대로 검사한다.
- 상태 식별자는 `mink_local_detour_checked_v1`이다.
- `hardware-guarded`는 단조 merit 조건과 20/40 mm를 그대로 유지한다.

저장된 마지막 active 자세를 재구성한 단일 스텝 비교에서 기존 경로는
`local_limit`, 0 deg/frame이었고 수정 경로는 3개 look-ahead 스텝을 승인하며
첫 관절 스텝 최대 0.0764 deg, 최소 거리 5.0011 mm를 유지했다. 이는 국소
접선 진행 복구이며 전역 경로 계획이나 목표 도달 보장은 아니다. 아래의 짧은
waypoint로도 해결되지 않는 국소해에는 APF 또는 전역 경로 계층이 추가로 필요하다.

이후 waypoint 계층을 추가한 180프레임 회귀에서는 최소 120프레임 이상
진행하고, 잠시 목표에서 멀어지는 우회 구간 뒤 최종 위치 오차가 시작 오차보다
작아지며 5 mm 검증 바닥을 유지하는 조건을 통과했다. 이 회귀는
`tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat`에서 VR 없이 반복한다.
