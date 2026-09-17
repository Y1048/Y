# Standard Mink 장비 없는 검증

## 검토

Unity 입력 계약, standard QP, 공통 궤적 제한, Gate 7 릴레이/가상 LowState,
해제 및 안전 검증을 확인했다. 실제 Quest 추적이나 실제 G1 응답 검증은 아니다.
G1/WSL/DDS/관리자 네트워크 작업은 하지 않았다. 통신시험은 Windows의
127.0.0.1 임시 포트만 사용했다. 물리 프로파일 6개 모두 잠금 유지 확인.

## 코드 수정

- test_standard_mink_live.py: 두 충돌 프로파일에서 위치 XYZ, 회전 XYZ,
  혼합 동작 7종을 각 120단계 시험한다. 총 1,680단계다.
  관절/충돌/설정 속도 상한 및 비오른팔 고정, 실제 QP 출력의 패킷 변환을 검사.
  통신 검사는 지원 entrypoint와 같은 provenance wrapper를 거친다.
- 가상 E2E에 실행별 relay token과 명시적 테스트 provenance를 추가했다.
  실제 릴레이의 provenance 요구 조건은 약화하지 않았다.
- 릴레이의 선택적 --ready-file은 bind 성공 후에만 기록한다.
  가상 시험은 새 고유 경로로 준비 신호를 기다려 첫 UDP 패킷 유실을 방지한다.
  실물 런처에는 이 옵션을 추가하지 않았다.
- IK 비용, PD, 속도, 물리 잠금, 설치된 MuJoCo 버전은 바꾸지 않았다.

## 테스트

| 항목 | 결과 |
| --- | --- |
| 새 IK/궤적/피드백/Gate 7/가상 통신 묶음 | 51 passed |
| 릴레이/E2E 반복 | 8 passed (위 묶음과 중복) |
| 입력/좌표/캘리브레이션/watchdog | 39 passed / 122 subtests |
| 기존 feasible/trajectory/orientation 회귀 | 24 passed / 10 subtests (75개 묶음 내) |
| 격리 MuJoCo 3.12 새 IK + 손목 회귀 | 22 passed / 3 subtests |
| Unity runtime/editor C# incremental build | 각각 오류 0 / 경고 0 |
| 변경 Python compile | 통과 |

첫 묶음의 E2E 실패는 토큰 누락, 다음 실패는 준비 전 송신으로 7/8패킷 수신이었다.
최종 51개 묶음 및 반복시험은 모두 통과했다. 초기 속도 assertion은 과거
0.08을 가정한 테스트 오류였으며 현재 소스 0.16 rad/s를 검증하도록 수정했다.
표의 여러 묶음은 중복이 있으므로 단순 합계를 전체 테스트 수로 쓰지 않는다.

결과 파일은 logs/test_results 아래에 있다:
- standard_mink_offline_20260906_verified.xml (최종 51개)
- standard_mink_relay_repeat_20260906.xml
- standard_mink_input_20260906.xml
- standard_mink_packet_20260906.xml
- standard_mink_312_20260906.xml
- standard_mink_offline_20260906_final.xml (중간 74 pass/1 fail 기록; 최종 성공 기록 아님)

## 남은 항목

- 기본 MuJoCo 3.11 거리 부호 문제는 그대로 남아 있다. 3.12 검증은 프로세스
  격리였으며 기본/WSL 환경 전환이나 전체 프로젝트 검증이 아니다.
- Unity Editor Play/VR 시점/실제 손목 축과 engage 동작은 Quest가 필요하다.
- 실제 지연, 드라이버/DDS, 모터 PD 응답, 힘/접촉/균형은 G1 시험이 필요하다.
- 이번 연속 입력은 제한된 정상 초기 자세의 작은 궤적이다. 모든 작업공간이나
  목표 도달 정확도를 보장하지 않는다. 가상 LowState는 이상적인 모델이다.
- C# 증분 빌드는 Unity 재import 또는 Player build를 대신하지 않는다.
