# Unity 양손 → 양팔 MuJoCo 시뮬레이션

## 현재 범위

양손 입력을 같은 프레임에 담아 Python의 14축 coupled IK로 보낸다.
고정 베이스 운동학 시뮬레이션이며 G1 전원/연결이 필요하지 않다.
기존 오른팔 씬을 복사해 별도 씬을 만드는 메뉴를 추가했다.
기존 dirty Desktop 작업본에는 이번 파일을 덮어쓰지 않았다.

## 실행 순서

1. 이 브랜치의 clean checkout에 있는 `Unity_G1_VR` 프로젝트를 Unity
   **6000.5.4f1**로 연다. Meta 패키지 import와 C# 컴파일 완료를 기다린다.
2. Play를 끈 상태에서 메뉴 **G1 Teleop → Create Separate Bimanual Simulation Scene**.
   `Assets/Scenes/BimanualSimulation.unity`를 생성하고 연다.
   이미 생성됐으면 해당 씬을 직접 연다. 메뉴는 기존 씬을 덮어쓰지 않는다.
3. 같은 checkout의 `tools\START_BIMANUAL_UNITY_SIM.bat`를 실행한다.
4. Quest/Link 손 추적을 켜고 Unity Play. MuJoCo 창에서 로봇 팔을 확인한다.
5. 두 손목을 양쪽 구에 0.35초 맞추면 함께 engage한다.
6. 어느 한 손의 엄지–검지 pinch를 0.5초 유지하면 **양팔이 함께 복귀**한다.
7. READY 후 pinch를 풀고 손을 구 밖으로 옮겼다가 다시 두 손을 맞추면 재engage한다.
8. 종료는 Unity Play 해제, MuJoCo 창 닫기 순서다. 실제 로봇 종료 절차가 아니다.

기존 오른팔/Robot/Relay BAT는 이 시험과 함께 실행하지 않는다.
기본 UDP 5020이 점유됐으면 프로세스를 확인한다. 런처는 기존 프로세스를 종료하지 않는다.
현재는 Quest 안에 engage 구/상태만 표시하며, **양팔 로봇은 PC MuJoCo 창에서 본다**.
기존 Unity 오른팔 preview는 복사본에서 제거한다. 양팔 Unity preview는 아직 없다.

## 입력/상태 동작

- 양손은 함께 engage/복귀한다. 좌우 독립 engage는 이번 단계에 넣지 않았다.
- 어느 손이든 추적 손실 <0.35초이면 시뮬레이션 자세를 유지한다.
  0.35초 이상이면 양팔 복귀. 패킷이 0.75초 이상 끊겨도 복귀한다.
- 복귀가 충돌 때문에 불가능하면 `blocked`. 자동 우회/자동 재시작하지 않는다.
  이때 시뮬레이터 재시작이 필요하다. 기존 샘플 경로 검사 한계가 그대로 적용된다.
- READY feedback이 신선하지 않으면 Unity는 새 engage를 만들지 않는다.
- 초기 active 패킷만 받아서는 engage하지 않는다. inactive → active 입력이 필요하다.
  복귀 중 engage도 무시하며 완료 뒤 새 inactive → active 전환을 요구한다.
- 두 손의 `Hand_WristRoot` pose를 사용한다. 최초 손 추적 때 고정한 head yaw
  프레임으로 표현하고, 각 engage에서 양손 위치/회전을 각각 영점화한다.
  이후 손 위치 변화는 1:1로 초기 로봇 손목에 더한다.
- 기존 오른팔 anatomical frame, body translation 보정, 필터/자세 개선 전체를
  복제한 경로가 아니다. 실제 손 방향/원점 일치와 자세 자연스러움은 Quest에서
  별도로 확인해야 한다. 이 비교 후보를 기존 오른팔 실행본으로 승격하지 않았다.

## 프로토콜

Unity → Python: **UDP 127.0.0.1:5020 / UTF-8 JSON**, 약 60Hz.
Python → Unity: 동일 소켓의 Unity 임시 source port로 상태 feedback.
기존 5005/5008/5014/5016/5017 경로를 사용하지 않는다.

```json
{"schema":"g1.bimanual.unity.sim.v1","simulation_only":true,"session":"example","sequence":1,"sender_time_s":1.2,"engage":false,"return_home":false,"left":{"tracked":true,"position_m":[-0.22,-0.24,0.38],"quaternion_wxyz":[1,0,0,0]},"right":{"tracked":true,"position_m":[0.22,-0.24,0.38],"quaternion_wxyz":[1,0,0,0]}}
```

入力座標: Unity 고정 heading 좌표계、+X右/+Y上/+Z前、m、quaternion **wxyz**。
Pythonで +X前/+Y左/+Z上へ変換する。回転も同じ基底変換を適用する。
Unity sender timestampは`Time.realtimeSinceStartupAsDouble`。
Python受信記録は`time.monotonic()`。両clockの絶対値を引き算しない。
sequenceとsender timestampが増えないパケットは採用しない。
これは遅延の実測値や送信時刻からの厳密な鮮度保証ではない。

状態 schema: `g1.bimanual.unity.sim.state.v1`、`simulation_only=true`、
`session/sequence/state/reason`。状態は ready/tracking/returning/blocked。
データには joint index 15..28順の名称とq(rad)もPythonログで記録する。

## 記録

`logs/test_results/bimanual/unity_<timestamp>.jsonl` に受信時刻、
採否、入力`raw_json_text`、状態/関節値を記録する。
これは実測G1ログではなく、Quest入力と시뮬레이션出力である。
生成ログは各PCローカルに残りGit同期されない。

## 既存経路の保護

SampleScene自体は保存変更しない。コピー内の旧G1コンポーネントは削除する。
disabledだけではAwakeが動くため削除が必要。
さらに `G1KeypadLocomotionUdpSender` の Install/Awake に、
シーン内に`G1BimanualSimulationSender`がある場合のみ自動起動を止めるガードを追加。
通常の右腕シーンの入力条件・プロトコル・値は変更しない。
同じUnity実行中に旧ライブシーンから切り替える運用は対象外。Play停止後に開く。

## 実行した検証と未確認事項

- MuJoCo 3.12.0: `test_bimanual*.py` **13件通過**。
  前段6件に加えて形式拒否、座標/回転変換、初期active拒否、pinch復帰、
  再engage、tracking-loss/timeout、順序/セッション、blockedを検査。
- Pythonプロセスを起動し、生成入力を実際のlocalhost UDPで送受信して
  ready→trackingとログを確認。G1やSDKは使っていない。
- Unity 6000.5.4f1のUnity DLLと既存Meta `Oculus.VR.dll`を参照して
  新runtime/editor C#と変更したkeypadファイルをRoslynでコンパイル成功。
  JsonUtility入力フィールド未代入警告・既存deprecated API警告等は残る。
- **Unity Editorでの完全なproject import/scene生成/Play、Quest実機入力、
  GUI表示、キー送信bootstrapの実ランタイム停止は未検証。** DLL参照コンパイルを
  それらの確認と混同しない。次のユーザー試験で確認する。

実G1経路、モーター、PD、XML/meshファイル、既存右腕IKは変更していない。
