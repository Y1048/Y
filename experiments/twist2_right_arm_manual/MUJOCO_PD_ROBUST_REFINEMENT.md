# 관절 제한을 유지하는 PD 강건성 세부 탐색

## 목적과 고정 조건

`mujoco_pd_robust_refine.py`는 기존 MuJoCo PD 엔진을 수정하지 않고 호출한다.
관절22의 준비자세 기준 +/-8도, 3회 왕복을 유지하며 게인은22..25에 함께 적용한다.
29개 관절의 soft/model-hard 범위, 추가0.05rad 여유, 정지거리 검사, 명령 개입 거부는
그대로 필수 조건이다. 유효 결과를 만들기 위해 제한을 넓히거나 궤적을 바꾸지 않는다.
실제 G1, DDS, SDK, VR 입력/릴레이, 실기 게인, XML/메시와 IK cost를 변경하지 않는다.

## 두 단계 비교

1. Kp72/80/88/96/100과 Kd0.6/0.7/0.8/0.9/1/1.2/1.5/2의40개 조합에
   비교 기준40/5,56/3,100/0.1,100/3을 추가한다.44쌍 모두에 동일한27조건을 실행한다.
   기존 motor18조건과 model9조건을 사용한다. model의 nominal/dt_half는 motor 조건과
   같으므로 중복하지 않는다. 같은 이름의 combined 조건은 family까지 구분한다.
2. 27조건 전부 통과한 후보만 최악 원래목표 RMSE로 정렬한다. 상위6쌍과 고정 비교
   기준을 `selection.json`에 기록한 뒤, 미리 정한 별도8조건을 실행한다. 이 단계의
   결과를 보고 게인이나 임계값을 다시 고르지 않는다. 통과 못한 후보는 작은 부분
   RMSE를 가지고 있어도 선택 가능한 점수가 없다.

추가8조건은 마찰, 토크 출력 지연/1차 지연의 미시험 조합과 질량/관성/수동감쇠 변화다.
정확한 수치는 실행 전에 저장하는 manifest의 calibration/holdout 필드에 있다.
이는 가정한 조건에 대한 비교이며 실제 G1의 오차 분포를 추정한 것은 아니다.
상위 후보가 Kp100에 있더라도 탐색 상한일 뿐, 국소/전역 최적이라는 뜻이 아니다.

## 실행

저장소 루트에서 `MUJOCO_PD_SWEEP.md`의 별도 MuJoCo3.3.7 환경을 사용한다.
기존 결과 폴더는 덮어쓰지 않는다. 아래 경로는 새 폴더여야 한다.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_robust_refine.py --workers 6 --output logs/test_results/mujoco_pd/robust_refinement_01
```

`--smoke`는 두 게인과 단계별 두 조건만 실행하는8회 점검이다. 전체 탐색으로
보고해서는 안 된다. `--audit-only`는 새 물리 계산 없이 이미 저장된 결과를 검증하고
파생 CSV와 audit.json만 갱신한다.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_robust_refine.py --audit-only --output logs/test_results/mujoco_pd/robust_refinement_01
```

## 기록과 판정

manifest.json은 조건/의존성/모델 해시를, calibration_plan.json과 holdout_plan.json은
정확한 실행 계획을, selection.json은 별도 조건 실행 전 확정된 후보와 당시 결과
해시를 기록한다. 사례별 JSON과 NPZ에는 실패도 남긴다. 성공한 사례만 추려서 기록하지 않는다.

summary.json은 각 단계의 전조건 통과 여부와 최악/평균 RMSE, overshoot, 토크,
관절 여유를 구분한다. `partial_worst_rmse_rad`는 탈락한 후보의 관측된 부분값이며
선택 점수가 아니다. `calibration_order_survivors`는 27조건의 순위를 유지하면서
별도8조건도 통과한 후보를 나열한다. holdout 오차로 다시 정렬한 추천 목록이 아니다.

감사기는 모든 q22 NPZ를 다시 읽어 해시/연속 시간/완료 구간/지표를 검사하고,
29관절 여유의 증거와 전후/마지막 단계 관측 횟수도 확인한다. 결과를 다시 계산해
저장 순위와 일치하는지 검사한다. 전체29관절의 시계열을 독립적으로 복원하는 것은
아니다. 해당 상태는 전 물리 단계에서 검사한 최소값/증거로 기록되어 있다.

## 해석 한계

골반 고정, 작은 단일관절 가진, 그룹 게인이다. 전신 균형/개별관절 PD 식별,
실측 지연/제동/잡음/백래시/온도, 실제 VR 경로 성능을 검증하지 않는다.
토크 출력 지연은 UDP 지연과 동일한 모델이 아니다. timestep 변경은 이상적 내부
PD 평가율도 바꾼다. 모의 실행 중단을 실제 G1 정지나 hold로 표현하지 않는다.
최종 실측 수치와 검증 결과는 handoff의 날짜별 기록을 확인한다.
