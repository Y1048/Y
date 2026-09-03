# 정밀 검토 계속 기록

기준 branch: `Y1048/Y` `refactor/teleop-architecture`

검토 기준 commit: `bf0b86327f371b539b84cba1c0dc55a23a863b40`

이 문서는 [`REVIEW_20260903.md`](REVIEW_20260903.md)의 R1~R19 이후 정밀 검토를 기록한다.
이번 작업은 **검토 전용**이다. Production controller, hardware configuration, authorization,
Unity scene, G1, WSL runtime을 변경하거나 실행하지 않았다.

## 우선순위

물리 시험 확대 전에 처리할 우선순위는 기존과 같다.

```text
R1 -> R2 -> R3 -> R15
```

아래 R20 이후 finding은 추가 검토 결과다. 그중 hardware pose provenance에 직접
연결되는 R21, 검증 도구의 거짓 성공 가능성이 있는 R20/R23/R25/R29를 다음 묶음으로
다루는 것이 적절하다.

## 추가 본문 검토 범위

이번 연속 검토에서 다음 계열을 본문 기준으로 확인했다.

- backend foundation: calibration, transforms, protocol V1/V2, watchdog, config,
  camera source/transport, base mapping, inspection contact, motion reference
- Mink offline diagnostics: candidate benchmark, rendered benchmark, step-acceptance
  comparison, speed/lag/reach/collision/distance diagnostics, feasible-target validation
- related backend tests: foundation, protocol V2, motion reference, candidate benchmark,
  tracking lag, recorded speed, simulation feedback, inspection contact
- hardware read-only/test utilities: initial-state receive/verify, base-state normalization,
  fake Mink generator/consumer, safety gate, manual joint probe and corresponding tests
- launchers: hardware pose sync, Gate 7 VR recording, read-only/dry-run/offline launchers,
  bounded jog and shoulder-pitch full-authority trial launchers

`logs/review/20260903/source_checks.csv`의 canonical count는 이번 문서에서 수정하지 않았다.
따라서 원래의 117 full-text / 147 static-only 수치는 이 추가 검토를 아직 반영하지 않는다.
정확한 전체 coverage 수치는 ledger를 다시 생성하거나 검토 경로를 대조한 뒤 갱신해야 한다.

## R20 · P2 · 실패 상태를 기록하면서 프로세스는 성공 종료할 수 있음

여러 benchmark/diagnostic CLI가 결과 JSON에는 실패 또는 검토 필요 상태를 기록하지만
종료 코드는 성공으로 남긴다.

- `benchmark_mink_candidate.py`: trajectory parity가 맞으면 timing deadline miss가 있어도 0을 반환한다.
- `benchmark_mink_rendered_replay.py`: `DEADLINE_MISSES`와 `DISPLAY_AGE_MISSES`도 0을 반환한다.
- `compare_recorded_pose_speeds.py`, `verify_feasible_target.py`: `REVIEW_REQUIRED`를 출력해도
  명시적인 실패 종료가 없다.
- `diagnose_mink_distance_invariance.py`: `BLOCK_DEPLOYMENT`를 기록할 수 있지만 명시적인
  nonzero 종료가 없다.

영향:

- BAT/CI가 `%ERRORLEVEL%` 또는 process return code만 보면 품질·시간 기준 실패를 PASS로
  해석할 수 있다.
- JSON 상태와 process 상태가 서로 다른 성공 의미를 갖는다.

조치:

1. 실행 오류, parity 실패, timing 실패, review-required를 서로 다른 nonzero code로 구분한다.
2. 단순 보고 전용 실행이 필요하면 `--report-only` 또는 `--allow-deadline-miss`처럼 명시적인
   opt-in을 둔다.
3. BAT는 JSON 최종 상태도 확인하고 예상 상태만 PASS로 표시한다.

## R21 · P2 · 초기 G1 자세 snapshot의 provenance와 freshness를 검증하지 않음

`receive_initial_state.py`는 UDP 5007 패킷에서 `right_arm_q_rad`가 7개이고 숫자로 변환되며
대략적인 범위 안에 있는지만 확인한다. 정상 WSL forwarder가 보내는 `mode`,
`sent_at_unix`, `received_packets`, 속도와 source provenance를 확인하지 않은 채
`Fresh G1 right-arm pose captured`라고 기록한다.

영향:

- 오래된 packet, replay packet 또는 다른 localhost sender의 합성 packet이 먼저 도착하면
  G1 실측 자세로 저장될 수 있다.
- 해당 프로세스는 command를 보내지 않지만 저장값은 Mink startup seed에 사용된다.

조치:

- `mode == READ_ONLY_LOWSTATE`를 요구한다.
- 송신 timestamp와 로컬 수신 시각의 freshness 계약을 정의한다.
- sequence/packet count 및 허용한 sender/provenance를 검증한다.
- 오른팔 q와 선택적으로 dq의 유한값·길이·일관성을 함께 확인한다.

## R22 · P3 · full-body pose sync PASS는 실제 G1 전신 동기화 증명이 아님

`verify_initial_pose_sync.py`가 실제 hardware snapshot에서 읽는 값은 오른팔 7개다.
29관절 검사는 `_state_packet()`이 만든 `all_joint_q_rad`를 같은 Mink configuration의
29관절과 다시 비교한다.

따라서 이 검증이 증명하는 범위는 다음과 같다.

```text
captured G1 right-arm 7 q -> Mink right-arm seed 보존
Mink 29 q -> Unity state packet serialization 보존
```

실제 G1 전신 29관절과 Mink 전신 29관절이 일치한다는 증명은 아니다.
결과 필드와 안내 문구에서 이 범위를 명확히 구분해야 한다.

## R23 · P2 · hardware-sync launcher가 실패 return code를 신뢰성 있게 전달하지 않음

`START_MINK_G1_HARDWARE_SYNC.bat`는 initial snapshot 수신 또는 검증 실패 시 `goto :end`로
이동하지만 마지막에 명시적인 실패 code를 반환하지 않는다. Mink controller가 실패한
경우에도 오류 메시지만 출력하고 호출자에게 해당 code를 보존하지 않는다.

영향:

- 사람이 창을 읽으면 실패를 볼 수 있지만 상위 launcher/automation은 성공으로 오해할 수 있다.

조치:

- 각 실패 분기에서 `RC`를 설정한다.
- 마지막에 `endlocal & exit /b %RC%` 패턴으로 통일한다.
- snapshot 실패, sync validation 실패, controller 실패를 구분한 code로 반환한다.

## R24 · P3 · 현재 velocity cap과 diagnostic report provenance가 다름

현재 virtual-center controller의 shoulder/elbow와 wrist cap은 모두
`math.degrees(0.08)`, 즉 약 `4.583662 deg/s`다. 그러나 다음 diagnostic report 문자열은
여전히 `40/100 deg/s` 조건이라고 기록한다.

- `backend/tools/compare_mink_step_acceptance.py`
- `backend/tools/diagnose_mink_tracking_lag.py`

실제 계산은 `live.virtual_center_velocity_limits()`를 호출하므로 현재 cap을 사용하지만,
결과 metadata는 과거 조건을 주장한다.

영향:

- 현재 report를 과거 40/100 조건의 재현 결과로 잘못 해석할 수 있다.
- hash가 같아도 사람이 읽는 experimental boundary가 틀리다.

조치:

- cap 값을 runtime에서 추출해 숫자 배열과 단위를 report에 기록한다.
- 설명 문자열에 하드코딩한 과거 값을 제거한다.
- 관련 test에서 report의 velocity metadata가 실제 helper 결과와 일치하는지 검사한다.

## R25 · P2 · Unity packet verifier가 stale compiled DLL을 검사할 수 있음

`backend/tools/verify_unity_state_packets.ps1`는
`Unity_G1_VR/Temp/bin/Debug/Assembly-CSharp.dll`을 직접 로드한다. 실행 전에 C# source를
compile하지 않고, DLL timestamp/hash와 source 상태도 비교하지 않는다.

영향:

- C# source가 바뀌었지만 Temp DLL이 재생성되지 않은 경우 이전 assembly가 PASS할 수 있다.
- 결과 JSON에 DLL SHA를 기록하는 것만으로 해당 DLL이 현재 source와 일치한다고 증명되지는 않는다.

조치:

- Unity batch compile을 선행하거나, 검증 대상 commit/source hash와 assembly build manifest를
  함께 묶는다.
- 최소한 DLL이 관련 source보다 오래되면 fail-closed한다.
- 기존 DLL을 검사하는 explicit mode라면 결과에 `prebuilt_assembly_only=true`를 기록한다.

## R26 · P3 · 아주 짧은 duration을 허용한 뒤 solver step이 0회가 될 수 있음

`verify_virtual_center_kinematics.py`는 `0 < duration <= 30`을 허용하지만 `RunCase`는
`range(round(duration_s / DT))`를 사용한다. `duration < 0.5 * DT`이면 iteration이 0회다.
그 뒤 마지막 `velocity`, percentile, error arrays를 사용하므로 정상 report 대신 예외가 날 수 있다.

조치:

- `duration_s >= DT` 또는 최소 1 step을 명시적으로 요구한다.
- loop count를 `max(1, ceil(duration_s / DT))`로 정하되 실제 의도와 report duration을 맞춘다.
- zero-step 및 1-step CLI regression test를 추가한다.

## R27 · P3 · calibration pose API가 rigid SE(3)가 아닌 scale/shear matrix를 허용함

`calibration._pose_matrix()`는 4x4 shape, finite 값, 마지막 homogeneous row만 확인한다.
회전 블록의 직교성 및 determinant +1을 검사하지 않는다. `ArmCalibration.map_pose()`는
source neutral 회전의 transpose를 inverse로 사용하므로 rigid rotation이라는 전제가 필요하다.

영향:

- 직접 4x4 API로 scale/shear가 포함된 matrix가 들어오면 결과 rotation도 비직교가 될 수 있다.
- JSON profile의 quaternion 경로는 정규화되지만 public matrix API는 같은 보장을 하지 않는다.

조치:

- 공통 `validate_rotation_matrix`를 두고 `R.T @ R ~= I`, `det(R) ~= +1`을 확인한다.
- `split_pose`, `invert_pose`, calibration 입력이 같은 SE(3) 계약을 사용하도록 통일한다.
- scale, shear, reflection, near-singular matrix test를 추가한다.

## R28 · P3 · workspace debounce 설정 계약이 서로 다르고 NaN direct input을 막지 못함

`load_teleop_config()`는 `workspace_exit_confirm_s`에 0을 허용하지만
`WorkspaceExitDebounce` constructor는 반드시 양수여야 한다. 따라서 config parser는 통과하고
runtime object 생성에서 실패할 수 있다.

또한 direct API에서 `NaN <= 0`과 `NaN < 0` 비교가 false이므로 constructor와 `update()`가
NaN을 받아 accumulator를 NaN으로 만들 수 있다. 현재 checked-in config는 0.8초이며 정상이다.

조치:

- config와 runtime class 모두 같은 `positive finite` 계약을 사용한다.
- `math.isfinite()` 검사를 constructor와 `update()`에 추가한다.
- 0, NaN, +inf, -inf 및 정상 continuous/reset sequence test를 추가한다.

## R29 · P2 · VR recording 성공이 Gate 7 dry-run 전달 성공을 증명하지 않음

`START_G1_GATE7_VR_RECORDING.bat`는 Gate 7 receiver를 UDP 5014에서 시작하지만 실제 5014 bind
또는 process liveness를 확인하지 않고 recorder와 Unity를 시작한다. 이후에는 recorder의 UDP 5008
bind만 확인한다.

`gate7_mink_capture.py`는 localhost 5014로 UDP `sendto()`한 뒤 수신 확인 없이 capture를 기록하고,
`accepted_packets > 0`만으로 result `passed=true`를 만든다.

영향:

- Gate 7 receiver가 시작 직후 종료하거나 5014 bind에 실패해도 capture 자체는 성공할 수 있다.
- 이 파일을 “Gate 7을 통과하며 기록된 session”으로 오해할 수 있다.

조치:

- recorder 시작 전에 5014 listener를 확인한다.
- launcher가 시작한 Gate 7/recorder process의 조기 종료와 cleanup을 관리한다.
- capture result와 Gate 7 result/session ID를 서로 연결해 최종 paired PASS를 만든다.
- receiver가 없는 상태에서 capture는 되지만 validation은 실패하는 process-level test를 추가한다.

## R30 · P3 · fake Mink safety E2E가 production Mink packet contract를 통과하지 않음

`mink_target_dry_run.py`는 `right_arm.joints` 7개만 읽고 schema, state source,
session, sequence, active/state 조합, freshness, 29관절 일치성을 검사하지 않는다.
첫 packet은 안전 게이트에 넣지 않고 simulated measured와 previous command로 그대로 사용한다.

반면 실제 Gate 7 parser는 schema/source/session/sequence/29관절/right-arm 일치와 상태 조합을
검사한다. `test_mink_safety_pipeline.py`도 production parser로는 부족한 최소 packet을 보낸다.

영향:

- 이 PASS는 7관절 rate-limit와 stale-stop consumer 동작만 증명한다.
- production Gate 7 transport/contract 또는 실제 measured-vs-requested startup 안전성의 E2E 증명이 아니다.

조치:

- test 이름과 출력에 `legacy_7_joint_gate_only` 같은 범위를 명시하거나,
- production parser를 사용하는 별도 E2E를 만들고 measured fixture를 독립 입력으로 둔다.
- 첫 requested packet을 measured state로 간주하는 동작을 실제 hardware 검증으로 해석하지 않는다.

## R31 · P3 · manual joint probe가 수신 stream의 연속 freshness를 확인하지 않음

`probe_joint_motion.py`는 최초 LowState 수신만 기다린 뒤 baseline/motion 구간에서 최신 snapshot을
10ms마다 반복해서 읽는다. packet count가 증가하는지 또는 마지막 수신 age가 timeout 이내인지
확인하지 않는다.

영향:

- 측정 중 stream이 멈추면 같은 stale sample을 반복 수집한다.
- 이미 excursion이 관측된 뒤 stream이 끊긴 경우 dominant index 결과가 PASS할 수 있지만
  전체 관측 구간의 실시간 연결은 증명되지 않는다.

조치:

- snapshot의 received count와 last_rx_monotonic을 함께 사용한다.
- 구간별 최소 unique packet 수, 최대 packet gap, 종료 시 freshness를 검사한다.
- stream stall, duplicate snapshot, 정상 continuous motion test를 추가한다.

## R32 · P3 · protocol V1 integer fields가 bool/string/float를 정수로 coercion함

`PosePacketV1`과 `StatePacketV1`은 sequence/time fields에 `int(value)`를 사용한다.
이 때문에 JSON boolean, numeric string, 소수 float가 정수로 변환될 수 있다. 예를 들어
`true -> 1`, `1.9 -> 1`, `"7" -> 7`이다.

V2 parser는 bool을 제외한 실제 integer type을 요구하므로 계약 강도가 서로 다르다.
현재 active path가 V2/legacy adapter 중심이라면 우선순위는 낮지만, V1을 strict protocol로
설명하거나 재사용할 때 sequence 의미가 약해진다.

조치:

- V1도 공통 strict `_integer()`를 사용한다.
- bool, float, numeric string, null, 음수, 정상 integer regression test를 추가한다.

## 검토했으나 새 finding으로 올리지 않은 사항

- `g1_base_state.py`의 quaternion 정규화와 초기 heading 기준 position/velocity 변환은 현재
  unit tests와 코드 의도가 일치했다. 실제 odometry topic의 frame 의미 검증은 별도 실기 범위다.
- bounded jog와 shoulder-pitch full-authority launcher는 physical output 전에 config validation,
  read-only motion-mode query, startup precheck, path permit, explicit operator confirmation을 거친다.
  이번 정적 검토에서 새로운 authorization bypass는 확인하지 않았다. 다만 기존 R8 freshness와
  precheck/path assumptions는 그대로 상속한다.
- `verify_camera_simulation.py`는 camera mount/image/shared-memory failure 시 nonzero 종료한다.
  실제 D435i, Unity display, latency/frame-drop 검증은 이 결과의 범위 밖이다.
- `offline_render_worker.py`의 latest-state slot은 bounded/nonblocking이며 sequence 감소와 non-finite
  snapshot을 거부한다. 이 정적 검토만으로 OS별 multiprocessing/render 안정성을 보증하지 않는다.

## 코드 수정과 실행 여부

```text
Production Python/C#/C++ 수정 : 없음
Config/authorization 수정      : 없음
Unity scene/asset 수정          : 없음
G1 파일/서비스/state 변경      : 없음
WSL/Unity/G1 실행               : 없음
Repository test 실행            : 없음
Hardware publisher 생성         : 없음
```

이번 commit은 review 문서만 추가한다. 위 finding의 수정은 별도 작업으로 분리한다.
수정에 착수하더라도 R1/R2/R3/R15 우선순위를 먼저 유지하고, physical output은 별도 명시적 승인 전까지 열지 않는다.
