# 양팔 Mink 시뮬레이션 후보

2026-09-18: 별도 Unity 양손 입력 경로가 추가됐다.
현재 실행 순서와 검증 범위는 [Unity 연결 문서](BIMANUAL_UNITY_SIM_20260918.md)를 참고한다.
아래는 2026-09-17 파일 재생/생성 데모 단계의 기록이다.

현재 단계는 **고정 베이스 운동학 시뮬레이션**이다. 기존 오른팔 실행본,
Unity, UDP 계약, 로봇 제어기, PD 및 저장된 XML/mesh는 변경하지 않았다.
기존 오른팔의 모든 자세 개선을 복제한 완성본도 아니다.

## 실행

저장소 루트에서 `tools\START_BIMANUAL_SIM.bat` 실행.
Python 3.11과 기존 프로젝트의 MuJoCo/Mink/qpsolvers/DAQP 설치가 필요하다.
두 팔이 함께 앞쪽/안쪽으로 이동한 뒤 초기자세로 복귀하는 생성 데모다.
30초 시뮬레이션이며 GUI 처리 시간에 따라 실제 시간은 더 걸릴 수 있다.
창을 닫으면 시뮬레이션만 종료된다. G1 연결이나 송신은 없다.

출력: `logs/test_results/bimanual/demo_<timestamp>.jsonl`.
기존 출력 파일은 덮어쓰지 않는다. 출력은 Git에 포함되지 않는다.

## 구조와 충돌 범위

- 왼팔 15~21, 오른팔 22~28의 14축을 하나의 QP에서 동시에 계산한다.
- 왼손 rubber-hand 충돌 형상을 별도 임시 모델에 추가한다. 오른손과
  동일하게 실제 모델 mesh를 사용하며 원본 XML 파일을 바꾸지 않는다.
- 양팔과 몸통/다리 및 반대편 팔/손의 등록된 형상 쌍을 함께 검사한다.
  직접 연결된 구조적 이웃 제외 규칙과 elbow/wrist-yaw 제외를 좌우에 적용한다.
  이 제외와 모델 형상 때문에 모든 실제 접촉을 검출한다는 보장은 없다.
- QP 충돌 여유 6mm, 사후 검사 5mm. 관절 경로를 최대 0.25도 간격으로
  샘플링한다. 이는 연속 충돌 증명이나 실제 로봇 안전성 검증이 아니다.
- 어깨/팔꿈치 90deg/s, 손목 180deg/s, 60deg/s²를 시뮬레이션에 사용한다.
- 설치된 Mink의 속도 단위 충돌 bound를 displacement 단위로 변환하고,
  기존 경로의 가짜 mesh zero-distance 보정을 양팔 미분으로 확장한다.
- 복귀도 양팔 관절 목표와 같은 충돌 제약을 사용한다. 도달 불가능하면
  `blocked`로 latch되어 멈춘다. 자동 우회 경로 탐색은 아직 없다.
  거부된 step의 즉시 hold는 시뮬레이션 정책이며 물리 감속 궤적이 아니다.
- 복귀 완료는 모든 팔 관절 오차 <0.002rad 및 속도 <0.01rad/s 조건이다.
  `ready` 후 새 양손 목표를 줄 수 있다. 아직 pinch/engage 입력과 연결되지 않았다.

## 양손 목표 파일

`START_BIMANUAL_SIM.bat --input paired_targets.jsonl`.
한 행이 1/60초, 로봇 좌표 +X 전방/+Y 왼쪽/+Z 위, 위치 m,
회전은 정규화한 **wxyz** quaternion이다. 양손을 같은 행에 넣는다.
전체 입력 검증 후 시뮬레이션을 시작한다. 네트워크 패킷 형식이 아니다.

```json
{"schema":"g1.bimanual.sim.v1","simulation_only":true,"left":{"position_m":[0.3,0.2,0.9],"quaternion_wxyz":[1,0,0,0]},"right":{"position_m":[0.3,-0.2,0.9],"quaternion_wxyz":[1,0,0,0]}}
{"schema":"g1.bimanual.sim.v1","simulation_only":true,"return_home":true}
```

위 좌표는 형식 예시이며 도달 가능성/안전 자세가 검증된 목표는 아니다.
복귀를 지속하려면 return_home 행을 여러 tick 제공한다.

## 실제 실행한 검증

`py -3.11 -m unittest discover -s backend/tests -p test_bimanual_sim.py -v`

MuJoCo **3.11.0 및 3.12.0**에서 각각 6개 테스트 통과:

1. 14축 순서와 양손 충돌 형상 쌍, 초기 충돌 여유.
2. 새 진입점에 transport/SDK import 없음 및 기존 송신 객체 미생성.
3. 누락 pose, 비정상 quaternion, nonfinite/provenance 거부.
4. 경로 검사 실패 시 자세 유지 및 blocked latch.
5. 교차 목표에서 샘플 충돌 여유, 속도/가속도, 나머지 관절 보존.
6. 양팔 이동 → 복귀 → ready → 새 목표 처리.

별도 1,800 tick 데모도 `ready` 종료 확인. 초기 실패 진단 로그는 삭제하지 않았다.
생성 fixture만 사용했으며 실제 Unity 양손/Quest 또는 G1 검증은 수행하지 않았다.
GUI 창의 시각적 확인은 아직이다. 수학적 추종 최적성/자연스러운 자세 판정도 아니다.

## 다음 작업

Unity 양손 pose 및 좌우 engage/pinch 의미를 기존 입력 코드와 맞춰 새 시뮬레이션
계약으로 연결한다. 기존 오른팔 UDP를 재사용해 양팔 값을 몰래 보내면 안 된다.
몸통 앞 교차, 양손 같은 위치, 한 팔 고정 중 반대팔 이동, 동시 복귀를 확대 검증한다.
실제 G1 통합은 하체 정책 담당자와 단일 전신 writer 계약을 맞춘 뒤 별도 진행한다.
