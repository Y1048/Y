# GPT 인계: 기존 오른팔 씬을 양팔 시뮬레이션으로 확장

기준일: 2026-09-18. 아래 내용은 같은 날짜의 이전 작업 기록보다 우선한다.

## 작업 후 push 권한 (2026-09-18 사용자 지시)

사용자는 이후 이 프로젝트의 검증된 작업 커밋을 별도 확인 없이
`codex/g1-laptop-sync-20260917` 브랜치에 push하도록 승인했다.
작업 상태와 검증 결과를 확인한 뒤 일반 fast-forward push를 수행하고,
원격 HEAD 반영 여부를 확인해 보고한다. 원격 이력이 달라졌다면 먼저 대조한다.
이 승인은 `main` 변경/병합, force push, reset/clean, 실제 G1 실행이나
무관한 변경의 게시를 포함하지 않는다.

## Latest: session report + near-hands return v2 (2026-09-18)

Read [BIMANUAL_NEAR_HANDS_RETURN_20260918.md](BIMANUAL_NEAR_HANDS_RETURN_20260918.md) and
[BIMANUAL_SESSION_REPORT_20260918.md](BIMANUAL_SESSION_REPORT_20260918.md) first.
The read-only report tool found a real historical simulation failure in
`unity_20260918_155812_5222579.jsonl`: tracking loss at sequence 697 entered return and
ended BLOCKED with `return_path_blocked:return_swept_clearance`. The exact q/velocity/
acceleration and 17-step checked brake tail are preserved as a regression fixture.

Current return policy is `bimanual_staged_return_v2`. When inter-arm clearance at return start
is below 12 mm, it consumes the checked brake tail to zero speed, chooses a one-arm separation
route, then uses the existing safe waypoint -> home -> 0.5s settle path. Published movement still
passes the original checked_stop_plan 5 mm / 0.25-degree sampled guards. Original fixture and
its left-right mirror both finish in 510 ticks (8.5s), with minimum clearance 5.696/5.751 mm.
Normal recorded returns remain 356/321 ticks and do not use the fallback.

The report runner propagates strict exit codes, scans latest sessions to EOF, distinguishes reason
changes from real state transitions, and reports malformed JSON without aborting summary.
After runtime install/restart, identify new logs with `return_policy=bimanual_staged_return_v2`.
No physical G1/DDS/motor validation. Collision performance baseline remains the 1e28597 sphere path.
A detached `43e108d`-based source suite and the installed runtime suite both pass 89/89 on
isolated MuJoCo 3.12.0. The trigger-specificity regression keeps recovery off for a posture with
6.769 mm global but 85.631 mm inter-arm clearance. Runtime backup is
`logs/backups/bimanual_near_hands_return_20260918_210946/`; 385 protected files were unchanged.
Headless BAT smoke passed on loopback port 57287 without using production port 5020.
Follow-up retry/fail-closed regression brings source/runtime suites to 91/91. In the recorded
near-hands fixture, zero-speed probes are left 5.788 mm and right 4.573 mm; therefore an injected
checked swept-clearance rejection of the left route correctly re-probes right and then BLOCKS
because right is below the unchanged 5 mm hard limit. A state-machine-only test also confirms the
transition to `separate_right` when the opposite candidate is explicitly probe-safe. No production
motion code changed in this follow-up. Runtime test-only backup:
`logs/backups/bimanual_near_hands_retry_20260918_214512/`; 391 protected files unchanged.

## Latest: performance micro-optimization stop point (2026-09-18)

Read [BIMANUAL_PERFORMANCE_STOP_POINT_20260918.md](BIMANUAL_PERFORMANCE_STOP_POINT_20260918.md) first.
After `1e28597`, further low-risk micro-optimizations were evaluated and rejected. Squared-distance
sphere masking was bit-equivalent but did not reproduce a full-replay speedup in an isolated rerun;
a second AABB stage and smaller `mj_geomDistance` distmax were slower/inconsistent. Unsafe-pair
early exit saved only 171 of 1,282,088 exact pair calls (0.0133%).

Therefore production remains `1e28597`. Do not relax 5 mm clearance, 0.25 deg sweep samples,
exact survivor geometry distance, or zero-distance/contact handling for performance. Any next
performance step must be architectural (for example independently validated batch/parallel checks),
retain the identical sampled trajectory and 0-rad Quest replay, and show reproducible clean A/B gains.
Concurrent session-report work was preserved and not committed by this analysis.

## Latest: conservative sphere broadphase (2026-09-18)

Read [BIMANUAL_PERFORMANCE_SPHERE_20260918.md](BIMANUAL_PERFORMANCE_SPHERE_20260918.md) first.
The checked stopping tail still dominated cost after the kinematics optimization.
Threshold broadphase now uses world bounding spheres that enclose each geom local AABB;
only certainly distant pairs are skipped, and survivors still use exact `mj_geomDistance`.
The 5 mm hard limit, 0.25 deg sweep samples, speed/acceleration, IK and return policy are unchanged.

2,927 recorded states rechecked 1,258,802 excluded pairs and 1,200 random states rechecked
510,643 excluded pairs with zero bad exclusions. Quest replay remains 0 rad identical and
minimum clearance remains 5.032381 mm. Clean detached suite: 77/77 PASS. Runtime targeted
suite: 16/16 PASS; current integrated runtime also passed 82/82 including unrelated local
session-report tests. A-B-B-A p95 mean fell 20.902 -> 17.300 ms under the same high-load run.
Only the two sphere files were installed with backup; 279 protected files were unchanged.

## Latest: clearance kinematics optimization (2026-09-18)

Read [BIMANUAL_PERFORMANCE_KINEMATICS_20260918.md](BIMANUAL_PERFORMANCE_KINEMATICS_20260918.md) first.
The first performance pass (`dc1a29a`) kept contact generation but used `mj_fwdPosition`.
The new normal clearance path uses `mj_kinematics`; only an exact zero distance promotes
once to `mj_fwdPosition` and the established robust contact/zero-mesh probe path.
No collision sample, 5 mm limit, 0.25 deg sweep substep, motion/return policy, or speed limit changed.

300 recorded poses x 439 pairs had 0 raw distance/transform difference, 500 random poses
matched full-forward nearest clearance, and the Quest fixture stayed 0 rad identical with
5.032 mm minimum clearance. Repeated A/B p95 mean: 15.055 -> 12.274 ms (18.47% lower).
Source/runtime suites: 76/76 PASS each; actual BAT headless smoke PASS. Two Python/test
files were installed with backup; 277 protected files were unchanged. Running Python was not restarted.

## Latest: clearance performance optimization (2026-09-18)

Read [BIMANUAL_PERFORMANCE_CLEARANCE_20260918.md](BIMANUAL_PERFORMANCE_CLEARANCE_20260918.md) first.
The Quest-confirmed replay showed that checked stopping-tail collision validation,
not the QP solver, dominated tracking time. `clearance()` now uses MuJoCo's
position/contact stage `mj_fwdPosition` instead of full `mj_forward`; sample count,
5 mm hard clearance, IK/motion/return policies and all speed/acceleration limits are unchanged.

A 500-pose equivalence check had 0 distance/pair/contact mismatches. The confirmed
Quest fixture remained bit-for-bit identical in joint output (0 rad max difference).
Direct old/new replay reduced p95 from about 16.42 ms to 14.63 ms and total replay
from 21.73 s to 19.79 s in one controlled pair. Source/runtime suites: 74/74 PASS each.
The hard 5 mm boundary remains unchanged because 28.3% of recorded tracking states
were below 7 mm; increasing it would materially change the already-confirmed feel.
Installed Python/test files are backed up under runtime logs/backups/bimanual_perf_20260918_154241.
The user's already-running Python process was not restarted; optimization loads next start.

## Latest: Quest pinch/re-engage confirmed (2026-09-18)

Read [BIMANUAL_QUEST_CONFIRMED_20260918.md](BIMANUAL_QUEST_CONFIRMED_20260918.md) first.
The user confirmed the latest Quest session works. The same log records two staged
pinch returns with one successful re-engage between them. A compact fixture replays
2,927 state ticks with 0 rad maximum logged-joint difference, 5.032 mm minimum
sampled clearance, and the 60 deg/s^2 output acceleration bound. Source and laptop
runtime bimanual suites both pass 73/73. This is Quest simulation confirmation,
not physical G1 validation or a guarantee of continuous host-side 60 Hz timing.

## 최신: pinch 재engage와 startup 후속 검증 (2026-09-18)

[재engage/startup 검증](BIMANUAL_REENGAGE_STARTUP_20260918.md)을 우선 읽는다.
실제 14축 BimanualSimulation/UnityCycle로 tracking → pinch → 단계형 복귀 → READY →
active-only 거부 → inactive rearm → 재engage를 끝까지 검사했다. 출력 연속성,
60도/s² 가속도 제한과 sampled clearance를 유지하며 전체 소스 suite는 71/71 PASS다.

Unity의 mustLeaveZones 해제 조건을 CanClearMustLeave()로 분리해 의미를 바꾸지 않고
회귀검사화했다. 실제 Unity 참조 C# 컴파일 error 0, engage/leave 592조합,
backend generation/order 17조합이 PASS했다. Unity Editor가 열려 있어 이번 C# 파일은
바탕화면 실행 폴더에 hot-copy하지 않았다. 다음 정상 Unity/Play 중지 때 선택 반영한다.

MuJoCo 3.12 fresh import 10회는 약 0.201~0.268초, headless full startup 5회는
약 1.196~1.277초였다. 이전 간헐 장시간 import 지연은 이번 반복에서 재현되지 않았고
원인은 여전히 미확정이다. 새 Quest 착용 pinch/reengage 사용감은 미검증이다.

## 최신: 단계형 복귀의 실제 기록 재생과 노트북 경로 동기화 (2026-09-18)

[새 기록과 검증 범위](BIMANUAL_OBSERVED_RUN_20260918.md)를 우선 읽는다.
노트북에 생성된 `unity_20260918_134204_4595123.jsonl`에는 단계형 복귀 정책과
출발 커밋 `7e74219`에 일치하는 다섯 Python 파일 해시가 있다.
startup부터 추적 손실 복귀 완료까지 3,433 상태 틱을 회귀 fixture로 추가했다.
소스/노트북 실행 폴더에서 각각 70/70 PASS, 경로 검사 21/21 PASS를 확인했다.
로그 관절값과 재생 결과는 최대 차이 0rad였다. 복귀는 로그 시각 6.063초,
시뮬레이션 5.75초이며, 중간 자세/home/0속도 0.5초 정착을 재시도 없이 완료했다.

추종 중 최소 sampled clearance는 약 5mm(왼손목/오른손 충돌 형상)였다.
새 후보의 정지 경로를 거부한 보호 감속이 반복됐으므로 이를 여유가 충분한
무충돌/사용감 보증으로 해석하지 않는다. 속도·IK·복귀 알고리즘은 변경하지 않았다.
이 기록에는 복귀 후 re-engage가 없고, 이번 작업에서 Unity/Quest를 새로 실행하지 않았다.

직전 경로 패치 9개 파일을 같은 노트북의 바탕화면 실행 폴더에 백업 후 반영했다.
4개 실제 BAT는 `--check-unity-path`만 실행해 확인했으며, 보호 파일 508개를 보존했다.
백업: 실행 폴더 `logs/backups/windows_tool_paths_20260918_135946/`.
별도 데스크톱의 실제 설치·동작은 미확인이다.
엔진 import 지연은 재발한 보조 실행을 별도 기록했고 해결 완료로 판정하지 않는다.

## 이전: 데스크톱 Unity 설치 경로 이식성 (2026-09-18)

사용자가 데스크톱 Codex의 실행 실패를 전달했다. 이제 데스크톱 실행 보고가 있으므로,
아래 과거의 “별도 데스크톱 작업 없음”을 현재 상태로 해석하지 않는다.
이 세션은 노트북 소스 작업본에서 수정·오프라인 검증했다. 데스크톱 설치를 직접
확인하거나 원격 파일을 덮어쓴 것은 아니다.

[Windows 경로 탐색과 검증](WINDOWS_TOOL_PATHS_20260918.md)을 참고한다.
Unity 실행 BAT 네 개는 공통 `tools/RESOLVE_UNITY_EDITOR.bat`를 사용한다.
유효한 UNITY_EXE → ProgramFiles Hub 6000.5.4f1 → USERPROFILE Hub 순서다.
`--check-unity-path`는 첫 인수로 주면 경로만 출력하고 다른 작업 전에 종료한다.
ADB_EXE/VCVARS64 override와 고정 설치 드라이브/사용자 안내문도 정리했다.
새 경로 검사 21개와 기존 관련 검사 2개 PASS. 실제 Unity·로봇/DDS·APK 설치·
C++ 컴파일은 수행하지 않았다. 기존 양팔/복귀 제어 코드는 변경하지 않았다.
데스크톱은 기준 브랜치의 변경과 공통 resolver를 함께 받아야 한다.

## 이전: 기존 단일팔 방식의 단계형 복귀 복원 (2026-09-18)

[복귀 방식/속도 비교와 검증](BIMANUAL_RETURN_PARITY_20260918.md)을 우선 읽는다.
사용자가 경계 보강 버전을 실행하고 복귀 방식/속도 차이를 보고했다.
기존 양팔의 posture-only 직접 복귀를 중간 자세 → home → 0속도 0.5초 정착의
Ruckig 복귀로 변경했다. 오른팔 waypoint와 jerk 프로파일을 재사용하고 왼팔에 미러링했다.
추종 공동 14축 QP/ArmMotionPolicy와 bilateral clearance/checked stop tail은 유지한다.
속도 90/180도/s, 가속도 60도/s² 상한은 올리지 않았다.

소스/노트북 실행 폴더에서 각각 68/68 PASS, 실제 BAT 기동 PASS.
같은 두 시작 상태의 60Hz 복귀 시간은 10.733→5.933초, 9.833→5.350초였다.
최신 로그 prefix 전체 재생도 복귀/재engage를 완료했다. 이는 새 Quest 검증이 아니다.
노트북 실행 폴더에 7개 파일을 선택 설치했고 363개 보호 파일은 유지했다.
기존 Python/Unity는 재시작하지 않았다. Play 중지 후 Python을 정상 종료하고
BAT부터 다시 실행한다. 새 run 행의 `return_policy=bimanual_staged_return_v1`을 확인한다.

## 이전: 추적 손실/예외/재시작 경계 보강 (2026-09-18)

[경계 보강과 검증](BIMANUAL_BOUNDARY_HARDENING_20260918.md)을 우선 읽는다.
`99202f5` 검토에서 발견한 손실 중 급정지를 검사 tail 감속으로 변경했다.
출력 qpos 차분과 내부 속도 일치, 0속도 READY, solver 예외 처리,
bounded JSON, origin quaternion 정규화, backend 세대/순서 검사를 추가했다.
소스와 노트북 실행 폴더에서 각각 58/58 PASS. C# 실제 참조 컴파일,
재시작/순서 17개와 기존 engage 576개 검사 PASS. 9개 파일을 백업 후
설치했고 보호 대상 604개 파일과 기존 오른팔 보정/씬은 유지했다.

새 C#은 옛 backend의 세대 필드 없는 피드백을 수락하지 않는다.
**Play 중지와 기존 Python 정상 종료 후 새 BAT와 Play를 모두 재시작한다.**
새 JSONL 첫 행의 `boundary_policy=bimanual_boundary_v1`을 확인한다.
간헐 엔진 import 지연 원인은 미확정이다. 단계별 시간 기록을 추가했고
중단된 보조 실행은 PASS로 합산하지 않았다. Quest 착용, 전체 Unity Play
재시작 시나리오 및 실제 G1은 미검증이다. 상세 한계는 위 문서에 있다.

## 이전: 양팔 동작 보정과 노트북 설치 (2026-09-18)

[동작 보정과 검증 기록](BIMANUAL_MOTION_CORRECTION_20260918.md)을 우선 읽는다.
사용자가 감속/실행 엔진 수정 후 Quest에서 단일 오른팔 대비 동작 회귀를 확인했다.
기존 오른팔의 접근 감속, 손목 우선, 어깨 자세, 몸통/팔꿈치 및 회전 우선순위를
좌우 공통 `ArmMotionPolicy`로 적용하고, 양팔 공동 QP와 검사된 정지 tail은 유지했다.
위치 60ms/회전 50ms 입력 필터와 재engage 초기화, JSONL 진단도 추가했다.

같은 노트북의 바탕화면 실행 폴더에 10개 파일을 백업 후 선택 설치했다.
최종 설치 폴더에서 45개 테스트 PASS, 실제 BAT 기동 검사 PASS.
오른팔 X회전의 손목 위치 이탈 59.37→2.30mm, 팔꿈치 변화 64.94→0.67도.
문제 기록의 추종 667틱 중 감속 전환 91→1틱; 최소 sampled clearance 19.69mm.
세부 조건과 한계는 위 문서에 있다. 실제 G1 제어는 하지 않았다.

**기존 Unity/시뮬레이션은 재시작하지 않았다. Play를 끄고 기존 Python 창을 정상
종료한 뒤 BAT부터 재실행해야 한다. 최신 보정의 Quest 사용감은 아직 미확인이다.**
아래의 실행 폴더 미반영 설명은 이전 작업 시점의 기록이며 이 절이 우선한다.

## 작업 장치와 폴더 정정 (2026-09-18 사용자 확인)

처음부터 현재까지 작업 장치는 계속 **노트북**이다. 별도 데스크톱 PC에서는
아직 추가 작업을 진행하지 않았다. 아래 두 경로는 모두 **같은 노트북** 안에 있다.

- 소스 작업본: `C:/Users/user/Documents/Codex/2026-09-16/d/work/g1-integration`
- 바탕화면 실행 프로젝트: `C:/Users/user/Desktop/G1_Teleop_Project`

경로의 `Desktop`은 Windows 바탕화면 폴더명이며 별도 장치를 뜻하지 않는다.
과거 문서의 데스크톱 이전 계획을 완료된 개발·설치·검증 이력으로 해석하지 않는다.
소스 작업본과 실행 폴더의 반영 상태는 장치 구분과 별개로 확인한다.

## 후속 작업: 실행 엔진 일치 (2026-09-18, 이 절 우선)

[실행 엔진 수정과 검증 기록](BIMANUAL_RUNTIME_VALIDATION_20260918.md)을 함께 읽는다.
최초 인계 `758684f` 뒤에 검증/실행 환경 불일치를 수정했다. 새 셸에서 기존 BAT는
기본 MuJoCo 3.11.0을 사용했지만 최초 17개 테스트는 격리 3.12.0을 사용했다.
3.11.0에서는 기존 교차 동작 clearance 회귀 검사가 실패했다.

양팔 전용 `g1_bimanual_runtime.py`와 두 BAT를 연결하고, 모델 생성에도
MuJoCo 패키지/native **3.12.0** 검사를 추가했다. 추가 12개를 포함해 **29/29 PASS**.
IK 감속/순차 engage/UI/오른팔 수식은 바꾸지 않았다. 최신 Quest 사용감은 여전히 미확인이다.

**후속 수정은 소스 작업본에만 적용했으며 같은 노트북의 바탕화면 실행 프로젝트에는 복사하지 않았다.**
소스 작업본의 새 BAT에 `--engine-root`로 노트북의 격리 엔진을 지정하는 실행 방법은
위 문서에 있다. 바탕화면 실행 폴더의 기존 BAT에 이번 수정이 반영됐다고 가정하지 않는다.
과거 전체 JSONL/Editor.log는 이번 후속 작업에서 분석하지 않았다.

## 저장소와 기준

- 저장소: `Y1048/Y`
- **작업 브랜치: `codex/g1-laptop-sync-20260917`**
- IK 감속 기능 기준 커밋: `3d54e5052d4ba3e25acc51ac7907c0e7c5d4067b`
- 최초 인계 커밋은 `758684f6ab16fefab55d08afe0a5e161c97871c9`이다. 후속 변경이 있으므로 작업 시작 때 브랜치 HEAD를 fetch하여 확인한다.
- `main`의 확인된 HEAD는 `0da866f7833c21ee1898c3e3ccf7932cdb401475`이며 이번 양팔 수정 기준이 아니다.
- 오래된 `codex/g1-regular-handoff-20260910`도 이번 작업 기준으로 쓰지 않는다.

로컬 파일을 사용할 수 있다면 먼저 git status/worktree/remote를 대조한다.
기존 dirty 작업본을 reset/clean하거나 통째로 pull하지 않는다. 깨끗한 작업본에서
개발하고 기존 실행 프로젝트에는 백업 후 변경 파일만 선택적으로 반영했다.
웹 GPT에서는 GitHub에 없는 로컬 로그/Unity 실행 상태를 확인했다고 말하지 않는다.

## 현재 목표와 사용자 피드백

기존 오른팔 SampleScene을 그대로 쓰면서 왼팔을 확장하고, 두 팔과 몸통 사이
충돌을 검사하는 양팔 **시뮬레이션**을 만든다. 별도 프로젝트/씬 생성은 사용자가
불편해하여 채택하지 않았다. 실제 G1 적용과 하체 정책 작업은 현재 범위가 아니다.

사용자가 확인한 순서:
1. 양손 engage 불가, 구 크기 불일치 → 참조 연결과 양쪽 마커 수정.
2. 카메라가 중앙 안내를 가림 → 카메라 바로 아래 상태 표시줄로 변경.
3. 양손 동시 정렬이 불편 → 먼저 정렬한 손의 준비를 4초 기억하도록 변경.
4. engage 약 2.2초 뒤 연동 중단 → 통신 단절이 아닌 `qp_infeasible`을 로그로 확인.
5. 최신 감속 수정은 오프라인 테스트까지 완료. **수정 이후 Quest 재시험은 아직 안 했다.**

## 지금 코드가 하는 일

- Unity 양손 입력과 시뮬레이션 feedback: `127.0.0.1:5020`, simulation-only JSON.
- 왼팔 관절 15~21, 오른팔 22~28을 coupled 14축 Mink QP로 계산.
- 속도 상한: 어깨/팔꿈치 90도/s, 손목 180도/s. 가속도 상한 60도/s².
- 각도 범위와 5mm 이상 sampled geometry clearance 유지, 양팔 상호 충돌 쌍 포함.
- 먼저 stable alignment를 마친 손의 준비를 4초 기억한다. 실제 시작 직전 양손
  현재 위치 정렬/유효 추적/신선한 ready feedback/비pinch 조건은 여전히 필요하다.
  두 손의 neutral은 실제 engage 순간 함께 캡처한다.
- 어느 손이든 pinch 0.5초 → 양팔 복귀. 복귀 후 영역 밖으로 손을 옮겼다 재정렬.
- 양손목 하늘색 구 6cm, 목표 구 5.5cm. 목표는 흰색/정렬 노란색/활성 녹색.
- 카메라 아래 한 줄에 좌우 상태, 아래 작은 줄에 복귀/추적 상태. 상세 수치는 PC 로그.
- 오른팔 전용 모드는 기존 경로 유지. 양팔 후보는 기존 오른팔의 모든 자세 개선
  (elbow assistance, torso projection, orientation relaxation)을 그대로 이식한 것은 아니다.

## 이번 IK 중단 수정

이전에는 다음 한 스텝만 확인해서, 속도가 붙은 뒤 충돌/범위 제한과 가속도
제한을 동시에 만족하지 못할 수 있었다. 이제 후보 속도에서 정지할 때까지의
이산 감속 경로를 먼저 검사한다. 새로운 해/정지 경로가 유효하지 않으면 직전에
검사된 감속 경로를 따라가며, 정지 후에도 새로운 추종 해를 시도한다.
유효한 경로가 전혀 없으면 여전히 BLOCKED 처리한다. 제한을 제거하지 않았다.

검사 비용은 world AABB 간격으로 확실히 먼 쌍을 제외해 줄였다. 가까운 쌍은
기존 robust distance를 검사한다. 고정된 기구학 시뮬레이션에 대한 처리이며,
움직이는 외부 장애물, 연속시간 충돌 무발생, 실제 로봇 제동을 보증하지 않는다.

## 실행과 주요 파일

새 작업본에서 처음 설정할 경우:
1. `Unity_G1_VR`의 기존 `SampleScene`을 연다. Play는 끈다.
2. `G1 Teleop → Arms → Use Both Arms (Simulation)`을 선택하고 저장한다.
3. `tools/START_BIMANUAL_UNITY_SIM.bat` 실행 후 Unity Play.

최초 인계의 양팔/감속 수정은 같은 노트북의 바탕화면 실행 폴더에 선택적으로 설치했다.
후속 실행 엔진 수정 `d52c2aa`는 그 폴더에 아직 복사하지 않았다. 소스 작업본에서
실행하는 방법은 상단 문서를 따른다. Python 수정은 실행 중 프로세스에 자동 적용되지 않는다. Play와 기존 양팔 시뮬레이션을 종료한 후 BAT부터 재실행한다.
포트 점유가 있으면 소유 프로세스를 먼저 확인하고 무관한 프로세스를 종료하지 않는다.

주요 파일:
- `MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py`: coupled QP, stopping tail, collision.
- `MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py`: strict UDP, 입력/복귀 상태, JSONL.
- `Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs`: 양손 engage, 상태 UI, 송수신.
- `Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs`: 기존 씬에 양팔 표시.
- `Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs`: 같은 씬의 모드 설정 메뉴.
- `backend/tests/test_bimanual_sim.py`, `backend/tests/test_bimanual_unity_sim.py`.
- `backend/tests/BimanualEngageGateTest.cs`: 컴파일된 C# gate 조건 검사.
- `backend/tests/fixtures/bimanual_recorded_engage_20260918.jsonl` 및 동명 설명 문서.

## 최초 인계 시 실제 수행한 검증 (후속 검증은 상단 문서)

- `py -3.11 -m unittest discover -s backend/tests -p "test_bimanual*.py"`: **17개 PASS**.
- MuJoCo 3.12.0 격리 엔진으로 검사. 노트북 PYTHONPATH:
  `C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0`.
  이 엔진 설치 폴더는 GitHub로 전달되지 않는다. 다른 PC는 의존성과 실제 버전을 확인한다.
- 실제 기록을 자른 fixture 재생: 209 ticks, checked braking 24 ticks,
  기존 sequence 607 실패를 통과. 이 실행의 p95 13.34ms / max16.14ms.
  실시간 성능 보증이 아니라 해당 PC의 관측치다.
- 120개 seeded 자세에서 broadphase/full collision 판정 일치.
- 강제 QP 실패 시 감속/정지/재추종, nonfinite 거부, 기존 protocol/collision/return 테스트 통과.
- C# Unity/Meta 실제 DLL 참조 컴파일, engage 조건 576개와 준비 기억 검사 통과.
- **Unity Play/Quest에서 최신 동작과 UI를 확인한 것은 아니다. 실제 G1 데이터/검증도 아니다.**

## GitHub에 있는 것 / 노트북에만 있는 것

GitHub에는 코드, 테스트, 잘라낸 recorded Unity simulation fixture, 문서가 있다.
노트북에는 전체 JSONL, Editor.log, Unity Library/설치 패키지, 엔진, 백업, 컴파일
response files가 따로 있다. 공개된 fixture를 전체 원본 또는 실제 G1 실측으로 혼동하지 않는다.

노트북 실행 프로젝트: `C:/Users/user/Desktop/G1_Teleop_Project` (dirty; 보호).
깨끗한 소스 작업본: `C:/Users/user/Documents/Codex/2026-09-16/d/work/g1-integration`.
마지막 설치 백업: `logs/backups/bimanual_checked_braking_20260918_100416` (실행 프로젝트).
전체 기록: `logs/test_results/bimanual/unity_20260918_094323_0712614.jsonl` (실행 프로젝트).

## 다음 작업

1. 최신 수정으로 한 손씩 engage, 양팔 움직임, pinch 복귀, 재engage를 Quest에서 확인한다.
2. 실패하면 새로운 JSONL과 `[BIMANUAL ENGAGE]` 로그로 원인을 구분한다.
   기존 기록에서 통과했다는 이유로 모든 움직임이 해결됐다고 단정하지 않는다.
3. 감속이 과도하거나 자주 멈추면 입력/자세/감속 횟수와 실제 루프 시간을 분석한다.
4. 사용감·자세 개선은 기존 오른팔과 비교하되 충돌/각도 제한을 임의 제거하지 않는다.
5. 실제 G1/SSH/DDS/모터 출력, 하체 정책 통합, gain 변경은 이번 작업에 포함하지 않는다.

사용자는 컴파일만으로 해결됐다고 말하는 것과 반복적인 시험 요청에 불편함을
표했다. 오프라인에서 재현 가능한 문제를 먼저 검증하고, 확인 범위를 정확히 말한다.
