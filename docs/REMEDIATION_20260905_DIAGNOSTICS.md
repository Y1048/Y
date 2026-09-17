# 검증 도구 수정

## 검토

R20, R24, R25, R26, R28의 현재 소스를 재확인했다. 기존 검토 번호를
유지한다. 이 문서는 전체 finding의 수정 완료 선언이 아니다.

## 코드 수정

- R20: benchmark 두 개와 품질 진단 네 개의 결과 상태를 프로세스 종료 코드에
  연결했다. 성공 0, parity/render 실패 1, 시간 기준 실패 2, 검토 필요 3,
  deployment 차단 4. 실행 예외는 기존대로 실패한다. 보고 파일 저장은 유지한다.
- R24: 두 진단 보고서의 고정 40/100 문구를 제거하고 실제 helper의 관절별
  rad/s, solver dt, collision 최소거리를 기록한다. 제한 비활성 조건을 검사하는
  테스트 목표를 현재 한 스텝 속도 한도 아래로 조정했다. 제어 값 변경은 없다.
- R25: Unity DLL보다 최신인 Assets C# 또는 csproj가 있으면 로드 전에 차단한다.
  결과는 prebuilt_assembly_only로 명시한다. 시간 비교는 재현 빌드 증명이 아니다.
- R26: solver 0회가 되는 duration 및 비유한 duration을 사전에 거부한다.
  CLI의 30초 상한은 유지하고, 내부 RunCase의 긴 기록 재생은 허용한다.
- R28: config와 WorkspaceExitDebounce 모두 양의 유한 시간을 요구한다.
  update는 비음수 유한 dt만 받고 잘못된 입력으로 누적 상태를 바꾸지 않는다.

## 테스트

아래 9개 pytest 파일: **121 passed, 64 subtests passed**.

```text
test_diagnostic_exit_contract.py
test_teleop_config.py
test_foundation.py
test_mink_tracking_lag.py
test_recorded_pose_speed_comparison.py
test_mink_step_acceptance_comparison.py
test_mink_candidate_benchmark.py
test_mink_distance_invariance.py
test_feasible_target_return.py
```

종료 코드 검사는 main의 실제 반환식을 평가하고 실제 __main__ wrapper를 실행한다.
전체 렌더링 benchmark를 재실행한 것은 아니다. PowerShell 시간 검사는 임시
fixture의 최신/오래된 DLL 두 경우를 실행했다. 실제 Unity assembly 실행은 하지 않았다.

## 남은 항목

- R24의 다른 오래된 테스트 기대값, R53의 공통 XML 쓰기와 provenance는 남아 있다.
- R25는 최소 freshness 차단이다. 소스 hash와 빌드 산출물을 결합하는 완전한
  reproducible-build 검증은 아니다.
- R20 도구의 전체 캡처/렌더링 CLI 통합 재실행은 별도다.
- 기존 R2/R33/R41/R42의 대체 진입 경로, R50 remote/deadman/CRC,
  R60-R67 카메라/빌드/설정 및 나머지 미해결 finding은 완료로 변경하지 않았다.
- G1/WSL/DDS/Unity 실행, publisher 생성, 하드웨어 설정 변경 없음.

## 2026-09-06 도달 범위 진단 후속 검토

### 검토

diagnose_recorded_reach.py도 REVIEW_REQUIRED를 기록한 뒤 성공 종료했다.
기존 R20에 범위를 추가했다. 새 finding 번호는 만들지 않았다.

### 코드 수정

main이 보고서를 저장한 후 3을 반환하고 __main__이 SystemExit로 전달한다.
거리 상한 안에 있다는 결과도 충돌 없는 도달 가능성을 보장하지 않으므로
성공 승인으로 바꾸지 않는다. IK, 속도, 하드웨어 설정은 변경하지 않았다.

### 테스트

test_recorded_reach_bound.py 5개와 diagnostic exit contract 92개, 총 97개.
실제 MuJoCo 모델 FK와 한 패킷 fixture로 main의 보고서 저장/반환값을 확인했다.
캡처 decoder와 구간 추출은 mock이며 전체 실사용 캡처 재생은 아니다.
기존 1000개 관절 자세 거리 상한 검사 및 실제 entry wrapper 검사도 포함한다.
결과: logs/test_results/r20_reach_exit_20260906.xml

### 남은 항목

R20의 전체 CLI 캡처/렌더링 통합 재실행은 여전히 남았다. 기본 3.11 엔진,
공유 모델 출력 관련 R24/R53 및 기타 finding은 이 수정으로 완료되지 않는다.
실제 G1/WSL/DDS/Unity/관리자 네트워크 실행 없음.
