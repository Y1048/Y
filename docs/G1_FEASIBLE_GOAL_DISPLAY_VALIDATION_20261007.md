# 양팔 초록 구의 IK 진행 목표 표시 — 2026-10-07

기준 커밋: `92042cd`. 미커밋된 goal-preview 초안은 evidence의 `before/`에 보존했다.
실측을 매 tracking tick에 넣는 폐루프 변경은 포함하지 않는다.

기존 초록 구가 사용하던 `checked_stop_target_poses()`는 현재 속도에서 감속해
정지하는 끝점이었으며, 사용자 목표 방향으로 진행 가능한 IK 위치와 달랐다.
표시 경로만 교체하고 실제 IK·송신·안전 검사·PD·모델 관절범위는 보존한다.

## 의미와 계산 경로

초록 구는 사용자 손 목표를 향해 현재 양팔 IK가 제약 안에서 진행할 수 있는
짧은 경로의 앞쪽 손목 위치다. 현재 명령 자세를 복사한 별도 프로세스에서
동일한 양팔 QP, motion policy, joint/velocity/acceleration/collision constraints,
checked-stop 검사를 60 Hz 기준 3틱 진행하고 마지막 자세의 FK를 표시한다.

실제 다음 관절 명령은 기존 live `UnityCycle`/`BimanualSimulation`에서 계속
생성한다. 예측 결과를 실제 명령으로 사용하거나, live state에 되돌려 쓰지 않는다.
요청 손 목표가 바뀌면 실제 제어기와 표시 예측 모두 새 목표를 기준으로 재계산한다.

이는 과거 `FeasibleTargetPlanner`의 **목표 방향의 검증된 look-ahead FK**라는
표시 의미를 복원하는 것이다. 과거 오른팔 solver/trajectory를 재사용하는 것이
아니며, 전체 workspace의 최단/최대 도달 해를 구하는 것도 아니다. 3틱의 국소
예측이므로 빠르게 움직이는 중에는 파란 손 목표와 일치하지 않을 수 있다.
검증된 braking prefix가 선택되면 상태를 `checked_braking_prefix`로 구분한다.
실제 G1의 도달·추종·물리적 충돌 안전성을 이 표시로 증명하지 않는다.

## 서로 다른 다섯 위치

| 위치 | 데이터 | 의미 |
|---|---|---|
| 사용자 requested hand goal | input `raw_json_text`의 양손 `position_m`/`quaternion_wxyz` | 사용자 입력 원본 |
| 현재 command FK | feedback `left/right_actual_wrist_world_m` | PC 명령 자세의 FK. 필드 이름의 `actual`은 LowState 실측을 의미하지 않음 |
| checked-stop endpoint | `left/right_checked_target_world_m` | 내부 감속 정지 경로의 끝점. 초록 구에서 사용하지 않음 |
| feasible/look-ahead display target | `goal_preview.left/right_world_m`와 `*_world_wxyz` | 별도 상태에서 검증한 짧은 진행 경로의 FK. 초록 구 표시용 |
| 실제 LowState wrist | measured-tracking 로그의 실측 모델 wrist FK | 실측 29관절을 Unity 모델에 적용한 손목 위치 |

`left/right_ik_target_world_m`은 solver에 전달된 effective hand goal이며,
검증된 도달 위치와 동일하다고 주장하지 않는다. 위의 원본 요청과 함께 유지한다.

## 표시 수명과 계산 비용

- 실제 IK/명령 생성은 기존 **60 Hz**. 표시 예측의 작업 제출 상한만 **10 Hz**.
- 자식 process 1개, 진행 중인 job 1개, backlog 없음. command publication 후 snapshot 제출.
- 모델/geometry/constant buffers는 자식에서 한 번 만들고 private state만 전달한다.
- Windows 자식만 idle priority와 한 개의 허용 logical CPU를 사용한다.
  부모 IK/Unity/다른 프로세스의 priority나 affinity는 변경하지 않는다.
- 결과 수명은 **생성 시점 기준 최대 200 ms**. 반복 송신으로 수명을 갱신하지 않는다.
  이 값은 표시 전용이며, 입력 timeout/LowState freshness/control safety를 변경하지 않는다.
- revision/session/backend 변경, tracking 종료, 잘못된 결과, 만료 시 숨긴다.
  raw goal이나 stop endpoint로 몰래 대체하지 않는다.
- Python과 Unity 모두 schema, 수치, quaternion, horizon, source sequence를 검증한다.
  예측 실패는 표시만 비활성화하며 실제 command state를 수정하지 않는다.
- 공통 Omni yaw는 표시 시 현재 frame으로 변환한다. frozen body posture와 measured-start
  revision은 예측 context에 포함되며, tracking 중 LowState reseed를 추가하지 않는다.

## 검증과 한계

evidence: `logs/test_results/goal_preview_revision_20261007/`.

기록 입력은 기존 operator 세션 `unity_20261007_141835_479784.jsonl`이다.
그 입력을 현재 software controller에 재생한 결과이며, 새 명령에 대한 실제 G1
응답을 측정한 데이터가 아니다. synthetic near/far/retract tests도 실제 로봇 시험이 아니다.

30/20 Hz 및 CPU 배치 후보에서 기록한 불리한 결과는 그대로 보존한다.
CPU 배치만으로 성능 개선이 반복 확인되지 않았으므로, 선택한 표시 cadence는 10 Hz다.
Windows의 시간 변동을 고려해 예측을 끈 앞뒤 replay와 비교하며, 결과는 PC와 해당
기록에 한정한다. 새 Quest 표시 사용감과 다른 PC의 timing은 별도로 확인해야 한다.

수학 재생 검사에서 tracking sample 645개 모두 원본 live 관절 명령과 차이
`0 rad`, 별도 상태에서 직접 3틱 계산한 FK와 차이 `0 m`였다. 부모 solver의
동적 상태는 변경되지 않았고, preview를 포함한 feedback의 최대 크기는
4,085 bytes로 기존 8,192-byte 수신 buffer 안에 있었다.

최종 10 Hz 후보의 앞뒤 baseline 비교 (`final_10hz_confirmation.json`):

| 항목 | 예측 끈 앞 baseline | 10 Hz preview | 예측 끈 뒤 baseline |
|---|---:|---:|---:|
| loop work p95 (ms) | 12.785 | 13.050 | 12.362 |
| loop work max (ms) | 17.788 | 18.240 | 17.536 |
| scheduler lateness p95 (ms) | 0.524 | 0.530 | 0.533 |
| live q 최대 차이 (rad) | 0 | 0 | 0 |

snapshot 비용 p95/max는 0.808/0.970 ms, marker 생성 age p95/max는
126.373/172.991 ms였다. eligible 645틱 중 644틱에 marker가 유효했고, 첫
worker 결과 이전 1틱은 숨겼다. 상태 전이는 원본과 같으며 최종 READY다.
별도 10 Hz 실행에서도 명령 차이 0, state match, 644/645 유효 결과를 확인했다.
baseline도 최대 16.7 ms를 넘으므로 모든 60 Hz deadline 보장을 주장하지 않는다.

실행 결과는 다음과 같다.

- bundled Python의 `unittest discover -s backend/tests -p test_*.py`: **344/344 PASS**.
- `unittest discover -s hardware/g1_arm_bridge -p test_*.py`: **44/44 PASS**.
  네트워크/SSH fixture는 mock이며 실제 G1 접속이 아니다.
- Unity **6000.5.4f1 edit-mode**: 신규 goal preview **24 checks**, 기존 measured display
  **155 checks**, measured start **17 checks** 모두 PASS. Play/sockets는 시작하지 않았다.
- 실제 spawn worker, 부모 affinity/priority 보존, snapshot state 격리, 잘못된 결과·NaN,
  revision 변경, 재송신에 의한 age 갱신 거부, stale 숨김을 포함한다.
- `build_code_index.py --check`와 task-scoped `git diff --check` PASS.
- 기존 solver/safety/return/measured-start/measured-view/local settings의 hash 대조 PASS.
  `DevAgentSettings.asset`의 기존 dirty 변경은 수정·stage·commit하지 않는다.

Portable 반영은 Play 정지 사용자 답변 후 대상 13파일만 backup/hash 대조하여
완료했다. Portable에서 신규 predictor 테스트 **23/23 PASS**도 확인했다.
Quest 표시 사용감·실제 G1 응답은 미검증이며 controller의 continuous
measured feedback, physical actuation, SSH, gain 변경은 이번에 실행하지 않았다.

## 다음 별도 단계

실제 관절과 명령 관절의 추종오차·지연을 계측한 뒤, 명령의 속도/가속도 연속성과
감속 경로를 유지하는 measured-feedback 설계를 결정한다. 이번 표시 변경으로
PC IK가 continuous measured-state closed loop가 되었다고 해석하지 않는다.
