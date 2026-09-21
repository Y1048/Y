# 양팔 목표 도달 가능성 및 QP 진단

2026-09-21, synthetic offline endpoint search. 실제 G1 측정/출력 없음.
제어기와 Unity 실행 설정은 변경하지 않았다.

## 방법

20초 baseline의 오른팔 관절값, home 및 seed 20260921의 무작위 8개 시작점에서
scipy least_squares로 7개 관절을 탐색했다. 실패 목표마다 10개 시작점이다.
모델 관절 범위 및 기존 shoulder yaw home ±90도 범위를 유지했다.
최초 탐색은 max_nfev=600, 추가 검사는 2000이었다.
위치/방향 탐색은 residual=[position(m), 0.15*rotation_log(rad)]를 최소화한다.
방향 제거 탐색은 위치만 최소화한다. 충돌은 최적화 목적에 넣지 않았고 각 결과에서
기존 clearance 함수를 평가한다. 경로는 생성하거나 검증하지 않았다.
탐색 전에 성공 기준을 위치 <=1mm, 회전 <=1도, clearance >=5mm로 고정했다.
position-only에서는 회전 기준을 적용하지 않는다.

## 결과 (2000 평가 한도)

| 목표 | 위치+방향 최저 weighted residual 해의 위치오차 mm | 회전오차 도 | 위치만 최적화한 최소 위치오차 mm |
|---|---:|---:|---:|
| 로컬 Y -45도 | 14.426 | 1.564 | <0.001 |
| 로봇 Y -50mm | 13.097 | 0.508 | 10.716 |
| 로봇 Z -50mm | 36.864 | 1.388 | 34.598 |

세 목표 모두 위치와 방향 성공 기준을 동시에 만족한 해가 0/10이었다.
대조군 home와 X+50mm는 위치/방향 일치 및 clearance 기준을 만족하는 해가 각각
8/9개 시작점에서 확인됐다. 실패 사례와 대조군의 탐색 수 차이는 baseline 시작점 유무다.
Y/Z 이동 사례는 다수가 평가 한도를 소진했다. 탐색 실패를 전역 도달불가 증명으로
해석하지 않는다. 손목 회전 사례는 손목 위치만 유지하는 해가 있지만, 요청한 방향을
함께 맞추는 해는 이 검사에서 발견되지 않았다. 방향을 무조건 포기하는 수정은 하지 않는다.

## 정착점 QP

저장된 20초 q에서 속도 0으로 새 QP를 풀어 실제 solver에 전달된 정규화 부등식
slack을 계측했다. 과거 마지막 tick을 완전히 재현한 것은 아니다.
최소 slack은 각 0.016323 / 0.016832 / 0.015881 rad/s로 모두 양수였다.
검사한 이 상태에서는 충돌/속도/가속도/관절 경계에 등호로 붙은 활성 부등식이 없다.
오른팔 pose Jacobian 최소 singular value는 0.003978 / 0.002698 / 0.001107이다.
위치와 회전 단위가 섞인 Jacobian이므로 절대적인 특이점 판정 기준으로 쓰지 않는다.
반복된 위치 잔여오차, 약한 Jacobian 방향, 비활성 경계는 운동학적 작업공간/자세 조건의
영향을 시사한다. 모든 목표가 도달 가능하다고 가정해 제약을 느슨하게 만들 근거는 없다.

## 실행 기록 및 재현

`audit_bimanual_reachability.py`의 두 대조군 assertion 통과, 세 실행 exit 0.
총 48 endpoint searches × 3실행 =144회. 초기 600회 제한 결과도 보존한다.
기존 전체 회귀/Unity 컴파일/실제 장비 테스트는 이번 단계에서 실행하지 않았다.

```powershell
py -3.11 backend/tools/audit_bimanual_reachability.py --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 --baseline docs/validation/bimanual_settling_20260921/baseline.json --output reachability-new.json
py -3.11 backend/tools/audit_bimanual_reachability.py --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 --baseline docs/validation/bimanual_settling_20260921/baseline.json --position-only --output position-only-new.json
```

현재 도구 기본 평가 한도는 2000. 기존 출력에는 max_nfev 메타데이터가 없지만
실행 명령/조건은 위에 기록했다. position-only 기존 출력의 rotation_residual_scale_m 및
acceptance.rotation_rad는 당시 공통 메타데이터가 남아 있으며 실제 계산에는 방향 목적과
방향 성공 기준이 없었다. 도구에서 메타데이터를 수정했으며 원본 결과는 덮어쓰지 않았다.
원본: docs/validation/bimanual_settling_20260921/reachability*.json.
