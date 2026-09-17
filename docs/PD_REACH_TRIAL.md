# 앞으로 팔 뻗기 PD 기준 시험

2026-09-08 최신 다관절 옵션 버전: /home/unitree/g1_pd_multi_trial_20260908에 별도 배포·aarch64 빌드 완료. 새 버전은 아직 실행하지 않았다. 기존40/5 버전은 첫 전진 추종오차로 중단한 기록이 있다.

## 고정 비교 조건

최신 배포 버전은 오른팔22..28번 여러 관절도 한 번에 지정할 수 있다:

```text
--pd-reach-trial --pd-gain 22:48:5 --pd-gain 23:40:4 --pd-gain 25:45:5
```

형식은 관절번호:Kp:Kd이며 지정하지 않은 관절은 기본값을 유지한다.
같은 관절 중복 지정,22번 shoulder 별칭과 중복,22..28 밖 번호는 거부한다.
이 예제는 문법 설명이며 해당 조합의 실기 결과가 아니다.

새 폴더로 이동한 뒤 다음처럼 실행마다22번 Kp/Kd만 지정할 수도 있다:

```text
cd /home/unitree/g1_pd_multi_trial_20260908
./build/g1_twist2_mink_udp_trial eth0 /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt --enable-actuation --policy-seconds 300 --pd-reach-trial --right-shoulder-kp 48 --right-shoulder-kd 5
```

두 옵션 모두 생략 가능하며 생략한 값은 빌드 기준(현재40/5)을 사용한다.
PD 모드에서만 허용하고, 시작 후 변경하지 않는다. 시작 전 표시와 writer CSV에 실제 적용값이 나온다.
입력 범위 Kp1..100, Kd0.1..20은 소프트웨어 입력 제한이며 실험으로 검증된 안전 범위가 아니다.
NaN/Inf·범위 밖·중복·알 수 없는 옵션·값 누락은 DDS 초기화 전에 거부한다.
명시하지 않은 관절의 PD·궤적·중단 기준은 변경하지 않는다.

- 보정 대상: 관절별 Kp/Kd. 속도·가속도·경로는 후보마다 바꾸지 않는다.
- 로컬 기준: 양팔 어깨·팔꿈치 Kp40/Kd5, 손목 Kp20/Kd1. 하체·허리는 기존 값 유지.
- 목표 관절속도 상한45도/s, 목표 각가속도 상한10rad/s².
- 공통 산출물: logs/test_results/pd_reach_limits_selected_20260908/report.json.
- 편도1.994초, 계산 최고44.9575도/s, 최대9.92397rad/s².
- 시작 대기1초 + (전진1.994초/대기1초/복귀1.994초/대기1초) ×3회 =18.964초.
  capture1초/blend4초 및 두팔 준비자세 이동은 별도다. 이전2초 결과는 개발 이력이다.

## 움직임과 실행 동작

가상 Mink ready 오른팔 [10,-22,0,55,0,0,0]도에서 출발한다.
손목은 앞으로27.37cm, 안쪽10.10cm, 위로32.01cm 이동한다.
전방으로 최대8cm 볼록한 task 경로를 IK로 풀고 끝점 고정 다항식으로 근사했다.
복귀는 동일 시간표를 역방향으로 따른다. 모든 관절이 동시에45도/s가 되는 것은 아니다.

새 C++의 --pd-reach-trial은 UDP 입력 없이 자동 왕복한다.
기존 START_TWIST2_MINK_UDP 런처는 계속 VR UDP 모드이며 PD 시험 런처가 아니다.
시험 모드는 P 입력 전에 오른팔 22..28번 Kp/Kd와 편도 시간을 출력한다.
두팔은 기존0.08rad/s로 준비 목표까지 이동한 후 pd_settling 단계에서 기다린다.
양팔15..28번 모두 목표 오차0.10rad 이하·실측 속도0.10rad/s 이하를
새 LowState 수신 표본 기준1초 연속 만족하면 왕복을 자동 시작한다.
조건 위반 또는 수신 간격60ms 초과 시 연속 구간을 초기화한다. 중복 표본은 시간을 누적하지 않는다.
오래된 표본·비유한값·시계 역행·정착 대기10초 초과는 오류로 기존 damping 경로에 전달한다.
이 수치는 로컬 초기 기준이며 실기로 검증된 정착/안전 한계가 아니다.
팔 정착 검사에서 하체·허리는 제외하되 기존 전신 상태/속도/추종/중단 검사는 유지한다.

실제 명령은 하체 TWIST2와 상체 목표를 합치는 전신 단일 송신 경로다.
R1 유지, Select/B 또는 p 중단을 유지한다. R1 해제 및 오류도 damping으로 종료한다.
완료 후 AI 자세 유지로 자동 복귀하지 않는다. dq 명령은0이다.

배포 및 초기 구간 검토 후 사용할 인자 형식(현재 G1 실행 지시가 아님):

```text
g1_twist2_mink_udp_trial <interface> <absolute-policy-path> --enable-actuation --policy-seconds 300 --pd-reach-trial
```

## 기록과 PD 평가

CSV는 실행 작업 폴더의 g1_twist2_trial_<microseconds>_<pid>/policy.csv에 저장하도록 구현했다.
시작 시 출력되는 CSV 경로를 사용한다. writer 기록은 약50Hz의 최신500Hz 송신 프레임이며,
모든 송신 프레임을 저장하는 것은 아니다. 추정 토크는 실측 토크와 구분한다.

pd_gain_comparison.py는 후보 계획과 완료된 기록을 평가하는 오프라인 도구다.
현재 joint22 후보는 Kp32/40/48 × Kd4/5/6이며 다른 관절값은 고정한다.
실행 설정을 바꾸거나 자동으로 로봇을 구동하지 않는다.
평가 한계값은 아직 미설정이다. 완료 메타데이터·CSV 해시·reference 일치 및 실제 기록된
전체 관절 PD를 검사하며, 불완전한 시험을 정상 후보로 평가하지 않는다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/pd_gain_comparison.py plan --joint 22 --output logs/test_results/pd_gain_plan_new.json
```

## 확인 범위와 남은 항목

- 오프라인 모델의 지정 충돌243쌍 500Hz 표본 최소거리40.30mm. 연속/전신 충돌 증명이 아니다.
- 목표 경로와 IK task 사이 최대 차이1.25mm/0.373도.
- 가상 준비자세에서의 왕복 검사이며 실측 LowState에서 준비자세까지의 경로 검증은 별도다.
- PC x86-64 및 G1 aarch64 빌드 완료. G1 실행파일 SHA256: 338f2d3ead7b9cdc8b446c7e6abd5086a446e2f3a29c9bdbe1b4d5c958395ac0.
- 새 정착 조건의 실측 확인, 실제 타이밍·추종 기록, PD 후보 비교는 남아 있다.
- 45도/s 및10rad/s²는 목표 궤적 조건이다. 실제 로봇 안전성이나 최적 PD를 검증한 결과가 아니다.
- 원본 키보드 및 기존 UDP 시험 경로는 보존했다. 새 시험 폴더에만 파일을 추가했다.
