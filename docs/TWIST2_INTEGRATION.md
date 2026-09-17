# TWIST2 Integration Notes

## Current direction (2026-09-07)

The user selected the existing TWIST2 right-arm trial as the next integration
path. Arm SDK waist ownership investigation is deferred, not resolved.
The following older architectural proposal is historical; the concrete baseline
is `experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp` and its local
reference header. The repository now contains supplied controller sources.

```text
Unity wrist pose -> PC Mink IK -> validated right-arm joint target
    -> planned receive-only C++ input -> upper_target[22..28]
    -> TWIST2 hybrid_target (policy legs + captured waist/left arm + right target)
    -> existing single 500 Hz rt/lowcmd writer
```

TWIST2, not Regular, owns the legs in this path. Waist12..14 and left15..21
retain captured upper targets. The existing R1 watchdog and damping termination
must remain; damping is not a standing hold. Do not run Arm SDK publishers in
parallel. This direction change does not authorize robot deployment or execution.

Implemented locally: `vr_input_offline.py` reuses the existing strict Mink parser,
extracts only22..28, preserves absolute radian signs, and rate-limits each joint
to0.08rad/s at a maximum0.02s step. Explicit session/sequence, captured baseline,
start-relative study bounds and input-age checks prevent silently rebasing on
re-engagement. Missing packets freeze the candidate; timeout/invalid/disengaged
input latches stop. No automatic Regular return is carried over from Arm SDK.

This returns an offline upper-target dictionary, not a robot command. The parser's
`mink_simulation` source denotes IK candidates, not actual G1 feedback. Separate
LowState feedback is still required before any physical use. Collision safety of
the interpolated whole-body path and actual-state consistency are not established.
The existing physical C++ controller and policy were not changed. Windows-only
`receive_target_shadow.cpp` now connects a bounded loopback receive queue to the
offline C++ candidate tick and local JSONL logging. It is not connected to the
TWIST2 policy or any robot publisher. The existing Unity/MuJoCo view still shows
Mink results, not this C++ candidate. Python Quest shadow/replay uses the first
active simulated Mink pose; the C++ receiver now supports either first-active
simulation capture or an explicit simulation baseline from config. Neither
initializes from actual G1 LowState. A local Quest run received2079 packets,
updated152 candidate ticks and stopped on pinch; non-target joints remained fixed.

The weight1.0 Arm SDK upper-body tilt incident remains unresolved and deferred.
Local VR tests must select simulation display and avoid conflicting UDP5008
receivers. From the project root in PowerShell use:
`.\START_VR_HAND_TO_MUJOCO.bat --standard-mink --external-feedback`.
Do not terminate unrelated port owners. The current Unity compilation/reload log
and the user's normal wrist-marker observation were verified. This does not
verify a C++ candidate visualization or separate true/false diagnostic-flag views.

Raw datagram hex, receipt times and validated tick goals are now logged locally.
`replay_cpp_receiver_log.py` replays these events through the memory-only queue,
compares candidates exactly and checks rate, overshoot and held joints. Synthetic
loopback release/timeout/error/overflow and near-goal reversals passed. The older
Quest session lacks raw goals and cannot be retroactively replayed this way.

A fresh Quest session at 15:24 received1127 datagrams and240 active ticks,
stopped on pinch and passed exact raw-event replay, rate/overshoot/held-joint checks.
Evidence: `logs/test_results/twist2_cpp_quest_raw_20260907_152430/result.json`.
Its baseline is still virtual Mink, not actual LowState.

A separate `measured_composition_offline.hpp` now accepts synthetic q/dq snapshots,
checks continuity/settling and initial VR alignment, and composes decoded leg positions
with captured waist/left arm and rate-limited right arm. A stop returns no candidate.
It is a position-only draft; actual LowState initialization is not implemented.

Next: prepare snapshot provenance/full-state validation and the policy position adapter
(including freshness/limits), then actual-state connection, policy integration and
full-body validation, followed by separately approved deployment
and bounded physical testing. Offline/runtime-local test passes establish none
of the robot's physical safety or ownership guarantees.

## Historical purpose

The initial design used TWIST2 as an architectural reference. Supplied local
controller sources and the right-arm derivative were added subsequently; see
the experiment README for provenance and physical verification boundaries.

Reference repository:

- `amazon-far/TWIST2`
- License: MIT

## Patterns worth adopting

TWIST2 separates high-level motion generation from low-level robot control. Its teleoperation path produces high-level whole-body targets, while simulation/real low-level controllers consume those targets and publish robot state. It also uses explicit teleoperation states and smooth transitions between idle, teleop, pause, and exit.

The useful design ideas for this repository are:

1. Separate operator intent from robot-specific control.
2. Keep simulation and physical-robot controllers behind the same logical interface.
3. Make teleoperation state transitions explicit and testable.
4. Smooth re-engagement instead of applying large target jumps.
5. Define joint ownership before combining independently developed upper- and lower-body controllers.

## Proposed G1 integration boundary

```text
Quest 3S / Unity
        |
        v
PosePacketV2 / Legacy adapter
        |
        v
InternalCommand
        |
        v
High-level teleop state machine
        |
        +----------------------+----------------------+
        |                                             |
        v                                             v
Right-arm IK                                 Lower-body policy
        |                                             |
        v                                             v
right_arm[7]                                base whole-body target
        |                                             |
        +----------------------+----------------------+
                               |
                               v
                    Whole-body coordinator
                               |
                               v
                      canonical G1 29-DoF target
                               |
                      +--------+--------+
                      |                 |
                      v                 v
                    MuJoCo          Physical G1
```

## Initial joint ownership

For the current 29-DoF G1 ordering used by the lower-body reference controller:

| Group | Indices | Initial owner |
| --- | --- | --- |
| left leg | 0-5 | lower-body policy |
| right leg | 6-11 | lower-body policy |
| torso | 12-14 | captured HOLD target in current static-stand derivative |
| left arm | 15-21 | captured HOLD target in current right-arm trial |
| right arm | 22-28 | current arm teleoperation IK |

The coordinator must be the only component that produces the final 29-DoF target. Individual controllers publish only the joint groups they own.

## Important compatibility rule

The current live Unity Legacy V0 packet does not have the same coordinate semantics as `PosePacketV2`.

- Legacy position is already mapped toward the controller/robot target frame by Unity.
- Legacy wrist rotation is still converted by the Python controller.
- V2 declares `unity_ovr_tracking` and is intended to carry a canonical tracked pose contract.

Therefore V2 must not be connected directly to the live right-arm IK until a dedicated coordinate-normalization stage converts both protocols into the same robot-frame target representation. This prevents a silent double transform or axis inversion.

## Integration phases

### Phase A — completed foundation

- Versioned V2 protocol contract
- Legacy/V2 parsing adapter
- Explicit runtime state-machine foundation
- 29-DoF joint-group ownership and composition utility

### Phase B — next

- Add coordinate-normalization stage after `InternalCommand`
- Move Legacy live receiver to `parse_command_packet()` without changing Legacy behavior
- Gate V2 live commands until normalization is complete
- Add receiver-level regression tests

### Phase C — whole-body integration

- Accept a lower-body 29-DoF base target
- Overlay right-arm IK target on indices 22-28 while teleop is active
- Return right-arm ownership to the lower-body controller when teleop is disabled if desired
- Define torso ownership explicitly before enabling simultaneous reaching and locomotion

### Phase D — sim/real parity

- Keep the same coordinator output contract for MuJoCo and the physical G1
- Put Unitree SDK-specific transport below the coordinator
- Add watchdog, freshness, joint-limit, and emergency-stop handling at the physical-robot boundary

## Attribution

TWIST2 is an external project by its original authors. Retain source license and
copyright notices when copying or adapting code. Local supplied deployment code
and its right-arm derivative are documented in the experiment README; this work
does not claim authorship of the supplied policy or original controller.

## Offline health and policy wrapper (2026-09-07)

`GuardedCompositionOffline` now checks explicit state health fields and a fresh,
sequence-matched clipped policy action snapshot, decodes leg positions with the
reference constants and validates final candidate limits. Constants are checked
against the local reference by tests. It remains separate from the receiver.
CRC is an adapter assertion, not a raw-byte CRC implementation or provenance proof.
Actual decoder/inference/artifact identity, full-body path checks and writer/blend/
damping integration remain outstanding. No robot execution was performed.

Saved Quest input is now connected to the guarded composition via an offline-only
fixture harness. Normal replay matched all240 recorded active upper candidates;
five injected fault scenarios latched without resuming. State is a frozen virtual
baseline and policy is synthetic sine input, not inference or robot dynamics.
Evidence: `logs/test_results/twist2_guarded_quest_fixture_20260907_v2/result.json`.
Actual-state/policy adapters and full-body/writer integration remain outstanding.

Offline CRC word calculation and policy hash/raw-array adapters are now tested.
The local policy hash matches the pinned reference. This does not implement a
LowState decoder or execute inference: hg SDK layout definitions/raw CRC samples
were not found in the project, and the checked Python3.11 has no Torch module.
Do not substitute the Go LowCmd example layout or treat a CRC assertion as raw
packet verification. These dependencies remain before actual-input integration.

## Pinned SDK decoder and CPU model smoke test (2026-09-07)

Official hg definitions are now vendored with commit/hash/license provenance.
The native little-endian2092-byte decoder passed official-class synthetic fixtures
and2092 single-byte corruption checks. It is not a DDS/CDR decoder and the deployed
robot ABI remains unverified. A separate CPU Torch2.14 environment now loads the
verified policy and passes two synthetic observation cases repeated10 times each.
First inference29.7ms: no50Hz guarantee. Actual LowState/history/applied-action loop,
robot tick continuity and full-body/writer integration remain unimplemented.
Evidence: `logs/test_results/twist2_cpu_policy_smoke_20260907.json` and the SDK manifest.

## Observation history and candidate feedback (2026-09-07)

The standalone C++1432 observation/history implementation matches200 frames of
extracted reference code exactly, including ankle masking, clipping and rollover.
A CPU-policy/C++-composition loop now replays saved Quest input:1801 inferences,
240 active ticks,386 candidate commits; tilt rejects without committing. Feedback
uses accepted candidate positions converted to action, not raw model action.
This is not physical applied feedback: state is frozen virtual data, timestamps
are simulated, mimic uses previous accepted upper targets, and blend/writer/dynamics
are absent. Current pre-inference upper preparation and actual writer-applied
feedback still require integration. Evidence: `twist2_policy_history_20260907_v1`.

## Current upper preparation and position blend (2026-09-07)

Guarded composition now stages current upper targets in Prepare, exposes them to
observation construction, and commits only after Finish validates policy/time.
The history harness uses current upper mimic and feedback from float-blended
positions. Invalid state/VR blocks inference; late policy/Abort discards staged
state. Early VR during blend is rejected in this offline harness.
601 blend points and6 phase cases passed; normal CPU Quest replay retained240 active
updates/386 commits; tilt and early engage stopped before inference. Evidence:
`logs/test_results/twist2_preinfer_blend_20260907_v2/result.json`.
This does not implement pre-engage leg takeover, torque/gains,500Hz writer or
physical applied feedback; first-active candidate gating and synthetic state/time
remain. Full physical-controller equivalence is not established.


## 현재 500Hz writer 계산 오프라인 검토 (2026-09-07)

- 기존 변경사항을 먼저 확인하고 물리 C++의 rate → joint → torque → joint
  순서를 검토했다. 기존 물리 C++와 reference 원본은 변경하지 않았다.
- 새 `offline_writer_study.hpp`는 소켓/SDK/LowCmd 직렬화 없는 메모리 진단이다.
  2ms당 하체 2.0rad/s, 상체 0.8rad/s writer 상한을 사용한다.
  VR 목표의 0.08rad/s 제한과는 별도 단계다. kp/kd/torque 상수는 로컬
  reference와 drift-test로 대조했다.
- 합성 입력으로 기존 순서의 충돌 2개를 재현했다. 관절27에서 last=desired=0,
  measured q=0.2/dq=0/ff=0이면 torque clamp가 목표를 0.075rad까지 옮겨
  0.0016rad writer 변화량을 넘는다. 같은 관절이 soft upper bound에 있고
  dq=1.5/ff=-2.5이면 최종 joint clamp 뒤 예측 torque=-4Nm로 2.5Nm를 넘는다.
  이는 소스 수식의 합성 반례이며 Arm SDK 기울어짐의 원인 진단이 아니다.
- 새 모델은 rate/joint/torque 구간의 교집합으로 제한한다. 교집합이 없으면
  전체 target commit 취소 후 damping 진단으로 latch한다. 따라서 충돌 시
  기존 물리 계산과 의도적으로 다르며 실제 controller에 적용된 수정이 아니다.
- health/20ms state watchdog, 60ms command watchdog(250ms grace), R1/비상정지,
  gains, capture torque clamp/fade, 중단 후 재개 금지와 35슬롯 damping을 검증했다.
  damping 진단의 predicted_torque=0은 미계산 placeholder다. 실제 토크가
  0이라는 의미가 아니다. damping 지속시간/종료 lifecycle은 아직 모델링하지 않았다.
- 모델 추가 규칙: 호출 간격 최소2ms, 긴 간격에도 고정2ms 변화량만 허용,
  desired 생성시각은 activation 이후여야 한다. 실제 scheduler/clock 측정은 아니다.
- `test_offline_writer_study.cpp`: 500tick×29축 정상 reference 일치/변화율/
  overshoot/gain/예측torque, 오른팔만 목표 변경 시 0..21 유지, 오류12종
  atomic 취소/latch, 충돌2종, watchdog/grace/명시 stop/누락desired,
  torque fade101단계 및 잘못된 alpha 거부 통과.
- MSVC C++17 /W4 /WX 빌드 통과. 관련 pytest **14 passed /110 subtests passed**.
  로그: `logs/test_results/twist2_writer_study_latest.txt`,
  `logs/test_results/twist2_writer_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
  G1/WSL/DDS/publisher/물리 출력은 실행하지 않았다.
- 다음: 저장 Quest→CPU 정책→blend의 desired를 이 모델에 연결하여
  50Hz/500Hz 다중 주기와 추론 지연·해제 전파를 파일 재생으로 검증한다.
  현재 writer 테스트는 합성 입력 단독이며 그 전체 경로 연결은 아직이다.
  실제 LowState/배포 ABI/동역학/실시간성 및 로봇 안전성은 미검증이다.

재실행(Windows 로컬, 빌드된 메모리 전용 테스트):
```powershell
.\logs\test_results\test_offline_writer_study.exe
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_offline_input_adapters.py experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py experiments/twist2_right_arm_manual/test_cpp_measured_composition.py
```


## 현재 정책 trace→500Hz 다중 주기 재생 (2026-09-07)

- 현재 변경사항과 CHAT_HANDOFF/정책 history/writer 코드를 확인한 뒤 진행했다.
  다른 작업과 물리 C++는 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_writer_trace_loop.cpp`는 stdin/stdout 전용 C++ probe다.
  `replay_writer_policy_trace.py`가 실제 CPU 정책/blend trace를 읽고 기록된
  inference_ms를 단일 worker 결과 도착 지연으로 반영하여 2ms writer를 호출한다.
  같은 시각에는 stop을 completion보다 먼저 처리하고 중단 후 completion은 폐기한다.
- CPU 정책 원본 재생을 새로 실행했다: 정상 1800 inference/386 commit/active240,
  tilt/blend_gate 포함 3종 통과. 첫 CPU 추론 36.1463ms, 중앙값 0.45805ms.
  전체 시작 구간을 포함한 실시간성 보장은 아니다. writer 재생은 첫 유효
  candidate 이후 구간만 사용하므로 초기 warm-up 지연은 포함하지 않는다.
- 입력은 alpha=1인 완료된 blend만 허용하며 feedforward=0 합성 fixture다.
  writer state는 직전 target q/zero dq로 매 tick 갱신한 이상화된 입력이다.
  정책 관측은 원본 frozen virtual baseline을 그대로 사용한다. writer 결과가
  정책 관측/history로 돌아가지 않는 open-loop trace 재생이며 동역학 모델이 아니다.
- 4종 통과:
  - 기록 inference 지연: 3931 writer tick, input_disengaged 중단.
  - 100ms까지 결과 도착 정체 주입: 223 tick 뒤 command_timeout, 이후 결과366개 폐기.
  - state receipt 갱신 중단: 209 tick 뒤 state_timeout, 이후 결과365개 폐기.
  - 마지막 candidate 40ms 추가 지연: 해제 후 결과1개 폐기, 재개 없음.
- 해제는 source의 검증된 stop tick 36.6105804초를 사용한다.
  writer 중단 36.6121153초, 전달 지연1.5349ms(모의 시계).
  실제 pinch/UDP 수신부터의 지연 또는 Windows 스케줄러 실측이 아니다.
- 성공 tick마다 rate/overshoot/waist·왼팔12..21 유지, 실패 첫 tick의 전체
  commit 취소, 이후 target 불변/damping 진단을 독립 비교했다.
  하체0..11은 정책대로 변경되므로 이 full-body writer에서 유지 대상이 아니다.
  최대 step 0.00400000066rad는 float 반올림을 포함한 하체2rad/s×2ms다.
  VR0.08rad/s와 writer 상체0.8rad/s는 별도 상한이다.
- 첫 release_pending 시험은 마지막 candidate가 해제20.24ms 전이어서 20ms
  주입 구간에 포함되지 않아 검사 실패했다. 30ms 선택 구간으로 수정하여
  실제 지연 completion이 존재하는 것을 확인했다. 최종 결과는 v3다.
- C++17 /W4 /WX 빌드 및 writer 단독 테스트 통과.
  pytest **14 passed /110 subtests passed**, skip0.
- 증거:
  `logs/test_results/twist2_writer_policy_source_20260907/result.json`,
  `logs/test_results/twist2_writer_multirate_20260907_v3/result.json` 및 4종 trace,
  `logs/test_results/twist2_multirate_regression_latest.xml`.
  입력 normal trace SHA256:
  `9e231b7eae74bfb9e8d2989b98747df1db234467770df0f11f6ce30317ed301b`.
  물리 C++ SHA256은 이전 기록 E61D8A3C…CC09F와 동일하다.
- 남은 다음 단계: Prepare→실제 추론 완료→Finish→writer를 하나의 모의
  이벤트 시계로 연결하여 stale 추론 폐기와 history commit 순서를 검증한다.
  현재는 precomputed 후보 전달 시험이므로 upstream freshness 검증의
  실제 추론 지연 반영 및 writer 중단의 upstream 전파는 아직 통합되지 않았다.
  실제 LowState/배포 ABI/동역학/물리 안전성은 계속 미검증이다.

재실행(프로젝트 루트, 출력 폴더는 새 이름 사용):
```powershell
py -3.11 experiments/twist2_right_arm_manual/replay_writer_policy_trace.py --source logs/test_results/twist2_writer_policy_source_20260907 --output logs/test_results/twist2_writer_multirate_rerun
```
MSVC 개발자 셸에서 probe 빌드:
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs/test_results/test_writer_trace_loop.exe /Fo:logs/test_results/test_writer_trace_loop.obj experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp
```


## 현재 단일 이벤트 시계 통합 검증 (2026-09-07)

- 현재 변경사항과 인계/GuardedComposition/ObservationHistory/writer를 확인했다.
  기존 물리 C++/다른 작업은 변경하지 않았다. G1/WSL/DDS/UDP/publisher 실행 없음.
- 신규 `test_event_clock_loop.cpp`, `run_event_clock_offline.py`:
  raw Quest 파일을 기존 Replay로 검증하고 Prepare→실제 CPU 추론→Finish→
  desired/history→2ms writer를 하나의 모의 이벤트 시계에서 실행한다.
  source tick은 기록된 약50Hz cadence, writer는 첫 candidate 후2ms 간격이다.
  Python heap 순서는 같은 시각 stop→writer→finish→packet→build다.
- Prepare 시각을 Finish 시각으로 재사용하던 방식과 달리 실제 측정 inference
  duration을 더한 완료 시각을 Finish에 전달한다. 정책 created_at은 완료 시각이며
  inference 중 snapshot30ms age 만료를 GuardedComposition에서 검사한다.
  단일 추론만 pending으로 허용하고 그동안 build는 건너뛰며 packet은 다음 build까지 보관한다.
- writer 실패가 guard.Abort/history.Stop/desired 제거로 전파된다. stop은
  pending observation과 준비 중인 upper를 취소한다. 이후 finish는 폐기되며
  target/history/previous_action은 유지된다. 정상 history feedback은 writer의
  rate-clipped q가 아니라 기존 규약대로 성공 Finish의 blend desired다.
- 모델은 검증된 같은 bytes TorchScript를 CPU로 실행한다. 초기 warm-up1회는
  모의 작업 밖에서 수행했고 cold-start/실시간성 검증으로 표현하지 않는다.
  이번 정상 최대 inference9.5081ms. NumPy 미설치/jit.load deprecated 경고가
  있으나 tensor-only 실행은 성공했다.
- 4종 통과:
  - 정상: inference1800/history386/writer3931, input_disengaged.
  - 40ms 지연 Finish: history13/writer152 후 state_expired_during_inference.
    해당 Finish는 후보/history에 commit하지 않았다.
  - 추론 pending 중 writer state age30ms 주입: history13/writer132에서
    state_timeout; 이후 완료 결과1개 폐기.
  - 마지막 추론40ms 지연 중 해제: history385/writer3931, 결과1개 폐기.
- 매 이벤트 history1270개/previous_action29개/commit count를 독립 비교했다.
  성공 writer의 rate/overshoot/12..21 유지, stop 최초·이후 target 불변과
  desired 제거/pending 취소도 확인했다.
- 해제는 raw 파일의 검증된 stop tick36.6105804초를 외부 stop 이벤트로 주입한다.
  이 이벤트에서 즉시 메모리 latch되며 그 뒤 writer 갱신은 없다.
  raw packet을 추론 중 별도 validator로 처리한 시험이나 실제 pinch 지연 실측은 아니다.
- 상태 경계: 정책 state는 frozen virtual baseline, writer state는 직전 target/
  zero velocity fixture다. history 연결과 stop 전파는 통합됐지만 두 단계가
  동일한 실제 LowState를 사용하거나 writer 위치가 다음 policy q 관측으로
  돌아가는 동역학 closed-loop는 아니다. 실로봇 안전성은 계속 미검증이다.
- C++17 /W4 /WX 빌드 통과. 기존 writer 단독 검사와 관련 pytest
  **14 passed /110 subtests passed**, skip0.
  결과: `logs/test_results/twist2_event_clock_20260907/result.json` 및4종 trace,
  `logs/test_results/twist2_event_clock_regression_latest.xml`.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 남은 다음 단계: 추론 pending 동안 raw 입력의 해제/오류/timeout을 별도
  검증해서 stop으로 전달하는 로컬 경로. 현재 외부 stop tick 주입을 대체하고
  packet FIFO/재참여/중복 sequence와 동시 완료 우선순위를 검증한다.
  실제 LowState/배포 ABI/동역학/콜드 스타트/실시간성/물리 실행은 미완료다.

재실행(프로젝트 루트, 새 출력 폴더 사용):
```powershell
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --output logs/test_results/twist2_event_clock_rerun
```
MSVC 개발자 셸 빌드:
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Fe:logs/test_results/test_event_clock_loop.exe /Fo:logs/test_results/test_event_clock_loop.obj experiments/twist2_right_arm_manual/test_event_clock_loop.cpp
```


## 현재 raw 입력 감시와 pending 추론 중단 (2026-09-07)

- 현재 변경사항과 인계/validator/queue/event harness를 읽고 기존 작업을 유지했다.
  물리 C++/G1/WSL/DDS/publisher/UDP 실행·수정 없음.
- 신규 `raw_input_watch_offline.hpp`: 단일 이벤트 소유자가 raw 도착 시
  InputValidator로 즉시 검증한다. 유효 active만64개 FIFO에 보관하고 Prepare가
  한 번 drain한다. 완전히 검증된 pre-engage inactive는 대기하며 보관하지 않는다.
  bootstrap validator는 drain과 무관하게 session/sequence를 유지한다.
- payload16384bytes/queue64 제한, 전체 스키마/해제/중복sequence/250ms
  receiver timeout을 검사한다. 오류 시 FIFO를 지우고 latch한다.
  timeout은 이벤트에서 Poll하므로 별도 실시간 timer/독립 thread 구현은 아니다.
- `test_event_clock_loop.cpp`의 선택적 raw_input 모드:
  packet/poll을 추론 pending 동안 처리하고 guard/history/writer/desired를
  함께 중단한다. raw 모드 build에 외부 packet batch를 섞으면 거부한다.
  기존 batch 모드는 유지한다. Finish/다른 이벤트 앞에서도 timeout을 확인한다.
- `run_event_clock_offline.py --raw-input`은 외부 stop tick 주입을 제거하고
  raw packet을 동일시각 writer/finish보다 먼저 처리한다.
  동일시각 packet 간에는 원본 FIFO 순서를 유지한다.
- 신규 `test_raw_event_clock.py` **9종 통과**: 해제=완료 시각 및 재engage,
  pending malformed JSON, drain 뒤 duplicate,250ms 경계와 timeout,
  oversized, pending65번째 queue overflow, FIFO 중간 역순sequence,
  engage 전 idle 장기대기, 유효 batch drain1회.
  합성 zero-action 정책 입력이며 실제CPU 정책 시험과 구분한다.
  중단 최초 및 늦은 Finish/재engage 이후 history/previous/target/write 불변,
  desired 제거/pending 취소/FIFO 제거를 검사했다.
- **실측 duration 재생은 통과하지 못했다.** warm-up1회로2회 시도했으나
  active 이전 state_expired_during_inference로 중단됐다. warm-up10회 후에도
  동일하게 실패했으며 v3 failure.json에 최대52.0336ms window가 기록돼 있다.
  window는 tensor 생성/model/clamp/list 변환을 포함한다. 지연 원인은 미진단이다.
  30ms state freshness 제한을 완화하지 않았다. 첫2회는 콘솔 오류만 남고
  v3부터 failure.json으로 trace를 저장하도록 개선했다.
- 입력 스케줄 검증을 분리하기 위해 `--fixed-inference-ms 1` 옵션을 추가했다.
  실제 CPU action은 계산하되 완료 시각만 명시적1ms 모의 값으로 사용한다.
  이 모드 **정상 재생 통과**: inference1800/history386/writer3921,
  raw 해제 도착36.591642초에서 input_disengaged 중단.
  다음 policy tick36.6105804초를 기다리지 않는다. 실제 물리 지연 측정이 아니다.
  이 실행의 실제 측정 최대40.8206ms도 별도 보고하며 실시간 통과로 해석하지 않는다.
- 상태는 정책 frozen virtual baseline/writer previous-target zero-velocity
  fixture로 유지한다. G1 LowState/동역학/로봇 안전성 검증이 아니다.
- C++17 /W4 /WX 빌드 통과. 관련 회귀 **23 passed /110 subtests passed**.
  증거:
  `logs/test_results/twist2_raw_event_regression_latest.xml`,
  `logs/test_results/twist2_raw_event_clock_20260907_v3/failure.json`,
  `logs/test_results/twist2_raw_event_clock_fixed_20260907/result.json` 및 trace.
- 물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 다음: 로컬 CPU 측정 window의 지연 구간을 tensor 준비/model/후처리로
  분리해 원인을 조사하고, 실측 시계에서 정상 종료까지 가능한지 확인한다.
  raw 입력 로직의 결정적 시험은 완료했지만 이번 실측 시간 전체 재생은 실패다.
  실제 로봇 실행 및 LowState/배포 ABI/동역학 검증은 미완료다.

프로젝트 루트에서 재실행(출력은 새 폴더):
```powershell
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_raw_event_clock.py
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --fixed-inference-ms 1 --output logs/test_results/twist2_raw_fixed_rerun
```
실측 시간 시험은 `--fixed-inference-ms 1`을 생략한다. 현재 실측 시험은
state_expired_during_inference 실패 기록이 있으므로 고정시간 시험과 구분한다.


## 현재 CPU 지연 분리 측정·정책 worker 격리 (2026-09-07)

- 인계/현재 변경사항/측정 코드를 읽고 로컬 파일 재생만 수행했다.
  기존 물리 C++/G1/WSL/DDS/UDP/publisher/물리 출력은 변경·실행하지 않았다.
- `run_event_clock_offline.py`에 tensor/model/output 시간, 호출 thread CPU 시간,
  GC callback의 시작/종료·generation을 기록했다. 성공/실패 모두
  `normal_timing.json`에 매 추론 구간을 저장한다.
- 직접 실행 실패를 재현했다: total40.9698ms, tensor0.0506ms,
  model40.8806ms, output0.0386ms. 이 model 구간에 generation2 GC가
  40.5913ms 실행됐다. 따라서 이번 재현에서 GC가 지연 대부분을 차지했다.
  이전52.03ms 건은 당시 세부 계측이 없어 동일 원인으로 단정하지 않는다.
  thread_time 값은 Windows의 거친 해상도로0/46.875ms 등이 나와 세부 분해에 사용하지 않는다.
- 신규 `policy_cpu_worker_offline.py`: 해시 검증한 동일 bytes 모델을
  별도 로컬 Python 프로세스에서 CPU 실행한다. stdin/stdout JSON만 사용,
  소켓/SDK 없음. 부모는 이 모드에서 torch/model을 로드하지 않는다.
  GC를 끄거나 임계값을 바꾸지 않고 policy heap과 replay/log heap을 분리했다.
- `--raw-input --isolated-policy`는 JSON 인코딩/pipe 왕복/worker 실행/
  응답 decode까지 포함한 실제 경과시간을 모의 Finish 시각에 더한다.
  worker 내부 세부시간도 별도 기록한다. 고정 완료시간 옵션은 사용하지 않았다.
  기존 직접 실행/고정시간 옵션은 비교용으로 남아 있다.
- 초기 model 로드/warm-up10회는 모의 시계 밖이다. 부모 event processing/
  전체 OS scheduler의 모든 지연을 모의 시계에 더하는 구조는 아니다.
  실제 asynchronous robot control이나 실시간성을 입증한 것은 아니다.
- 분리 실행2회 정상 종료:
  - 첫 실행1800 inference/history386/writer3921, 최대왕복1.8442ms,
    중앙값0.7393ms, worker 내부 최대0.9748ms. 측정 window에서 부모/worker
    generation2 GC event는0개였다.
  - worker 정리 경로 보강 후 최종v2도1800 inference/writer3921,
    최대왕복2.0556ms. history385/해제 뒤 completion1개 폐기.
    마지막 Finish와 raw release의 측정시간 순서에 따른 차이이며 재개 없음.
  - 두 실행 모두 raw release36.591642초에 input_disengaged.
  30ms state freshness 기준은 그대로다. 최대치의 장기 상한을 보장하지 않는다.
- 신규 `test_policy_worker_offline.py`는 합성1432차원8입력에 대해
  직접 실행과 worker의 clip 후29축 출력을 exact 비교해 통과했다.
  별도 unittest1개/내부8case이며 관련 pytest는 **23 passed /110 subtests passed**.
  syntax/diff check 및 worker 정상 종료 확인. 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.
- 증거:
  `logs/test_results/twist2_timing_split_20260907/failure.json` 및 timing,
  `logs/test_results/twist2_timing_isolated_20260907/result.json`,
  `logs/test_results/twist2_timing_isolated_20260907_v2/result.json` 및 timing/trace,
  `logs/test_results/twist2_policy_worker_equivalence_latest.txt`,
  `logs/test_results/twist2_cpu_isolation_regression_latest.xml`.
- 남은 다음 단계: worker 응답 누락/비정상 종료/잘못된 응답에 대한 제한시간과
  stop 전파를 파일·합성 worker로 검증한다. 현재 readline은 응답을 동기 대기하며
  worker hang에 대한 응답 deadline은 없다. 정상 종료/예외 정리의5초 대기는 별도다.
  실제 LowState/배포 ABI/동역학/물리 안전성 및 live 동시성은 계속 미검증이다.

프로젝트 루트에서 재실행(출력은 새 폴더):
```powershell
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --isolated-policy --output logs/test_results/twist2_isolated_rerun
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/test_policy_worker_offline.py
```
직접 실행의 GC 비교는 `--isolated-policy`를 생략한다.


## 현재 worker 응답 제한시간·실물 전환 우선순위 (2026-09-07)

- 사용자 요청에 따라 실물 연결의 필수 장애 처리부터 진행했다.
  현재 변경사항/인계/worker를 읽고 기존 물리 C++와 다른 작업은 유지했다.
  G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `policy_worker_client_offline.py`: 자신이 만든 로컬 worker에만 접근하는
  단일 요청 client다. daemon I/O thread가 pipe write/read를 수행하며 부모는
  초기 ready10초/요청응답30ms deadline으로 대기한다. 최대응답65536bytes,
  newline/UTF8 JSON/중복key/NaN/응답ID/finite29축[-2,2]를 검증한다.
  오류는 latch되며 worker를 종료하고 늦은 결과로 재개하지 않는다.
- `policy_cpu_worker_offline.py`는 request_id를 응답에 되돌린다.
  기존 list 입력은 출력 동등성 비교용으로 유지한다. 실제 client는 ID 포함 dict를 사용한다.
- `run_event_clock_offline.py`는 새 client를 사용하고 오류를 worker_failure
  이벤트로 C++ Stop에 전달한다. 무응답을 무기한 readline으로 기다리던 경로를 제거했다.
  모의 큐에서는 elapsed 이후 Stop 이벤트이며 live 비동기 제어 구현은 아니다.
- deadline은 OS 실행 상한 보장이 아니다. timeout 감지 후 소유 worker
  terminate/wait/kill 및 thread join의 정리 시간이 추가된다(각1초 제한).
  시험에서 오류 호출은 정리 포함1초 미만이고 프로세스/thread 종료를 확인했다.
  현재 메모리 재생의 C++ stdin 응답 자체에 대한 장애 처리는 별도다.
- 신규 client 테스트5개/내부14case: 응답timeout/EOF/깨진JSON/ID불일치/
  boolean action/oversized, 시작timeout,NaN/중복key,정상ID응답,
  장애6종→C++ pending Stop→늦은Finish·재engage 후 history/target 불변.
  합성 worker는 모두 로컬 테스트 프로세스이며 무관한 PID를 종료하지 않았다.
- 전체 관련 회귀 **28 passed /124 subtests passed**.
  직접 정책과 worker 출력 exact8입력 비교도 unittest1개 통과.
- 실제CPU/저장Quest 정상 재생 통과: inference1800/history385/writer3921,
  최대왕복4.9294ms, 해제36.591642초, 늦은completion1개 폐기.
  fixed_inference_ms=null. warm-up10회는 모의 시계 밖이며 실시간/물리 안전성 보장은 아니다.
- 증거:
  `logs/test_results/twist2_worker_deadline_regression_latest.xml`,
  `logs/test_results/twist2_worker_deadline_20260907/result.json` 및 timing/trace,
  `logs/test_results/twist2_worker_deadline_equivalence_latest.txt`.
  물리 C++ SHA256:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.

### 실물 VR까지의 필수 순서 — 부가 오프라인 시험보다 우선

| 단계 | 현재 상태 | 통과에 필요한 증거 |
|---|---|---|
| 입력/정책/목표/중단 로컬 준비 | 합성·저장파일 재생 통과 | 위 테스트·trace; 실제 로봇 안전성과 구분 |
| 실제 LowState 초기화 | 미완료 | 실제 배포 SDK/LowState 형식 확인, fresh CRC/모드/관절/속도/IMU 상태와 정지구간 캡처, VR 첫 목표 정렬 |
| 단일 full-body owner 연결 | 미완료 | 기존 물리 C++를 유지한 별도 검토 가능한 연결안, 0..11 정책·12..21 할당·22..28 VR 통합, 송신자1개와 fail-stop |
| 제한된 실물 비VR 시험 | 미승인/미실행 | 실행 파일·대상·모드 전환·중단/종료 동작을 사전에 특정하고 승인 후 확인 |
| 최초 실물 VR 시험 | 미승인/미실행 | 앞 단계 통과, 작은 목표 범위·0.08rad/s·해제/오류 중단 확인 |

- 다음 작업은 실제 LowState 입력과 단일 owner의 연결 준비다. 동일한 정상
  오프라인 검사를 반복하는 것으로 실제 초기화/물리 시험을 대체하지 않는다.
- 기존 physical writer의 순차 clamp 충돌 반례는 아직 물리 원본에 수정되지 않았다.
  새 owner 연결 때 해결/검토해야 하며 Arm SDK 사고 원인으로 단정하지 않는다.
- 현재 금지된 G1/WSL/DDS/publisher 실행은 별도 구체적 범위의 승인이 필요하다.
  기존 Arm SDK 기울어짐은 해결이 아닌 보류이며 새 C++의 Unity 시각화도 별개다.


로컬 재실행:
```powershell
py -3.11 -m pytest -q experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py
.\logs\diagnostics\twist2_cpu_venv\Scripts\python.exe experiments/twist2_right_arm_manual/run_event_clock_offline.py --raw-input --isolated-policy --output logs/test_results/twist2_deadline_rerun
```
출력 폴더는 새 이름을 사용한다.


## 현재 native LowState→초기화→전신 후보 연결 (2026-09-07)

- 현재 변경사항/인계/native decoder/초기화 코드를 검토했다. 기존 물리 C++와
  다른 작업은 유지했고 G1/WSL/DDS/UDP/publisher/물리 출력 실행 없음.
- 신규 `native_composition_offline.hpp`는 native bytes를 DecodeOfflineHgNative에
  통과시켜 실제 입력 형태의 sample/health를 GuardedComposition Prepare에 전달한다.
  JSON/Mink를 measured state로 대체하지 않는다. Finish가 유효 policy를 받은
  뒤에만 후보를 노출한다. 초기 정지1초→VR 첫 목표 정렬→정책 하체와 캡처 상체
  결합까지 기존 개별 단계를 연결했다.
- CRC/ABI profile/health/age 외에 receipt 증가와 robot tick 연속성을 검사한다.
  tick duplicate/backward/reset은 latch중단, uint32 max→0 rollover는 serial
  arithmetic으로 허용한다. tick 단위/최대 허용 jump는 배포 확인 전 미검증이다.
- profile은 여전히 `hg_native_le2092_9754cd15`라는 Windows native fixture
  layout이다. 실제 G1 배포 ABI 확인도 DDS/CDR 디코딩도 아니다.
- `test_native_composition.cpp`: pinned SDK class accessor로 만든 합성 LowState
  bytes→CRC→1초 settle→VR align→policy legs/캡처 upper를 검증했다.
  waist12를 모델 default와 다른0.1rad로 설정해 실측 입력 역할의 capture를
  사용하는지 확인했다. Prepare 중 후보null, 정상Finish 후0번 정책 반영/
  12..28 캡처 유지,중복tick 후후보제거/재개금지 통과.
  CRC/profile/stale/R1/mode/motor fault/tilt7종 거부, rollover/backward,
  Finish state 만료도 통과했다.
- 초기 시험은 strict20ms 간격 경계에서 실패했다. fixture cadence를10ms로
  하여 경계 반올림을 피했다. strict age/receipt gap20ms 비교의 부동소수 경계
  처리는 변경하지 않았으므로 정확히20ms cadence에 대한 허용을 주장하지 않는다.
- MSVC C++17 /W4 /WX 및 관련 회귀 **14 passed /110 subtests passed**.
  증거: `logs/test_results/twist2_native_composition_latest.txt`,
  `logs/test_results/twist2_native_composition_regression_latest.xml`.
- 로컬 기존 상태 자료도 확인:
  `logs/runtime/g1_hardware_lowstate.json`은2026-09-07 14:42:30 저장된
  read_only_lowstate 상태 요약으로 당시 mode_pr0/mode_machine5와29축q/dq가 있다.
  native bytes/CRC/시간 연속 sample이 없어 이번 native 초기화 입력으로 사용할 수 없다.
  내부 last_packet_age_s는 저장 당시 값이며 현재 fresh 상태로 해석하면 안 된다.
  `logs/review/20260903/saved_lowstate_review_fixture.json`은29축0값 fixture다.
- 실물 전환에 필요한 다음 입력: 배포 SDK/native layout 확인과 최신 연속
  LowState 원본 및 local receipt 시각. 현재 로컬 자료만으로 실측 초기화
  완료를 선언할 수 없다. G1/WSL/DDS 실행 금지는 유지한다.
- 단일 송신자 연결은 아직 후보 계산 단계다. 0..11 정책/12..21 캡처/
  22..28 VR 소유권을 구성할 수 있지만 실제 lowcmd writer/모드 handoff/
  종료 lifecycle과 배포 ABI는 미연결이다. native 후보 연결 통과는 물리 안전성 검증이 아니다.
- 기존 물리 C++ SHA256 불변:
  `E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F`.


MSVC 개발자 셸의 로컬 빌드(기존 생성 fixture header 필요):
```powershell
cl /nologo /std:c++17 /EHsc /W4 /WX /Ilogs/test_results /Fe:logs/test_results/test_native_composition.exe /Fo:logs/test_results/test_native_composition.obj experiments/twist2_right_arm_manual/test_native_composition.cpp
```
테스트 stdin은 `test_cpp_upper_target.Packet()`의 JSON 한 줄이다.


## 현재 실제 tick 중복 분석·연속성 어댑터 수정 (2026-09-07)

- 저장된 실제6000sample을 Windows에서만 재생했다. 신규 WSL/DDS/로봇 접속/
  publisher/물리 출력 없음. 현재 변경사항과 인계 및 기존 어댑터를 읽고 수정했다.
- 같은tick291쌍 전부 IMU/motor/CRC 영역이 달랐고 header/remote/reserve는
  같았다. 전체bytes 동일쌍0,중복쌍receipt 간격0.329115~5.589701ms.
  따라서 tick을 패킷별 unique sequence로 해석한 기존 규칙이 관측자료와 맞지 않는다.
  실제 firmware의 tick 단위/갱신 구현까지 확인한 것은 아니다.
- 신규 offline_state_continuity.hpp: local receipt 단조 증가/20ms freshness와
  receipt gap을 유지한다. 동일robot tick은 허용하되 마지막tick 전진 이후20ms
  초과 시robot_tick_stalled. 역행/reset은 거부, uint32 rollover는 허용한다.
  중단은 latch되고 나중 전진으로 자동 복구되지 않는다. tick의 정상 주기 가정은 없다.
  이 검사는 Check 호출 시 동작하며 독립 타이머가 아니다.
- native_composition_offline.hpp는 이 검사를 사용한다. local sequence는
  유효상태마다 증가하므로 반복robot_tick을 local sequence로 대체하지 않는다.
  CRC/health/pose/alignment/deadman 조건은 완화하지 않았다.
- decoder에 hg_sdk_crc_le2092_b95a5304를 별도 profile로 추가했다.
  설치SDK CRC source 해시/패킹을 확인한 representation이며 native G1 ABI/
  CDR원본으로 명명하지 않는다. 기존native fixture profile도 유지한다.
- 신규 test_real_state_continuity.cpp:
  수집metadata CRC source/representation 확인→6000CRC/receipt/tick 연속성 통과,
  duplicate291허용, 합성stall/receipt재사용/stale/latch 검사 통과.
  실제 첫sample은 원본buttons0 상태로 native composition에 전달하여
  operator_stop/nullcandidate를 확인했다. R1값을 조작하지 않았다.
- 기존 native composition 테스트는 짧은중복 허용→지속정체중단으로 갱신했고
  capture/정책하체/캡처상체/health7종/rollover/역행/Finish만료까지 통과.
  MSVC C++17 /W4 /WX 빌드 통과. 회귀 **14 passed /110 subtests passed**.
- 증거:
  logs/test_results/twist2_real_state_continuity_latest.txt,
  logs/test_results/twist2_real_state_continuity_review.json,
  logs/test_results/twist2_native_composition_tick_latest.txt,
  logs/test_results/twist2_state_continuity_regression_latest.xml.
- 다음은 실측 캡처 자세와 VR 최초목표의 정렬 준비다. 현재 자료는 R1 off이며
  실제 제어초기화가 성공한 자료가 아니다. 실제single lowcmd owner/모드전환/
  비VR 물리시험/VR 물리시험은 여전히 미실행·미승인이다.
  코드의20ms 부동소수 경계 비교 문제는 이번 변경으로 별도 보정하지 않았다.
- 기존 물리 C++ SHA256 불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.


로컬 재생:
```powershell
.\logs\test_results\test_real_state_continuity.exe logs/test_results/twist2_hg_readonly_capture_20260907.jsonl
```


## 현재 저장 실측 자세↔VR 최초목표 정렬 검사 (2026-09-07)

- 현재 변경사항/인계와 MeasuredComposition의 기존 initial_arm_error0.025rad
  조건을 읽고 유지했다. 새로운 WSL/DDS/로봇 실행이나 물리 C++ 변경 없음.
- 신규 audit_saved_alignment.cpp는 실제 CRC-packed 상태에서1초 정지구간을
  확인한 뒤(1011samples) 저장Quest 첫 active 목표를 pose-only 검사에 전달한다.
  다른 시각에 수집한 세션이므로 packet receipt를 비교시각으로 재지정했다.
  따라서 동시수집 live 정렬 시험이 아니며 health/R1 arming 시험도 아니다.
- 결과 initial_arm_mismatch, 후보null. 오른팔7축 중6축이0.025rad를 초과했다.
| 관절 | 실측 rad | 저장 VR rad | 차이 ° | 허용 |
|---|---:|---:|---:|---|
| 22 right_shoulder_pitch | 0.16053 | 0.17453 | 0.80 | 통과 |
| 23 right_shoulder_roll | -0.05057 | -0.38397 | -19.10 | 초과 |
| 24 right_shoulder_yaw | -0.06134 | 0.00000 | 3.51 | 초과 |
| 25 right_elbow | 1.39617 | 0.95993 | -24.99 | 초과 |
| 26 right_wrist_roll | -0.10733 | 0.00000 | 6.15 | 초과 |
| 27 right_wrist_pitch | 0.28316 | 0.00000 | -16.22 | 초과 |
| 28 right_wrist_yaw | -0.07005 | 0.00000 | 4.01 | 초과 |

- 양성 대조군으로 동일 실측q를 목표로 만든 합성packet은 정렬 검사를 통과했다.
  합성packet은 테스트 안에서만 사용했고 runtime 파일/Unity/VR에 보내지 않았다.
  로봇을 기존 VR 기본자세로 이동하거나 관절 offset을 더하지 않았다.
- 공통 Mink 코드 g1_right_arm_common.py의 DEFAULT_RIGHT_ARM_READY_DEGREES는
  [10,-22,0,55,0,0,0]이며 저장VR 첫 목표와 일치한다.
  G1_USE_HARDWARE_INITIAL_STATE=1이면 별도 right_arm_q_rad를 읽는 기존 경로가
  있지만 freshness/동일세션/CRC를 이 loader가 확인하지 않으며7축만 초기화한다.
  이번에 환경변수/공용초기화파일/기존 hardware-sync launcher는 변경·실행하지 않았다.
- 다음 구현 대상: 최신 LowState와 동일세션에 묶인 Mink 초기 자세/기준 프레임
  동기화. 필요하면 full29축 기구학 자세까지 반영하고 collision/첫 goal 정렬을
  다시 검사해야 한다. 오래된 저장 snapshot을 현재 로봇 상태로 재사용하면 안 된다.
- MSVC C++17 /W4 /WX 빌드와 실제 mismatch 거부/합성 matched 허용2경로 통과.
  증거 logs/test_results/twist2_saved_alignment_review.json(입력hash/관절별오차 포함).
  pose-only 정지구간 검사 통과를 제어 초기화/물리안전성 통과로 해석하지 않는다.


## 현재 Mink29축 LowState seed 초기화 경로 (2026-09-07)

- 현재 변경사항/인계/기본 초기화 함수를 확인하고 기존 변경분을 보존했다.
  기존 물리 C++/G1/WSL/DDS/publisher 실행·변경 없음. VR 프로세스도 시작하지 않았다.
- 신규 MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py:
  schema g1.mink.lowstate_seed.v1,명시적session ID,29관절 이름 순서,
  received_at_unix_s의0..250ms age,reviewed SDK CRC-packed2092bytes를 검증한다.
  CRC 독립검사,mode0/5,finite q/dq/IMU,abs dq<=0.1,roll/pitch<=0.15,
  온도<=75/motorfault0 조건을 확인한다. 부정확한 관절값을 clamp해서 숨기지 않는다.
  이것은 시뮬레이션 초기 seed 검사이며 R1/실제제어arming 판정이 아니다.
- 기존 run_mink_g1_right_arm_virtual_center_live.py에 opt-in
  --initial-lowstate-seed PATH / --initial-lowstate-session ID를 추가했다.
  두 옵션은 함께 필요하며 없으면 기존 기본자세로 시작한다.
  model joint qpos 주소로29축을 모두 적용하고 태스크/목표 프레임을 그 자세에서
  초기화한다. 소켓 생성 전 age를 재검사하고 기존 planner의 CheckConfiguration
  충돌/범위 검사를 통과해야 한다. loader실패 시기본자세로 fallback하지 않는다.
- 적용은 joint29축에 한정된다. free-base 위치/방향은 model 초기값을 유지하며
  metadata base_pose_measured=false다. 실제 월드 프레임 정렬까지 완료된 것이 아니다.
  session은 seed와명시적실행값을 대조하며 아직Unity/수신기세션전달 전체계약은 미연결이다.
- 신규 backend/tests/test_lowstate_mink_seed.py:
  실제 저장 q를 테스트 시계로만 seed fixture화하여29축exact 적용/다른qpos유지/
  입력불변,stale/future/session/order/CRC/length/schema/representation 거부,
  관절범위오류의atomic거부10tests 통과. 오래된상태를live로 승인하거나runtime에 쓰지 않았다.
- 기존standard Mink24tests 포함 **34 passed**.
  XML logs/test_results/twist2_mink_seed_latest.xml.
  최종계약재검사10passed: logs/test_results/twist2_mink_seed_contract_latest.xml.
  syntax/diff 검사 통과. 새로운옵션으로 전체GUI시작/VR사용자확인은 아직이다.
- 다음 필수 연결: 명시적동일세션의최신LowState→seed파일을atomic갱신하는
  읽기전용공급기,플랫폼간wall-clock timestamp 확인,simulation launcher인자전달.
  현capture로그는wallclock/session envelope가없으므로live seed로바로사용할수없다.
  seed유효시간은완화하지않는다. 소켓전검사이후live첫engage freshness/일치 여부는
  C++정렬gate와동일세션상태로다시검증해야한다.
- 기존공유초기화파일/G1_USE_HARDWARE_INITIAL_STATE/BAT는변경하지않았다.
  실물초기화·single rt/lowcmd owner·물리안전성은계속미검증이다.
- 기존물리C++ SHA256:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.


seed envelope 예시 구조(실행용 실제데이터 아님):
```json
{"schema":"g1.mink.lowstate_seed.v1","session_id":"explicit-session",
 "joint_names":["29 ordered names required"],
 "received_at_unix_s":0,
 "representation":"sdk_crc_packed_le2092_b95a5304","packed_hex":"2092 bytes required"}
```
현재 공급기 미연결이므로 위 예시는 loader에서 거부된다. 직접 timestamp를 고쳐
과거기록을 fresh 상태로 사용하지 않는다.


## 현재 LowState→atomic seed 공급기 준비 (2026-09-07)

- 현재 인계/capture/seed loader를 검토하고 로컬 코드를 작성했다.
  신규 WSL/DDS/로봇 실행/VR 시작/publisher/물리 출력 없음.
- 신규 lowstate_seed_writer.py: 세션별 새 폴더의 seed 경로를 소유한다.
  임시파일에 기록/fsync→기존 ReadSeed 검증→os.replace 순서로 교체한다.
  잘못된CRC/health/age/receipt 또는교체실패 시이전seed와임시파일을제거한다.
  기존다른파일을 인수하지 않으며 timestamp는새수신값일때만전진한다.
- 신규 supply_lowstate_seed_readonly.py: 승인 후 Domain0/eth2/rt/lowstate만
  최대30초 구독한다. 새run폴더를exclusive생성,약50Hz로 SDK CRC-packed seed를 갱신.
  msg수신 직후Unix wall-clock을부여하고CRC는수신마다검사한다.
  timeout/오류/종료시seed삭제. 강제종료로남아도consumer250ms만료로거부한다.
  외부45초timeout으로시작정체도제한할계획이다.
- 신규 observe_seed_file_offline.py: Windows에서35초동안seed파일만읽어
  동일session/CRC/health/250ms유효시간과종료후삭제여부를기록한다.
  WSL↔Windows wall-clock/DrvFs파일교체의실제동작은아직미검증이다.
- backend/tests/test_lowstate_seed_writer.py의6tests:
  교체/수신중단뒤만료/삭제,CRC/stale/receipt/replace오류시정리,
  다른소유파일보존 통과. 기존seed loader10개포함 **16 passed**.
  logs/test_results/twist2_seed_supply_latest.xml.
  합성시계+저장bytes fixture만사용했으며runtime seed파일은작성하지않았다.
- 기존물리C++ SHA256불변:
  E61D8A3CF830F0481D8ED664B485D6D8A6CB539956EC9D5FCD6156EB08FCC09F.
- 다음승인요청:30초읽기전용DDS seed공급과Windows 파일검증만실행.
  session=twist2-seed-check-20260907,새폴더=logs/test_results/twist2_seed_live_20260907.
  Unity/Mink 실행이나모터명령/모드변경은포함하지않는다.
  실제제어arming/세션별VR프레임/전체base pose동기화는계속미완료다.

실행 범위(프로젝트 루트, 아직 실행하지 않음):

WSL 공급기:
```powershell
wsl -d Ubuntu -- timeout --signal=TERM --kill-after=2s 45s /home/user/.venvs/g1-teleop/bin/python -B /mnt/c/Users/user/Desktop/G1_Teleop_Project/experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py --directory /mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results/twist2_seed_live_20260907 --session twist2-seed-check-20260907
```

동시에 Windows 파일 검증:
```powershell
py -3.11 experiments/twist2_right_arm_manual/observe_seed_file_offline.py --seed logs/test_results/twist2_seed_live_20260907/seed.json --session twist2-seed-check-20260907 --output logs/test_results/twist2_seed_live_observer_20260907.json
```
DDS discovery/상태 수신 트래픽은 발생한다. publisher·모드 변경·G1 파일작업은 없다.
