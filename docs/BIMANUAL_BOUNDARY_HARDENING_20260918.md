# 양팔 시뮬레이션 경계 처리 보강 — 2026-09-18

기준: `codex/g1-laptop-sync-20260917`, 출발 커밋 `99202f5`.
같은 노트북의 소스 작업본에서 개발하고 바탕화면 실행 폴더에 선택 설치했다.
범위는 양팔 시뮬레이션이다. 실제 G1, DDS/SSH, 하체 정책, 모터 출력은 실행하지 않았다.

## 수정한 내용

### 추적 손실에서도 출력 위치와 내부 속도 일치

기존 `tracking_hold`는 qpos 갱신만 생략하고 내부 속도를 유지했다. 직전 검토에서
한 틱의 손실/복구 때 출력 위치 차분 가속도가 약 977.52/968.00도/s²로 재현됐다.
이 값은 실제 모터 측정값이 아니라 명목 dt=1/60초의 시뮬레이션 출력 차분이다.

`BimanualSimulation.brake()`로 이미 검사한 tail을 한 스텝씩 소비한다.
짧은 손실에서 목표 추종 대신 감속하며, 정지 후에는 검사된 정지 자세를 유지한다.
추적 복구는 그때의 위치/속도에서 이어진다. 0.35초 손실 후 복귀 및
0.75초 입력 timeout 정책은 바꾸지 않았다. 손실 직후 초기 속도가 0이고 tail이
없으면 정지 자세를 먼저 검사한다. 움직이는데 tail이 없으면 BLOCKED로 처리하며
속도 변수를 0으로 덮어 정상 정지처럼 가장하지 않는다.

복귀도 실제 0속도 명령을 한 번 출력한 뒤 READY를 선언한다. 근접 허용오차에
도달했다는 이유만으로 작은 잔여 속도를 둔 채 위치 갱신을 중단하지 않는다.

### solver 실패와 입력 파싱 경계

`SolverError`는 유형/메시지를 기록하고 기존 검사 tail을 사용한다. tail이 없으면
명시적으로 BLOCKED가 된다. 설정/프로그래밍 오류를 넓은 Exception 처리로
숨기지는 않는다. 무해답, NaN 결과, 알려진 solver 예외를 별도로 검사했다.

decoder는 파싱 전 최대 중첩 8단계를 검사하며 문자열 안의 괄호는 세지 않는다.
정수 토큰 18자리, 실수 토큰 64자 상한을 적용하고 비유한 수를 거부한다.
예상된 숫자/깊이 변환 예외는 ValueError로 분류한다. 기존 8,192바이트 상한과
필드/타입/세션/순서 검사는 유지한다. 잘못된 packet은 cycle 상태를 갱신하지 않는다.

engage origin과 필터 초기 회전은 같은 정규화 quaternion을 사용하도록 맞췄다.

### backend 재시작과 피드백 순서

피드백에 `backend_id`, `backend_started_ns`, `feedback_sequence`를 추가했다.
`G1BimanualFeedbackGate`는 입력 ack와 별도로 피드백 순서를 검사하고,
새 backend에서는 더 작은 입력 ack도 수락하되 재준비를 요구한다. 알려진/미확인
옛 backend의 지연 피드백, 역순/중복 피드백과 미래 ack는 거부한다.

시작 순서는 Python 3.11의 같은 호스트 QPC 기반 `perf_counter_ns()`로 비교한다.
Unity 시계와 빼서 신선도를 계산하는 것이 아니다. loopback/같은 OS 부팅 세션을
전제로 하며 다중 PC 시간 동기화 계약으로 일반화하지 않는다. 초기 구현의
`monotonic_ns()`는 이 노트북에서 15.625ms 해상도로 두 인스턴스가 같은 값을
가질 수 있어 검사에서 발견하고 바꿨다. QPC의 확인된 해상도는 100ns다.
Python의 시스템 공통 performance counter 문서:
https://docs.python.org/3.11/library/time.html#time.perf_counter

Unity는 새 backend를 확인하면 active/복귀 대기/준비 기억/캘리브레이션을 정리하고
새로운 inactive 입력 뒤 재정렬하도록 한다. C# helper의 상태/순서 검사와 실제
Unity/Meta DLL 참조 컴파일은 수행했지만 Quest에서 빠른 재시작을 직접 시험한
것은 아니다. 새 C#은 세대 필드가 없는 이전 backend의 피드백을 수락하지 않는다.
**Python과 C#을 같은 변경 묶음으로 적용하고 둘 다 재시작해야 한다.**

## 검증

- 소스 작업본: 58/58 PASS, 55.741초.
- 같은 노트북 실행 폴더: 엔진 경로 환경변수를 제거한 새 실행에서 58/58 PASS,
  56.334초. 격리 MuJoCo 3.12.0을 자동 선택했다.
- 새 Python 테스트는 13개다. 기존 45개를 없애거나 통과로 바꾸지 않았다.
- 손실 1/6/20틱을 좌우 각각 시험하고, 장기 손실→복귀→재engage를 검사했다.
  내부 velocity뿐 아니라 qpos 차분 속도와 그 가속도도 확인한다. 관측 최대는
  60.0000000000268도/s²로 수치 허용오차 안이다.
- 알려진 solver 예외/NaN 결과의 감속·정지·재추종, tail 없는 실패,
  프로그래밍 오류 전파, quaternion 기준 일치와 입력 거부 상태 불변을 검사했다.
- 임시 loopback 서버에 큰 정수/깊은 JSON/중복 키/잘못된 UTF-8을 보낸 뒤에도
  정상 입력으로 tracking을 유지하고 정상 종료한 것을 확인했다. 사용자 5020
  세션에 이 테스트 입력을 보내지 않았다.
- C# 재시작/순서 검사 17개 PASS, 기존 engage 조합 576개와 준비 기억 검사 PASS.
  Unity/Meta 실제 참조 컴파일 exit 0. 직렬화용 필드 등의 컴파일 경고는 남아 있고
  상세 경고 수/종류는 검증 JSON에 있다. Unity 전체 빌드나 Quest 착용 증거는 아니다.
- 문제 기록의 1,404틱 재생: 추종 fallback 1틱, 정상 복귀. 총 braking 2틱에는
  새로 명시한 복귀 마지막 0속도 정착 1틱이 포함된다. 최소 sampled clearance
  19.69mm. 출력 처리시간은 해당 실행의 관측치이지 실시간 성능 보증이 아니다.
- 실제 BAT: 별도 loopback 포트의 입력 없는 headless 기동/정상 종료 검사 PASS.

`g1_bimanual_motion_policy.py`, 기존 오른팔 기준 구현과 양팔의 `clearance()` 및
`checked_stop_plan()` 본문은 변경하지 않았다. 기존 X/Z 회전·전방 이동의 동작
보정, 공동 14축 QP, 양팔 충돌과 각도/속도/가속도 제한을 유지했다.

## 간헐 시작 지연은 별도로 남아 있다

loopback 테스트의 stdout/stderr를 읽지 않는 pipe 대신 파일에 기록하고,
engine import, controller import, 모델 생성, listener 준비, 첫 feedback,
정상 종료 시점을 QPC 값으로 출력하도록 했다. 실패한 subprocess 기록은 임시
폴더 삭제 전에 별도 보존한다. 대기 예산을 늘려 실패를 감춘 것은 아니다.

추가 실행 하나에서 MuJoCo import가 약 50.65초 걸렸고 해당 보조 테스트는 이후
직접 중단했다. 별도 import probe는 약 0.209초에 완료됐고 위 두 전체 테스트는
통과했다. **간헐 import 지연의 근본 원인은 아직 확정하지 못했다.** 이 중단된
실행을 PASS로 합산하거나 제어 루프 결함이 해결됐다는 근거로 쓰지 않는다.

## 설치와 확인 방법

노트북 `C:/Users/user/Desktop/G1_Teleop_Project`에 Python/C#/테스트 9개 파일만
선택 설치했다. 설치 전후 보호 대상 604개 파일의 해시를 확인했고, 씬과 기존
오른팔 파일을 변경하지 않았다. 백업은 실행 폴더 기준 다음에 있다.

`logs/backups/bimanual_boundary_20260918_123607/`

Unity/C# 파일 변경은 Editor 설정에 따라 재컴파일을 일으킬 수 있다. 이번 작업에서
Unity Play를 조작하거나 사용자의 기존 Python을 강제 종료하지는 않았다.
새 코드를 확인할 때는 Play를 끄고 기존 Python 창을 정상 종료한 뒤 실행한다.

```powershell
Set-Location 'C:/Users/user/Desktop/G1_Teleop_Project'
.\tools\START_BIMANUAL_UNITY_SIM.bat
```

이후 기존 SampleScene에서 Play한다. 새 JSONL의 첫 `kind=run` 행에는
`boundary_policy=bimanual_boundary_v1`이 있어야 한다. 짧은 추적 손실 동안
`tick_action=tracking_braking`, `ik_reason=checked_braking:tracking_unavailable`로
기록되며, 알려진 solver 예외는 `solver_error` 필드에서 구분한다.

검증 요약/선택된 테스트 출력은 이 변경 묶음에 포함한다. 전체 원본 로그, Unity
Library/설치 패키지, 엔진, 설치 백업과 초기 실패/중단 실행 원본은 노트북에 있다.
최신 Quest 사용감, Unity 전체 Play 재시작 시나리오, 실제 G1은 미검증이다.

[검증 JSON](validation/bimanual_boundaries_20260918/verification.json)
[소스 테스트 출력](validation/bimanual_boundaries_20260918/source_suite.txt)
[설치 폴더 테스트 출력](validation/bimanual_boundaries_20260918/runtime_suite.txt)
[C# 테스트 출력](validation/bimanual_boundaries_20260918/csharp_tests.txt)
