# Split/relative 후보 소스 전송·빌드 준비

## 최신 시작 시도: CLI 진입부 거부 / 로컬 수정·검증 완료 (2026-09-08)

- 사용자가 지지/접지/안정/R1 준비 및 구체8초 시험 질문에 "시작"으로 답하여 1회 시작.
  실행전 후보ELF b670e52e...380d2 및 정책463be037...9015 확인, 관련프로세스/5013 없음.
- 후보 --vr-relative-candidate 실행 직후 기존 최상단 --vr-right-arm 전용 검사가 거부.
  `[fatal] native VR draft requires explicit VR invocation; not a keyboard executable`, exit1.
  원인: 후보옵션을 후속파서에만 추가하고 첫 guard를 누락한 구현결함.
  앞선 빌드/adapter시험은 실제 main 진입을 검증하지 못했다. 이는 물리조건 실패가 아니다.
- main 첫 guard에서 종료: P 질문, Policy 구성, Controller/DDS 초기화, publisher 생성,
  ReleaseMode/모터명령 전에 중단. 이번시도는 AI해제/damping 전환을 수행하지 않았다.
  이후 관련프로세스 및5013 없음 확인, SSH 종료. 사용자에게 R1 놓아도 됨 안내.
  현재 AI모드를 새로 조회한 것은 아니며 자동 재시도 없음.
- 로컬 native_vr_invocation.hpp로 첫 guard와 mode선택의 공통검사를 통합.
  후보는 --vr-relative-candidate, 기존진단은 --vr-right-arm만 허용.
  실기 제어/속도/한계/준비 임계값 변경 없음. 기존 물리원본 SHA E61D8A3C...CC09F 유지.
- SDK없는 test_native_vr_invocation.cpp: 옵션교차거부, 명시actuation/기간인자필수,
  잘못된옵션/argc/null 거부 및 양쪽정상옵션 허용 MSVC /W4 /WX exit0.
  WSL 두target 재빌드·링크 exit0. 로컬native/G1바이너리 재실행 없음.
- 패치 `logs/test_results/twist2_invocation_fix_20260908.tar.gz` 파일4개 바이트검증 완료.
  SHA256 `68960570d4d275900e2a07c75f6361acb84047b0f9b2d65c187976059116d75a`.
  cpp/newheader/INVOCATION_FIX_MANIFEST.json/INVOCATION_FIX_SHA256SUMS 포함.
  아직G1미전송. 원격대상은 기존 신규임시폴더 하나로 한정하고 candidate만 재컴파일 제안.
  적용 후 기존 SHA256SUMS의 cpp해시는 과거버전이므로 새 INVOCATION_FIX_SHA256SUMS로 검증.
- 증거: twist2_split_attempt1_terminal_20260908.json,
  twist2_invocation_fix_build_20260908.log, twist2_invocation_fix_check_20260908.json
  (모두 logs/test_results). 시험용패치에는 실행스크립트/정책/SDK/ELF 없음.
- 남은 작업: 이 수정본 반영·재컴파일 승인 및 동일범위1회 재시험 승인/준비 확인.
  현재실기 ready/시간지연/정지 검증은 아직시작하지 못함. 임시폴더 추후삭제 의무 유지.

## 최신 G1 후보 전송·컴파일 완료 / 실행하지 않음 (2026-09-08)

- 사용자가 새 임시폴더 전송·컴파일 질문에 "진행"으로 승인. 이 범위만 수행.
- LAN SSH 연결 확인, 대상폴더 부재 및 실행중 g1_twist2 프로세스 없음 확인 후
  `/home/unitree/g1_vr_split_candidate_20260908` 생성. 기존 작업 되돌림 없음.
- source.tar.gz 전송, archive SHA db190c66...af403 및 SHA256SUMS21항목 모두 OK.
  G1 aarch64 / Torch2.0.0+nv23.05 / ABI1 / 기존 unitree_sdk2-main 확인.
- 후보 target만 CMake configure 및 clean-first -j1 컴파일·링크 성공, SSH exit0.
  ELF `/home/unitree/g1_vr_split_candidate_20260908/build/g1_twist2_vr_split_candidate`
  SHA256 `b670e52e471d8eb2feb297887f63d449159a9d7e62f4e81c799f4159b18380d2`.
- 기존 물리 ELF a3c1e936...74f60, 진단 ELF2af67725...65ef16 전후 동일.
  빌드 후 관련 프로세스 없음. 생성된 바이너리는 --help 포함 실행하지 않았다.
  DDS 초기화/publisher/모드변경/물리출력 없음. 로봇 자세/AI모드는 이번에 조회하지 않았다.
- 기록: `logs/test_results/twist2_g1_split_candidate_build_20260908.log`,
  `logs/test_results/twist2_g1_split_candidate_build_check_20260908.json`.
  stdout 빌드로그이며 SDK/Torch stderr 경고 전체는 포함하지 않는다.
- 다음은 별도 승인·현재 지지/R1 준비 확인 후 VR engage 전 제한된 전신 준비 시험.
  G1 빌드 성공은 split/relative 방식의 물리 검증이 아니다. 실행 승인은 받지 않았다.
- 신규 임시폴더 전체(source/manifest/build 포함)와 기존
  `/home/unitree/g1_vr_native_review_20260908` 추후삭제 미완료 유지.

아래는 패키지 준비 당시 절차 기록이다.

2026-09-08. 로컬 패키지 준비 완료. G1 전송/빌드/실행은 아직 하지 않았다.

- 패키지: `logs/test_results/twist2_split_candidate_source_20260908.tar.gz`
- SHA256: `db190c6692b26a3c8828e4a70ec16024577cdfb6ecfdb1f5b31f57efc44af403`
- 파일22개, 169779 bytes. 재귀적인 로컬 quoted include 의존성 포함.
- 실제 로컬 빌드·오프라인 시험에서 검증된 소스 해시와 일치 확인.
- 압축의 모든 항목은 상대경로 일반파일이며 원본 바이트와 동일. 심볼릭링크/상위경로 없음.
- 기존 SDK/Torch 설치가 필요하다. SDK, 정책 파일, 실행파일, 자동설치/실행 스크립트는 포함하지 않는다.

## 승인할 작업의 정확한 범위

LAN SSH `unitree@192.168.123.164`에서 신규 임시 디렉터리
`/home/unitree/g1_vr_split_candidate_20260908`만 생성하고 패키지 전송·해시검증·압축해제·컴파일한다.
이미 디렉터리가 있으면 내용을 확인하고 덮어쓰기 전에 범위를 다시 판단한다.
실행 중인 관련 프로세스를 읽기 전용으로 확인하며 무관한 프로세스를 종료하지 않는다.
기존 `/home/unitree/g1_right_arm_trial` 및 이전 진단 디렉터리는 변경하지 않는다.
바이너리를 --help를 포함하여 실행하지 않는다. DDS 초기화, publisher 생성, 모드 변경, 물리 출력 없음.
빌드 로그와 ELF 해시는 Windows로 복사하여 기록한다. 전송/빌드 승인은 물리 시험 승인이 아니다.

## 승인 후 빌드 순서

1. 신규 디렉터리·기존 SDK/Torch 위치와 관련 프로세스 부재를 확인한다.
2. 패키지를 신규 디렉터리의 source.tar.gz로 복사하고 위 SHA256을 확인한다.
3. 패키지 해시 확인 후 신규 디렉터리에 압축을 풀고 `sha256sum -c SHA256SUMS`를 실행한다.
4. 확인한 SDK 경로로 CMake 구성 및 후보 target만 빌드한다. G1 시계는 바꾸지 않는다.

```sh
# 작업 디렉터리: /home/unitree/g1_vr_split_candidate_20260908
# SDK 경로는 실행 전에 존재/종류를 확인한다.
cmake -S experiments/twist2_right_arm_manual/native_vr_build -B build -DUNITREE_SDK2_ROOT=/home/unitree/unitree_sdk2-main
cmake --build build --target g1_twist2_vr_split_candidate --clean-first -- -j1
file build/g1_twist2_vr_split_candidate
sha256sum build/g1_twist2_vr_split_candidate
```

CMake는 설치된 Python torch의 경로/ABI를 조회한다. 기존 G1 기록은 Torch2.0/aarch64이며,
현재 환경은 아직 재확인하지 않았다. 로컬 x86 빌드 성공은 G1 빌드 성공이 아니다.

## 남은 확인과 정리

빌드 후 별도 물리시험에서 준비 상태, writer 지연, R1/중단 동작을 먼저 확인한다.
하중오차 허용·상대 VR 방식의 실기 안전성은 아직 검증되지 않았다.
새 임시 폴더 전체와 이전 `/home/unitree/g1_vr_native_review_20260908`는 추후 정리 대상이다.
필요한 로그를 복사·검증하고 실행 프로세스 부재와 삭제 대상 절대경로를 확인한 뒤 정리한다.
이번 턴에는 G1에 접속하거나 파일을 변경하지 않았다.
