# 정밀 검토 계속 기록 5

기준 branch: `Y1048/Y` `refactor/teleop-architecture`

검토 기준 commit: `a9d9fbdd515938a1fa8fe1aeb638bea8c4afd616`

이 문서는 다음 검토 기록을 잇는다.

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1~R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20~R32
- [`REVIEW_20260903_CONTINUATION_2.md`](REVIEW_20260903_CONTINUATION_2.md): R33~R39
- [`REVIEW_20260903_CONTINUATION_3.md`](REVIEW_20260903_CONTINUATION_3.md): R40~R49
- [`REVIEW_20260903_CONTINUATION_4.md`](REVIEW_20260903_CONTINUATION_4.md): R50~R59
- 이 문서: R60~R67

이번 작업도 **검토 전용**이다. Production Python/C#/C++, configuration,
authorization, Unity scene/prefab, Windows network/firewall, G1, WSL runtime을 변경하거나
실행하지 않았다.

## 이번 본문 검토 범위

- 공통 camera frame/profile/shared-memory contract
- G1 `VideoClient.GetImageSample` → WSL TCP 5011 → Unity PiP 경로
- synthetic camera replay, Unity camera parser/status와 관련 tests/launchers
- Unity UDP 5005 → command adapter/watchdog/Mink command stream의 backlog·session 처리
- 현재 virtual-center controller와 `config/teleop.json`의 연결 여부
- Unity Android APK build/install 경로

`logs/review/20260903/source_checks.csv`의 117 full-text / 147 static-only 수치는 이번
추가 검토를 아직 반영하지 않는다. 정확한 coverage count는 ledger를 다시 생성한 뒤 갱신한다.

## 우선순위 갱신

기존 P1/P2 묶음을 유지하고, operator safety transition 보존을 R64로 추가한다.

```text
release/fault finalization : R1, R34, R46
final/acquire validation   : R2, R33, R40, R41, R42
runtime state supervision  : R50
safety-event preservation  : R3, R64
interruption/provenance    : R15, R35, R51, R65
experimental lowcmd path   : R43, R44, R45
```

현재 repository hardware authorization 값이 잠겨 있다는 사실은 유지된다.

## R60 · P2 · Camera sequence/capture time/source가 표시 경계까지 보존되지 않음

위치:

- `backend/g1_teleop/camera.py`
- `backend/g1_teleop/unitree_image_transport.py`
- `hardware/g1_arm_bridge/g1_camera_tcp_bridge.py`
- `Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs`
- `config/camera_profile.json`

공통 `CameraFrame`은 `sequence`, `capture_time_ns`, `source`를 갖는다. 그러나 simulation
shared-memory writer의 `write_frame()`은 image bytes만 넘기고, source frame의 sequence/time/source를
버린 뒤 전송 시점의 새 wall-clock millisecond timestamp를 만든다.

실제 G1 TCP bridge도 `VideoClient.GetImageSample()`이 반환된 뒤 `time.time_ns()`를 header에 넣는다.
이는 camera exposure/capture time이 아니라 bridge가 packet을 만든 시각이다. TCP v1 header에는
source type과 source session도 없다.

Unity는 header parser에서 sequence와 timestamp를 읽을 수 있지만 `ReceiveFrames()`에서 두 값을
`out _`로 버린다. `HasLiveFrame`은 JPEG가 Unity main thread에서 decode된 로컬 시각만으로 판단한다.
따라서 다음을 구분하거나 측정할 수 없다.

- duplicate/out-of-order/wrapped sequence
- bridge backlog 또는 오래된 frame
- live G1와 synthetic replay source
- camera capture → bridge → TCP → Unity decode의 단계별 latency
- 실제 frame drop rate

`camera_profile.json`은 첫 연결 시 `glass_to_quest_end_to_end_latency`와 `frame_drop_rate`를 측정하도록
기록하지만 현재 transport/result에는 이를 계산할 evidence가 없다. 영상은 명령 입력이 아니지만,
operator situational awareness와 hardware acceptance 결과가 오래된 화면을 최신으로 오인할 수 있다.

조치:

1. camera protocol v2에 source/session, source sequence, source capture time, bridge send time를 넣는다.
2. 각 clock domain과 동기화 방법을 명시하고 비교할 수 없는 monotonic clock을 직접 빼지 않는다.
3. Unity에서 session/sequence order와 maximum age를 검사한 뒤에만 green/live 상태를 갱신한다.
4. replay는 protocol source 자체로 표시하고 live source와 같은 status로 합치지 않는다.
5. duplicate, reverse order, delayed backlog, session restart, replay/live 전환 및 latency/drop metric 시험을 추가한다.

## R61 · P3 · 부분 TCP frame을 보낸 client가 Unity camera listener를 장시간 점유할 수 있음

위치:

- `Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs`

Unity receiver는 한 client를 `AcceptTcpClient()`한 뒤 header와 JPEG payload를
`NetworkStream.Read()` 반복으로 정확한 길이만큼 읽는다. per-frame/header/payload read deadline이나
`ReceiveTimeout`이 없다. Cancellation 시 `active_client.Close()`가 read를 깨우지만, 정상 Play 중
local client가 header 또는 payload 일부만 보낸 채 연결을 유지하면 receiver thread는 그 client 안에
머물고 다음 source를 accept하지 않는다.

`HasLiveFrame`은 1초 뒤 false가 되어 indicator가 red로 바뀌지만, 기존 client가 닫히기 전에는 새
정상 bridge/replay가 연결돼 복구할 수 없다. Listener가 loopback에 제한돼 있어 범위는 local process에
한정되지만, bridge crash 또는 partial write에서도 같은 operational stall이 가능하다.

조치:

- header/payload별 bounded read deadline과 maximum frame assembly time을 둔다.
- cancellation-aware async read 또는 socket receive timeout 후 client를 닫고 accept loop로 돌아간다.
- partial header, partial payload, zero-byte close, stalled client 이후 정상 reconnect 시험을 추가한다.

## R62 · P3 · Camera validation PASS가 실제 physical PiP 표시 성공을 증명하지 않음

위치:

- `tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat`
- `backend/tools/verify_camera_simulation.py`
- `hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py`
- `hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py`
- `tools/TEST_CAMERA_REPLAY_TO_UNITY.bat`
- `hardware/g1_arm_bridge/g1_camera_replay_tcp.py`

`VERIFY_HEAD_CAMERA_FOUNDATION.bat`는 backend unittest와 MuJoCo → shared-memory simulation verifier를
실행한다. 실제 physical path인 `VideoClient.GetImageSample` → TCP 5011 → Unity JPEG decode는 실행하지
않으며, `hardware/g1_arm_bridge/test_g1_camera_*`도 해당 backend discovery에 포함되지 않는다.

별도 replay launcher는 operator에게 Unity 화면을 직접 확인하도록 안내하지만 replay process의
`passed`와 exit code는 `sendall()`에 성공한 frame이 하나 이상인지로 결정된다. Unity가 header/JPEG를
실제로 decode하고 화면에 표시했는지에 대한 ACK가 없다. 상대 TCP listener가 bytes를 받은 직후
parser/decode에서 실패해도 sender는 이미 PASS가 될 수 있다.

따라서 현재 결과를 다음처럼 구분해야 한다.

```text
simulation render/shared-memory layout passed
TCP packet producer/parser unit tests passed
TCP bytes sent to a listener
Unity decoded and displayed ordered current frames
physical VideoClient path met latency/drop acceptance
```

조치:

- launcher/result 문구에 위 검증 단계를 명시한다.
- Unity가 decode한 session/sequence를 loopback ACK 또는 test result로 반환한다.
- physical path acceptance는 VideoClient/TCP/Unity와 latency/drop 측정을 포함한 별도 시험으로 둔다.

## R63 · P3 · Camera numeric/profile validation이 strict하지 않고 설정 surface가 서로 다름

위치:

- `backend/g1_teleop/camera_factory.py`
- `hardware/g1_arm_bridge/g1_camera_tcp_bridge.py`
- `hardware/g1_arm_bridge/g1_camera_replay_tcp.py`
- `config/camera_profile.json`
- `config/teleimager_real_d435i.yaml`
- `config/teleimager_simulation.yaml`
- `hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh`

`load_camera_profile()`은 width/height/fps를 `int()`로 coercion한다. 따라서 JSON boolean,
numeric string 또는 fractional float도 profile 검사를 통과하거나 truncation될 수 있다. Live/replay CLI의
fps/timeout/duration validation은 비교 연산만 사용하므로 NaN은 `<=`와 `>` 조건을 모두 통과할 수 있다.
현재 checked-in 값은 정상 finite 값이다.

Camera 설정도 서로 다른 경로에 존재한다.

```text
camera_profile.json / teleimager YAML : 640x480 @ 30 fps
active WSL VideoClient TCP starter    : --fps 20
teleop.json runtime head_camera_fps   : 30
```

각 값이 다른 목적이라면 그 목적과 owner가 명시돼야 한다. 현재는 이들 사이의 cross-validation이 없어
한쪽을 수정해도 실제 physical PiP rate가 바뀌지 않을 수 있다.

조치:

- bool/string/fraction/non-finite를 거부하는 strict typed camera schema를 사용한다.
- source별 width/height/fps owner를 하나로 두거나 명시적으로 파생한다.
- TeleImager shared-memory, direct RealSense, G1 VideoClient/TCP profile을 서로 다른 backend로 구분한다.
- NaN/inf/bool/string/fraction과 20↔30 drift 회귀 시험을 추가한다.

## R64 · P1 · UDP backlog에서 safety transition 뒤의 ACTIVE가 같은 poll에 재engage될 수 있음

위치:

- `backend/g1_teleop/live_receiver.py`
- `backend/g1_teleop/runtime_state.py`
- `backend/g1_teleop/mink_command_stream.py`
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py`
- `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py`
- 관련 backend tests

`receive_available_commands()`는 socket queue를 모두 비운다. Accepted packet을 순서대로 state machine에
적용하지만 반환값에는 마지막 command 하나와 `workspace_exit`/`operator_disengage` OR flag만 남긴다.
따라서 controller pause 또는 scheduling stall 중 다음 packet들이 같은 queue에 쌓일 수 있다.

```text
active -> pinch_disengaged -> later active
active -> workspace_exit   -> later active
```

State machine은 마지막 active까지 적용돼 다시 `active`가 된다. `MinkCommandStream.poll()`은 OR flag로
clutch를 reset한 직후 같은 poll의 마지막 active command를 사용해 다시 engage한다. 이때
`reset_clutch=true`와 `engage_clutch=true`가 동시에 반환되고, `input_command_mode`는 마지막 `active`다.
Virtual-center controller는 current pose에서 새 clutch reference를 잡으므로 즉시 position jump를 줄이지만,
Mink state packet에는 pinch/workspace transition이 한 frame도 남지 않는다.

Gate 7은 `active -> pinch_disengaged` edge를 intentional Regular return trigger로 사용한다. 위 backlog에서는
해당 edge가 downstream UDP 5008에 나타나지 않아 operator가 요청한 HOLD/Regular return phase가 생략될 수 있다.
Workspace fault도 downstream에서 관측되기 전에 같은 poll 안에서 해제될 수 있다.

조치:

1. safety transition을 단순 OR flag가 아니라 ordered event로 보존한다.
2. pinch/tracking/workspace transition을 처리한 poll에서는 later active를 적용하지 않거나 다음 cycle까지 격리한다.
3. `reset_clutch`와 `engage_clutch`가 같은 update에서 동시에 true가 되지 않게 한다.
4. downstream에 최소 한 개의 non-active state frame 또는 explicit event sequence를 전달한다.
5. `[active,pinch,active]`, `[active,workspace_exit,active]`, controller backlog와 정상 다음-cycle reengage 시험을 추가한다.

## R65 · P2 · 현재 Unity→Mink path가 sender address와 Unity source timestamp를 버림

위치:

- `Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs`
- `backend/g1_teleop/command_adapter.py`
- `backend/g1_teleop/live_receiver.py`
- `backend/g1_teleop/watchdog.py`
- `backend/g1_teleop/mink_command_stream.py`
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py`
- 관련 backend tests

실제 Unity legacy packet은 `timestamp=Time.realtimeSinceStartupAsDouble`와
`source=quest3s_head_relative`를 보낸다. Legacy adapter는 timestamp를 읽지 않고
`InternalCommand.source_time_ns=None`으로 만들며, source string은 allow-list 없이 진단용
`frame_id`로만 보존한다.

Mink UDP listener는 `0.0.0.0:5005`에 bind하고 `recvfrom()`의 sender address를 버린다. 각 packet의
arrival time도 kernel receive time이 아니라 Python이 queue에서 JSON parse를 마친 뒤
`time.monotonic_ns()`로 새로 찍힌다. 따라서 controller가 정지했다가 재개되면 queue에 남은 오래된
increasing-sequence packet이 방금 도착한 것으로 평가되어 timeout 동안 active target으로 사용될 수 있다.
Mink가 새 상태 packet을 만들면 이 stale Unity input은 다시 작은 `input_packet_age_s`를 갖게 되므로,
별도 승인된 Gate 7 hardware path에도 freshness가 재포장될 수 있다.

Unity의 realtime clock과 Python monotonic clock을 직접 빼면 안 되므로 clock-domain 계약 없이 단순히
기존 timestamp를 비교하는 것도 올바른 수정은 아니다.

조치:

- 현재 same-PC Link path에서는 UDP listener를 loopback 또는 명시적 source allow-list에 제한한다.
- launcher/session nonce와 sender identity를 command contract에 포함한다.
- source timestamp를 comparable wall clock, session clock-offset handshake 또는 explicit sender age로 정의한다.
- controller pause/backlog age와 maximum queue residence를 검증하고 오래된 batch를 폐기한다.
- 이전 session 재등장, foreign source, queued old active, 정상 live stream 시험을 추가한다.

## R66 · P3 · `config/teleop.json`이 현재 root VR controller의 authoritative 설정이 아님

위치:

- `config/teleop.json`
- `backend/g1_teleop/config.py`
- `backend/g1_teleop/__init__.py`
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py`
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py`

Typed loader는 public package export에 포함돼 있으나 현재 root virtual-center controller의 imports와
CLI에는 `load_teleop_config()` 또는 config path가 없다. Runtime/IK/collision 값은 controller source의
상수에서 직접 만들어진다.

동시에 checked-in `teleop.json`에는 typed `IKConfig`가 표현하지 않는 큰 `ik.fallback` subtree가 있다.
Loader는 unknown key를 거부하지 않아 fallback threshold/multiseed 값의 type, range와 실제 사용 여부를
검증하지 않는다. 예를 들어 JSON collision margin은 15 mm지만 current virtual-center는 20 mm soft target과
12 mm Gate 7 hard-stop 상수를 별도로 사용한다.

영향:

- 사용자가 `teleop.json`을 수정해도 현재 기본 controller 동작이 바뀌지 않을 수 있다.
- config와 hardcoded source가 조용히 drift하고, unknown/typo field도 loader PASS가 될 수 있다.

조치:

- active controller를 typed config에 실제로 연결하거나 파일을 non-authoritative/legacy로 명확히 분류한다.
- 사용하는 fallback 구조를 dataclass/schema에 포함하거나 제거한다.
- unknown key를 fail-closed 또는 warning으로 처리하고 current controller constants와 config parity test를 둔다.

## R67 · P2 · Unity APK builder와 installer가 서로 다른 output path를 사용함

위치:

- `Unity_G1_VR/Assets/Editor/G1VRBuild.cs`
- `tools/BUILD_AND_INSTALL_VR_APK.bat`

`Application.dataPath`는 `<repo>/Unity_G1_VR/Assets`다. C# build method는 여기에
`../Builds/G1TeleopVR.apk`를 결합하므로 정규화된 output은 다음이다.

```text
<repo>/Unity_G1_VR/Builds/G1TeleopVR.apk
```

반면 BAT는 다음 파일을 검사하고 ADB에 넘긴다.

```text
<repo>/Builds/G1TeleopVR.apk
```

따라서 정상 build 뒤에도 root APK가 없으면 BAT가 실패로 판정할 수 있다. 더 위험한 경우는 root path에
과거 APK가 남아 있을 때다. 현재 build는 project 내부에 새 APK를 만들고 BAT는 존재하는 오래된 root APK를
설치할 수 있다. 이는 R59의 stale artifact/device binding 문제를 직접 강화한다.

조치:

1. build와 install이 사용할 절대 output path를 하나의 source of truth로 만든다.
2. build 전에 target artifact를 제거하고 build report의 실제 output path/hash/mtime을 기록한다.
3. 그 exact artifact만 지정 device serial에 설치한다.
4. repository/project layout을 임시 directory로 재현하는 path-resolution regression test를 추가한다.

## 검토했으나 이번에 새 finding으로 올리지 않은 사항

- G1 live camera bridge는 `VideoClient.GetImageSample`만 호출하고 motor/mode/camera-setting command를
  만들지 않는다. WSL starter와 Unity listener도 output/listen address를 loopback으로 제한한다.
- Synthetic camera replay 화면에는 `OFFLINE REPLAY - NOT LIVE G1 VIDEO` banner가 들어가 있어 사람이
  정상 화면 전체를 보면 source를 구분할 수 있다. R60은 protocol/status level provenance가 없다는 문제다.
- Unity camera receiver는 pending JPEG 하나만 유지해 decode backlog를 bounded latest-frame slot으로 만든다.
- Current checked-in camera dimensions, fps and timeout values are finite and within the intended normal range.
- Current controller resets and re-captures the clutch reference on a same-poll session/safety reset, so R64는
  즉시 큰 target jump를 재현했다는 주장과 다르다. 문제는 required safety state/Regular return event가
  downstream에 보존되지 않는다는 점이다.
- Android build source path mismatch는 정적 path resolution으로 확인했다. Unity build와 ADB install은
  이번 검토에서 실행하지 않았다.

## 코드 수정과 실행 여부

```text
Production Python/C#/C++ 수정 : 없음
Config/authorization 수정      : 없음
Unity scene/prefab 수정         : 없음
Windows network/firewall 변경   : 없음
G1 파일/서비스/state 변경      : 없음
WSL/Unity/G1 실행               : 없음
Repository test 실행            : 없음
Hardware publisher 생성         : 없음
```

이번 commit은 이 review 문서만 추가한다. 수정 작업은 별도 단계로 분리하며, physical output은
별도 명시적 승인 전까지 계속 잠근다.
