# 오른팔 단독과 양팔 모드의 대표 동작 비교

기준 source commit: `47bdd9eb7c4683080dd8483aa0268af1af5fdde4`.
2026-09-21 MuJoCo 3.12.0에서 실제로 실행한 synthetic offline 비교다.
새 Quest/실제 G1 계측은 아니다. 제어기, gain, 속도, runtime 파일은 수정하지 않았다.

## 방법과 범위

각 사례마다 초기자세로 새 시뮬레이터를 생성한다. 오른팔 단독 기준은
`replay_upstream_mink.build()`의 기존 StandardMinkPlanner/UpstreamMinkTracking이다.
양팔 모드는 왼손 목표를 초기자세로 유지하고 오른손에 같은 목표를 준다.
위치 고정 상태에서 손목 로컬 X/Y/Z축 ±45도 회전 6개와, 회전 고정 상태에서
로봇 좌표 X/Y/Z축 ±50mm 이동 6개를 각각 360틱(6초) 실행했다.
입력 필터와 Unity/UDP를 통과하지 않는 IK 출력 비교다.

## 결과

12개 사례 모두 전체 시계열 관절값의 단독/양팔 차이가 수치 오차 수준이었다.
최대 차이 **1.48744e-10도**. 유지 목표를 준 왼팔의 최대 움직임은 **0도**였다.
양팔은 모든 사례에서 tracking을 유지했고 BLOCKED는 없었다.
두 모드와 모든 사례의 최소 sampled clearance는 **12.3465mm**였다.
기록 결과 검사에서 12개 사례의 일치, 왼팔 유지, 최종 tracking,
60도/s² 가속도(+1e-4 rad/s²와 같은 규모의 수치 여유) 조건을 확인했다.

| 목표 | 6초 후 위치 오차: 단독/양팔 공통 (mm) | 6초 후 회전 오차 (도) |
|---|---:|---:|
| 로컬 X -45도 | 0.202 | 0.188 |
| 로컬 X +45도 | 0.240 | 0.188 |
| 로컬 Y -45도 | 14.898 | 1.811 |
| 로컬 Y +45도 | 2.426 | 0.280 |
| 로컬 Z -45도 | 0.381 | 0.189 |
| 로컬 Z +45도 | 0.338 | 0.188 |
| X -50mm | 0.209 | 0.011 |
| X +50mm | 2.088 | 0.013 |
| Y -50mm | 13.822 | 0.200 |
| Y +50mm | 0.764 | 0.025 |
| Z -50mm | 37.716 | 0.426 |
| Z +50mm | 1.245 | 0.044 |

이는 비교한 자유 공간 조건에서 오른팔 동작 이식이 보존됐다는 증거다.
모든 목표를 정확히 추종했다는 PASS로 해석하지 않는다. 특히 Y -45도 회전,
Y -50mm 이동, Z -50mm 이동의 오차는 기존 오른팔에도 공통으로 존재한다.
현재 비교만으로 도달불가/관절 제한/자세 비용/6초 정착 부족 중 원인을 확정할 수 없다.
이 세 목표의 활성 제약과 장시간 정착을 확인하는 것이 다음 분석 항목이다.

왼팔 단독과의 동등성, 양손 동시 교차 목표, 팔 간 충돌 근처에서 단독과 같은 궤적,
입력 필터를 포함한 체감 지연, 실제 G1 성능은 이 비교의 검증 범위가 아니다.
기존 Quest normal operator acceptance를 대체하거나 취소하지 않는다.

## 재현

```powershell
py -3.11 backend/tools/compare_bimanual_single_arm.py `
  --engine-root C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0 `
  --output docs/validation/bimanual_single_arm_20260921/comparison.json
```

측정 수치와 핵심 구현 파일 SHA-256:
[comparison.json](validation/bimanual_single_arm_20260921/comparison.json).
이번에는 위 12사례 비교와 결과 검사, `git diff --check`를 실행했다.
기존 96개 전체 회귀는 이번 작업에서 재실행하지 않았다.
