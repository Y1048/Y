# 실제 LowState 표시와 headless IK

START_G1_VR_TELEOP는 양팔 IK를 --headless로 실행한다. MuJoCo 별도 창 없이 Unity에서 표시한다.
기존 viewer가 열린 프로세스를 새 headless 프로세스로 자동 교체하지 않는다. 기존 관리 창에서 Enter로 종료한 뒤 재실행한다.

```text
G1 rt/lowstate (unitree_hg LowState_, CRC 검사)
 → G1에서 SSH stdin으로 실행하는 ChannelSubscriber
 → SSH JSON lines → PC g1_lowstate_view.py
 → UDP 127.0.0.1:55073 → Unity G1LowStateLegView
```

G1에 파일을 설치하지 않는다. 관찰 전용이며 새 LowCmd publisher나 55070 입력 수신기를 만들지 않는다.
DDS LowState 구독용 통신만 사용하므로 파트너 제어기와 관찰자의 command port ownership은 별개다.
새 PC 최초 key login은 관리 창에서 끝낸 후 background lowstate worker를 실행한다.

수집: 29축 q(rad), dq(rad/s), tau_est(Nm), motor temperature/status, mode_machine, IMU quaternion(wxyz), gyro(rad/s), acceleration(m/s²), tick, CRC, session, sequence.
순서: left leg0..5, right leg6..11, waist12..14, left arm15..21, right arm22..28.
약60Hz로 새 실측을 전달한다. SDK LowState motor_state의 미사용 추가 슬롯은 출력하지 않는다.
JSONL은 logs/test_results/lowstate_view에 기록하며 raw motor command/acceptance를 의미하지 않는다.
age_s는 첫 연결 이후 최소 clock offset 기준의 추가 전송 지연 추정이다. 절대 동기화된 sensor age가 아니다.

Unity 로봇 모델은 전체29축 실측값을 적용한다. 파란 사용자 손목·초록 IK 목표는 독립적으로 유지하며, 연결선은 실측 손목 FK에서 목표로 이어진다.
실측 base position/IMU로 root를 움직이지 않는다. 최초 표시 localPosition을 유지한다.
입력중단0.5초 후 stale을 표시하고 마지막 전신 실측자세를 유지하며 외삽하지 않는다.
이 실측표시는 fixed-base MuJoCo 모델의 IK/충돌계산에 주입되지 않는 시각화다.

검증: 전체 Unity/Meta 참조 C# 컴파일 통과(기존 CS1701 경고).
23 Python tests /18 subtests PASS. 실제 G1에서2초117개29축 표본, CRC/순서 PASS.
PC loopback55073에 실측5개 도착/형식 검증 PASS. No motor/mode command.
Unity Play 정지 확인 후 노트북 설치; 움직임 표시/체감은 아직 미검증이다.


2026-09-21 latency inspection: PC receipt median16ms, p95 31ms, max172ms across latest6000 samples, no sequence gaps. Relative age is not total robot-to-screen latency. No display filtering change. IK target limits restored to shoulder/elbow90 deg/s, wrist180 deg/s, acceleration60 deg/s^2; these do not limit measured-state visualization.
