# 오른팔 PD 반복 시험 준비

최신 시험은 [전체 팔 뻗기 기준](PD_REACH_TRIAL.md)으로 변경됐다.
아래10도/.32rad/s²는 이전 예비 도구 설명이며 현재 C++ 시험 선택지는 --pd-reach-trial이다.

Python 도구는 오프라인 전용이다. 새 실험 C++에는 별도 반복 모드를 로컬 구현했으나
G1 배포·실행은 하지 않았다. 실제 PD, live 속도 및 원본 키보드 제어 파일은 변경하지 않았다.

## 로컬 C++ 시험 모드 현황

새 실험 버전의 선택 인자 --pd-right-shoulder-trial은 --udp-right-arm과 동시 사용 불가다.
UDP를 생성하지 않고 기존 하체정책/캡처 상체 자세에서 오른쪽 어깨 pitch만 +10도 왕복한다.
초기 두팔 ready 이동은 이 모드에서 하지 않는다. 관절 soft 범위는 검사하지만
캡처 자세의 충돌 경로는 아직 검증하지 않았다. 현재 사용자 실행 단계로 안내하지 않는다.
기존 인터랙티브 P/R1/Select/B/p 보호 유지. 자동 반복은 한 세션 안의 고정3회뿐이며
보호 중단 후 재시도하지 않는다. 완료 후 damping이며 AI 복귀는 수동이다.

명령 구간: writer_trial_phase 1=시작대기,2=전진,3=끝점대기,4=복귀,5=시작점대기.
writer_trial_cycle은0..2. 이 필드는 명령 프레임과 함께 기록된다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/pd_trial_offline.py review path/to/new.csv --reference writer --writer-trial-phase 2
```

가속도 .32rad/s² 유지 시 실제 최고10.566도/s, 시험17.647초(초기대기1초 포함).
capture/blend 포함 약22.65초다. 45도/s 도달 시험이나 PD 후보 최적화가 아니다.

## 궤적 생성

프로젝트 루트에서 다음을 실행한다. 출력 파일이 있으면 덮어쓰지 않고 실패한다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/pd_trial_offline.py generate --output logs/test_results/pd_preview.csv
```

기본값은 상대 이동 10도, 속도 상한 45도/s, 가속도 상한 .32rad/s²,
끝점 대기 1초, 왕복 3회, 500Hz다. 가속도는 기존 Mink 값을 준비 단계의 가정으로 유지했다.
5차 위치식 10s³-15s⁴+6s⁵의 정확한 속도/가속도 극값으로 이동시간을 결정한다.
예제 편도 1.77453초, 최고속도 10.56618도/s, 총16.64718초. 45도/s 도달 시험이 아니다.
offset_rad는 기준각에 더할 상대값일 뿐 관절 지정·실측 초기화·충돌 검증을 하지 않았다.
이 CSV를 live 전용 relay에 보내거나 로봇 실행 명령으로 취급하지 않는다.

## 기존 로그 기초 평가

```powershell
py -3.11 experiments/twist2_right_arm_manual/pd_trial_offline.py review path/to/robot.csv --phase udp_ready
```

관절22..28의 desired_target-q RMS/최대오차를 출력한다. 유한값/시간순서를 검사한다.
기존 desired_target은 writer 제한 전 목표다. 최종 송신각 추종 오차와 구분해야 한다.
udp_ready는 active VR와 idle을 구분하지 않으므로 이 결과는 PD 최적화 점수가 아니다.

## 다음 구현 항목

최종 writer 명령과 사용 상태의 프레임 기록도 로컬 구현됐다. 새 CSV에는 writer_* 컬럼이
추가된다. 최종 q/dq/kp/kd/tau와 동일 계산에 사용한 LowState 및 steady clock 시각을 담는다.
500Hz 전체 기록이 아닌 약50Hz 샘플이며, Write 호출 반환은 기기 수신 ACK가 아니다.
정책 행의 phase와 프레임 시각을 혼동하지 않는다. 기존 로그에는 이 컬럼이 없다.

```powershell
py -3.11 experiments/twist2_right_arm_manual/pd_trial_offline.py review path/to/new.csv --phase udp_ready --reference writer
```

위 평가는 writer_sequence 중복 및 오른팔 Kp=0 프레임을 제외한다.
PD 최적화나 전체 시간 구간의 최대오차 보장은 아니며, G1 실기 기록으로는 아직 검증 전이다.

주기 저장은 로컬 실험 C++에 구현했다. 별도 스레드가 약250ms마다 flush하고,
최대250개 큐 및 쓰기 실패를 검사한다. AI handoff 전에 출력 경로를 표시한다.
새 위치는 실행 폴더/g1_twist2_trial_<microseconds>_<pid>/policy.csv다.
이는 OS 전원손실 내구성 보장이 아니다. G1에는 아직 배포하지 않았다.
기존 CSV의 목표/phase 의미는 변하지 않았다.

1. PC 회수, active/시험 구간의 명시적 식별 및 실기 기록 타이밍 확인.
2. 로컬 C++ 반복 시험 모드의 충돌 검토/실기 타이밍 검증 및 G1 배포 준비.
3. 충돌 및 복합 동작 검토 후 같은 궤적의 실제 기준 시험.
4. PD 후보 범위와 탈락 기준을 고정한 뒤 실측 비교. 현재 도구는 자동 PD 탐색기가 아니다.

검증: test_pd_trial_offline.py 4개 통과. 극값/끝점/왕복/덮어쓰기 방지/
잘못된 인자/알려진 오차/시간 역순 또는 중복 검사. 실기 검증 없음.
