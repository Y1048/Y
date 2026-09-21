# 양팔 IK 잔여 오차: 정착시간 및 자세 비용 진단

2026-09-21. 실제 Quest/G1 계측이 아닌 synthetic fixed-target offline 실행.
기존 비교에서 오차가 남았던 3개 목표를 6/12/20초에 계측했다.
각 경우 왼팔은 home 목표를 유지한다. 두 실행 모두 MuJoCo 3.12.0이며
각 3조건 × 1200 ticks, 총 7200 simulation ticks를 실제 실행했다.

| 목표 | 기존 6초 위치오차 mm | 기존 20초 mm | posture 비용 제거 20초 mm |
|---|---:|---:|---:|
| 손목 로컬 Y -45도 | 14.898 | 15.643 | 15.461 |
| 로봇 Y -50mm | 13.822 | 13.715 | 13.642 |
| 로봇 Z -50mm | 37.716 | 37.571 | 37.569 |

20초 기다리는 것과 posture 비용 제거만으로는 해결되지 않았다.
이는 단순 정착시간 부족 또는 posture 비용만이 주원인이라는 설명을 지지하지 않는다.
검사한 checkpoint에서 tracking 유지, torso target projection 없음,
elbow assist 비활성이다. 원시 관절 범위까지 여유와 clearance 수치는 JSON에 있다.
clearance가 5mm보다 크다고 모든 충돌 QP 제약이 비활성이라고 판단하지 않는다.
이번 진단만으로 목표 도달불가, 특이점, 충돌 제약 또는 비용 간 경쟁을 확정할 수 없다.
다음으로 고정된 손목 방향에서 목표의 운동학적 도달 가능성과 QP 활성 제약을
분리해 확인해야 한다. 속도/가속도/IK 비용을 실행 프로젝트에 임의 반영하지 않았다.

## 재현

```powershell
py -3.11 backend/tools/audit_bimanual_settling.py --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 --output baseline-new.json
py -3.11 backend/tools/audit_bimanual_settling.py --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 --without-posture --output without-posture-new.json
```

출력은 기존 파일을 덮어쓰지 않는다. --without-posture는 해당 offline 프로세스의
오른팔 posture task에만 적용되며 source controller/runtime을 수정하지 않는다.
최초 실행은 정수 rotation array가 Mink SO3.exp와 호환되지 않아 중단됐다.
진단 도구에서 float array로 수정 후 위 두 실행이 exit 0으로 완료됐다.
기존 전체 회귀/Unity 컴파일/하드웨어 검증은 이번에 실행하지 않았다.
결과: docs/validation/bimanual_settling_20260921/{baseline,without_posture}.json.
