# 정밀 검토 계속 기록 3

기준 branch: `Y1048/Y` `refactor/teleop-architecture`

검토 기준 commit: `c0b667f129ac74d99d2657a035ef53c58b20b4f1`

이 문서는 다음 검토 기록을 잇는다.

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1~R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20~R32
- [`REVIEW_20260903_CONTINUATION_2.md`](REVIEW_20260903_CONTINUATION_2.md): R33~R39
- 이 문서: R40~R49

이번 작업도 **검토 전용**이다. Production Python/C#/C++, configuration,
authorization, Unity scene/prefab, G1, WSL runtime을 변경하거나 실행하지 않았다.

## 이번 본문 검토 범위

- Gate 6 startup precheck와 measured-pose HOLD publisher boundary
- Gate 7 active packet collision evidence와 publisher-boundary state binding
- right-arm Jog runtime, pose-bound collision permit, full-authority shoulder profile 및 관련 tests/launcher
- `START_VR_HAND_TO_MUJOCO.bat`의 process identity/liveness 판정
- `g1_regular_arm_pose.json`과 Regular pose loader
- TWIST2 오른팔 수동 실험 C++ 전체 본문, 공통 header, CMake, README와 offline verifier

`logs/review/20260903/source_checks.csv`의 117 full-text / 147 static-only 수치는
이번 추가 검토를 아직 반영하지 않는다. 정확한 coverage count는 ledger를 재생성하거나
검토 경로와 다시 대조한 뒤 갱신해야 한다.

## 우선순위 갱신

기존 P1을 유지하며 다음 항목을 물리 시험 확대 전 같은 묶음으로 처리해야 한다.

```text
release/fault finalization : R1, R34, R46
final/acquire validation   : R2, R33, R40, R41, R42
interruption/provenance    : R3, R15, R35
experimental lowcmd path   : R43, R44, R45
```

현재 repository hardware authorization 값이 잠겨 있다는 사실은 유지된다. 아래 finding은
해당 physical path가 별도로 승인되어 실행될 때의 fail-closed 계약을 검토한 것이다.

## R40 · P1 · Physical publisher precheck가 현재 전신 state에 결박되지 않음

위치:

- `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog.py`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk.py`
- `hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py`

Gate 6의 `validate_precheck()`는 schema, decision, recovery flag, publisher/output flag와
결과 age만 확인한다. 현재 29관절 pose, mode snapshot, IMU/base evidence를 요구하지 않는다.
관련 unit test도 joint pose가 전혀 없는 payload를 valid precheck로 기대한다. Gate 6는 이후
새 LowState를 읽어 measured HOLD를 만들지만, 이 현재 자세가 precheck에서 collision/readiness를
검사한 자세와 같은지는 확인하지 않는다.

Gate 7과 right-arm Jog는 공통 `validate_snapshot_matches_precheck()`를 호출하므로 Gate 6보다
강하지만 비교 범위가 joint index 15..28, 즉 양팔 14축뿐이다. waist 12..14, legs 0..11,
base/IMU 상태는 publisher boundary의 precheck binding에 포함되지 않는다. Gate 7은 실제
publisher 생성 직전에 이 함수를 다시 호출하지만 비교 범위 자체는 동일하다.

영향:

- precheck가 `DIRECT_TELEOP_READY`였던 전신 configuration과 publisher를 여는 시점의
  configuration이 다를 수 있다.
- waist 또는 lower-body 변화는 arm-to-torso/body collision 및 지지 상태를 바꿀 수 있지만,
  양팔 값이 tolerance 안이면 현재 gate를 통과한다.
- Gate 6는 pose binding뿐 아니라 measured HOLD 시작점의 별도 collision validator도 없다.

조치:

1. precheck result에 현재 physical run이 요구하는 전신 joint/base/IMU/mode evidence와
   model/config hash를 명시한다.
2. publisher 직전 동일 snapshot 또는 허용 tolerance의 전신 snapshot인지 검사한다.
3. collision에 영향을 주는 값이 바뀌면 precheck를 재사용하지 말고 다시 계산한다.
4. Gate 6도 current measured HOLD pose 및 필요한 작은 복원 구간을 collision 검증한다.
5. arms unchanged + waist/leg changed, base tilt changed, exact match 및 stale precheck를
   fake LowState로 회귀 시험한다.

## R41 · P1 · Gate 7 active packet이 수치 collision clearance 없이 tracking 가능

위치:

- `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py`
- `hardware/g1_arm_bridge/gate7_mink_wsl_relay.py`
- `hardware/g1_arm_bridge/gate7_live_dry_run.py`

`parse_mink_arm_sample()`은 `right_arm.minimum_clearance_m`의 `null` 또는 누락을 허용한다.
Controller는 clearance가 없고 `collision_limited=true`이면 incomplete collision state로 HOLD하지만,
clearance가 없고 `collision_limited=false`이면 active tracking 경로를 계속 허용한다. Relay도
이 `null` 값을 canonical packet에 그대로 보존한다.

따라서 schema/source/session/sequence가 모두 정상이어도 다음 조합이 contract상 가능하다.

```text
input_command_mode = active
right_arm.active = true
right_arm.collision_limited = false
right_arm.minimum_clearance_m = null
```

이 경우 command target은 collision 수치 evidence 없이 Gate 7에 들어간다. 현재 Mink sender가
정상 실행 중일 때 대개 clearance를 제공한다는 사실과, parser/controller가 fail-closed contract로
이를 요구한다는 것은 별개다. R2의 final Ruckig-shaped command collision 누락과도 별도 문제다.

조치:

- active command에는 finite `minimum_clearance_m`를 필수로 한다.
- collision 검사 자체가 unavailable이면 `collision_state_unavailable_hold`로 fail-closed한다.
- schema version에 collision evaluator/model/config identity를 포함한다.
- active null/missing clearance, false flag + low clearance, true flag + high clearance,
  정상 packet을 회귀 시험한다.

## R42 · P1 · right-arm Jog collision permit이 현재 전신/model 및 최종 command에 유지되지 않음

위치:

- `hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog.py`
- `hardware/g1_arm_bridge/right_arm_jog_contract.py`
- `hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py`

Jog permit은 startup precheck pose에서 각 right-arm joint를 독립적으로 움직인 trajectory를
MuJoCo collision validator에 넣어 허용 offset 범위를 만든다. Runtime loader는 permit의 precheck
timestamp, 29관절 배열과 numeric bounds를 확인하지만 다음 provenance는 저장·검사하지 않는다.

- collision model/XML/mesh hash
- validator/config/code version
- joint-limit 및 contact policy hash

Runtime의 현재-pose 확인은 R40처럼 양팔 14축뿐이다. 첫 joint 선택 이후에는 precomputed permit을
사용하면서 current waist/legs/base 또는 다른 arm 변화에 대해 collision을 다시 계산하지 않는다.
기본 bounded Jog는 `hold_unselected_start_pose=false`이므로 선택하지 않은 arm target도 current
measured pose를 따라 바뀔 수 있다. `ArmJointJogController.advance()`의 final checks는 joint limit,
rate와 target-measured error이며 per-tick FK collision validator는 없다.

영향:

- permit을 만든 configuration에서는 안전했던 selected-joint range가 이후 전신 상태에서
  유효하지 않을 수 있다.
- model/config가 바뀌어도 같은 precheck artifact와 numeric bounds가 남아 있으면 permit loader가
  이를 식별하지 못한다.

조치:

1. permit에 model/mesh/config/validator hash와 생성 tool version을 기록하고 runtime에서 확인한다.
2. collision-relevant full-body state를 permit pose와 지속 비교한다.
3. 매 final command 또는 최소한 다음 swept segment를 current full-body pose에서 재검사한다.
4. permit invalidation 후 authority를 올리지 않고 검증된 release/hold로 전환한다.
5. waist/left-arm drift, model hash 변경, permitted endpoint 사이의 segment, joint switch,
   정상 one-joint run을 회귀 시험한다.

## R43 · P1 · TWIST2 오른팔 수동 path에 collision/workspace 및 acceleration/jerk envelope가 없음

위치:

- `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp`
- `references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp`
- `experiments/twist2_right_arm_manual/verify_offline.py`
- `experiments/twist2_right_arm_manual/README.md`

이 실험본은 `rt/lowcmd` 단일 전신 writer이며 keyboard mode에서 오른팔 7축 모두를 독립적으로
명령할 수 있다. `+`, absolute `0 rad`, `-` key는 각 joint soft limit 안에서 target을 바꾸고,
1~9 배속은 0.08~0.72 rad/s target rate를 선택한다. Writer는 추가 target-rate, joint-limit,
ideal PD torque clamp를 적용하고 IMU/deadman/state/temperature/velocity를 감시한다.

그러나 source에는 다음 검사가 없다.

- self/body/environment collision 또는 Cartesian workspace
- current full-body pose에 대한 selected target swept-path validation
- acceleration 또는 jerk bound
- 여러 right-arm joint command 조합의 collision envelope

자동 right-shoulder 30도 path도 endpoint joint limit만 검사한다. Offline verifier는 source derivative와
keyboard increment/rate/soft-limit 계산만 컴파일하며, README 역시 collision/실측 부호/안정성을
검증하지 않는다고 정확히 밝힌다.

영향:

- joint limit과 target velocity를 지켜도 elbow/wrist/hand가 torso 또는 다른 body에 닿는 조합을
  배제하지 못한다.
- speed multiplier 변경과 target 시작/정지는 rate는 제한하지만 acceleration이 순간적으로
  바뀌는 piecewise-linear command가 된다.

현재 이 파일은 experimental이며 실물 승인 상태가 아니다. 따라서 이 finding은 현재 main
Unity/Mink path가 자동으로 unsafe하다는 뜻이 아니라, 이 C++ binary를 physical test에 쓰기 전의
필수 차단 항목이다.

조치:

- 최초 physical test를 한 joint, 작은 pose-bound range와 낮은 speed로 제한한다.
- current full-body state를 사용하는 collision/path permit과 final writer-side segment check를 둔다.
- acceleration/jerk shaping을 추가하고 speed multiplier change도 같은 limiter에 통과시킨다.
- 실제 sign/response가 확인되기 전 absolute zero 및 2x~9x key를 잠근다.

## R44 · P2 · TWIST2 500 Hz writer의 output path가 damping latch로 완전히 감싸지지 않음

위치:

- `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp`

`write_cycle()`의 local `try/catch`는 state validation, desired snapshot과 command watchdog까지만
감싼다. 이후 LowCmd 구성, torque-bound 계산, CRC, `publisher_->Write(command)`와 statistics update는
catch 밖에 있다. Source comment는 handoff 뒤 potentially throwing operation을 latch 안에 둔다고
설명하지만 writer output 전체에는 해당되지 않는다.

정확한 Unitree recurrent-thread wrapper 및 `Write` 실패 동작은 저장소 source만으로 확인되지 않았다.
따라서 DDS/serialization/write 실패가 exception, return status 또는 thread termination으로 나타날 때
현재 코드가 반드시 `damping_`을 latch하고 3초/continuous damping 경로로 진입한다고 증명할 수 없다.

조치:

- one-cycle command build/CRC/write를 최상위 catch-all fail-safe block으로 감싼다.
- Write가 status를 반환한다면 확인하고, exception이면 reason을 latch한다.
- main/safety thread가 writer heartbeat와 last-successful-write age를 별도로 감시한다.
- fake publisher write failure, CRC/build failure, recurrent-thread exit와 정상 write를 회귀 시험한다.
- SDK wrapper가 exception을 어떻게 처리하는지는 pinned SDK source/version으로 문서화한다.

## R45 · P2 · TWIST2 성공 종료는 stable control handback을 증명하지 않음

위치:

- `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp`
- `experiments/twist2_right_arm_manual/README.md`

`finish()`는 damping command를 3초 동안 보낸 뒤 planned completion 또는 keyboard `P` stop이면
`active_=false`로 writer를 멈춘다. 이후 MotionSwitcher에서 `ai`를 다시 선택하거나, firmware가
어떤 owner/mode로 전환됐는지 확인하는 handshake가 없다. Main은 planned duration과 keyboard `P`
stop을 completed 상태로 보고 exit code 0을 반환하며 마지막 문구는 controller가 damping에서
끝났다고 표현한다.

README에는 `AI standing is not restored`, `damping is not standing`이라고 이미 경고한다. 따라서
숨겨진 동작은 아니지만, process 성공을 robot의 안정된 standing/control ownership 복귀로 해석하면
안 된다. Writer가 멈춘 뒤 실제 firmware timeout과 mode 변화는 저장소 source만으로 증명되지 않는다.

조치:

- result status를 `LOWCMD_PHASE_ENDED`와 `STABLE_OWNER_CONFIRMED`로 분리한다.
- planned run도 operator takeover/mode acknowledgement 전까지 bounded damping을 유지하거나,
  승인된 service handback 절차를 구현한다.
- 마지막 successful damping write, writer stop, mode reacquisition과 standing confirmation을
  서로 다른 evidence로 기록한다.

## R46 · P2 · Jog fault result가 zero release 완료 전에 output disabled로 기록됨

위치:

- `hardware/g1_arm_bridge/g1_right_arm_jog.py`

Active exception handler는 즉시 `result["command_output_enabled"] = false`를 설정한다. 이후
`finally`에서 남은 zero-weight tail을 best-effort로 보낸다. 이 전송이 실패하면
`emergency_zero_release_error`는 기록하지만 `command_output_enabled=false`는 그대로이며,
마지막으로 성공 전송한 weight도 저장하지 않는다.

이 경로는 `passed=false`와 exit code 2를 유지하므로 R1처럼 release 실패를 전체 PASS로 만드는
문제는 아니다. 그러나 JSON의 output 상태만 보면 실제 마지막 nonzero command와 release 실패를
놓칠 수 있다. Fault 시 정상 ramp-down 없이 zero tail로 바로 전환되는 정책도 result에 명시되지 않는다.

조치:

- last successful transmitted weight/frame timestamp를 기록한다.
- `release_attempted`, `zero_release_completed`, `output_state_unknown`을 분리한다.
- zero tail 완료 전에는 output disabled를 확정하지 않는다.
- first zero write failure, partial zero tail, normal ramp release와 publisher failure를 회귀 시험한다.

## R47 · P2 · Root VR launcher가 UDP port occupancy를 controller identity로 사용함

위치:

- `START_VR_HAND_TO_MUJOCO.bat`

Launcher는 UDP 5005가 점유됐으면 어떤 process인지, 어떤 script/version/config인지 확인하지 않고
기존 Mink controller가 실행 중인 것으로 처리한다. UDP 5012도 동일하게 port occupancy만 본다.
Unity를 새로 시작한 뒤에는 2초를 기다리지만 해당 project process가 살아 있는지 재확인하지 않고,
Mink를 detached `cmd /k`로 시작한 뒤에도 5005 bind 또는 protocol handshake를 기다리지 않는다.
마지막 return code는 child process의 실제 startup 결과가 아니라 launcher checklist가 끝났음을 뜻한다.

영향:

- unrelated/stale listener가 현재 controller로 오인될 수 있다.
- Unity 또는 Mink가 startup 직후 종료돼도 root BAT는 ready 안내와 exit code 0을 낼 수 있다.
- higher-level dry-run launcher가 root BAT의 code만 전달하면 session acceptance와 process-start
  acceptance가 혼동된다.

조치:

- PID, executable/command line, expected project/script path와 commit/config identity를 확인한다.
- controller와 nonce/version handshake를 수행하고 expected UDP ports가 실제로 bind될 때까지 기다린다.
- Unity project process와 child exit를 startup timeout 동안 재확인한다.
- `CHECK_READY`, `STARTED`, `SESSION_VALIDATED`를 서로 다른 exit/result 상태로 둔다.

## R48 · P3 · Regular pose artifact의 두 arm vector 관계가 contract에 없음

위치:

- `config/g1_regular_arm_pose.json`
- `hardware/g1_arm_bridge/arm_sdk_teleop_contract.py`

Regular pose loader는 `dual_arm_q_rad`와 `reference_all_joint_q_rad`를 각각 finite/joint-limit
검사하지만, 전자의 14개 값이 후자의 index 15..28과 같아야 하는지 또는 의도적으로 다른
snapshot인지 검사·설명하지 않는다.

현재 checked-in artifact를 비교하면 최대 차이는 right wrist roll에서 약 5.42도이며,
left wrist roll도 약 2.08도 차이가 난다. Live controller의 Regular return target은
`dual_arm_q_rad`를 사용하지만, fake packet/test fixture 또는 reference full-body consumer는
`reference_all_joint_q_rad`를 사용할 수 있으므로 동일한 `RegularArmPose` 객체 안에서 서로 다른
arm posture가 사용될 수 있다.

조치:

- 두 값이 동일해야 한다면 tolerance를 두고 loader에서 일치시킨다.
- 서로 다른 역할이라면 `return_target_dual_arm_q_rad`와
  `reference_full_body_snapshot_q_rad`처럼 이름을 분리하고 source/time/hash를 각각 기록한다.
- current artifact의 차이가 의도된 것인지 캡처 provenance로 확인한다.

## R49 · P3 · TWIST2 state freshness가 검증 대상과 다른 snapshot에서 계산됨

위치:

- `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp`

`validate_state(const LowState& state, ...)`는 전달받은 `state`를 검사하면서 freshness age는
내부에서 `snapshot(&age_ms)`를 다시 호출해 최신 buffer timestamp로 계산한다. 두 호출 사이에
새 LowState callback이 도착하면 age는 새 packet 기준이고 q/dq/temperature/remote 값은 이전
packet 기준이 된다.

현재 call site 대부분은 snapshot 직후 validate를 호출하므로 일반적인 차이는 작을 가능성이 높다.
그러나 state와 receipt timestamp가 하나의 immutable sample로 묶이지 않아 함수 계약상 특정
sample의 freshness를 검증한다고 볼 수 없다.

조치:

- LowState와 `received_at`을 한 snapshot 구조체로 함께 반환한다.
- `validate_state()`는 같은 snapshot의 age와 fields만 사용한다.
- callback update가 validation 사이에 들어오는 concurrency test와 stale/fresh sample test를 추가한다.

## 검토했으나 이번에 새 finding으로 올리지 않은 사항

- Full-authority shoulder launcher는 Arm SDK weight 1.0이 양팔 14축에 적용되며 unselected targets도
  고정된다는 사실을 화면에 명시한다. 이름만 보고 오른쪽 shoulder 하나만 authority를 갖는다고
  해석하면 안 되지만, launcher 안내 자체는 현재 동작을 숨기지 않는다.
- right-arm Jog의 operator 정상 종료는 current weight에서 감소하므로 Gate 6 R3과 같은
  acquire-interrupt weight 상승은 확인되지 않았다.
- Jog launcher는 startup precheck와 path permit을 매 run 전에 삭제·재생성하고 Python runtime에서
  age를 다시 확인한다. R42는 이 fresh artifact가 model/full-body 변화와 final command에 지속적으로
  결박되지 않는 문제다.
- TWIST2 offline verifier는 full controller build, physical sign, collision과 stability를 검증하지
  않는다고 명시한다. 이번 finding은 그 PASS 범위를 확장 해석하지 않기 위한 physical-path 검토다.
- Current repository hardware authorization fields는 이번 작업에서 변경하지 않았다.

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

이번 commit은 이 review 문서만 추가한다. 다음 review batch에서는 남은 startup-recovery
experiments, static-only network/admin/build launchers와 나머지 tests의 acceptance semantics를
확인한다. Physical output은 별도 명시적 승인 전까지 계속 잠근다.
