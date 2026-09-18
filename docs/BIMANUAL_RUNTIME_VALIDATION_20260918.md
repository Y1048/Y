# 양팔 시뮬레이션: 검증 엔진과 실행 엔진 일치

기준 브랜치: `codex/g1-laptop-sync-20260917`.
출발 커밋: `758684f6ab16fefab55d08afe0a5e161c97871c9`.
범위: 기존 SampleScene의 양팔 **시뮬레이션**. 실제 G1, SSH/DDS,
모터 출력, 하체 정책, gain 변경, Unity/Quest 실행은 하지 않았다.

## 확인한 문제

인계 문서의 17개 테스트는 노트북의 격리 MuJoCo **3.12.0**을 사용했다.
반면 기존 양팔 BAT 두 개는 `py -3.11`로 시뮬레이터를 직접 실행하고 엔진을
선택하지 않았다. 이 노트북의 새 Python 프로세스에서 `PYTHONPATH`와
`G1_BIMANUAL_ENGINE_ROOT` 없이 확인한 기본 설치는 **3.11.0**이다.
이는 과거 Quest 세션이 어떤 엔진을 썼는지 확인했다는 뜻은 아니다.
과거 전체 JSONL과 Editor.log는 이번 작업에서 분석하지 않았다.

수정 전 같은 소스에 대한 이번 세션의 관측 결과:

| 실행 환경 | 기존 테스트 | 기록 fixture 재생 |
| --- | --- | --- |
| 격리 3.12.0 | 17/17 통과 | 209틱, 감속 24틱, p95 13.01ms, max 15.92ms |
| 기본 3.11.0 | 16/17 통과, 교차 동작 clearance 검사 실패 | 209틱, 감속 24틱, p95 43.09ms, max 85.45ms |

3.11.0 실패는 `test_crossed_targets_keep_sampled_clearance`에서
`-0.11604602731831921 >= 0.005` 조건이 성립하지 않은 것이다.
이는 해당 엔진의 geometry clearance 계산을 포함한 회귀 검사의 실패이며,
실제 G1에서 측정한 침투 거리나 접촉 결과가 아니다. 버전 간 거리 계산 차이의
내부 원인을 모두 규명한 것은 아니므로, 3.11.0을 검증된 대체 엔진으로 쓰지 않는다.
위 수정 전 관측치는 이번 도구 실행에서 확인한 값이다. 아래 커밋된 transcript는
수정 후 검증 실행을 자동 저장한 것으로, 수정 전 전체 실행 원본은 아니다.

## 변경 사항

- `MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py`를 추가했다.
  `--engine-root`, `G1_BIMANUAL_ENGINE_ROOT`, 프로젝트 내부 격리 엔진,
  설치된 패키지 순서로 엔진 위치를 결정한다. 명시적으로 지정한 위치가 없거나
  잘못되면 다른 위치로 조용히 대체하지 않는다.
- MuJoCo Python 패키지 버전과 native `mj_versionString()`이 모두 `3.12.0`인지
  확인한다. 지정한 엔진의 실제 모듈 파일 경로도 일치해야 한다. 이미 다른
  MuJoCo가 로드된 프로세스에서는 런타임을 교체하지 않고 새 프로세스를 요구한다.
- `BimanualSimulation.__init__`에도 버전 검사를 추가했다. 기존 Python 파일을
  직접 호출해 새 실행기를 우회하더라도 잘못된 버전에서는 모델을 만들지 않는다.
- `START_BIMANUAL_UNITY_SIM.bat`와 `START_BIMANUAL_SIM.bat`는 각각 새 실행기의
  `--mode unity`, `--mode demo`로 연결했다. `--mode test`도 같은 엔진을 선택하고,
  테스트가 띄우는 Python 자식 프로세스에 선택한 엔진 경로를 전달한다.
- `--validate-only`는 엔진 경로, Python, 패키지 버전, 세 Python 파일의 SHA-256을
  JSON으로 출력한다. 엔진/메타데이터 확인용이며 전체 의존성 실행 검사나
  Unity/Quest 검증을 대신하지 않는다. 실행 검사는 `--mode test`로 한다.

설치 패키지를 자동으로 받거나 시스템 Python을 업그레이드하지 않는다.
IK 수식, 감속 tail 계산, collision/range/velocity/acceleration 제한,
Unity/C# engage 조건, UI, 기존 오른팔 경로와 SampleScene은 바꾸지 않았다.

## 수정 후 검증 결과

`backend/tests/test_bimanual_runtime.py`에 12개 테스트를 추가했고,
기존 17개와 합쳐 **29/29 통과**했다. 패키지/native 버전 불일치, 잘못된
경로, 환경변수 선택, 이미 로드한 다른 엔진, 자식 프로세스 경로 전파,
실행기 import 이전 차단과 모델 생성 이전 차단을 검사한다.

추가로 실제 Python 프로세스에서 기본 3.11.0 거부, 없는 경로 거부,
명시적/환경변수 3.12.0 선택, 직접 생성 시 버전 거부를 확인했다.
새 실행기의 headless loopback 경로와 입력 파일 기반 demo 경로도 실행했다.
loopback은 임시 포트와 합성 입력/대기 상태를 사용했다. 기존 5020 세션이나
Unity 창을 시작하거나 종료하지 않았다.

최종 테스트 재생: **209틱, 감속 24틱, p95 14.09ms, max 16.82ms**.
이 숫자는 기록 fixture의 `cycle.tick()` 실행 시간이며 전체 실시간 루프,
Quest 체감 지연 또는 실물 로봇 성능 보증이 아니다.

이번에 확인한 환경은 Python 3.11.9, MuJoCo 3.12.0, Mink 1.3.0,
qpsolvers 4.13.0, DAQP 0.9.1, NumPy 2.4.6이다. 다른 컴퓨터의 의존성 설치까지
이 저장소만으로 완료되는 것은 아니다.

검증 기록:
- [실행 결과 JSON](validation/bimanual_runtime_20260918/verification.json)
- [프로세스 출력 transcript](validation/bimanual_runtime_20260918/transcript.txt)

JSON의 8개 실행 경로 검사에는 29개 unittest를 실행한 항목 하나가 포함된다.
이를 29개와 별개의 추가 8개 unittest로 합산하지 않는다. 예상된 버전/경로
차단은 exit code 1이 올바른 결과다. Python 구문 검사와 기존 Unity/fixture/
상태기계 파일이 변경되지 않았는지도 확인했다.

## 현재 노트북에서 실행

**소스 작업본만 수정했다. Desktop 실행 프로젝트에는 아직 복사하지 않았다.**
기존 Desktop BAT를 그대로 쓰면 이번 실행기 수정이 적용되지 않는다.
Unity는 기존 Desktop 프로젝트의 SampleScene을 유지하고, Python backend만
아래 소스 작업본에서 실행할 수 있다.

```powershell
Set-Location 'C:/Users/user/Documents/Codex/2026-09-16/d/work/g1-integration'
$Engine = 'C:/Users/user/Desktop/G1_Teleop_Project/logs/diagnostics/mujoco_versions/3.12.0'

# 창, 모델 또는 UDP runtime을 시작하지 않는 엔진 확인
py -3.11 MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py --engine-root $Engine --validate-only

# 같은 엔진으로 오프라인/합성 loopback 회귀 테스트
py -3.11 MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py --engine-root $Engine --mode test

# 기존 backend를 정상 종료한 뒤 실행한다. 임의의 포트 소유 프로세스를 죽이지 않는다.
.\tools\START_BIMANUAL_UNITY_SIM.bat --engine-root $Engine
```

다른 PC에서는 검증된 엔진을 별도로 설치한 후 실제 경로를 지정한다.
해당 작업본의 `logs/diagnostics/mujoco_versions/3.12.0`에 엔진이 있거나,
사용하는 Python에 MuJoCo 3.12.0이 설치되어 있으면 `--engine-root`를 생략할 수 있다.
엔진 폴더는 GitHub에 없고, 개인 노트북의 경로를 그대로 복사해서 해결되지는 않는다.

## 증거 범위와 남은 작업

이 변경 묶음에는 소스, 기존 잘라낸 recorded Unity simulation fixture, 테스트,
이번 실행 검증 JSON/transcript와 문서가 있다. 노트북의 전체 JSONL, Editor.log,
Unity Library, 엔진 설치 폴더, 백업, C# 컴파일 response file은 포함하지 않았다.
이번에 원격으로 확인한 것은 소스 작업본/dirty 실행 프로젝트 상태, 설치된 엔진과
새 오프라인 테스트 결과다. 과거 전체 로그를 새로 분석한 것이 아니다.

최신 Quest 사용감은 여전히 미확인이다. 올바른 엔진으로 한 손씩 engage,
양팔 움직임, pinch 복귀, 재engage를 확인하는 단계가 남아 있다.
기존 JSONL의 checked-braking 원인/횟수와 실제 루프 시간 진단 보강은 이번 커밋에
포함하지 않았다. `--validate-only`의 환경 JSON이 기존 세션 JSONL에 자동으로
기록된다고 가정하지 않는다.

이 변경으로 모든 동작이 해결됐다고 판정하지 않는다. sampled clearance는
고정 기구학 장면의 회귀 기준이며 연속시간 무충돌이나 실제 G1 제동 보증이 아니다.
