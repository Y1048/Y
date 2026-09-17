# 자세 스윕 결과 판정 수정

## 검토
- 기존 R54에 해당한다. 스윕 실행 완료와 복구 성공을 같은 PASS로 표시하던 문제다.
- 기존 R53의 실험 모델 공유 및 재개 시 provenance 문제는 이번 수정과 별개로 남는다.

## 코드 수정
- GetSweepOutcome에서 빈 결과/전체 SKIPPED는 NO_EVALUATED_POSES, 전체 FAIL은 NO_SUCCESSFUL_POSES로 구분하고 종료 코드 3을 반환한다.
- ERROR 또는 알 수 없는 상태는 INFRASTRUCTURE_ERROR, 종료 코드 2다.
- 성공과 실패/제외가 섞이면 COMPLETED_PARTIAL_MAP, 모두 성공하면 COMPLETED_ALL_SAMPLED_POSES다. 두 경우 종료 코드 0은 지도 생성 완료를 뜻하며 모든 자세의 안전성을 뜻하지 않는다.
- summary JSON에 outcome/exit_code를 저장하고 콘솔에도 같은 outcome을 표시한다.
- 두 BAT의 무조건적인 PASS 문구와 오류 원인을 단정하는 안내를 교체했다.
- 복구 알고리즘, 충돌 거리, 비용, 속도 및 물리 출력 설정은 변경하지 않았다.

## 테스트
- `py -3.11 -m pytest experiments/startup_recovery_posture_sweep/test_sweep.py -q`
- 결과: 5 passed, 7 subtests passed.
- 상태 분류, 기존 격자/관절 제한/HTML 단위 테스트다. 실제 스윕, BAT 실행, WSL/DDS/G1 실행 검증은 하지 않았다.

## 남은 항목
- R53 실험 runner 모델 격리 및 재개 provenance 검증.
- 기존 손목 roll 충돌 거리 회귀 실패는 해결되지 않았다.
- Startup Recovery 전략 지도 확장 실험은 계속 보류한다.
