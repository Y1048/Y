# 상체 Omni 수신 독립 및 손목 축 매핑 (2026-09-22)

## 변경
- 초기 HMD 정렬, 양손 인게이지, 상체 추적/IK에서 Omni freshness 조건 제거.
- Omni 최초 샘플 전에는 yaw=0. 최초 샘플과 HMD 정렬이 준비되면 기준을 한 번 저장.
- 이후 샘플이 없으면 마지막 yaw 유지. 같은 세션에서 수신 재개 시 첫 yaw 변화도 반영.
- 다른 송신 세션의 첫 샘플은 기존처럼 기준을 재설정하여 갑작스러운 base 회전을 방지.
- Quest 손목 뼈 quaternion 대신 중지 방향과 검지-새끼손가락 방향으로 G1 손목 축 구성.
  G1 MuJoCo +X는 손가락, +Z는 엄지 쪽이며 Unity에서는 각각 +Z, +Y이다.
  `LookRotation(finger_direction, palm_across)`가 양손의 서로 다른 엄지 방향을 반영한다.
- 표시용 하늘색 손목 축과 IK command quaternion은 같은 값을 사용.
  `raw_quaternion_wxyz`에는 진단용 원본 Quest 뼈 회전을 별도로 남긴다.
- 실제 손 추적 신뢰도, 이상 위치 검출, IK 상태/통신 제한은 유지.
- Omni movement x/y/yaw-rate 송신과 로봇 수신부는 이번 변경 대상이 아니다.

## 검증 및 한계
- 결과: Python 26개 통과, C# heading 28개 assertion 통과, runtime C# 컴파일 오류 0개(기존 obsolete API 경고).
- C# heading 테스트: 장시간 정지 후 동일 yaw/변경 yaw, wrap, 세션 재시작, 잘못된 샘플.
- 오프라인 Python: 양손 palm-down 및 몸통 0/±90/180도 회전의 축 변환,
  기존 양팔 solver/Unity 정책 회귀 검사.
- Unity 생성 response file로 runtime C# 컴파일. Play/실제 로봇 실행 없음.
- 과거 로그에는 손가락 뼈 위치가 없어 새 해부학적 회전을 정확히 재구성할 수 없다.
  기존 replay_display_world_session.py의 raw quaternion 재생 결과를 이 변경의 손 방향 검증으로 사용하지 않는다.
- 사람이 Unity에서 확인할 항목: Omni를 움직이지 않고 양손 인게이지;
  양손 손바닥 아래/엄지 위/손바닥 위로 돌릴 때 모델 손의 같은 방향 변화.
  실제 HMD 입력과 모델 외형의 최종 일치는 이 확인이 필요하다.
