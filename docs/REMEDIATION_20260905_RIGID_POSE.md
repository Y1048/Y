# R27 수정: 회전 및 자세 행렬 검증

## 검토

기존 R27 범위다. calibration 입력은 회전의 직교성과 determinant를 검사하지
않았고 invert_pose는 회전블록 전치를 역행렬로 사용했다.

## 코드 수정

transforms의 공통 validate_rotation_matrix/validate_pose_matrix를
회전 변환, split_pose, invert_pose, 기저/머리 상대 변환, calibration에 적용했다.
R.T@R=I 및 det(R)=1 검사의 절대 허용치는1e-6, 상대 허용치는0이다.
동차행 허용치는1e-7이다. 물리적 오차 허용치가 아니라 수치 검사 기준이다.
scale/shear/reflection을 임의 보정하지 않고 ValueError로 거절한다.
Unity handedness 기저변환 자체는 유지한다. 자세 회전블록과 기저는 구분한다.
make_pose는 유한3원소 위치를 요구한다. calibration 샘플 전체를 검증한 뒤
저장하여 실패한 샘플의 일부만 추가되는 문제를 방지했다.

## 테스트

scale/shear/reflection/특이 근처/NaN/Inf, 동차행/위치 크기 오류를 검사했다.
단위/180도/난수50회전 round-trip 및 inverse, 작은 수치오차 허용,
샘플 부분저장 방지를 검증했다. 관련85 passed/90 subtests passed.
G1/WSL/DDS/Unity 실행 없음. IK 비용/속도/충돌거리 및 물리출력 변경 없음.

## 남은 항목

R27 로컬 수정/회귀 검증 완료. 실제 입력 통합/성능 및 원격CI 미검증.
R20/R24/R53 및 R50 등 나머지 항목은 해결된 것으로 처리하지 않는다.
