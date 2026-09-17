# R32 수정: V1 정수 필드 검증

## 검토

기존 finding R32의 범위다. 새 R-number를 만들지 않았다.
PosePacketV1/StatePacketV1의 int(value)가 bool, 문자열, 소수를 정수로
변환하던 문제를 확인했다. 검토 완료와 수정 완료는 별개다.

## 코드 수정

backend/g1_teleop/protocol.py의 V1 파서6개 정수 필드를 기존 _integer로 검증한다.
sequence/source_time_ns/robot_time_ns/calibration_request는0 이상,
acknowledged_source_sequence는-1 이상이다.
calibration_request 생략 시0, acknowledged_source_sequence 생략 시-1은 유지한다.
필수필드 누락, bool, 문자열, float, null, 하한 미만은 ProtocolError다.
정상 JSON 정수와 직렬화 round-trip은 유지한다. V2/legacy 파서는 변경하지 않았다.
이전의 잘못된 타입을 보내는 V1 송신자는 이제 거절되므로 송신 측을 수정해야 한다.

## 테스트

- protocol/foundation:34 passed,42 subtests passed.
- 관련 명령스트림 및 offline IK 포함:81 passed,42 subtests passed.
- 실제 네트워크/Unity/WSL/DDS/G1 실행 없음.

## 남은 항목

R32 파서 수정 및 로컬 회귀 검증 완료, 커밋/원격CI는 이번 작업 범위에 없었다.
R20/R24/R27/R53 등 다른 finding은 해결된 것으로 바꾸지 않는다.
R50의 remote/deadman/CRC 및 물리 경로 검증도 남아 있다.
다음 수정 우선순위는 R27 회전행렬 검증, R20 진단 종료코드, R24 낡은
속도 기대값, R53 공유 XML 쓰기 분리다. 각 항목은 별도 수정/검증한다.
