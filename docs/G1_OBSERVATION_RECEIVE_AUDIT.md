# G1 수신 전용 관찰 링크

목적: PC에서 읽은 양팔14축/Omni 보정값의 복사본을 실제 G1에서 받아 print하고,
수신 순번과 원본 datagram SHA256을 ACK로 PC에 돌려 실제 전달을 확인한다.
기존 Arm Relay 5014/Omni 명령5017/양팔sim5020과 분리한 UDP55070만 사용한다.
SDK/DDS/LowCmd/모터출력은 없다. 기존 제어 프로그램과 연동하지 않는다.

## G1 준비 (연결 후)

PC 프로젝트 폴더에서 아래를 실행한다. 파일 이름은 이번 수신검사용 고유 이름이며
기존에 같은 파일이 있다면 다른 이름으로 바꿔 보존한다.

```powershell
scp .\tools\G1_INPUT_RECEIVE_AUDIT.py unitree@192.168.123.164:g1_input_receive_audit_20260921.py
ssh -t unitree@192.168.123.164 "python3 -u ~/g1_input_receive_audit_20260921.py receive"
```

이 SSH 창에서 G1이 직접 출력하는 수신값을 본다. G1 python3 표준 라이브러리만
사용하므로 SDK/package 설치 불필요. UDP55070 점유 시 bind 오류로 종료하며
기존 프로세스를 종료/교체하지 않는다. receive 로그는 G1 현재 폴더의
input_receive_YYYYmmdd_HHMMSS.jsonl에 새로 생성한다.
옵션 --allow-peer PC_IP로 수신 허용 IP를 제한할 수 있다.

## PC 송신

기존 양팔 simulation 및 Omni CSV 기록을 실행하고 별도 PC 창에서:

```powershell
.\tools\SEND_G1_INPUT_AUDIT.bat
```

다른 주소라면 `--host 실제_G1_IP`를 붙인다. 정상 확인:
- PC receiver_status=ACK_CONFIRMED, ack_verified_count 증가.
- G1 rx=RECEIVED, receive_count 증가, 순번/수신 payload 출력.
- 최신 실제 입력인지 arm/omni 각각의 status=FRESH_LOG도 확인한다.
- 원래 입력을 움직이며 양쪽 값이 같이 바뀌는지 확인한다.

WAIT_ACK는 응답 없음, ACK_STALE은 0.75초 이상 응답 갱신 없음이다.
G1 프로세스의 RECEIVED는 관찰 복사본 수신 의미이며 실물 모터 명령 수신/실행이 아니다.
원본 값이 HISTORICAL/STALE이어도 관찰 패킷 자체의 ACK는 정상일 수 있다.
그 경우 네트워크 연결은 확인했지만 새 Quest/Omni 입력은 확인한 것이 아니다.
PC source log buffering/50Hz latest snapshot 방식의 제한은 기존 콘솔과 같다.
동일 원본값 재표시는 observation sequence만 증가하고 source sequence는 유지된다.
PC는 ACK peer/session/sequence/SHA256를 대조한다. 이는 관찰용 ACK이며 암호학적
송신자 인증은 아니다. G1/PC monotonic 시각은 직접 빼지 않는다. RTT는 PC시계로 계산한다.
PC/Ctrl+C 또는 G1 수신창 Ctrl+C로 관찰 프로그램만 종료한다.

## 이번 검증

접속시도: 192.168.123.164 TCP22 2회 timeout. 실제 G1 업로드/실행/수신 확인 못 함.
4개 unit/integration tests PASS: 명령 schema 거부 및 전용 포트, 잘못된14축/비유한수,
ACK source/session/sequence/hash 검증, loopback UDP 송수신+ACK+수신파일 hash 일치.
loopback fixture payload는 WAIT 상태이며 실제 G1 또는 센서측정 결과가 아니다.
사용자 연결상태 응답을 기다리는 중이다. 원래 제어파일은 변경하지 않았다.

## 연결 후 확인 결과

앞선 timeout 이후 사용자가 재연결하여 실제 G1 배포/수신까지 완료했다. 배포 폴더는 `/home/unitree/g1_input_audit_20260921_7e83c4`. PC247송신/G1 247수신/누락0, PC ACK246 확인. 양팔/Omni 값은 HISTORICAL이며 새 입력 및 모터 실행 검증은 아니다. 재실행은 `ssh -t unitree@192.168.123.164 "cd /home/unitree/g1_input_audit_20260921_7e83c4 && python3 -u G1_INPUT_RECEIVE_AUDIT.py receive"`. 이미 수신기가 실행중이면 중복 실행하지 않는다.
