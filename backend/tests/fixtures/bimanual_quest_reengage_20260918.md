# Quest pinch/re-engage 기록 fixture — 2026-09-18

원본은 같은 노트북 실행 폴더의 다음 JSONL이다.

`logs/test_results/bimanual/unity_20260918_144806_4738178.jsonl`

원본 SHA-256: `cd9f1af99c2c1000035d5c277fbe0cde55e487db92c4c91c36588b3f0ab204d3`
원본 크기: 9,289,214 bytes.

사용자가 이 세션에서 동작이 정상이라고 확인했다. 로그 자체에서도
READY → TRACKING → RETURNING(pinch) → READY → TRACKING → RETURNING(pinch) → READY
순서가 확인된다. 이는 사용자 평가와 기계 기록을 구분해 보존하기 위한 fixture다.

Git fixture는 첫 engage 직전 sequence 450부터 두 번째 복귀 완료 뒤 sequence 2465까지 선택했다.
run 행 1개, input 2,016개, state 2,927개로 총 4,944행이다.
원본 행 순서와 receive/tick monotonic 시각을 유지한다.

압축 파일: `bimanual_quest_reengage_20260918.json.gz`
압축 SHA-256: `1f05d7f921768955e64515d3486f7f2c975db9653a4ebaa1945e5915f5b26814`
압축 크기: 766,234 bytes.

fixture의 run 행은 `bimanual_motion_v1`, `bimanual_boundary_v1`,
`bimanual_staged_return_v1`, MuJoCo 3.12.0을 기록한다.
다섯 Python source SHA-256도 원본 run 행에서 보존한다.

이 fixture는 실제 G1 실측이 아니며 Quest/Unity가 생성한 loopback 시뮬레이션 입력과
Python 시뮬레이션 상태 기록이다. 사용자 착용감 자체를 자동 테스트가 재현하는 것도 아니다.
회귀 테스트는 원 packet을 decode/receive하고 원 tick 시각으로 UnityCycle을 재생해
상태 전이, 출력 관절값, 속도/가속도 제한과 sampled clearance를 검사한다.

선택 구간 뒤의 READY 대기와 파일 종료 부분은 포함하지 않았다.
backend 빠른 재시작도 이 세션에는 없으므로 해당 검증은 별도 generation/order 테스트를 따른다.
