# Bimanual Quest simulation preflight — 2026-09-20

## Scope

Unity/Quest를 켜기 전에 fixed-base 양팔 시뮬레이션 경로를 최대한 닫기 위한
read-only/offline 검증이다. 실제 G1, SSH, DDS, motor output 경로는 사용하지 않는다.

새 진입점:

- `tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat`: 아래 3단계를 한 번에 실행한다.
- `tools/RUN_BIMANUAL_NEAR_HANDS_SWEEP.bat`: near-hands 경계 회귀만 실행한다.
- `tools/RUN_BIMANUAL_UDP_CYCLE.bat`: Unity 없는 실제 UDP cycle만 실행한다.
- `tools/bimanual_preflight.py`: 구조/런타임 parity/port/engine 검증.
- `MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py`: ephemeral loopback UDP E2E.
- `backend/tests/test_bimanual_near_hands_sweep.py`: 12mm trigger 경계 sweep.

## Preflight gate

`PREFLIGHT_BIMANUAL_QUEST_SIM.bat`는 다음을 확인한다.

1. runtime root와 isolated MuJoCo 3.12.0 존재.
2. source에 same-scene bimanual installer가 존재.
3. runtime `SampleScene`이 `useExistingScene=1`, `armMode=1`, port 5020으로 저장됨.
4. bimanual production/report/Unity-launch support 파일 12개의 source/runtime SHA-256 parity.
5. bimanual Python 경로에 Unitree/rclpy/cyclonedds/paramiko import가 없음.
6. production simulation UDP 5020이 비어 있음.
7. MuJoCo package/native 모두 3.12.0, `hardware_output_authorized=false`.
구조 검증 뒤에는 near-hands sweep과 ephemeral-port UDP E2E를 연속 실행한다.
최종 성공 문자열은 `READY FOR QUEST TEST`이다. 이 문구는 Unity/Quest 사용감까지
검증했다는 뜻이 아니다.

## Source/runtime drift 발견

첫 preflight 실행은 runtime `G1BimanualSimulationSender.cs` SHA mismatch를 잡았다.
diff는 commit `45146f4`에서 source에 도입된 `CanClearMustLeave(...)` helper가
runtime에는 아직 inline condition 형태로 남아 있던 것이었다.

두 구현의 조건은 동일했다:

`backend ready && tracked && !inZones && !pinch`

runtime 원본을 다음 위치에 백업한 뒤 source 버전으로 동기화했다.

`logs/backups/bimanual_sender_sync_20260920_134512/...`

그 뒤 core parity를 정리했고, 2026-09-20 후속 보강에서 report/resolver/verifier까지 포함해 parity 12개가 모두 일치하도록 확장했다.

## Near-hands 12mm boundary sweep

seed `20260920`으로 hard-clearance-safe 자세 320개를 검사했다.

- near-hands: 160개.
- ordinary: 160개.
- trigger threshold: inter-arm 12mm.
- threshold fraction: `0.2951253054328338`.
- local 5mm-safe lower fraction: `0.28489868044654365`.
- 12mm 경계 최근접 샘플 margin: `0.058464mm`.
- 320개 중 최소 global clearance: `5.063977mm`.
- false near-hands trigger / missed near-hands trigger: 0.

대표 4개 실제 return도 실행했다.
near-hands 두 자세는
`separate_left → safe_waypoint → home → complete`,
ordinary 두 자세는
`safe_waypoint → home → complete`로 READY에 도달했다.

대표 결과의 최소 clearance는 7.092192mm 이상,
최대 출력 가속도는 50.557419deg/s² 이하였고,
5mm hard clearance와 60deg/s² limit을 유지했다.

### 중요한 경로 관찰

기록 fixture에서 home까지 단순 joint-space interpolation을 진단용으로 검사하면
중간 `t≈0.18~0.27`에서 geometry penetration이 발생한다.
관측 최저는 약 -31mm였다. 이는 실제 출력 경로가 아니며,
현재 v2가 direct-home 대신 separation과 safe waypoint를 쓰는 이유를 뒷받침한다.

## Unity-free real UDP cycle

production 5020을 사용하지 않고 ephemeral loopback port에서 실제 backend subprocess와
UDP packet/feedback을 주고받았다.

최종 preflight 실행 port: `55879`.

상태 전이:

`READY → TRACKING → RETURNING(pinch) → READY(pinch) → TRACKING`

- accepted inputs: 9.
- minimum sampled clearance: `40.372503mm`.
- maximum reconstructed output acceleration: `33.886225deg/s²`.
- BLOCKED: 0.
- MuJoCo: 3.12.0.
- simulation_only: true.
- hardware_output_authorized: false.

## Full regression

near-hands sweep 2개, post-session cycle requirement, report numerical-tolerance 회귀가 포함되어 전체 bimanual suite는 96개다.
source worktree:

- `96/96 PASS`
- runtime: `114.384s`
- recorded replay p95: `6.63ms`
- recorded replay max: `8.04ms`

runtime folder:

- `96/96 PASS`
- runtime: `127.967s`
- recorded replay p95: `7.19ms`
- recorded replay max: `15.80ms`

Windows Unity launcher/path contract는 source 집중 검증 포함 31/31 PASS,
runtime의 `test_windows_tool_paths`는 23/23 PASS였다.
이 시간은 해당 노트북의 실행 관측치이며 hard real-time 보증이 아니다.

## Post-session Quest cycle verifier

실제 Quest operator 테스트가 끝난 뒤에는 다음 명령으로 최신 operator session을 자동 판독한다.

`tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat`

이 도구는 Unity를 실행하지 않고 최신 accepted-input JSONL을 찾아 static report + current-code replay를 수행한다.
필수 cycle 조건은 최소 1회 engage, 완료된 pinch return, 그 뒤 re-engage이며,
BLOCKED/출력 한계/replay mismatch는 기존 strict failure와 함께 비정상 종료로 반환한다.
report에는 pinch return 수, re-engage 수, near-hands recovery 수, separation side 집계가 기록된다.

기존 user-confirmed Quest fixture에 새 조건을 적용한 결과:
`Quest cycle PASS`, `Replay PASS`, tracking starts 2, re-engage 1,
pinch returns 2, near-hands recovery 0, final READY였다.

## Unity remote-launch environment hardening

원격 command shell에서 누락될 수 있는 `PROGRAMDATA`, `ALLUSERSPROFILE`, `TMP`는
`tools/RESOLVE_UNITY_EDITOR.bat`가 현재 CMD process에만 기본값을 채운다.
`setx`/registry write는 사용하지 않으며 machine/user environment를 변경하지 않는다.
실제 노트북 CMD smoke에서 세 변수를 비운 뒤 각각 `C:\ProgramData`,
`C:\ProgramData`, 사용자 Temp로 복구되는 것을 확인했다.

## 2026-09-21 Quest operator acceptance

최신 operator session `unity_20260921_091420_0176388.jsonl`에서 normal flow acceptance를 닫았다.

- Quest cycle verifier: PASS.
- current-code replay: PASS.
- tracking starts: 2.
- re-engage: 1.
- completed pinch returns: 2.
- final state: READY / pinch.
- BLOCKED: 0.
- malformed/nonfinite output: 0.
- replay minimum sampled clearance: 30.914499mm.
- maximum output speed: 43.090153deg/s.
- replay maximum output acceleration: 60.000000000005deg/s².
- tracking control tick p95/max: 12.360040 / 13.328100ms.
- near-hands recovery: 0 in this operator session.

사용자도 실제로 re-engage 1회가 정상 동작했다고 확인했고,
동일 re-engage가 로그 sequence 491에서 두 번째 TRACKING으로 기록되었다.
세션 원본 SHA-256은
`d091391676a2603c88c7e7d501e5163e22cc92e02a6b22ce2a506650f2eacd21`이다.

첫 09:07 세션은 engage → pinch return → READY까지 정상이고 re-engage를 실제로 수행하기 전에
끝났기 때문에 verifier가 `quest_cycle_no_reengage`를 반환했다. 이는 기능 실패가 아니라
해당 세션 범위 미완료였다. 09:14 세션이 완전한 acceptance evidence다.

session report의 acceleration comparison tolerance는 기존 controller regression과 동일한
`+1e-4 rad/s²` numerical slack으로 맞췄다. 설정된 60deg/s² limit 자체는 변경하지 않았다.

near-hands recovery는 이번 operator session에서는 실제 발동하지 않았다.
그 경로는 deterministic 320-pose sweep, recorded fixture, mirror, retry/fail-closed,
UnityCycle replay로 별도 검증된 상태를 유지한다.

따라서 fixed-base Quest → Unity → MuJoCo **normal bimanual operator flow는 완료 checkpoint**로 본다.
현재 범위는 fixed-base simulation과 sampled geometry에 한정되며,
실제 G1의 연속시간 충돌 회피, 제동, 구조 오차, 네트워크 지연 또는 물리 안전을
증명하거나 실행을 승인하지 않는다.
