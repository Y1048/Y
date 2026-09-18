# 기록된 단계형 복귀 확인과 실행 폴더 동기화 — 2026-09-18

기준 브랜치: `codex/g1-laptop-sync-20260917`. 출발 커밋: `7e74219`.
이번 작업은 연결된 노트북에서 기존 로그를 읽고 오프라인 검증을 수행했다.
Unity/Quest를 새로 실행하거나 로봇/DDS/ADB/컴파일러를 시작하지 않았다.
별도 데스크톱의 작업본·설치·동작은 직접 확인하지 않았다.

## 확인한 새 기록

`unity_20260918_134204_4595123.jsonl`의 run 행에는
`bimanual_motion_v1`, `bimanual_boundary_v1`, `bimanual_staged_return_v1`이 있다.
기록된 다섯 Python 파일 SHA-256은 출발 커밋의 소스와 모두 일치했다.
따라서 옛 직접 복귀 로그가 아니라 새 단계형 복귀 코드를 사용한 기록으로 구분한다.
이 확인이 모든 메시·의존성의 해시 검증이나 사용자의 착용감 평가를 의미하지는 않는다.

전체 파일에서 고정한 prefix는 53,426,095바이트, 34,792행이다.
그중 상태 행은 32,506개로 약 571.297초를 포함한다.
회귀 fixture에는 startup부터 첫 복귀 완료까지 5,635행만 넣었다.
긴 READY 대기 구간과 반복 메타데이터는 제외했다.

| 기록에서 확인한 항목 | 결과 |
| --- | --- |
| 상태 순서 | READY → TRACKING → RETURNING(tracking_lost) → READY |
| 추종 상태 구간 | 약 46.937초, 2,694틱(손실 감속 20틱 포함) |
| 복귀 실행 | 중간 자세 → home → 0속도 0.5초 정착 |
| 복귀 소요: 로그 시각 차이 | 6.063초 |
| 복귀 소요: 고정 dt 시뮬레이션 시간 | 5.750초, 345틱 |
| 복귀 재계획 | 0회 |
| 최대 출력 관절속도 | 38.954도/s |
| 최대 출력 차분 가속도 | 60.000000000027도/s²(수치 오차 범위) |
| 기록 재생과 원 관절값 차이 | 최대 0rad |

출력 속도·가속도는 고정 dt=1/60초에서 qpos를 차분한 값이다.
실제 G1 측정값이나 순간 모터 속도가 아니며, wall-clock 지연을 숨기는 수치로 쓰지 않는다.
실제 기록의 제어 tick p95는 11.351ms, 최대 48.721ms였다.
호스트 주기 변동까지 포함한 지속 60Hz 동작을 보증하지 않는다.

이 기록에는 추적 손실 복귀가 한 번 있고 그 뒤의 re-engage는 없다.
이를 실제 pinch 복귀·빠른 backend 재시작·재engage 검증으로 확대하지 않는다.
보존한 prefix에는 정상 종료 행도 없으므로 종료 상태는 판정하지 않는다.

## 충돌 경계에서의 관측과 남은 주의점

추종 목표를 계산한 2,674틱 중 254틱은 검사된 감속 경로를 사용했다.
242틱은 새 후보의 정지 경로가 sampled clearance 검사를 통과하지 못했고,
12틱은 QP 무해답이었다. 이는 거부된 후보에 관한 이유이지,
출력된 자세가 254회 충돌했다는 뜻이 아니다.

재생 중 최소 sampled clearance는 5.000012853mm로, 요구치 5mm 경계에 매우 가깝다.
가장 가까운 쌍은 `left_wrist_yaw_link`의 충돌 형상과
`mink_right_rubber_hand_collision`이었다(로그 시작 후 약 47.109초).
양손 간 제약이 실제 입력에서 활성화된 사례다. 현재 한계/감속을 제거하거나
전역 속도를 올려 이 결과를 숨기지 않았다. 사용감이 끊기는지 여부는 별도 피드백이 필요하다.

이번 커밋은 IK·ArmMotionPolicy·복귀 Ruckig·속도·충돌 경계를 바꾸지 않는다.
고정 기구학 장면의 sampled 검사이며, 연속시간 무충돌·새 외부 장애물 대응·실물 제동 보증이 아니다.

## 새 회귀 검사

`backend/tests/test_bimanual_recorded_session.py`에 기록 출처 검사와 재생 검사를 추가했다.
수신한 원 packet을 decoder/UnityCycle에 넣고 매 출력마다 다음을 검사한다.

- 출력 qpos 차분과 내부 속도 일치, 관절 범위, 속도·가속도 제한, 비제어 관절 고정.
- 양팔/몸통 sampled clearance 5mm 이상, 기록 관절값과 절대 오차 5e-6rad 이하.
- 손실 감속 20틱, 중간 자세/home/정착 완료, 재계획 없음, 0속도 READY.

fixture는 gzip으로 압축한 JSON이며 실행 코드는 포함하지 않는다.
[fixture 출처](../backend/tests/fixtures/bimanual_staged_session_20260918.md)에
원본 prefix와 압축 파일의 해시·선택 범위·검증 한계를 적었다.
전체 원본 로그는 Git에 올리지 않았고 노트북에만 보존했다.

## 노트북 실행 폴더의 누락된 경로 패치 반영

직전 `7e74219`의 경로 탐색 수정은 소스에만 있고,
`C:/Users/user/Desktop/G1_Teleop_Project`의 실행 BAT에는 아직 없었다.
기존 파일이 `5844d2d`와 일치하는지 먼저 확인한 뒤 9개 경로 관련 파일만 복사했다.
백업: `logs/backups/windows_tool_paths_20260918_135946/`(실행 폴더 기준).
그 외 실행 코드·씬 등 보호 파일 508개의 바이트 해시가 유지됨을 확인했다.

실행 폴더의 Unity 관련 BAT 네 개는 `--check-unity-path`로만 검사해 모두 종료 코드 0을 확인했다.
노트북에서는 ProgramFiles의 Unity 6000.5.4f1이 선택됐다.
환경변수 우선순위/USERPROFILE 설치 등 21개 경로 검사는 임시 폴더에서 재실행했다.
경로 검사 중 실제 Unity·APK 빌드·설치·로봇·WSL·DDS를 실행하지 않았다.
새 회귀 테스트와 압축 fixture 두 파일도 실행 폴더에 추가했다.

## 다음 직접 확인 범위

노트북에서 이미 확인된 기존 로그와 별도 데스크톱의 실제 실행을 혼동하지 않는다.
데스크톱은 해당 브랜치 변경과 resolver를 함께 받고 아래 경로 전용 검사를 실행한다.
미커밋 파일이 있으면 먼저 보존·대조하며 reset/clean으로 덮어쓰지 않는다.

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --check-unity-path
.	ools\BUILD_AND_INSTALL_VR_APK.bat --check-unity-path
```

실제 손 추적의 주관적 사용감, pinch 후 복귀·재engage, 빠른 backend 재시작을 포함한
Unity Play 검증은 이번 작업에서 새로 수행하지 않았다.
엔진 import 지연도 근본 해결로 판정하지 않는다. 지연된 보조 실행은 통과 횟수에서 제외한다.

## 최종 실행 검증

소스 작업본: **70/70 PASS**, 85.186초, exit code 0.
같은 노트북 실행 폴더: **70/70 PASS**, 74.662초, exit code 0.
기존 68개와 새 기록 출처/재생 2개의 합계이며 두 실행을 140개 독립 검사로 합산하지 않는다.
경로 검사: **21/21 PASS**, 3.531초. 실제 BAT 4개는 경로 전용 모드로 각각 PASS.
소스·실행 폴더 모두 로그 관절값과의 최대 차이가 0rad였다.

보조 전체 검사 실행 한 건은 `engine_begin`에서 unittest 출력 없이 지연돼
이번 작업이 만든 해당 자식 프로세스만 종료했다. 원인을 규명했다고 주장하지 않으며,
중단된 실행과 재시도 후 완료된 위 결과를 구분해 JSON에 남겼다.
기존 사용자 Unity/Python 프로세스는 종료하거나 재시작하지 않았다.

검증 기록:
- [결과 JSON](validation/bimanual_observed_run_20260918/verification.json)
- [소스 전체 검사 출력](validation/bimanual_observed_run_20260918/source_suite.txt)
- [실행 폴더 전체 검사 출력](validation/bimanual_observed_run_20260918/runtime_suite.txt)
- [경로 검사 출력](validation/bimanual_observed_run_20260918/path_tests.txt)

전체 로그 prefix·로컬 설치 manifest·중단 실행 기록은 노트북 소스 작업본의
`logs/test_results/bimanual_followthrough_20260918_135648/`에 있다.
Git에는 선택한 압축 fixture·회귀 테스트·검증 요약과 출력·인계 문서만 포함한다.
