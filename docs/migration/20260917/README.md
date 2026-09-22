# 2026-09-17 노트북 소스 동기화

이 브랜치는 데스크톱 이전을 위한 소스 보존·통합 체크포인트다. 실물 실행 승인이나 정상 동작 인증이 아니다. `main`에는 아직 병합하지 않았다.

## 현재 장치 정정 (2026-09-18 사용자 확인)

처음부터 현재까지 작업은 계속 같은 노트북에서 진행했다. 별도 데스크톱 PC에서는
아직 추가 작업을 진행하지 않았다. `C:/Users/user/Desktop/G1_Teleop_Project`는
노트북의 바탕화면 실행 폴더이며 별도 데스크톱 장치를 뜻하지 않는다.
아래 이전 절차는 계획/참고 자료이고, 완료된 데스크톱 작업 기록이 아니다.
현재 양팔 시뮬레이션은 [최신 인계](../../GPT_BIMANUAL_HANDOFF_20260918.md)를 우선한다.

## 당시 이전 계획 (2026-09-17; 현재 실행 단계 아님)

- 먼저 GitHub 소스를 데스크톱의 새 폴더에 복원하고 checkout을 검증한다.
- 하체 정책 개발과 기존 velocity 12DoF 정책의 실제 G1 시험은 중단한다. 하체 정책은 다른 개발자가 제공하며, 추후 이 저장소의 Unity/Mink 상체 목표 및 단일 LowCmd 소유자 경계에 통합한다.
- 2026-09-16의 기존 velocity 축 시험은 `+vx=0.05` 전환 중 IMU 제한에 도달했다. 당시 관측값은 roll `-0.19 rad`, pitch `+0.34 rad`였고 제어기는 마지막 유효 전신 위치 명령을 유지했다. 이 시험을 데스크톱에서 반복하지 않는다.
- 다음 개발 주제는 데스크톱 소스·환경 복원이 끝난 뒤 별도로 정한다.

## 포함한 내용

- 기준: `codex/g1-main-continuation-20260914`의 `563614a3f10e7188f820f19467ecafd4678c7212`. 이 기준은 당시 `main`보다 21커밋 앞선 시스템 식별 작업을 포함한다.
- 노트북 주 프로젝트 `05d4ebf3827ffbaf287d3d6d39ce4ef89c6ed3e8` 이후의 미커밋 코드·Unity 설정·문서. GitHub 쪽 변경은 유지했다.
- 주 프로젝트의 긴 작업 이력은 `LAPTOP_CHAT_HANDOFF.md`에 원문 보존했다. 그 문서의 상대 링크는 원래 `docs/` 기준이며 역사적 기록이지 현재 상태 판정이 아니다.
- 추가 임시 작업 폴더 2개의 미커밋 내용은 `pd_final.patch`, `pd_review.patch`로 보존했다. 각각 원래 기준에서 10개, 14개 파일을 정확히 복원하는지 검증했다.
- `pd_review.patch`는 Q/Ctrl+C 종료·Regular 전환 및 응답 기록 처리를 변경한다. 최신 시스템 식별 writer와 충돌하므로 현재 실행 코드에 자동 적용하지 않았다. 반드시 별도 검토·오프라인 검증이 필요하다.
- Unity DevAgent 설정의 접근 토큰은 업로드 사본에서 비웠다. 원본 노트북 파일은 수정하지 않았다.

`integration-actions.json`에 파일별 처리 결과를 기록했다. `excluded_generated_backup_retained` 57개는 Unity `.utmp` 빌드 캐시, 배포용 압축 사본, 생성된 분석 이미지·영상이다. Git에 넣지 않았으며 기존 전체 이전 백업에 남아 있다. CSV·실행 로그, Unity Library, 설치된 Python/WSL 환경 등 Git 제외 데이터도 Git clone만으로 복원되지 않는다.

## 검증 결과와 한계

- 선택한 Python 테스트 파일 45개 중 42개 통과, 3개 실패. 두 GitHub CI 워크플로의 안전·provenance 테스트 22개는 모두 통과했다.
- `test_mink_feasible_target.py`: 테스트 fixture의 `speed_profile` 속성 누락. 노트북 원본에서도 동일하게 실패했다.
- `test_virtual_center_kinematics_regression.py`: 손목 회전 시 충돌 여유 검사 실패(-133.205 mm, 기준 19.5 mm). 노트북 원본에서도 동일 수치로 실패했다. 이 문제를 물리 안전성이 확보된 것으로 해석하지 말 것.
- `test_sysid_pipeline.py`: 21개 중 과거 커밋 이후 기존 runtime 파일이 불변이어야 한다는 검사 1개 실패. 노트북 변경을 합친 이 브랜치는 해당 불변 조건을 만족하지 않는다. 검사를 지우거나 통과로 바꾸지 않았다.
- 변경·추가 Python 258개 구문 분석 통과. 제한된 비밀값 패턴 검사에서 남은 탐지 없음. 이는 모든 종류의 비밀값 부재를 보증하지 않는다.
- 기존 문서의 Markdown 줄 끝 공백, 원문 vendor 파일 및 복원용 patch의 공백 경고는 원본 보존을 위해 남겼다. 전체 `git diff --check`가 통과했다고 주장하지 않는다.
- 테스트 중 실제 G1 연결·DDS 초기화·로봇 명령·프로그램 배포는 하지 않았다. 네트워크를 사용하는 선택된 테스트는 loopback 통신만 허용했다.
- Unity 빌드, 전체 C++ 빌드, 실제 Quest/G1/Omni, 데스크톱 설치 환경은 검증하지 않았다.

세부 결과: `test-results.json`, `static-verification.json`, `original-baseline-results.json`.

## 데스크톱에서 이어받기

기존 전체 백업을 덮어쓰지 말고, 여유 공간이 있는 새 폴더에 소스를 받는다. GitHub에서 받으려면 인터넷이 필요하다. LAN으로 이미 복사한 환경/자료 복원에는 인터넷이 필수는 아니다.

노트북과 데스크톱을 오가며 작업할 때는 반드시 [두 PC GitHub 동기화 규칙](TWO_PC_SYNC.md)을 따른다. 핵심은 작업 전 `fetch`와 clean 상태 확인, clean 상태에서만 `pull --ff-only`, 작업 후 작은 commit/push, 그리고 reset/clean/force push 금지다.

```powershell
git clone --branch main https://github.com/Y1048/Y.git G1_Teleop_Source
Set-Location .\G1_Teleop_Source
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1
```

새 Codex에 아래 내용을 전달한다.

> 이 프로젝트에서 docs/migration/20260917/README.md, docs/migration/20260917/TWO_PC_SYNC.md와 docs/CHAT_HANDOFF.md를 먼저 읽어라. 전체 목표는 노트북 G1 Unity/VR/MuJoCo/Omni/학습 환경을 데스크톱에서 이어가는 것이다. Git 소스와 기존 전체 이전 백업을 함께 사용한다. 하체 정책은 다른 개발자가 제공하므로 기존 velocity 12DoF 정책을 계속 개발하거나 실제 G1에서 재시험하지 않는다. 먼저 현재 설치/복원/저장 공간 상태를 읽기 전용으로 확인하고, 세 가지 실패 검증과 분리 패치를 구분한다. 사용자 승인 없이 G1 명령·모드 전환·배포·파티션 삭제를 하지 않는다. 물리 실행 전 오프라인 환경 복원과 검증부터 진행한다.

전체 백업의 `MigrationDocs/DESKTOP_CONTINUE.md`에는 설치 버전·환경 복원·저장 공간 관련 인계가 있다. 그 문서는 2026-09-16 상태이므로 실제 이전을 시작할 때 현재 상태와 대조한다. 아직 데스크톱 추가 작업을 수행했다는 뜻이 아니다. Ubuntu.tar는 노트북 WSL 백업이며 데스크톱 듀얼부팅 Ubuntu의 백업이 아니다.

## 분리 패치 복원 예시

기존 작업 폴더에 덮어쓰지 않는다. 아래 명령은 검토용 별도 소스 폴더를 만드는 예시이며 로봇 프로그램을 실행하지 않는다.

```powershell
$patch = (Resolve-Path docs/migration/20260917/pd_review.patch).Path
$base = (Get-Content docs/migration/20260917/pd_review-base.txt).Trim()
git worktree add --detach ../G1_pd_review_recovered $base
git -C ../G1_pd_review_recovered apply --check $patch
git -C ../G1_pd_review_recovered apply $patch
```

`pd_final`도 동일하게 해당 이름의 patch와 base 파일을 사용한다. 소스 복원 성공은 충돌 해결이나 동작 검증을 뜻하지 않는다.
