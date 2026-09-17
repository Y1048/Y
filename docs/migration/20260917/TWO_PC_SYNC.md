# 노트북·데스크톱 GitHub 동기화 규칙

두 PC는 당분간 `codex/g1-laptop-sync-20260917` 브랜치를 공용 기준으로 사용한다. 기존 dirty 작업 폴더에 이 브랜치를 덮어쓰지 않고, 각 PC의 clean clone에서 작업한다.

## 작업을 시작할 때

```powershell
git status --short --branch
git fetch origin
git rev-list --left-right --count HEAD...origin/codex/g1-laptop-sync-20260917
```

로컬 변경이 없고 출력이 `0  N`이면 다음 명령으로 원격 변경을 받는다.

```powershell
git pull --ff-only origin codex/g1-laptop-sync-20260917
```

로컬 수정·미추적 파일이 있으면 pull하지 않는다. 먼저 파일 목록과 원격 변경을 비교하고, 현재 작업을 별도 커밋 또는 별도 브랜치로 보존한다.

## 작업을 마칠 때

이번 작업과 관계있는 파일만 명시적으로 stage한다. `git add .`은 사용하지 않는다.

```powershell
git status --short
git add <이번에 수정한 파일>
git diff --cached --check
git diff --cached --stat
git commit -m "변경 내용을 설명하는 메시지"
git push origin codex/g1-laptop-sync-20260917
```

push 후 로컬과 원격 HEAD가 같은지 확인한다.

```powershell
$local = (git rev-parse HEAD).Trim()
$remote = ((git ls-remote origin refs/heads/codex/g1-laptop-sync-20260917) -split '\s+')[0]
"LOCAL=$local"
"REMOTE=$remote"
if ($local -ne $remote) { throw 'Remote HEAD mismatch' }
```

소스 checkpoint가 clean할 때 다음 검증도 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1
```

## 다른 PC의 Codex에 전달할 문장

```text
`codex/g1-laptop-sync-20260917` 브랜치에 새 변경사항이 push됐다.
먼저 git status와 git fetch origin을 실행하고 로컬 변경 여부를 확인해.
clean 상태일 때만 git pull --ff-only origin codex/g1-laptop-sync-20260917을 실행해.
dirty 상태면 pull, reset, clean을 하지 말고 변경 파일과 원격 차이를 먼저 보고해.
갱신 후 로컬 HEAD와 원격 HEAD 일치 여부를 확인하고
docs/migration/20260917/README.md, TWO_PC_SYNC.md, docs/CHAT_HANDOFF.md를 다시 읽어.
```

## 충돌 방지 규칙

- 두 PC에서 같은 파일을 동시에 수정하지 않는다.
- 작업을 시작하기 전에 pull하고, 마칠 때 작은 단위로 commit/push한다.
- 어느 PC에서 어떤 범위를 작업 중인지 `docs/CHAT_HANDOFF.md` 상단에 짧게 기록한다.
- 상대 PC가 작업 중인 범위는 별도 파일이나 별도 브랜치에서 진행한다.
- 생성 로그, Unity Library, Python/WSL 설치 환경은 Git 동기화 대상으로 간주하지 않는다.
- 실제 G1 배포 파일과 원격 G1 상태는 Git pull로 갱신되지 않는다.

## 금지 사항

- `git reset --hard`
- `git clean -fd` 또는 `git clean -fdx`
- force push
- dirty worktree에서의 무조건적인 pull
- 사용자의 기존 live 작업 폴더 덮어쓰기
- 충돌을 확인하지 않은 자동 merge

`main`으로 병합하기 전까지 이 브랜치가 두 PC 사이의 source checkpoint다. 브랜치가 바뀌면 이 문서와 migration README를 같은 커밋에서 갱신한다.
