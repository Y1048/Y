# Omni 몸 회전과 Unity 작업 방향

## 적용 범위

Omni 위에서 몸을 돌리면 가상 작업 방향도 함께 회전한다. Quest의 고개만 돌리는
동작은 그대로 유지한다. G1 실제 이동/방향을 측정하거나 모터를 제어하는 기능은 아니다.

기존 양팔 IK는 fixed-base 로봇 좌표에서 계산한다. 이 좌표를 계속 유지하기 위해
가상 로봇 루트/IK 목표를 직접 회전시키는 대신 **XR tracking frame과 주변 환경에
몸 회전의 역변환**을 적용한다. 따라서 공간에 대한 시각적 작업 방향은 돌아가지만,
몸과 함께 움직인 손목은 몸 기준의 같은 위치/방향으로 읽히도록 한다.
몸 회전과 별개의 손·고개 움직임은 유지된다. 이동 위치(vx/vy) 적분은 하지 않는다.

Omni world +yaw는 robot-left이며 Unity의 body yaw 부호와 반대다.
그러므로 robot-centred inverse transform에는 +Omni delta를 적용한다.
Omni 시작 각도(예: 112도)는 원점으로 잡고 이후 변화량만 누적한다.

## 데이터 경로

기존 `ObservationTap('omni')`의 관찰본에 별도 loopback 복사본을 추가했다.
기존 G1/audit 패킷과 전달 성공 여부는 바꾸지 않는다.

```text
Omni Gateway -- G1_OMNI_UNITY_HEADING=1 --> UDP 127.0.0.1:55072
                                          Unity G1OmniBodyHeading
```

```json
{"schema":"g1.omni.unity.heading.v1","session":"producer-session","sample":[42,12345.67,142.0]}
```

sample 순서: source sequence, source monotonic seconds, absolute arm yaw degrees.
표시 복사본 전송 실패는 기존 audit 전송 성공을 실패로 바꾸지 않는다.
Unity는 loopback만 바인딩한다. 비정상 데이터·역순/중복·이전 session·큰 단발 점프는 무시한다.
250 ms 이상 입력 간격이나 session 재시작이면 현재 표시 방향을 유지한 채 새 기준을 잡는다.
누락 구간의 몸 회전을 추측해서 복원하지 않는다. 이 경우 손 정렬이 어긋나면 재engage로
기준을 다시 맞추고 장치 연결을 확인한다.

## 실행

최신 Unity 소스와 최신 Omni Gateway/observation launcher를 **함께** 사용한다.
Unity Play를 멈춘 상태에서 수정본을 반영한 뒤 Omni 창을 다시 실행하고 Play를 켠다.
통합/관찰 launcher가 표시 복사본을 자동으로 활성화한다. 수동 실행 시에는
`G1_OBSERVATION_TAP=1`, `G1_OMNI_UNITY_HEADING=1`이 둘 다 필요하다.
UDP 55072가 이미 점유됐으면 Unity Console 오류를 확인하고 자신의 이전 실행만 종료한다.

## 검증과 남은 확인

- 실제 Unity/Meta DLL을 참조한 전체 G1Teleop C# 컴파일 통과. 기존 netstandard 참조 경고는 남음.
- production C# heading gate 20개 assertion 실행 통과: 원점, +/- 회전, 360도 경계,
  중복/역순/nonfinite 거부, stale/session 재기준 설정.
- Python 관찰 tap/launcher 28개 테스트 통과. 표시 복사 실패와 기존 전달 결과의 분리를 확인.
- 실제 Quest+Omni의 회전 방향, 몸에 고정한 손의 목표 유지, 고개만 돌리기,
  pinch/재engage 체감은 아직 실착 확인 전이다. 컴파일 결과를 실착 성공으로 해석하지 않는다.
- IK cost/PD/속도·가속도 제한/실제 G1 command protocol은 변경하지 않았다.
