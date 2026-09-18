# 양팔 pinch 재engage와 startup 후속 검증 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`, 출발 커밋 `caaafdc`.
이번 검증은 연결된 노트북에서 시뮬레이션과 오프라인 C# 테스트만 수행했다.
실제 G1/DDS, 새 Quest 착용 세션, Unity Play 조작은 수행하지 않았다.

## 목적

이전 단계에서 남은 항목은 세 가지였다.

1. 실제 14축 시뮬레이터에서 pinch 복귀 후 inactive rearm과 재engage가 끝까지 이어지는지 확인한다.
2. Unity 쪽 `mustLeaveZones` 해제가 실제 영역 밖 조건을 요구하는지 회귀검사로 고정한다.
3. 간헐적으로 관측된 MuJoCo import 지연이 fresh process에서 반복되는지 계측한다.

## pinch → 복귀 → 재engage

`backend/tests/test_bimanual_return.py`에 실제 `BimanualSimulation`과 `UnityCycle`을 함께 사용하는 검사를 추가했다.
Mock 시뮬레이터가 아니라 공동 14축 QP, 단계형 Ruckig 복귀, 충돌/범위/속도/가속도 검사를 그대로 사용한다.

검사 순서는 다음과 같다.

`READY → TRACKING → 실제 이동 → pinch return → safe waypoint → home → settle → READY`

그 뒤 active-only packet을 먼저 보내면 재engage하지 않아야 하며,
inactive packet으로 backend를 rearm한 뒤 active packet을 보내야 TRACKING으로 다시 들어간다.
출력 qpos 차분과 내부 속도 일치, 최대 60도/s² 출력 가속도 제한, sampled clearance도 매 tick 확인한다.

단독 full-cycle 검사는 통과했고, 전체 bimanual suite에도 포함했다.
최종 소스 전체 결과는 **71/71 PASS, 87.316초**다.
복귀 전용 suite는 **11/11 PASS, 7.148초**다.

## leave-zone 재확인

G1BimanualSimulationSender의 기존 조건은 동작 의미를 바꾸지 않고
CanClearMustLeave() 정적 함수로 분리했다.

해제 조건은 네 조건을 모두 만족할 때뿐이다.

- backend가 ready 상태다.
- 양손 추적이 유효하다.
- 현재 손이 engagement zone 밖이다.
- pinch가 해제되어 있다.

BimanualEngageGateTest.cs는 기존 576개 engage 조합에 leave-zone 조합 16개를 추가했다.
실제 Unity 참조로 C# 전체 어셈블리를 다시 컴파일했으며 error 0, 기존 경고 81개였다.
Engage/leave gate는 **592개 조합 PASS**, backend generation/order gate는 **17개 PASS**였다.

이 변경은 현재 inZones 계산이나 binder의 정렬 임계값을 바꾸지 않는다.
테스트에서 inline 조건을 직접 검증할 수 있도록 이름만 부여한 리팩터링이다.

## MuJoCo import/startup 지연 재검사

격리 MuJoCo 3.12.0을 fresh Python process에서 10회 import했다.
이번 실행의 import 시간 범위는 약 **0.201~0.268초**였고 timeout은 없었다.

같은 runtime entrypoint의 headless startup을 fresh process에서 5회 실행했다.
전체 wall time은 약 **1.196~1.277초**, engine ready는 시작 후 약 **0.160~0.201초**였다.
controller import, 모델 생성, listener 준비와 정상 종료 stage가 모두 기록됐다.

따라서 이전에 한 번 관측한 수십 초 import 지연은 이번 반복에서 재현되지 않았다.
원인을 규명했다고 보거나 timing watchdog을 새 안전 조건으로 추가하지 않는다.
간헐적 OS/스토리지/보안 검사/프로세스 환경 영향 가능성도 현재 증거만으로 특정하지 않는다.

## 실행 폴더 반영 상태

검증 시점에 노트북 Unity Editor가 열려 있었다.
이번 C# 변경은 동작 의미가 같은 테스트 가능성 리팩터링이지만,
실행 중 프로젝트에 파일을 복사하면 Unity script hot-reload가 발생할 수 있어
바탕화면 실행 폴더에는 의도적으로 hot-install하지 않았다.

현재 실행 폴더는 이전 단계의 기능 코드 상태를 유지한다.
다음 정상 Play/Unity 중지 시 source와 runtime의 세 파일을 대조한 뒤 선택 반영한다.
실제 G1, DDS, APK, ADB는 실행하지 않았다.

## 검증 자료

- validation/bimanual_reengage_20260918/verification.json
- validation/bimanual_reengage_20260918/startup_probe.json
- validation/bimanual_reengage_20260918/return_suite.txt
- validation/bimanual_reengage_20260918/unity_compile.txt
- validation/bimanual_reengage_20260918/engage_run.txt
- validation/bimanual_reengage_20260918/feedback_run.txt

남은 직접 확인은 새 Quest 세션에서 pinch 복귀 후 실제로 손을 zone 밖으로 이동하고,
다시 정렬해 재engage했을 때 체감 속도와 끊김이 없는지 확인하는 것이다.
