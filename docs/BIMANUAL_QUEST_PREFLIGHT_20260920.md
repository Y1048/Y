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
4. bimanual production/source 파일 9개의 source/runtime SHA-256 parity.
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

그 뒤 parity 9개가 모두 일치했고 preflight가 PASS했다.

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

새 sweep 2개가 추가되어 전체 bimanual suite는 94개다.
source worktree:

- `94/94 PASS`
- runtime: `118.379s`
- recorded replay p95: `8.42ms`
- recorded replay max: `10.40ms`

runtime folder:

- `94/94 PASS`
- runtime: `127.907s`
- recorded replay p95: `6.50ms`
- recorded replay max: `9.70ms`

이 시간은 해당 노트북의 실행 관측치이며 hard real-time 보증이 아니다.

## Remaining operator validation

Unity 없이 닫을 수 있는 범위는 여기까지다. 다음 실제 operator 단계는
`SampleScene Play + Quest`에서 손 추적/정렬/사용감과 실제 pinch 흐름을 확인하는 것이다.

현재 검증은 fixed-base simulation과 sampled geometry에 한정된다.
실제 G1의 연속시간 충돌 회피, 제동, 구조 오차, 네트워크 지연 또는 물리 안전을
증명하거나 실행을 승인하지 않는다.
