# Quest APK 입력 확인 — 2026-10-08

이 단계는 **Quest에서 직접 손·머리를 추적하여 PC에 원본 입력을 기록**하는 별도 실험이다. 기존 Unity Editor, IK, Omni, G1 수신기·모터 제어는 연결하지 않는다. APK는 기존 로봇 화면의 완성된 대체 앱이 아니다.

```text
Quest APK (손·머리 추적, 간단한 상태 화면)
       │ UDP 55100 / JSON, 목표 전송 주기 60 Hz
       ▼
PC quest_input_observer.py → JSONL 기록
       │ 동일 소켓으로 발견 응답·기록 ACK
       └──────────────────► Quest APK
```

## 실행

1. PC에서 `tools\RECORD_QUEST_APK_INPUT.bat` 실행한다. Python 표준 라이브러리만 필요하다. Portable의 bundled Python을 우선 사용하고, 없으면 Windows `py -3`를 사용한다.
2. PC와 Quest를 같은 Wi-Fi/LAN에 연결한다. 이 포트의 PC 수신기는 하나만 실행한다. Windows 방화벽이 묻는 경우 사용 중인 신뢰하는 사설 네트워크에서 Python 수신을 허용한다. 이 작업은 방화벽을 자동 변경하지 않는다.
3. Quest 개발자 모드를 켜고 USB로 PC에 연결하여 헤드셋 안에서 USB 디버깅을 허용한다. `tools\INSTALL_QUEST_INPUT_APK.bat`로 APK를 설치한다. Unity Android SDK의 ADB를 자동 탐색한다. 여러 기기가 연결돼 있으면 `-Serial`로 정확한 기기를 지정한다.
4. Link를 종료하고 Quest의 **알 수 없는 출처 → G1 Quest Input Observation**을 실행한다. Native APK 실행과 기존 PC Link 화면의 동시 사용을 전제로 하지 않는다. 설치 후 USB를 빼도 입력 전송은 Wi-Fi로 이루어진다.
5. 손을 펴고 양손·머리를 움직인 다음 index pinch를 해본다. Quest의 `L/R tracked=True`, PC의 `accepted` 증가를 확인한다. pinch는 기록만 하며 engage·복귀·모터 동작을 발생시키지 않는다.
6. APK를 종료하거나 PC 창에서 Ctrl+C를 눌러 기록을 마친다. 로그는 `logs/test_results/quest_apk/quest_*.jsonl`에 저장한다. 자동 삭제하지 않는다.

PC 자동 발견은 UDP 브로드캐스트를 사용한다. AP 격리, VLAN, VPN, 방화벽 때문에 발견이 차단될 수 있다. 수신기가 없거나 여러 곳에서 응답하면 APK는 입력을 전송하지 않는다. 이는 인증 프로토콜이 아니므로 신뢰하는 로컬 네트워크에서만 사용한다.

## 입력 형식

| 필드 | 의미 |
|---|---|
| `schema` | `g1.quest.raw_input.v1` |
| `observation_only` | 항상 `true`, 제어 패킷이 아님 |
| `session_id`, `sequence` | 앱 세션 식별자, 샘플 순번 |
| `source_time_s` | Quest Unity `realtimeSinceStartupAsDouble`, 초 |
| `clock_source` | `quest_unity_realtime_since_startup` |
| `frame` | `unity_tracking_origin_lh_xright_yup_zforward` |
| `send_hz` | 목표 전송 주기 60; 센서 신규 측정률이나 실측 전송률 보장이 아님 |
| `focused`, `head_tracked` | 앱 입력 포커스, 머리 추적 여부 |
| `head` | 머리 `position_m[3]`, `quaternion_xyzw[4]` |
| `left`, `right` | `tracked`, `high_confidence`, `pinch`, `wrist`, `index_base`, `middle_base`, `pinky_base` |
| 각 pose | tracking origin 기준 위치 m, 회전 quaternion x/y/z/w |

좌표계는 Unity의 왼손 좌표계 x=오른쪽/y=위/z=앞이다. 아직 MuJoCo/G1 좌표 변환을 하지 않는다. 손목은 skeleton type에 따라 legacy wrist-root 또는 OpenXR wrist를 선택하며 palm을 대신 사용하지 않는다. 손가락 기준점은 향후 기존 anatomical hand orientation과 연결할 때 사용할 원본이다. 추적이 없으면 해당 pose를 유효한 입력으로 사용하지 않는다.

수신 JSONL 스키마는 `g1.quest.observation.record.v1`이다. `sample` 외에 **원본 JSON 평문**, PC `time.monotonic()` 수신 시각, 송신 주소, sequence gap, 세션 첫 샘플 여부를 보존한다. Quest와 PC clock은 정렬하지 않았으므로 timestamp 차이를 물리 지연으로 해석하지 않는다. ACK는 **PC가 형식을 검증하고 버퍼에 기록했다**는 뜻이며 파일의 영구 저장이나 G1 수신/실행을 증명하지 않는다. 1초 간격으로 파일을 flush하고 종료 시에도 flush한다.

잘못된 JSON, 중복 key, 비유한 값, 누락 pose, 잘못된 quaternion, 같은 세션의 역순/중복 sequence·timestamp는 거부한다. 원본 입력을 기존 포트로 전달하는 코드·SDK/DDS/publisher는 없다. 다음 단계의 PC Unity network adapter는 이 측정이 실제 Quest에서 확인된 후 별도로 연결한다.

## 빌드

Unity Android Build Support (SDK/NDK/JDK)가 필요하다. 새 isolated 작업본에서 `G1_QUEST_OBSERVATION_APK`에 새 출력 경로를 지정하고 `G1QuestObservationBuild.Build`를 batch executeMethod로 호출한다. 기존 SampleScene 대신 독립 관측 씬만 빌드한다. Android ARM64/IL2CPP, 최소 API 32, application ID `kr.kaeri.g1questobservation`, Unity splash 없음. SDK가 주입하는 editor agent 설정·credentials는 이 APK의 build guard가 비활성화·제거한다. 기존 프로젝트의 사용자 DevAgentSettings를 변경하지 않는다.

## 검증 경계

수신기 테스트는 generated fixture 및 PC loopback이며 실제 Quest/G1 측정 데이터가 아니다. APK 빌드 성공과 실제 손 인식 성공은 구분한다. 현재 설치·실착 결과는 CHAT_HANDOFF에 기록하며, 확인 전에는 완료로 주장하지 않는다.

2026-10-08 실행 결과: 수신기 테스트 15/15 PASS (실제 로컬 UDP loopback 포함), 기존 손목 skeleton mapping C# 컴파일 테스트 1/1 PASS, installer PowerShell parser PASS, Portable bundled Python 수신기 시작/종료 smoke PASS. 새 isolated Unity 6000.5.4f1 작업본에서 Android Release APK 빌드 성공. AAPT로 application ID, ARM64, 최소 API 32/target API 36, hand tracking·internet permission을 확인했다. SDK의 editor agent credential 제거 build guard도 실행됐다. 기존 tracked hardware/backend/tools/teleop/기존 scene/model 파일 preservation check PASS.

APK는 Git 대상이 아닌 로컬 산출물이다: `C:\Users\user\Desktop\G1_Teleop_Portable\Builds\Quest_input_observation_20261008\G1QuestInputObservation.apk` (60,865,008 bytes). SHA256: `46FE0CC63B40B413D952A17177059ADEFF0BB1DC196F1715A2E5A4D88373AAC7`. 다른 PC에서는 이 APK를 별도로 복사하거나 위 빌드 절차로 생성한다. 설치/실제 native 손 인식/실제 Wi-Fi packet 수신은 아직 확인하지 않았다. USB 연결 자체는 Windows Meta USB interface에서 확인됐지만 ADB device 목록이 비어 있어 Quest 개발자 모드/디버깅 승인이 남아 있다.
