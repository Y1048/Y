# G1 실측 기반 오프라인 모델용 데이터

현재 구현은 데이터 출처·조건·품질을 보존하는 준비 단계다. 식별 모델이나 검증된 디지털 트윈은 아직 없다.
새 로컬 코드의 기록 기능은 G1에 아직 배포하지 않았다. 기존 다관절 PD 배포 버전에는 포함되지 않는다.

## 실험마다 보관

- policy.csv: 명령을 구성한 LowState와 실제 writer 목표/PD. 약50Hz로 최신500Hz 프레임을 표본화.
- run.json: 실행파일·정책 SHA256, 인자,29관절 PD,캡처 초기각,reference 계수·시간표.
- result.json: 종료 사유,왕복 완료 여부,CSV/run 해시,행 수. 강제 종료/로그 저장 실패 시 없을 수 있다.
- context.json: 사람이 확인한 조건. 아래 빈 문자열을 실제 관찰로 채운다. 모르는 값은 추정하지 않는다.

```json
{
  "robot_id": "",
  "session_group": "",
  "support": "",
  "payload": "",
  "contact": "",
  "operator_observations": "",
  "split": "train"
}
```

support에는 지지대 위치·지지 정도·발 접지, payload에는 손/팔 부착물과 알려진 질량,
contact에는 외부 접촉 유무, observations에는 진동/예상 밖 동작/온도 관련 관찰 등을 기록한다.
같은 날 같은 셋업의 반복은 같은 session_group을 사용한다.
분할은 train/validation/test 중 하나이며 같은 session_group 전체를 같은 분할에 둔다.
행을 임의로 섞으면 인접 표본이 학습/검증에 동시에 들어가므로 피한다.

## 로컬 검사 예시

G1 실행 디렉터리를 Windows에 복사한 뒤:

```powershell
py -3.11 experiments/twist2_right_arm_manual/audit_identification_run.py logs/test_results/my_run --context logs/test_results/my_run/context.json --output logs/test_results/my_run/audit.json
```

기본 검사는 해시·행 수·기록된 PD 일치,시간 역행·비유한값,중복/건너뛴 writer 프레임,
표본 간격,3왕복 phase 존재,완료 여부와 조건 누락을 확인한다.
passes_basic_audit는 기본 기록 검사를 통과했다는 뜻이며 모델 식별 가능/안전 판정이 아니다.
현재 검사만으로 phase 지속시간·충분한 입력 변화·센서 정확도는 검증하지 않는다.
중단 기록은 버리지 말고 실패 진단용으로 보존한다. 정상 완료 평가와 분리한다.

## 모델 보정으로 넘어가는 조건

1. 같은 궤적·조건의 반복과 별도 검증 세션을 확보한다. 조건과 PD 변경을 기록한다.
2. 현재50Hz 기록은 느린 추종 비교부터 사용한다. 빠른 진동/지연 식별에는 전체 writer/LowState 기록,
   누락 계수 및 저장 부하 검증이 추가로 필요하다. 저장 빈도만 올려 해결했다고 하지 않는다.
3. tau_est는 추정값이며 관성/마찰/중력·센서 지연을 각각 식별했다고 해석하지 않는다.
   같은 프레임의 q는 해당 명령 이후의 응답이 아니므로 시간축을 정렬한 뒤 모델을 맞춘다.
4. 후보 모델은 별도 세션의 움직임을 예측하게 하고 관절별 오차·위상·속도 범위를 비교한다.
   모델 보정에 쓴 데이터만 잘 맞는 것을 검증 성공으로 삼지 않는다.
5. MuJoCo 모델/asset 해시와 보정 파라미터를 함께 버전 관리한다. 미관측 자세·하중·접촉에 대한
   예측은 검증 범위 밖으로 표시한다. 최종 PD 후보는 실제 G1에서 다시 확인한다.

기존 첫40/5 중단 CSV는 그대로 보존한다. 자동 run/result 정보가 없으므로 사후에 생성해
자동 측정 provenance로 가장하지 않는다. 알려진 정보는 별도 수동 기록으로 남긴다.
