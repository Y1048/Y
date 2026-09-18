# 양팔 초기자세 복귀: 기존 단계와 속도 프로파일 복원

기준 브랜치: `codex/g1-laptop-sync-20260917`. 출발 커밋: `b692d2a`.
같은 노트북의 소스 작업본과 바탕화면 실행 폴더에서 작업했다.
실제 G1 제어, DDS/SSH, Unity 씬/C# 변경 또는 사용자 Play 조작은 하지 않았다.

## 사용자 피드백과 확인한 원인

사용자가 경계 보강 버전을 실행한 뒤 초기자세 복귀 방식과 속도가 이전과 다르다고
보고했다. 최신 로그 `unity_20260918_130929_6784747.jsonl`의 첫 행에서
`bimanual_motion_v1`, `bimanual_boundary_v1`, MuJoCo 3.12.0과 설치 코드 해시를 확인했다.

기존 단일 오른팔은 `SimulationReturnCycle`의 **중간 자세 → 초기자세 → 0.5초 정착**을
따랐고, `RuckigJointMotionLimiter`로 속도/가속도/jerk를 제한했다. 반면 양팔은
`PostureTask(gain=.01)`로 초기자세에 직접 접근했다. 추종 동작 보정을 복원하면서
이 복귀 방식까지 보존한 것은 아니었다.

직전 경계 보강은 속도 상한을 낮추지 않았다. 그 수정은 마지막에 0속도를 출력한
뒤 READY가 되도록 바꾼 것이며, 느린 복귀의 주원인은 이미 달라져 있던 복귀 경로다.
최신 로그의 복귀는 실제 기록 시각으로 11.156초와 10.250초였다. 마지막 2초의
최대 관절속도도 약 0.23도/s로 매우 느렸다. 이를 새 실행의 사용감으로 혼동하지 않는다.

## 변경한 복귀 경로

`g1_bimanual_return.py`의 `BimanualReturnMotion`을 추가했다. 추종은 기존의
공동 14축 QP와 `ArmMotionPolicy`를 유지하고, **복귀만** 기존 Ruckig 단계로 연결한다.
복귀 중에는 두 손목 IK 목표를 해결하는 대신 14개 관절의 단계별 궤적을 생성한다.

오른팔 중간 자세는 기존 `SAFE_RIGHT_ARM_RAD`를 직접 사용한다.
왼팔은 같은 관절 기준으로 미러링한다.

```text
순서: shoulder_pitch, shoulder_roll, shoulder_yaw, elbow,
      wrist_roll, wrist_pitch, wrist_yaw
오른팔 중간 자세 (deg): [10, -35, 0, 70, 0, 0, 0]
왼팔 중간 자세 (deg):   [10,  35, 0, 70, 0, 0, 0]

현재 자세/속도/가속도에서 시작
  → 양팔 중간 자세
  → 양팔 초기자세
  → 0속도 출력 및 0.5초 정착
  → READY
```

| 항목 | 사용한 값 |
| --- | --- |
| 어깨/팔꿈치 속도 상한 | 90도/s, 변경 없음 |
| 손목 속도 상한 | 180도/s, 변경 없음 |
| 가속도 상한 | 60도/s², 변경 없음 |
| 정상 복귀 jerk 프로파일 | 기존 `JOINT_MAX_JERK_RAD_S3` = 1.28 rad/s³ |
| 초기자세 정착 | 0속도에서 0.5초 |

기존 limiter의 관절별 독립 시간 진행을 그대로 쓴다. 다만 중간 자세에서 다음 단계로
넘어갈 때는 양팔 모두 도착해야 하므로, 비대칭 양팔 동작의 전체 시간이 단일 오른팔과
항상 같다고 보장하지 않는다. 새로 속도 상한을 올려서 빠르게 만든 것이 아니다.

## 유지한 검사와 실패 처리

`clearance()`와 `checked_stop_plan()` 본문은 변경하지 않았다. Ruckig의 각 후보는
동일한 양팔/몸통 geometry 및 관절/속도/가속도 검사를 포함한 정지 tail 검사를 통과한
경우에만 출력한다. 출력 위치 차분/주기와 내부 속도가 일치하도록, Ruckig의 순간
끝점 속도와 별도로 실제 출력 구간의 평균 속도를 사용한다.

새 후보가 부적합하면 현재 검사된 tail로 감속하고 정지 후 해당 단계 재계획을 시도한다.
반복 실패 또는 30초의 시뮬레이션 진행 한도에서는 감속 후 명시적으로 BLOCKED가 된다.
시간 한도는 시뮬레이션 tick 기준이며 호스트 지연을 포함한 wall-clock 보증이 아니다.
잘못된 waypoint, 비정상 궤적 값, 생성기 RuntimeError, 충돌 경로 거부도 별도로 검사했다.

이 보호 감속 경로는 기존 가속도 제한 tail이며 정상 Ruckig 궤적과 동일한 jerk 보증을
주장하지 않는다. 고정된 기구학 장면의 sampled clearance 검사다. 움직이는 외부 장애물,
연속시간 무충돌, 모든 시작 자세의 복귀 가능성이나 실제 로봇 제동을 보증하지 않는다.

## 검증 결과

소스 작업본과 노트북 실행 폴더에서 각각 **68/68 PASS**를 확인했다.
기존 58개에 복귀 프로파일, waypoint/home의 오른팔 기준 궤적 비교, 출력 연속성,
완료 후 중복 복귀 방지, 재engage, 예외/충돌/timeout의 감속 후 fault 등 10개를 추가했다.
두 자유 공간 단계는 기존 오른팔 limiter의 관절값과 매 tick `1e-8 rad` 허용오차로 비교했다.
이를 모든 자세의 전체 궤적이 단일팔과 동일하다는 주장으로 확대하지 않는다.

최신 로그에서 잘라낸 두 복귀 시작 상태를 사용한 비교다. 양쪽 열 모두
**동일한 dt=1/60초 기준의 시뮬레이션 시간**으로 비교한다.

| 기록의 복귀 원인 | 수정 전 | 수정 후 | 수정 후 최소 clearance |
| --- | ---: | ---: | ---: |
| 추적 손실 | 10.733초 | 5.933초 | 40.37mm |
| pinch | 9.833초 | 5.350초 | 39.14mm |

두 경우 모두 경로 재시도 없이 waypoint와 home을 거쳤다. 최대 출력 가속도는
각각 58.78도/s², 60.00도/s²였다. READY는 0속도 출력 후에만 확인했다.

또한 최신 원본 로그의 고정 prefix 13,330개 상태 행을 입력 수신 순서대로 재생했다.
추종·추적 손실 복귀·재engage·pinch 복귀가 중단 없이 완료됐다. 전체 재생의 최소
clearance는 35.49mm, 최대 출력 가속도는 수치 오차 허용 안의 60도/s²였다.
이 재생은 실제 새 Quest 세션이 아니다. 과거 로그의 tick 시각과 CPU 실행 시간도
새 Quest 전체 지연 또는 지속 60Hz 보증으로 취급하지 않는다.

실행 폴더의 실제 BAT는 별도 loopback 포트 60164에서 headless 1초 기동 후 정상 종료했다.
Unity/C#은 변경하지 않았으므로 이번에는 C#을 재컴파일하지 않았다.
기존 단일팔 구현과 추종 보정 파일, 사용자 씬은 변경하지 않았다.

검증 자료:
- [기계 판독 결과](validation/bimanual_return_20260918/verification.json)
- [소스 테스트 출력](validation/bimanual_return_20260918/source_suite.txt)
- [설치 폴더 테스트 출력](validation/bimanual_return_20260918/runtime_suite.txt)
- [두 복귀 시작 상태 fixture](../backend/tests/fixtures/bimanual_return_starts_20260918.json)

fixture의 속도와 가속도는 로그의 시뮬레이션 관절 위치 차분으로 복원한 값이다.
실제 G1 실측이 아니다. 원본 전체 JSONL과 이번 prefix/상세 재생 출력은 노트북의
`logs/test_results/bimanual_return_20260918_131457/`에 남겼다. Git에는 작은 시작 상태
fixture와 검증 요약/테스트 출력만 포함한다.

## 설치와 재실행

같은 노트북의 바탕화면 실행 폴더에 코드/테스트/fixture 7개를 선택 설치했다.
363개 보호 파일의 내용이 유지됐는지 확인했다. 백업:
`logs/backups/bimanual_return_20260918_132555/` (실행 폴더 기준).

사용자의 실행 중인 Python/Unity는 종료하지 않았다. 새 Python 프로세스로 시작해야
이 복귀 경로를 사용한다. Play 중지 후 기존 양팔 Python 창을 정상 종료하고 실행한다.

```powershell
Set-Location 'C:/Users/user/Desktop/G1_Teleop_Project'
.\tools\START_BIMANUAL_UNITY_SIM.bat
```

그 후 기존 SampleScene에서 Play한다. 새 JSONL 첫 행은
`return_policy: bimanual_staged_return_v1`과 복귀 profile/다섯 Python 파일 해시를 기록한다.
상태 행의 `return_motion.stage`로 중간 자세/home/정착 완료와 거부 원인을 구분한다.
새 복귀의 Quest 착용 사용감은 아직 미확인이다. 간헐적인 엔진 import 지연의
근본 원인도 이번 복귀 수정으로 해결됐다고 주장하지 않는다.
