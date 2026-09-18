# GPT 인계: 기존 오른팔 씬을 양팔 시뮬레이션으로 확장

기준일: 2026-09-18. 아래 내용은 같은 날짜의 이전 작업 기록보다 우선한다.

## 저장소와 기준

- 저장소: `Y1048/Y`
- **작업 브랜치: `codex/g1-laptop-sync-20260917`**
- 최신 기능 커밋: `3d54e5052d4ba3e25acc51ac7907c0e7c5d4067b`
- 이 인계 문서 커밋은 위 기능 커밋 뒤에 있다. 작업 시작 때 브랜치 HEAD를 fetch하여 확인한다.
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

기존 노트북에는 선택적 설치가 끝났다. 최신 Python 수정은 실행 중 프로세스에
자동 적용되지 않는다. Play와 기존 양팔 시뮬레이션을 종료한 후 BAT부터 재실행한다.
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

## 실제 수행한 검증

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
