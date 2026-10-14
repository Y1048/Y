# Unity Game 키보드 이동 입력

Omni 없이 Unity Game 창에서 기존 Omni 수신 형식의 vx, vy, arm_yaw_deg를 생성한다. PC gateway만 변경하며 G1 수신기 변경이나 재배포는 필요 없다.

| 키 | 전달 동작 |
| --- | --- |
| W / S | G1 전방 / 후방 vx = +0.2 / -0.2 m/s |
| A / D | G1 좌 / 우 vy = +0.2 / -0.2 m/s |
| Q / E | G1 목표 방향을 좌 / 우로 초당 0.2 rad씩 변경 |

이동 키를 놓으면 이동속도는 0이다. Q/E를 놓으면 마지막 목표 방향을 유지한다. **G1이 목표 방향에 아직 도달하지 않았다면 키를 놓은 뒤에도 남은 각도만큼 회전할 수 있다.** 반대 키는 상쇄되며 대각 이동 합성 속도도 0.2 m/s다. 실제 속도는 하체 제어기의 응답에 따라 다르다.

## PC 입력 확인

1. 이전 teleop/Omni gateway 세션을 정상 종료한다.
2. 실행용 프로젝트 루트의 TEST_G1_UNITY_KEYBOARD.bat를 실행한다.
3. 같은 폴더의 Unity 프로젝트에서 Play 후 Game 탭 내부를 클릭한다.
4. 이동 키를 모두 한 번 놓고 WASD/QE를 누른다.

Preview BAT는 PC loopback 입력만 확인한다. G1 연결, SSH, 관측 송신, 모터 출력, Omni Connect는 필요 없다. 전체 IK/로봇 화면 준비 상태와는 별개다.

Game 포커스가 사라지면 이동속도와 목표각 증가율을 0으로 하고 마지막 목표각을 유지한다. 다시 포커스를 얻어도 모든 이동 키를 놓기 전에는 재개하지 않는다. Unity 입력이 끊기면 gateway는 150 ms 유효기간 후 이동속도와 목표각 증가율을 0으로 한다. Gateway가 150 ms 넘게 정체하면 경과 시간을 한꺼번에 목표각에 반영하지 않는다. Gateway 자체 종료에는 기존 수신기 freshness 제한이 적용된다.

## 통합 실행

실행용 프로젝트 루트에서:

```powershell
.\START_G1_VR_TELEOP.bat --base-input keyboard
```

기본값은 기존 Omni 모드다. keyboard는 Omni gateway를 대체하며 두 입력은 동시에 실행할 수 없다. 통합 실행은 기존 GROOT 시작 확인과 종료 절차를 사용한다. 이 명령은 preview 전용이 아니다.

기존 G1 heading 수신기, GROOT 원격 런처와 quiet supervisor는 기준 커밋 그대로다. 앞서 제안한 수신기 rate-control 분기와 별도 배포 요구를 제거했다. 이번 수정에서는 G1에 접속하거나 프로그램을 실행하지 않았다.

## 전달 형식

Unity Game → PC UDP 55077 keyboard gateway → PC UDP 55071 combined sender → G1 UDP 55070 기존 수신기 → G1 내부 UDP 15100 C++ 제어기.

Gateway는 PC UDP 55076의 Unity에 60 Hz 요청을 보낸다. Unity 응답은 렌더 프레임에 종속되며 최대 60 Hz다. 토큰·요청 순서·유효기간을 확인한다. UDP 55074는 Omni와의 배타 소유에 사용한다.

기존 payload.omni.values 슬롯 예시(Q를 1초 누른 뒤):

```json
{
  "input_mode": "unity_keyboard",
  "source_origin": "unity_game_keyboard",
  "calibrated": true,
  "arm_yaw_deg": -11.4591559,
  "vx": 0.2,
  "vy": 0.0,
  "yaw_rate": 0.2
}
```

이는 가상 입력이다. 실제 Omni 측정값이 아니며 출처를 명시한다. calibrated=true는 가상 각도 원점을 0으로 설정했다는 뜻이다. 기존 수신기는 vx/vy와 arm_yaw_deg를 사용한다. yaw_rate는 요청한 목표각 증가율 진단값이며 직접 회전 명령으로 사용하지 않는다.

기존 통합 런처의 --yaw-sign -1에 맞춰 Q는 가상 Omni 각도를 감소시킨다. 수신기에서 부호를 적용하면 로봇의 좌회전 목표가 된다. 이 수신기 부호를 수동으로 바꾸면 Q/E 방향도 달라진다. 수신기 시작 시 현재 가상 각도와 G1 방향을 원점으로 삼으므로 연결 준비까지 키를 놓고 시작한다. Q/E는 Quest tracking space나 사람 몸 좌표계를 인위적으로 회전시키지 않는다. 입력 전환은 세션을 정상 종료한 뒤 한다.

## 검증 및 상태

- 가상 Omni 변환 수정 시 Python 98/98 통과; 최종 배포 회귀는 147/147 통과. 가상 각도 누적·양방향·반전·wrap·키 해제·포커스 상실·입력 만료·정체·기존 수신기 호환·런처 회귀 포함.
- 생성 입력을 실제 PC loopback UDP preview로 전달한 테스트 포함. 실제 G1 송신은 없음.
- 기존 수신기와 원격 실행 소스가 HEAD와 동일함을 확인.
- 최종 UI 문구는 키 해제 시 이동 정지·목표 방향 유지로 수정. Unity 실제 참조 어셈블리로 Editor/Player × Input System/legacy 4가지 컴파일 재검증 통과.
- 실제 Unity Game 조작 및 G1 회전 응답은 미검증. 오프라인 테스트는 로봇 안전성 검증이 아님.
- IK, PD, C++ actuator, 관절 모델, 하체 정책 변경 없음. 최종 LowCmd 기록 확인은 별도 후속.
- 브랜치 codex/g1-unity-keyboard-20261014, 기준 4e89f45e5e80b506cd453754cea5dc252f4b33e7. 2026-10-14 main 배포 묶음에 포함.
- 테스트 기록: logs/test_results/keyboard_omni_adapter_20261014/tests.txt.
