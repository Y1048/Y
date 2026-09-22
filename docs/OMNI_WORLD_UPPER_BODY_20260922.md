# Omni 기준 양팔 IK (2026-09-22)

## 동작

Unity Play 시작 후 Quest 머리 추적과 Omni yaw가 정상이고 약 1초간 안정되면
초기 전방을 맞춘다. 외부 고정버튼은 현재 패킷에 포함되어 있지 않으므로
버튼 눌림/해제를 자동 감지하지 않는다. 사용자는 차렷하고 정면을 보며
고정버튼을 누른 채 Play를 시작하고, 화면의 ALIGNED/정렬 완료 표시 후 해제한다.
데이터가 늦게 도착하거나 움직이면 대기 시간이 길어질 수 있다.

초기 머리 위치를 G1 head mount에 맞추는 한 번의 평행이동과 yaw 정렬 이후,
Quest tracking space는 고정된다. 사람 몸 기준점은 초기 머리-로봇 머리 대응으로
추정한 것이며, 실제 골반 추적이나 체격 자동 보정은 없다. 회전 중심 차이와
신체 비율에 따른 오차는 실착 확인이 필요하다.

Unity 로봇 root와 MuJoCo base는 동일한 Omni 초기 yaw 대비 변화량을 따른다.
MuJoCo의 기존 free-base qpos는 외부에서 지정하고 양팔 14개 관절만 QP로 푼다.
Unity 상체 제어 모델은 실제 관절 LowState로 IK 결과를 덮어쓰지 않는다.
실제 G1 odometry yaw는 이 입력/표시 경로에 사용하지 않는다.
Omni movement x/y 및 G1 하체에 전달되는 vx/vy/yaw-rate 경로는 변경하지 않았다.

## 손목 경로

정렬된 Quest 손목 world pose -> Unity/G1 축 대응 -> 월드 손목 목표 -> 회전하는 G1 모델 IK.
손목 위치는 engage 변위가 아닌 절대 world 위치이다. 손 회전은 해부학적 손 프레임을
사용하며 engage 때 손 방향과 G1 초기 wrist 방향의 대응을 저장한다.
Engage 때 HMD 전방을 다시 저장하지 않는다.
필터는 Omni base 기준으로 적용한 뒤 동일한 base 회전으로 world에 돌려놓는다.
이 처리는 몸 회전 자체에 필터 지연이 생겨 팔을 뒤로 끌어당기는 것을 방지한다.
하늘색 표시는 Quest 원본 손목, 초록 목표는 backend가 실제 IK에 사용한
필터/충돌 투영 후 world 목표이다. 제한이 작동하면 둘의 위치가 다를 수 있다.

입력 계약: g1.bimanual.unity.sim.v2, input_frame=omni_world_v1,
base_yaw_rad=G1 축 부호의 Omni 상대 yaw, position_m=정렬된 Unity world 좌표,
quaternion_wxyz=Unity 손의 해부학적 프레임.
기존 v1 녹화 재생은 지원하지만 v1 상대 변위와 v2 world 입력을 혼용하지 않는다.
오래된 backend는 v2를 거부한다. Unity와 양팔 IK backend를 모두 재시작해야 한다.
피드백은 기존 state.v1에 input_frame, base_yaw_rad, *_ik_target_world_m,
*_ik_target_world_wxyz를 추가했다.

Omni 샘플이 0.25초 이상 끊기거나 송신 세션/시계가 바뀌면 초기 정렬을 무효화하고
재engage를 차단한다. 조작 중이면 기존 복귀 절차로 전환한다.
이 경우 Play를 재시작하고 초기 정렬부터 다시 한다.

## 검증

- 원래 양팔 입력/복귀/목표/Unity 구조 테스트 통과.
- 0~360도 공동 회전 시 home 팔 관절 및 FK/표시 목표 일치.
- 0, +90, 180, -90도에서 전방/좌우 목표의 팔 관절 결과 일치.
- 회전하면서 팔을 뻗을 때 정지한 base의 동일 몸 기준 동작과 관절 결과 일치.
- 회전 직후 손 추적 손실 시 정지 궤적이 이전 base 회전을 복원하지 않음.
- 잘못된 yaw/좌표 계약 거부, 세션 내 frame 변경 시 복귀.
- Unity runtime C# 소스를 프로젝트 참조로 Roslyn 컴파일. .NET SDK가 없어
  dotnet build 대신 설치된 Visual Studio csc를 사용했다.
- 실제 Quest 착용 Play 및 G1 명령 실행은 하지 않았다.

검증 출력: logs/validation/omni_world_20260922/ (로컬, Git 제외).
