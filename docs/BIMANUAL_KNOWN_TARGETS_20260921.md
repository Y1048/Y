# 도달 가능한 FK 목표를 사용한 양팔 IK 검증

2026-09-21. Synthetic fixed-base simulation, MuJoCo 3.12.0.
실제 Quest 입력/실제 G1 측정 데이터가 아니다.

## 목표 생성과 사전 기준

home에서 관절을 변경한 witness 자세를 만들고 FK 손목 pose를 목표로 사용했다.
왼팔/오른팔 각각 wrist pitch ±30도, elbow ±15도, shoulder pitch -20도 + elbow +10도의
5조건을 실행했다. 양팔 동시 reach 및 wrist pitch +30도 2조건을 더해 총12조건이다.
모든 목표 witness는 관절범위 안에 있고 clearance >=5mm였다. home→witness 관절선형
보간 101개 표본도 검사했다. 이는 endpoint 도달 가능성 및 sampled route의 증거이며
연속 충돌 검증/실제 IK 경로의 도달 보장은 아니다.

결과를 보기 전 고정한 기준: 10초 후 양손 위치 <=5mm, 회전 <=2도, BLOCKED=0,
모든 tick sampled clearance >=5mm, 관절별 속도 cap 준수, 가속도 <=60도/s²
(+1e-4 rad/s² 수치 비교 여유). 현재 live/물리 안전 합격기준을 변경하지 않았다.

## 실제 실행 결과

12조건 ×600ticks =7200ticks 실행, 12/12 PASS. output 결과를 다시 읽어 개수와
모든 조건 result=pass를 assert했다. 원본 JSON에는 각 목표/witness 관절값과 pose,
3/6/10초 checkpoint, 최저 clearance/최대 속도비/최대 가속도를 기록했다.

| 시점 | 12조건 양손 전체 최대 위치오차 | 최대 회전오차 |
|---|---:|---:|
| 3초 | 5.926mm | 1.725도 |
| 6초 | 1.479mm | 0.158도 |
| 10초 | 0.894mm | 0.058도 |

모든 실행의 최소 sampled clearance=40.015mm, 최대 속도/cap 비율=0.153269,
최대 가속도=1.0471975511967266rad/s², target projection=0, BLOCKED=0.
작은 목표의 정착 시험이며 최고 설정속도 도달이나 빠른 VR 연속 추종 시험은 아니다.
팔 교차/충돌 근접 목표를 포괄하지 않는다. 실제 목표에 도달 가능한 witness가 있을 때
현재 양팔 IK가 따라가는 대표 사례가 확인됐다. 앞선 3개 arbitrary Cartesian 목표의
잔여오차를 양팔 이식 자체의 일반적 실패로 간주하지 않는다.
현재 IK/속도/가속도/Unity runtime은 수정하지 않았다. 이 제한된 표본에서 개선 근거가
없는 비용 튜닝은 진행하지 않는다. 다음 변경은 실제 operator 로그의 구체적인 미해결
문제나 인터페이스 요구가 있을 때 추진한다.

## 재현

```powershell
py -3.11 backend/tools/audit_bimanual_known_targets.py --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 --output known-targets-new.json
```

출력 파일은 exclusive create로 기존 결과를 보존한다. source SHA256 기록 포함.
이번 실행은 위7200tick 및 결과 assertion/diff 검사이며 기존 전체102개 회귀와
Unity 컴파일은 재실행하지 않았다. 실제 G1 실행 없음.
결과: docs/validation/bimanual_known_targets_20260921/baseline.json.
