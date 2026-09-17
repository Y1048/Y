# Current review and remediation index

Last updated: 2026-09-07
Latest local validation: 2026-09-07

## Offline trajectory A/B experiment

- Source: optional viewer mode and isolated local launcher; live controller unchanged.
- Tests: 10 selected tests pass. Initial .5 candidate failed settling and was
  rejected; .1 candidate settles but is slower than A on the simple waypoint test.
- Remaining: candidate is NOT accepted for live use; synthetic visual comparison
  is not captured Quest replay or physical verification. See TRAJECTORY_AB.md.
- Ledger/index now contain 341 scoped files, all full_text_review, static_only 0.

## R20 full recorded trajectory timing

- 검토: segment 2 입력/HOLD/RETURN 전체 1756단계, 격리 3.12,
  horizon 3, 캐시 없이 조건별 3회. 기존 중복 조회는 프로세스 메모리에서 재현.
- 코드 수정: 없음. 소스 검토 coverage 및 canonical ledger 항목 변경 없음.
- 테스트: 두 조건 모두 기준 대비 qpos/preview 오차 0, accepted step 불일치 0.
  평균 계산 11.325 -> 8.081ms (약 29% 감소). 16.667ms 초과는
  기존 총 4회, 새 방식 총 1회/5268단계. 둘 다 DEADLINE_MISSES.
  logs/test_results/r20_single_clearance_full_20260907.json 및
  r20_double_clearance_control_20260907.json 참고.
- 남은 항목: planner-only 순차 측정, 단일 segment다. paced/GPU/VR 및
  실물 검증 아님. 이동 속도/IK/충돌 설정 변경 없음. R20 partial 유지.

## R20 single-call clearance result

- 수정: 공용 검사에 (valid, clearance) API 추가, 기존 bool API 유지.
  후보 비교기만 중복 거리 계산 제거; benchmark 검사 계측도 새 API 적용.
  캐시/샘플/안전거리/IK 수치 변경 없음.
- 테스트: 3.11 87 passed/10 subtests/2 skipped; 3.12 47 passed/2 skipped.
  GPU smoke는 이번에 미실행. 합성 궤적/판정 동일성 검사 통과.
  12프레임 거리 계산 336 -> 192. r20_single_clearance* XML 참고.
- 남은 항목: 전체 paced 재생 deadline/실제 렌더 검증. R20 partial 유지.

## R41 recorded capture compatibility

- 검토/테스트: logs/captures의 12 JSONL을 전체 패킷 파싱 및 capture loader로 확인.
  11파일 129938패킷/활성11184 모두 통과. 기존 빈 캡처 1개는 정상 거부.
  당시 accepted_packets=0 확인. pytest 28 passed / 35 subtests.
- 코드 수정: 없음. 원본 캡처 보존. 결과 r41_capture_inventory_20260907.csv 및
  r41_capture_compatibility_20260907.xml (logs/test_results).
- 남은 항목: 다른 입력/전체 IK 재생/실제 runtime 검증. 데이터 해독 통과와
  로봇 동작 성공을 구분한다.

## R41 core active-clearance contract

- 검토/수정: active packet의 누락/null 거리 거부, 거리 boolean/string 거부.
  direct active sample의 invalid clearance는 HOLD. inactive pinch 계약 유지.
- 테스트: 71 passed / 26 subtests; r41_core_clearance_20260907.xml.
  parser/controller/mock relay/replay/entry/release 선택 검사, 실제 소켓 없음.
- 남은 항목: 과거 active-no-clearance 캡처는 거부되는 의도적 호환성 변경.
  전체 캡처/runtime 검증 미완료; 수치 거리는 실제 충돌 안전 보증이 아니다.

## R2/R33/R41 unguarded core runtime blocked

- 검토: supported entry를 건너뛴 core main의 SDK 접근 경로 확인.
- 코드 수정: validate-only는 보존하고 다른 실행은 guard 설치 완료를 요구.
  pre-publisher-check-only도 공식 entry 경유. 승인 및 잠금 검사는 유지한다.
- 테스트: 64 passed / 8 subtests / localhost UDP 1 deselected.
  gate7_guarded_entry_regression_20260907.xml. SDK/socket import trap으로
  direct 거부와 validate-only의 무통신 경로 확인. 제어 수치 변경 없음.
- 남은 항목: core 함수 단독 사용/파서 자체의 계약 통합, 실제 SDK/물리 검증.
  wrapper 우회 runtime을 닫았으며 모든 R2/R33/R41 해결로 표시하지 않는다.

## R1 extracted production finalizer execution

- 검토/수정: 운영 finally AST를 fake IO로 실행하는 테스트 5개 추가.
  실제 shared release 함수 사용; production 코드 변경 없음.
- 테스트: 50 passed / 5 subtests, gate7_extracted_finalizer_20260907.xml.
  정상/이전 fault/부분 및 전체 실패/실측 부재/해제 예외/송신기 부재 검사.
  result와 저장 JSON, 자원 정리 및 hold config 전달을 확인했다.
- 남은 항목: 전체 main/SDK/WSL/물리 runtime. R1의 물리 검증은 아직 미완료.
  fake Write 성공을 실제 DDS 전달 또는 firmware 제어권 반환으로 해석하지 않는다.

## HOLD/release offline regression refresh

- 검토: R1/R3/R33/R40/R50 관련 release/acquisition/state-machine 회귀 범위.
- 코드 수정: production 변경 없음. release contract에 전체 송신 실패 및
  해제 중 snapshot 상실 테스트 2개 추가; 새 finding은 만들지 않았다.
- 테스트: 7파일 45 passed, hold_release_regression_20260907.xml.
  fail-closed 증거 확인. Gate7 finalizer wiring은 AST 검사이고 callbacks는 fake다.
- 남은 항목: physical validation은 미완료. pinch REGULAR_RETURN과 종료
  zero-weight release는 구분해야 한다. 8개 Gate6/7 설정 잠금 유지.

## R20 duplicate clearance inspection

- 검토: EvaluateStep의 중간 자세 루프가 CheckConfiguration(q) 내부에서
  GetClearance(q)를 호출한 뒤 거리 기록용으로 다시 호출한다.
  EvaluateLookahead도 첫 next_q 거리를 별도 계산한다. 기존 R20 범위다.
- 코드 수정: 없음. 검사 횟수/안전 기준/IK 설정 변경 없음.
- 테스트: MuJoCo 3.11.0, 합성 목표 +[0.02,0,0.01]m, 12프레임에서
  거리 호출 336회, 직전과 완전히 동일한 q인 호출 180회, 모두 accepted.
  test_mink_step_acceptance_comparison.py: 26 passed.
  최초 측정 CLI는 PowerShell 인용 오류로 실패했고 stdin 방식으로 재실행했다.
- 남은 항목: 동일 검사에서 유효성 및 거리를 함께 반환하는 API 검토/구현.
  공개 CheckConfiguration(bool) 호환성과 관절 제한 조기 거부를 유지해야 한다.
  q만 키로 쓰는 장기 캐시는 모델/geom/pair 변경을 놓칠 수 있어 채택하지 않는다.
  위 측정은 단일 합성 입력이며 3.12 전체 캡처 성능 개선 또는 원인 확정이 아니다.

## R20 candidate CPU profile

- 검토/테스트: cProfile 1756스텝 + warmup, 기준 궤적 오차 0.
  충돌 거리 계산 2432556호출; CheckConfiguration 누적 6.031s,
  solve_ik 5.155s, DAQP 누적 .635s. 누적 시간은 중첩됨.
- 코드 수정: 없음. 안전 검사/설정 유지.
- 남은 항목: 중복 계산 재사용 검토. profile 수치는 realtime 성능 판정이나
  간헐 프레임 지연 원인 확정이 아니다. 기본 vanilla 경로 성능 아님.
  결과 logs/test_results/r20_candidate_profile_20260907.prof 및 .json.

## R20 three-repeat timing evidence

- 검토/테스트: 동일 후보 경로 1756스텝 x3, 궤적/표시 관절값 불일치 0.
  release deadline misses 6/1/0, 서로 같은 프레임에서 재발하지 않음.
  3회차 표시 age deadline misses 57; 전체 DEADLINE_MISSES 유지.
- 코드 수정: 없음. 통과 기준/제어값을 바꾸지 않았다.
- 남은 항목: 간헐 지연 원인 미확정. 추가 반복으로 PASS를 고르지 말 것.
  결과 logs/test_results/r20_paced_render_repeat3_20260907.json.

## R20 render latency isolation

- 검토: 3.12 standalone와 전체 후보 replay의 환경별 비교.
- 코드 수정: 없음. thread 제한은 시험 프로세스에만 임시 적용.
- 테스트: standalone 2 passed. 전체 replay thread 제한/default 재시험
  표시 age P95 6.830/5.936ms, 양쪽 1756프레임/오차 0.
  deadline 초과 3/1회로 둘 다 DEADLINE_MISSES.
- 남은 항목: 과거 130ms 지연 미재현, 원인 미확정. thread 제한을 기본으로
  적용하지 않는다. 제어/장치 설정 변경 없음; 결과 경로는 CHAT_HANDOFF 참고.

## R20 paced candidate render integration

- 검토: 오래된 XML 기준 거부 확인 후 현재 모델의 동일 캡처 기준 재생 생성.
- 코드 수정: 없음; 격리 3.12 후보 진단 경로, 기본 vanilla 경로와 다름.
- 테스트: 1756스텝 궤적 완전 일치, renderer state mismatch 0. 하지만
  DEADLINE_MISSES: release deadline 1회 초과, 표시 age P95 130.094ms.
  결과 logs/test_results/r20_paced_render_20260907.json. 성능 PASS 아님.
- 남은 항목: 렌더 지연 원인 분리/재측정. 장치/네트워크 미실행.

## R20 real renderer process smoke

- 검토/수정: 실제 startup 실패 후 pipe poll의 BrokenPipeError 재현 및 수정.
- 테스트: 실제 렌더/자식 프로세스 lifecycle 포함 187 passed. 60프레임 전달,
  qpos mismatch 0, 화면 변화 59, 정상/시작 오류 뒤 잔류 프로세스 없음.
- 남은 항목: 전체 IK paced replay 성능은 미측정; 짧은 합성 renderer smoke다.
  결과는 logs/test_results/r20_render_smoke. G1/WSL/DDS 미실행.

## R20 rendered replay exception boundary

- 검토: 준비/로드/종료 실패의 최종 보고 누락.
- 코드 수정: ERROR/exit 1 및 부분 출력 경고; renderer 종료 중복 방지.
- 테스트: 185 passed, compile, 실제 missing-reference CLI. 자원 실패는 mock 검증.
- 남은 항목: 전체 GPU/worker 통합 및 다른 진단 CLI; R20 partial 유지.

## R20 candidate benchmark exception boundary

- 검토: 기준/구간/계산 예외 처리 누락. 기존 R20 범위 확장.
- 코드 수정: FAIL/exit 1 및 저장 실패 경고; 정상 성능 판정은 유지.
- 테스트: 183 passed; 실제 missing-reference CLI exit 1 및 FAIL 확인.
- 남은 항목: 다른 진단 CLI 및 전체 성능/렌더 통합 검증.

## R20 return inspection exception boundary

- 검토: 누락된 두 번째 연동 구간과 기준/계산 실패의 보고 경로 확인.
- 코드 수정: FAIL/exit 1 및 저장 실패 경고; 정상 판정 유지.
- 테스트: 178 passed/4 subtests; 실제 missing-reference CLI 실패 보고 확인.
- 남은 항목: 전체 렌더 통합, 다른 진단 도구. 물리/IK 변경 없음.

## R20 reach diagnostic exception boundary

- 검토: 모델/계산 예외 시 이전 결과가 남는 경로를 확인했다.
- 코드 수정: 예상 예외는 FAIL/exit 1; 저장 실패는 명확한 stale-report 경고.
- 테스트: 172 passed/2 subtests; 실제 missing-capture CLI exit 1 및 FAIL 저장.
- 남은 항목: 다른 진단 CLI 통합/예외 처리. R20은 여전히 partial.

## R24 local default engine mitigation

- 검토: 설치된 MuJoCo 3.11에서 wrist-roll 거리 회귀 실패 재현 (-133.2 mm).
  해당 수치를 실제 침투의 증거로 해석하지 않는다.
- 코드 수정: 로컬 공통 BAT만 검증된 격리 3.12를 기본 선택한다.
  물리/이전 prototype 선택, IK 비용, 속도, 충돌 프로파일은 유지한다.
- 테스트: 3.11 회귀 1 failed/4 passed/2 subtests; 격리 3.12 관련 검사
  38 passed/3 subtests; BAT 선택 및 standard 검사 38 passed (중복 포함).
- 남은 항목: VR 확인, 다른 R24 회귀 항목, 물리/전역 3.11 경로.
  전체 엔진 마이그레이션이나 물리 검증 완료가 아니다.

## R53 applied joint limits and engine

- Review/fix: record applied joint-limit hash and MuJoCo version in both senders;
  validate optional fields and compare before replay. Old records stay unverified.
- Tests: 99 passed, 17 subtests passed; seven modules compiled. No device runtime.
- Remaining: other runtime model changes, solver configuration and other replay
  paths. Limits and engine-version equality is not full dynamics equivalence.

## R53 explicit asset bytes

- Review/fix: generated flat MJCF explicit mesh/hfield/texture content digest;
  pre/post-load comparison; capture format validation and replay mismatch rejection.
- Tests: 93 passed, 9 subtests passed; five Python files compiled.
- Remaining: runtime settings/engine equivalence, other replay routes and atomic
  asset snapshot. Legacy XML-only captures do not verify assets. R53 remains partial.

## R53 prototype metadata follow-up

- Review/fix: prototype main now attaches the loaded XML metadata to packets,
  matching the common live path without changing existing state fields.
- Tests: 81 passed; two modules compiled. Sender is mocked and selected main
  statements are extracted, not a complete runtime validation.
- Remaining: asset/runtime binding and other replay paths; R53 stays partial.

## R53 replay XML check

- Review: replay decoded but did not compare captured XML identity.
- Fix: opt-in loader metadata; reject mismatched XML before pose application.
  Legacy captures remain explicitly UNVERIFIED, not equivalent-model evidence.
- Tests: 56 model-isolation tests passed; three Python modules compiled.
  No viewer, WSL, DDS or physical runtime. Canonical ledger/index refreshed (338/338).
- Remaining: external assets/runtime binding, other replay paths and prototype
  sender metadata. R53 remains partial. Evidence: CHAT_HANDOFF.md.

## 3.12 로컬 실행 경계

- 검토: 로컬 엔진 선택과 물리 provenance 거부.
- 코드 수정: 격리 entry/명시적 BAT 선택. 기존 물리 런처 미변경.
- 테스트: 25 passed 및 validate-only import.
- 남은 항목: Unity Play/VR/실물 검증 없음. STANDARD_MINK_LIVE.md 참고.

This file is the current entry point for the precision review. It does not replace the detailed evidence in the linked review documents.

## 2026-09-06 Standard Mink 선택 준비

- 검토: 별도 prototype 대신 공통 live 루프에 IK 선택점을 연결.
- 코드 수정: StandardMinkPlanner 및 로컬/잠금 물리 런처 추가. 기존 기본 IK 유지.
- 테스트: 고유 31개 단위 테스트/10 subtests; Python compile 통과.
- 남은 항목: VR/G1 검증 없음; 알려진 MuJoCo 거리 문제 및 기존 미해결 finding 유지.
  [구조와 실행파일](STANDARD_MINK_LIVE.md) 참조.

## Review record

- 2026-09-06 MuJoCo 3.12 격리 확대 검증: 83 passed/26 subtests,
  렌더 및 viewer smoke 통과. 코드 수정 없음; 기본 3.11/WSL/물리 미변경.
  DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md에 검토/테스트/남은 항목 기록.

- 2026-09-06 추가 검토/수정/테스트/남은 항목:
  [Standard Mink offline](STANDARD_MINK_OFFLINE_20260906.md).
  기존 R40 provenance 계약에 맞춘 가상 helper 수정; 물리 검증 완료로 보지 않는다.

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1-R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20-R32
- [`REVIEW_20260903_CONTINUATION_2.md`](REVIEW_20260903_CONTINUATION_2.md): R33-R39
- [`REVIEW_20260903_CONTINUATION_3.md`](REVIEW_20260903_CONTINUATION_3.md): R40-R49
- [`REVIEW_20260903_CONTINUATION_4.md`](REVIEW_20260903_CONTINUATION_4.md): R50-R59
- [`REVIEW_20260903_CONTINUATION_5.md`](REVIEW_20260903_CONTINUATION_5.md): R60-R67
- [`REVIEW_20260904_BACKEND_CORE.md`](REVIEW_20260904_BACKEND_CORE.md): backend protocol/config/calibration/camera/runtime core review; no new finding, R27/R32 reconfirmed
- [`REVIEW_20260904_BACKEND_SUPPORT.md`](REVIEW_20260904_BACKEND_SUPPORT.md): inspection/admin/feedback/diagnostic helper review; R20 extended to `inspect_feasible_target_return.py`
- [`REVIEW_20260904_BACKEND_DIAGNOSTICS.md`](REVIEW_20260904_BACKEND_DIAGNOSTICS.md): Mink collision/feasibility/step diagnostic review; R20/R27 reconfirmed and R24 extended to stale velocity expectations
- [`REVIEW_20260904_BACKEND_DIAGNOSTICS_2.md`](REVIEW_20260904_BACKEND_DIAGNOSTICS_2.md): Mink benchmark/render/tracking/reach review; no new finding, R20/R24/R27 boundary reconfirmed
- [`REVIEW_20260904_BACKEND_DIAGNOSTICS_3.md`](REVIEW_20260904_BACKEND_DIAGNOSTICS_3.md): remaining backend virtual-center/camera helpers; R24/R53 extended, R27 boundary retained
- [`REVIEW_20260904_LAUNCHERS.md`](REVIEW_20260904_LAUNCHERS.md): remaining `tools/*.bat` and launcher source review; no new finding, existing launcher findings reconfirmed
- [`REVIEW_20260904_CONFIG_AND_FRAME.md`](REVIEW_20260904_CONFIG_AND_FRAME.md): configuration, camera-profile and wrist-frame source review; R66 reconfirmed, physical locks unchanged
- [`REVIEW_20260904_RECOVERY_MULTISTRATEGY.md`](REVIEW_20260904_RECOVERY_MULTISTRATEGY.md): deferred multi-strategy recovery experiment review; R53/R55 reconfirmed
- [`REVIEW_20260904_REMAINING_EXPERIMENTS_AND_HARDWARE_HELPERS.md`](REVIEW_20260904_REMAINING_EXPERIMENTS_AND_HARDWARE_HELPERS.md): final posture-sweep, TWIST2 and hardware-helper full-text review; no new finding, existing R20/R43-R45/R49/R50/R53/R54/R56 boundaries reconfirmed
- [`REMEDIATION_20260904.md`](REMEDIATION_20260904.md): R64/release batch
- [`REMEDIATION_20260904_CONTINUATION.md`](REMEDIATION_20260904_CONTINUATION.md): R2/R33/R40/R41/R42 supported-path mitigation
- [`REMEDIATION_20260904_RUNTIME_SUPERVISION.md`](REMEDIATION_20260904_RUNTIME_SUPERVISION.md): R40/R50 runtime supervision
- [`REMEDIATION_20260904_PROVENANCE.md`](REMEDIATION_20260904_PROVENANCE.md): R15/R21/R23/R35/R51/R65 provenance/freshness
- [`REMEDIATION_20260904_STATE_BINDING.md`](REMEDIATION_20260904_STATE_BINDING.md): R40 base/model/config binding
- [`REMEDIATION_20260904_DIRECT_JOG_RELEASE.md`](REMEDIATION_20260904_DIRECT_JOG_RELEASE.md): R46 direct-controller release integration

The bounded source inventory has now been read in full. Full-text coverage does
not mean the code is correct or that open findings are remediated.

## Current reconciled coverage

The canonical bounded ledger and code index were regenerated from the current
checkout after adding the checked Mink stateful-trajectory layer.

```text
total current scoped files : 341
full_text_review           : 341
static_only                : 0
static check failures      : 0
```

Authoritative files:

```text
logs/review/20260903/source_checks.csv
logs/review/20260903/source_checks_summary_20260904.json
docs/CODE_INDEX.md
```

The semantic rule is deliberately conservative: prior decisions are preserved,
explicit continuation deltas can promote a path to `full_text_review`, and newly
discovered files default to `static_only`. Therefore 341/341 is a review-state
count, not a correctness score or physical acceptance.

## Remediation status

Local continuation: [R32 V1 integer validation](REMEDIATION_20260905_PROTOCOL_V1.md).
Local continuation: [R27 rigid pose validation](REMEDIATION_20260905_RIGID_POSE.md).
Full-text coverage is complete only for the bounded 341-file inventory, not every
asset/vendor/generated file in the repository. Remediation remains incomplete.

| Finding | Status | Current evidence |
| --- | --- | --- |
| R57 | SOURCE SCOPE FIXED; environment validation pending | ASIX interface + 192.168.123.0/24 only; 5 fully mocked PowerShell tests pass; no firewall applied |
| R58 | SOURCE MITIGATION; supported IPv4 configuration only | Ethernet/DNS/diagnostics 131 tests; custom routes and mismatched stores blocked before mutation; DHCP lease and real network validation pending |
| R63 | PARTIAL; TCP default and head-profile drift checks | Shared TCP default retained at 20; JSON vs TeleImager head stream checked offline (97 tests/96 subtests). Full TeleImager/runtime relationships and device rate validation remain open |
| R59/R67 | SOURCE FIXED; Unity build/install pending | Unique shared APK destination; SHA256 and explicit serial; fixture tests pass |
| R52 | SOURCE MITIGATION; physical validation pending | Settle tail age/gap and pre-publisher snapshot recheck; fake-buffer regressions pass |
| R64 | IMPLEMENTED; integration validation pending | Command-ingress current-checkout CI PASS |
| R1 | IMPLEMENTED; integration/physical validation pending | Release regression PASS in offline safety CI |
| R3 | IMPLEMENTED; integration/physical validation pending | Gate 6 interruption/fault regression PASS |
| R34 | IMPLEMENTED; integration/physical validation pending | Gate 6 fault-release regression PASS |
| R46 | IMPLEMENTED IN DIRECT CONTROLLER; runtime/physical validation pending | Shared release finalizer integrated in `g1_right_arm_jog.py`; direct/wrapper release regressions PASS |
| R2 | SUPPORTED PATH MITIGATED; unguarded core runtime blocked | Final-segment guard tests PASS; direct main requires installed guards; physical validation pending |
| R41 | CORE SOURCE FIXED; runtime validation pending | Active finite numeric clearance mandatory; invalid direct samples hold; inactive pinch preserved; 71 tests/26 subtests pass |
| R33 | SUPPORTED PATH MITIGATED; unguarded core runtime blocked | Acquisition freshness/order checks retained; direct main blocked before SDK; runtime validation pending |
| R40 | SUPPORTED PHYSICAL PATH SOURCE MITIGATION COMPLETE; physical validation pending | 29-joint/model/config binding plus raw startup/runtime `rt/odommodestate` position/quaternion continuity and live base stability checks |
| R42 | SUPPORTED JOG PATH MITIGATED; direct controller path still uses entry-installed collision/full-body guard | Permit/full-body/final-segment tests PASS |
| R50 | PARTIAL SUPPORTED-PATH MITIGATION | IMU/motor health + current runtime base/odometry stability PASS; remote/deadman/CRC remain open |
| R21 | SUPPORTED HARDWARE-SYNC PATH MITIGATED | Startup provenance tests PASS |
| R51 | SUPPORTED PHYSICAL STARTUP PATHS MITIGATED | Per-run token/precheck/raw-odom tests PASS |
| R23 | IMPLEMENTED; process validation pending | Static failure-propagation assertion PASS; BAT process run pending |
| R35 | SUPPORTED GATE 7 RELAY PATH MITIGATED | Relay token/retired-session tests PASS |
| R65 | SUPPORTED UNITY/MINK PATH MITIGATED | Source clock/backlog/sender tests PASS |
| R15 | SOURCE MITIGATION COMPLETE ON SUPPORTED LIVE PATH; runtime validation pending | Live/replay/relay/hardware provenance tests PASS |
| R20 | PARTIAL; reach CLI exception boundary | Decode/FK/model/runtime failures report FAIL; unwritable reports warn against stale output. 172 tests/2 subtests pass; missing-capture CLI exit 1 verified. Other diagnostic CLI coverage pending |
| R24 | PARTIAL | Local shared-loop BAT defaults to isolated 3.12 after distance regression; physical/global 3.11 and other regression items remain; VR unverified |
| R25 | MINIMUM STALENESS GATE IMPLEMENTED | Newer C#/csproj blocks prebuilt DLL; fixture tests pass; build equivalence not proven |
| R26 | IMPLEMENTED | Zero-step/nonfinite duration rejected; internal long replay preserved |
| R28 | IMPLEMENTED | Config/runtime finite positive confirmation and finite nonnegative dt agree; regression passed |
| R53 | PARTIAL | Isolated loaders; both senders attach XML/assets/applied joint limits/version; capture replay compares these fields (99 tests/17 subtests). Other runtime changes, other replay paths, atomic asset binding and device integration remain open |
| R27 | IMPLEMENTED IN WORKING TREE; local regression verified | Shared SO(3)/SE(3) input checks; invalid matrix and valid round-trip tests pass; runtime/remote CI not run |
| R32 | IMPLEMENTED IN WORKING TREE; local regression verified | V1 uses strict _integer; 34 protocol/foundation tests and 42 subtests pass; remote CI not run |

## Historical Remote CI

The following runs are earlier remote evidence, not verification of the current
uncommitted working tree. Their current remote state was not rechecked in this batch.

```text
.github/workflows/offline-provenance-regression.yml
Run 33824261133 : PASS
```

This covers command ingress, Unity source-clock/backlog provenance, Gate 7 relay/replay/hardware provenance, startup token/state/raw-odometry binding, and live Mink producer provenance.

```text
.github/workflows/offline-safety-regression.yml
Run 33824155653 : PASS
```

This covers release finalization, Gate 7 collision/acquisition guards, LowState IMU/motor health, runtime base/odometry stability and startup/runtime odometry continuity, Jog safety/final-segment checks, and direct Jog shared-release integration.

Both workflows are offline from the robot: no Unitree publisher, DDS endpoint, WSL runtime, Unity/Quest runtime or G1 connection is created.

## Current Next Work

1. R20/R24/R53: remaining diagnostic contracts and writers; keep source fixes separate from test coverage.
2. R58: real Windows provider validation remains pending; supported IPv4 rollback includes DNS/marker failure. Custom routes and differing stores are blocked, not reconstructed. No admin runtime without approval.
3. R63: camera configuration ownership/rate consolidation.
4. R50 and R43-R45/R49: retain physical/experimental restrictions; do not infer missing SDK or hardware evidence.
5. Unity/Quest/WSL/G1 runtime checks require their actual environments and exact authorization where applicable.

R57 source scope is fixed in this batch. Real WSL source routing may require a
separately reviewed interface/source rule; do not restore LocalSubnet/Any-interface
access merely to make a test pass. R58 LowState rule failure recovery now passes
47 combined mocked tests. DNS-local recovery plus diagnostics pass 103 tests;
supported Ethernet configuration rollback now passes 131 tests; custom route
configurations remain blocked and real provider/lease validation is pending. See
`REMEDIATION_20260906_FIREWALL_SCOPE.md` for the verification boundary.

## Historical Progress Notes

The entries below are chronological evidence snapshots. Later entries in the
handoff/diagnosis documents and the status table above supersede their old
"remaining" statements. In particular: opt-in local 3.12 and viewer checks now
exist, C# builds passed, and selected R53 resume integrity work was implemented.

Isolated version comparison: 3.12.0 removes the observed sign flip for the fixed
fixture and passes wrist regression (4 tests/3 subtests) plus six related files
(43 tests/12 subtests). Default Python remains 3.11.0; no production upgrade.
Broader compatibility and viewer validation are still required before adoption.

Fixed wrist-roll fixture engine comparison: native default and increased iterations/
tighter tolerance still flip signs; legacy is consistent on these seven samples only.
No controller change. Official documentation cautions against legacy distance accuracy;
do not treat this as a replacement approval. See the wrist-roll diagnosis document.

Wrist-roll regression rerun: 4 passed/2 subtests/1 failure reproduced. Fixed-pose
audit on MuJoCo 3.11.0 flips distance sign under 1e-12m global translation while
mesh projection separation remains positive. See DIAGNOSIS_20260906_WRIST_ROLL_DISTANCE.md.
No control changes or test weakening; this is not a physical collision clearance approval.

2026-09-06 combined verification: 161 tests/106 subtests passed across eight related
test files. Runtime and Editor csproj builds passed (63/6 warnings respectively),
including camera PiP and APK builder sources. Five changed Python modules compiled.
This is not a Unity Editor/Player build or device test. The known wrist-roll
kinematics regression was not in this run and remains unresolved.

R61 source fix: one 2-second header/payload assembly deadline and decreasing read
timeout prevent indefinite partial-frame occupation. 91 contract tests passed,
including extracted C# compile/mock-stream execution. Full Unity build and real
stalled TCP/reconnect/display verification remain unperformed.

R63 numeric validation partial fix: strict profile dimensions/fps and finite FOV,
finite live/replay CLI timing. 115 tests/80 subtests passed; CLI validators extracted
without transport execution. Configuration ownership/rate consolidation remains open.

R58 final IPv4/DHCP verification added to configure/restore. Stale static marker
is cleared before mutation and address removal errors propagate. 50 tests passed,
all network cmdlets mocked. DNS verification and rollback remain open; no actual
network configuration was changed.

R58 adapter-selection partial remediation: configure/restore require exactly one
matching ASIX or an explicit matching InterfaceIndex. Subsequent setters use the
index. 42 contract tests passed; selection prefixes only with mocked adapters.
Transactional rollback and final-state verification remain open; no network changes.

R56: native pktmon exit codes and nonempty artifacts now gate completion. Removed
unconditional pre-start stop. 32 diagnostic-contract tests passed, with pktmon
mocked in PowerShell; no actual capture/admin/network operation was performed.

R53 retained-evidence follow-up: state/result/log hashes, containment, pose and
summary-result consistency are checked before reuse. SKIPPED needs state only.
12 tests/14 subtests passed; subprocess mocked, full sweep not run. This detects
accidental evidence changes, not coordinated tampering with summary and files.

R53 per-attempt follow-up: RunCase uses UUID evidence directories and rejects
malformed result contracts as ERROR. Mixed timeout output is preserved. Eleven
tests/eleven subtests passed (subprocess mocked); no full sweep or hardware run.
Retained artifact integrity on resume remains open.

R53 resume follow-up: SHA256 source/config/G1-asset inventory plus Python/package
versions now gate reuse and final promotion. Legacy maps without provenance cannot
resume. Eight tests/seven subtests passed; full sweep not run. This is not a
continuous filesystem monitor; per-case artifact validation remains open.

2026-09-06 R53: posture-sweep workers now use temporary XML instead of the shared
demo XML. Six tests and seven subtests passed, including actual model loading and
exception cleanup. Resume provenance and other experiment writers remain open;
no full sweep or hardware runtime was executed.

R54 local reporting remediation: sweep results now distinguish partial completion,
no successful poses, and infrastructure errors. Five tests and seven subtests passed;
no actual sweep or hardware run. See REMEDIATION_20260905_SWEEP_OUTCOME.md.

```text
1. R20/R24/R53 remain open backend-contract/tool issues; R27/R32 locally remediated; keep remediation separate from review bookkeeping
2. Preserve the experimental TWIST2 R43-R45/R49 block before any physical use
3. Do not invent R50 remote/deadman/CRC checks; verify actual read-only Unitree SDK fields first
4. Plan simulation/WSL integration checks with hardware output locked
5. Keep the reconciled ledger/CODE_INDEX current when files change
```

R40's source-side startup/runtime odometry continuity is closed on supported paths, but physical validation is not. Do not expand physical testing yet: actual connected-G1 SDK field compatibility, remote/deadman/CRC evidence, and WSL/DDS runtime behavior remain unverified.

## Safety boundary

- Repository hardware authorization remains locked.
- No physical G1 command is authorized by a review or remediation commit.
- No G1 file, service, mode or state may be mutated without explicit approval for that exact action.
- Unit, process, simulation and physical verification must remain separately labeled.
