# IK 변경 전후 관절 목표 비교

실제 로봇 없이 두 target trace를 비교한다. IK를 실행하는 도구는 아니므로
동일 입력을 각 IK 버전에 재생한 결과를 먼저 생성해야 한다.
현재 실제 새 IK 버전 비교는 하지 않았으며 예제는 합성 입력이다.

## 실행

```powershell
py -3.11 experiments/twist2_right_arm_manual/compare_ik_targets.py before.json after.json --input hand_input.jsonl --speed 0.7 --acceleration 0.1745329252 --position-delta 0.05 --output comparison.json
```

speed는rad/s,acceleration은rad/s²이다. 위 값은 현재 VR0.7rad/s·10deg/s² 기준.
position-delta는 두 결과의 자세 차이 재검토 기준이며 안전 한계나 자동 PD 보정 기준이 아니다.
raw IK와 속도제한 후 목표를 섞지 말고 stage가 같은 trace끼리 비교한다.

## Trace 형식

```json
{
  "schema": "g1.ik.target_trace.v1",
  "input_sha256": "원본 입력 파일 바이트의 SHA256",
  "model_sha256": "동일 모델 및 설정 묶음의 SHA256",
  "stage": "limited_target",
  "ik_version": "커밋 또는 변경 버전 식별자",
  "initial_q_rad": ["실제 사용한 초기각29개 숫자"],
  "right_lower_rad": ["실제 모델의 오른팔 하한7개 숫자"],
  "right_upper_rad": ["실제 모델의 오른팔 상한7개 숫자"],
  "samples": [
    {"input_index": 0, "elapsed_s": 0.0, "q_rad": ["목표각29개 숫자"]}
  ]
}
```

위 문자열 배열은 설명용이며 실제 파일에는 숫자를 넣고3표본 이상 기록한다.
실행 가능한 합성 예제는 logs/test_results/ik_compare_example_20260908에 있다.
input_index와elapsed_s는 증가해야 하며 두 trace가 같은 시간축을 사용해야 한다.
입력 원본 해시는 직접 검사한다. 모델/초기조건/stage/범위와 표본수가 다르면 거부한다.
자동 보간으로 불일치를 숨기지 않는다. producer가 실제 같은 입력을 썼는지는 별도 생성 단계의 책임이다.

## 결과 해석

- 오른팔22..28별 최대 자세 차이,이동 범위/총 이동량,최대 속도·가속도,관절 한계 여유.
- position-delta 초과 시점,속도/가속도 초과 구간,재검토 여부.
- 나머지0..21번의 최대 차이도 별도 표시한다.
- 속도는 구간 유한차분,가속도는 구간 중점 사이 유한차분. 불균일 시간 간격을 반영한다.
- 표본 사이 순간 peak는 알 수 없고,빠른 움직임과 수학적 불연속을 단정적으로 구분하지 않는다.
- 충돌/FK task 오차/PD 동역학/실제 추종은 검사하지 않는다. review_required는 사람이 살펴볼
  구간이지 PD 재보정 필수 또는 안전 여부 판정이 아니다.

검증: 동일 trace,불균일 시간축 선형 움직임,큰 점프/관절범위 초과,
입력/모델/시간 불일치,중복 시간·index·비유한값 거부 테스트5개와 CLI 합성 실행 통과.
