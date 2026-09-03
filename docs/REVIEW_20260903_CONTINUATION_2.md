# 정밀 검토 계속 기록 2

기준 branch: `Y1048/Y` `refactor/teleop-architecture`

검토 기준 commit: `ecda6e54d172679cb28863a89a9068d6f48b62af`

이 문서는 다음 검토 기록을 잇는다.

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1~R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20~R32
- 이 문서: R33~R39

이번 작업도 **검토 전용**이다. Production Python/C#/C++, Unity scene/prefab,
configuration, authorization, G1, WSL runtime을 변경하거나 실행하지 않았다.

## 이번 본문 검토 범위

- Gate 6 measured-pose HOLD contract, runtime, interruption test와 SDK message verifier
- Gate 7 algorithm/order contract, Windows relay, WSL hardware adapter, dry-run과 profile tests
- right-arm Jog config/command frame 및 collision permit 관련 tests
- root VR launcher와 wrist-frame static contract test
- Unity `SampleScene.unity`, setup/batch validator, G1-owned script GUID/meta 연결
- official G1 prefab의 일부 joint-node 연결과 package manifest/lock

`logs/review/20260903/source_checks.csv`의 기존 117 full-text / 147 static-only 수치는
이번 검토를 아직 반영하지 않는다. 정확한 coverage count는 ledger를 다시 생성한 뒤 갱신해야 한다.

## 우선순위 갱신

기존 R1/R2/R3/R15 우선순위를 유지하되, 아래 두 P1도 물리 시험 확대 전에 같은 묶음으로
수정해야 한다.

```text
release/fault finalization : R1, R34
final/acquire validation   : R2, R33
interruption/provenance    : R3, R15
```

## R33 · P1 · Gate 7 acquire가 한 개의 ACTIVE packet만으로 authority를 올림

위치:

- `hardware/g1_arm_bridge/gate7_live_arm_sdk.py`
- `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py`
- `hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py`

`WaitForFirstActiveMink()`는 형식상 ACTIVE인 packet 하나를 받으면 publisher boundary를
통과시킨다. 이 단계에서는 다음을 확인하지 않는다.

- `input_packet_age_s`가 Gate 7 timeout 안인지
- 해당 session/source가 이후에도 계속 살아 있는지
- 같은 sender가 acquisition 동안 계속 ACTIVE packet을 보내는지

첫 packet은 함수 안에서 소비된다. 그 뒤 약 5초의 acquisition 구간에서는 Mink socket을
읽거나 Gate 7 input watchdog을 실행하지 않고, 고정한 acquisition target으로 Arm SDK weight를
계속 올린다. 따라서 packet 하나만 도착하고 Unity/Mink가 즉시 종료돼도 publisher가 생성되고
weight가 최대값까지 올라갈 수 있다. 이후 control 단계에서 입력 부재를 HOLD로 처리하지만,
authority acquisition은 이미 끝난 뒤다.

같은 acquisition 분기는 LowState freshness와 mode만 확인하고, 현재 양팔과 고정 acquisition
target 사이의 `maximum_target_error` 및 arm joint-limit validation을 호출하지 않는다.
`build_measured_hold_frame()` 자체도 이 검사를 수행하지 않는다. acquisition 도중 실측 팔이
움직여도 command는 시작 target을 유지한 채 weight가 증가한다.

이 finding은 R4의 timestamp/freshness 계산 문제와 구분된다. 여기서는 packet age가 명백히
오래됐거나 stream이 바로 사라져도 **publisher 생성 전 acquire gate**가 이를 사용하지 않는 것이 문제다.

조치:

1. publisher 생성 전에 ACTIVE packet의 embedded/transport freshness를 검사한다.
2. acquisition 전체에서 승인된 session의 ordered ACTIVE stream이 계속 fresh한지 확인한다.
3. 매 acquisition tick마다 `validate_measured_hold()`와 현재 mode/LowState 검사를 함께 수행한다.
4. command loss, session change, measured-target error, joint-limit fault가 발생하면 weight를 더
   올리지 않고 검증된 release 경로로 전환한다.
5. 한 packet 뒤 단절, stale ACTIVE packet, acquisition 중 10도 이상 measured drift,
   session 교체와 정상 연속 stream 회귀 시험을 추가한다.

## R34 · P1 · Gate 6 runtime fault가 release 없이 종료되고 weight=0으로 기록됨

위치:

- `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py`
- `hardware/g1_arm_bridge/test_gate6_interrupt_release.py`
- `hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py`

정상 종료와 signal 기반 Ctrl+C는 loop 안에서 release schedule을 진행한다. 그러나 publisher
생성 후 다음과 같은 exception이 발생하면 outer `except`로 바로 이동한다.

- LowState 소실/stale
- `mode_pr` 또는 `mode_machine` 변경
- measured HOLD validation 실패
- SDK frame/CRC/publisher write 예외

이 `except`에는 weight ramp-down이나 zero-weight tail 전송이 없다. status에는
`weight=0.0`, `command_output_enabled=false`를 기록하지만 마지막으로 실제 전송한 frame은
nonzero weight일 수 있다. 프로세스 종료나 firmware timeout이 최종적으로 authority를
돌려줄 가능성과, 소프트웨어가 zero-weight release를 완료했다는 증명은 구분해야 한다.

현재 interruption test는 이미 최대 weight에서 정상 release profile을 수학적으로 생성할 뿐,
active loop의 fault branch를 실행하지 않는다. R3의 acquire 중 Ctrl+C weight 상승 문제와도
별개의 경로다.

조치:

1. publisher 생성 이후 모든 종료를 하나의 idempotent release finalizer로 통합한다.
2. 마지막 성공 전송 weight에서 단조 감소시키고 가능한 zero tail을 별도로 시도한다.
3. release 실패 시 status를 성공/weight zero로 기록하지 말고 실제 마지막 전송값과 fault를 남긴다.
4. LowState stale, mode change, validation reject, first release write failure, zero-tail 중간 실패를
   fake publisher로 주입하는 회귀 시험을 추가한다.
5. 마지막 명령 전송, DDS writer 제거, firmware/Regular authority 복귀 확인을 서로 다른 결과로 기록한다.

## R35 · P2 · Gate 7 hardware 입력의 source/session provenance가 닫혀 있지 않음

위치:

- `hardware/g1_arm_bridge/gate7_mink_wsl_relay.py`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk.py`
- `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py`
- `config/g1_gate7_*_hardware_output.json`

Windows relay는 localhost UDP 5008만 받지만 WSL hardware adapter는 설정상
`0.0.0.0:5013`에 bind한다. `_ReceiveLatestMink()`는 sender address를 읽고 버리며, relay가
전달한 packet인지 확인하는 token/source allow-list가 없다. 따라서 adapter가 명시적으로
승인되어 실행 중일 때 UDP 5013에 도달할 수 있고 strict JSON을 만들 수 있는 다른 process도
relay를 우회해 publisher 시작 조건 또는 control input을 제공할 수 있다.

session order guard도 현재 session 하나만 기억한다. relay와 Gate 7 controller 모두 session ID가
달라지면 sequence 기준을 즉시 초기화한다. 따라서 다음 순서를 retired-session 재등장으로
거부하지 않는다.

```text
session A sequence 100 -> session B sequence 0 -> delayed session A sequence 101/102
```

첫 재등장 packet은 session sync HOLD가 되지만 다음 증가 packet은 다시 tracking에 사용될 수 있다.
이 finding은 R12의 display-only mirror rollback보다 직접적인 command-input 경로이며, R15의
recorded replay provenance와 같은 근본 원인을 공유한다. Repository config가 잠겨 있다는 사실은
유지되며, 이것만으로 hardware가 자동으로 unlock된다는 뜻은 아니다.

조치:

- adapter를 가능한 특정 WSL/loopback interface에 bind하거나 source allow-list를 적용한다.
- relay가 생성한 짧은 수명의 실행 token/session nonce를 packet contract에 포함한다.
- 승인된 live session과 replay/offline source를 명시적으로 구분한다.
- retired session ID를 bounded history로 폐기하고 명시적인 takeover 절차만 허용한다.
- direct-to-5013 sender, A→B→A, stale previous session, 정상 restart와 relay packet을 회귀 시험한다.

## R36 · P2 · Gate 7 live dry-run PASS 조건이 denied/rejected 결과를 무시함

위치:

- `hardware/g1_arm_bridge/gate7_live_dry_run.py`
- `hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py`

manual dry-run result는 다음 조건만으로 PASS와 exit code 0을 만든다.

```text
candidate_frames > 0 and Unitree SDK not imported
```

따라서 한 번이라도 candidate가 생성되면 이후 `denied_frames`, malformed/reordered Mink reject,
LowState reject, final state/reason과 무관하게 PASS가 될 수 있다. process E2E test 하나는 별도로
`denied_frames == 0`을 요구하지만 실제 manual recording/dry-run의 result predicate에는 연결되지 않는다.

영향:

- 긴 Quest run에서 대부분 frame이 거부됐어도 “candidates generated without robot output” PASS로
  요약될 수 있다.
- R20과 같이 JSON/console/exit-code의 성공 의미가 품질 acceptance와 다르다.

조치:

- transport-only, candidate-generated, clean-run acceptance를 다른 status로 분리한다.
- clean PASS에는 rejected/denied 허용 기준, final state와 최소 active duration을 명시한다.
- 허용 가능한 의도적 deny와 parser/order/LowState deny를 reason별로 구분한다.
- 첫 candidate 이후 지속 deny, malformed burst, stale LowState와 정상 run을 process test로 추가한다.

## R37 · P2 · Arm SDK gain과 35-slot frame validation이 완전하지 않음

위치:

- `hardware/g1_arm_bridge/arm_sdk_hold_contract.py`
- `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog.py`
- `hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py`

Gate 6/Jog config loader는 gain을 finite number로만 읽는다. `proximal_kp`, `proximal_kd`,
`wrist_kp`, `wrist_kd`가 음수여도 config validation을 통과한다. frame builder는 이 값을 arm
slots에 그대로 넣고, `validate_command_frame()`도 gain의 부호를 검사하지 않는다.
Repository의 현재 gain 값은 모두 양수이며 이 finding은 현재 파일이 이미 음수라는 뜻이 아니다.

`validate_command_frame()`의 35-slot 검사도 부분적이다.

- body index 0..28의 non-arm mode/gain/dq/tau는 검사한다.
- arm slots 15..28의 mode가 정확히 1인지, gain이 허용 범위인지 검사하지 않는다.
- weight slot 29는 q와 `frame.weight`의 일치만 확인한다.
- slot 29의 mode/dq/tau/kp/kd와 reserved slot 30..34는 검사하지 않는다.
- `_apply_frame()`은 이 35개 값을 모두 SDK message로 복사한다.

현재 builder가 reserved 값을 0으로 초기화하므로 정상 builder 출력이 곧바로 잘못됐다는 뜻은
아니다. 문제는 config와 최종 command boundary가 스스로 주장하는 허용 범위를 완전히 검증하지
않는다는 점이다.

조치:

- Kp/Kd를 finite nonnegative 값으로 제한하고 profile별 상한을 둔다.
- arm mode, weight/reserved slots의 모든 필드를 exact contract로 검사한다.
- final SDK message를 publisher write 직전에 다시 검증한다.
- negative gain, arm mode 0/255, nonzero reserved dq/tau/gain, NaN과 정상 builder frame 시험을 추가한다.

## R38 · P3 · wrist-frame contract test가 현재 기본 controller를 검사하지 않음

위치:

- `MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py`
- `tools/TEST_MINK_WRIST_FRAME.bat`
- `START_VR_HAND_TO_MUJOCO.bat`

root launcher의 기본 controller는 `run_mink_g1_right_arm_virtual_center_live.py`다. 그러나
wrist-frame static test는 비교용 baseline인 `run_mink_g1_right_arm_prototype.py`만 읽는다.
테스트가 PASS해도 현재 기본 virtual-center의 외부 yaw-wrist contract, 내부 roll/yaw task 분리,
feasible-target 연결은 검사하지 않는다.

또한 이 검사는 몇 개의 source 문자열과 `operator_forward_scale=1.00`만 확인한다. Unity scene의
serialized references, 실제 axis mapping 함수, rotation 변환, current launcher 선택을 실행하거나
수치 비교하지 않고 “Quest/Unity/MuJoCo/Mink wrist frame contract is unified”라고 출력한다.

조치:

- launcher가 선택한 default controller path를 test가 직접 해석한다.
- virtual-center의 external yaw-wrist와 internal roll/yaw split을 별도 assertion으로 둔다.
- mapping 함수와 대표 SE(3) fixture를 수치 검증한다.
- baseline 전용 검사는 명칭과 PASS 문구를 `baseline_static_source_contract`로 제한한다.

## R39 · P3 · Unity engagement hold 시간이 source/scene/launcher에서 다름

위치:

- `Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs`
- `Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs`
- `Unity_G1_VR/Assets/Scenes/SampleScene.unity`
- `Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs`
- `START_VR_HAND_TO_MUJOCO.bat`

현재 source field 기본값과 launcher 안내는 engagement hold를 약 0.55초로 설명한다. 그러나 실제
checked-in scene의 serialized 값은 0.35초이며, Editor setup도 매번 0.35초를 기록한다. Unity는
serialized scene 값을 사용하므로 현재 SampleScene runtime 기준은 source initializer가 아니라
0.35초다.

batch validator는 alignment 사용 여부와 tracking-loss debounce를 검사하지만
`engagement_hold_duration`의 canonical 값을 검사하지 않는다. 따라서 어느 값이 의도된 정책인지
소스와 실행 화면만으로 일관되게 판단할 수 없다. 같은 계열의 engagement distance/stability도
source initializer와 setup override가 다르지만, 이번 finding은 launcher가 명시적으로 잘못
안내하는 hold 시간에 한정한다.

조치:

- 0.35 또는 0.55 중 승인된 값을 하나 정한다.
- component initializer, scene setup, serialized scene, validator, launcher 안내를 같은 값으로 맞춘다.
- 새 scene 생성과 기존 scene reload 모두 같은 값을 사용하는 Editor test를 추가한다.
- 실기 측정 결과에는 frame rate와 실제 unscaled elapsed time을 함께 기록한다.

## Unity serialized graph 확인 결과와 한계

현재 `SampleScene.unity`의 G1-owned script GUID는 각 `.meta`와 일치했다.

- `G1ExistingTargetUdpSender`
- `G1UnityRightArmPreview`
- `G1ExistingHandTargetBinder`
- simulation/hardware `G1RobotStateUdpReceiver`
- `G1HeadLockedCamera`

`G1_Teleoperation_System`의 sender/binder/preview와 UDP 5006/5010 receiver fileID 연결도 현재
scene 본문에서 확인했다. simulation receiver는 Mink source, hardware receiver는 strict
`g1_lowstate_read_only` source로 직렬화되어 있다. official G1 prefab에서 확인한
`G1JointNode` script GUID도 현재 `.meta`와 일치했다.

다음은 아직 전체 graph 검증으로 부르지 않는다.

- Meta XR package prefab GUID와 stripped component의 package-cache 원본
- official G1 prefab의 모든 mesh/material GUID와 모든 29 joint-node parent/axis 값
- Play 이후 runtime-created object와 serialized scene의 최종 일치
- Android/Quest build에서의 asset stripping 및 package import 결과

`Packages/manifest.json`과 `packages-lock.json`은 Meta XR 205.0.0 계열을 고정하지만, 저장소에
package cache 전체가 없으므로 package-owned prefab GUID를 GitHub 파일만으로 끝까지 역추적하지 않았다.

## 검토했으나 이번에 새 finding으로 올리지 않은 사항

- 현재 scene에는 G1-owned teleoperation component stack이 한 세트이며 확인한 내부 fileID는
  존재했다. 전체 prefab/package graph가 완전하다는 보증은 아니다.
- `validate_right_arm_jog_collision_path.py`는 independent one-joint path를 검사하고 runtime은
  joint switch 전에 start pose 복귀를 요구한다. 이번 정적 검토에서 그 정책을 우회하는 새
  경로는 확인하지 않았다. 기존 R8/R9/R10의 precheck/full-body/collision assumptions는 상속한다.
- Gate 7 first-live/visible profile tests는 repository lock과 numeric envelope를 확인한다.
  이 PASS는 mesh collision, dynamics, actual DDS timing 또는 release failure injection을 포함하지 않는다.
- Gate 6 interruption offline test의 정상 0.2→0 release profile은 단조였다. R3과 R34는
  실제 interrupt/fault 분기 연결이 그 수학 profile과 다르다는 문제다.
- LowState/VR dry-run launcher는 detached 창의 수명과 cleanup을 대부분 운영자에게 맡긴다.
  실패 분기에서 orphan process가 남을 수 있으나 이번 문서에서는 기존 process-lifecycle 검토의
  운영 한계로 기록하고 별도 severity finding으로 중복 분류하지 않았다.

## 코드 수정과 실행 여부

```text
Production Python/C#/C++ 수정 : 없음
Config/authorization 수정      : 없음
Unity scene/prefab 수정         : 없음
G1 파일/서비스/state 변경      : 없음
WSL/Unity/G1 실행               : 없음
Repository test 실행            : 없음
Hardware publisher 생성         : 없음
```

이번 commit은 이 review 문서만 추가한다. R33/R34는 물리 시험 확대 전 우선 수정 대상이다.
수정 후에는 fake publisher/fake LowState로 acquire-loss와 fault-release를 먼저 재현하고,
physical output은 별도 명시적 승인 전까지 계속 잠근다.
