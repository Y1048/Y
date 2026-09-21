# 정지 후에도 남는 파란 손목 / 초록 목표 오차

## 계측

Unity 실제 실행 로그 `Unity_G1_VR/Logs/Editor.log`에서 `[BIMANUAL TARGET]`
좌우 각 8개를 확인했다. 이 로그는 사용자 Quest 시험이며 G1 측정 데이터가 아니다.
AppData의 Editor.log에는 프로젝트 로그로 이동했다는 안내만 있으므로 실제 로그 경로를 사용한다.

| 항목 | 왼손 | 오른손 |
|---|---:|---:|
| engage 기준점 차이 크기 | 6.1634cm | 5.3988cm |
| 마지막 표본의 green/raw 간격 | 6.12cm | 5.30cm |
| sender 입력 처리 차이 | 0cm | 0cm |

engage 기준점 차이는 왼손 `(2.34, 4.26, 3.79)cm`,
오른손 `(-1.17, 4.49, -2.76)cm`로 고정되어 있었다.
정지 구간 backend 처리 차이는 수 mm 수준으로 줄어들어도 이 기준점 차이는 유지됐다.
핵심 원인은 기존 상대 제어에서 실제 손 neutral과 robot home을 서로 다른 원점으로
포착하고 그 차이를 제거하지 않은 것이다. 단순 IK 추종 지연이나 PD 문제가 아니다.
원시 진단 표본: [observed_offsets.json](validation/bimanual_engage_offset_20260921/observed_offsets.json).

## 수정 의미

색만 겹치게 옮기지 않고 **시뮬레이션에 요청하는 목표 자체**에 초기 잔여 위치를 반영한다.
Unity는 `engage_offset_m = inverse(OperatorHeading) * (CalibratedWristPosition - EngagementTargetPosition)`를
각 손 packet에 추가한다. Python은 engage 시 1회 복사해 해당 cycle 동안 유지한다.
목표는 `home + BASIS * (filtered_position - captured_origin + engage_offset_m)`다.
복귀 home/재engage 조건은 유지하며 다음 engage에서는 새 offset을 포착한다.
도달 가능한 목표이며 몸 보정/투영이 없고 필터가 정착하면 green/raw 기준점 오차가 해소된다.
실제 IK 손목의 목표 추종 오차는 별도다.

offset은 길이 3, 유한 실수, norm 0.15m 이하만 decode에서 수락한다.
필드가 없는 과거 fixture/클라이언트는 offset 0으로 기존 상대 매핑을 유지한다.
별도 독립 씬 클라이언트는 0을 전송해 기존 동작을 유지한다.
새 Unity와 새 Python을 함께 재시작해야 한다. 기존 Python은 새 필드를 무시한다.

이것은 위치 목표 매핑 변경이며 단순 UI 수정이 아니다. IK/속도/가속도/충돌 검사,
초기 joint pose/복귀 경로는 바꾸지 않았다. 첫 engage에서도 관절값을 바로 대입하지 않고
기존 QP와 60도/s² 제한으로 새 목표를 향해 이동한다.
오른팔 단독 및 실제 G1 코드/SDK/DDS는 변경하거나 실행하지 않았다.

## 검증

새 offset의 좌우 축 변환, cycle 내 고정, 재engage 초기화,
잘못된 offset 거부, 첫 step의 가속도/변위 제한과 collision clearance를 검사했다.
marker/offset tests 6개 PASS 및 실제 Unity 참조 C# 컴파일 exit 0/error 0.
전체 회귀와 runtime 설치 결과는 CHAT_HANDOFF의 후속 기록을 따른다.
수정 후 실제 Quest 화면에서의 오차 감소는 아직 확인되지 않았다.
