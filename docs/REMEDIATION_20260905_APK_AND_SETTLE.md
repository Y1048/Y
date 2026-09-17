# APK 경로와 Jog 준비 검사

## 검토

R59/R67의 APK 경로 및 장치 결박, R52의 settle 마지막 패킷 만료를 재확인했다.
기존 번호를 사용한다. 전체 finding 수정은 아직 완료되지 않았다.

## 코드 수정

- APK BAT가 GUID별 출력 경로를 생성하고 G1_APK_OUTPUT_PATH 환경변수로
  Unity builder와 같은 경로를 공유한다. 지정 경로에 기존 APK가 있으면 거부한다.
- 성공한 빌드만 SHA256 sidecar를 생성한다. BAT는 파일 해시를 확인한 후
  사용자가 명시한 serial에 `adb -s`로 설치한다. 실행마다 빌드 로그도 분리한다.
- Jog settle은 최신 패킷의 age, sequence 역행, 수신 간격을 검사한다.
  반환 직전에 age를 다시 검사해 초반 burst 후 단절을 차단한다.
- KeyboardReader 진입 후 publisher 생성 직전에 snapshot을 다시 가져와
  freshness/mode/precheck 자세/초기 속도를 검사한다.

## 테스트

57 passed, 3 subtests passed:

```text
backend/tests/test_diagnostic_exit_contract.py
hardware/g1_arm_bridge/test_g1_right_arm_jog.py
hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py
hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py
```

APK의 정상/변경/해시 누락 fixture에서 BAT의 실제 PowerShell 해시 구문을 실행했다.
이 환경에서는 자식 Windows PowerShell의 Get-FileHash 자동 로딩이 실패하여
추가 모듈 없이 .NET SHA256 스트림으로 검사하도록 수정했고 재검사했다.
Jog는 가짜 시계/버퍼로 정상 연속 수신, 마지막 구간 단절, 중간 gap을 검사했다.

## 남은 항목

- Unity C# 전체 컴파일/Android 빌드/Quest 설치 미실행. C# 변경은 소스 검토다.
- R52는 검사 경계 개선이며 물리/DDS 검증은 하지 않았다. snapshot과 실제
  publisher 사이 모든 외부 상태가 원자적으로 고정된다는 보장은 아니다.
- G1/WSL 실행, publisher 생성, 명령 송신, 물리 허가 설정 변경 없음.
- R53 잔여 writer, R50 및 다른 미해결 finding, 손목 roll 충돌 거리 실패는 남는다.
