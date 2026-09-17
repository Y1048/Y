# 다음 연결용 진단 패치

후속 로컬 신선도 수정(2026-09-08)은 이 패키지에 포함되지 않는다.
현재 패키지는 배포된 진단버전 이력이며, 새 로컬 초안을 전송하려면 다시 묶어야 한다.

최신 상태: 2026-09-08 사용자 재연결 후 전송·manifest 검증·G1 clean-first 빌드 완료(exit0).
새 ELF SHA256 `2af67725e0f8c36f6cb11a11c58673edbe6fc7c7b5113c3832d5c4489065ef16`.
바이너리는 실행하지 않았다. 아래 미전송 설명과 이전 ELF는 패키지 준비 당시 이력이다.
빌드 로그: logs/test_results/twist2_g1_state_stop_build_20260908.log.

2026-09-08. 로컬 준비 완료, G1 미전송/미빌드/미실행.
G1은 사용자 확인상 배터리 부족으로 전원이 꺼져 있다.

## 파일과 범위

`logs/test_results/twist2_state_stop_diagnostic_patch_20260908.tar.gz`

SHA256: `52826afc6ea48dacd217a986bc586a9cc2f4a616fbc9ce55cbe21d816c176fa1`

포함 파일은 native 초안 C++와 native_state_audit.hpp/native_stop_audit.hpp,
STATE_STOP_PATCH_MANIFEST.json이다. 파일4개의 경로/형식과 소스 바이트 해시를 검증했다.
설치/실행 스크립트, 정책, SDK, 원본 물리 C++는 포함하지 않는다.
이 파일은 **기존 임시 빌드 폴더용 증분 패치**이며 단독 빌드 소스 전체가 아니다.
원래 임시 폴더가 없거나 다른 버전이면 그대로 풀지 말고 먼저 차이를 확인한다.

기존 원격 진단 ELF 예상 SHA256:
`2d9614eb88ecdfb3115282649aaf3405a840057c43f3d2a13529e03d4c68ee9b`

원격 대상은 `/home/unitree/g1_vr_native_review_20260908`로 한정한다.
G1 기존 물리 프로그램 `/home/unitree/g1_right_arm_trial`는 변경하지 않는다.

## 전원이 켜지고 연결된 뒤의 빌드 절차

아래는 다음 작업을 위한 기록이며 이번 턴 실행하지 않았다.
먼저 대상 폴더, 기존 ELF 해시 및 해당 프로그램이 실행 중이지 않음을 확인한다.
사용자가 승인한 임시 소스 전송·컴파일 범위를 확인하고 진행한다. 물리 실행은 포함하지 않는다.

Windows 프로젝트 루트 PowerShell:

```powershell
Get-FileHash logs/test_results/twist2_state_stop_diagnostic_patch_20260908.tar.gz -Algorithm SHA256
scp.exe -o StrictHostKeyChecking=yes -o ConnectTimeout=5 logs/test_results/twist2_state_stop_diagnostic_patch_20260908.tar.gz unitree@192.168.123.164:/home/unitree/g1_vr_native_review_20260908/state_stop_patch.tar.gz
```

SSH로 대상 폴더에서 확인 후 빌드한다. 비밀번호를 파일에 저장하지 않는다.

```sh
cd /home/unitree/g1_vr_native_review_20260908
printf '%s  %s\n' 52826afc6ea48dacd217a986bc586a9cc2f4a616fbc9ce55cbe21d816c176fa1 state_stop_patch.tar.gz | sha256sum -c -
# 위 검증 성공을 확인한 뒤에만 다음 명령을 진행한다.
tar -xzf state_stop_patch.tar.gz
cmake --build build --clean-first -- -j1
# 컴파일 성공을 확인한 뒤 산출물 종류/해시를 기록한다. 바이너리는 실행하지 않는다.
file build/g1_twist2_vr_native_draft
sha256sum build/g1_twist2_vr_native_draft
```

PC/G1 시계 차이가 있으므로 clean-first로 실제 재컴파일한다. 시계 설정을 변경하지 않는다.
빌드 로그와 새 ELF 해시를 Windows에 남기고, manifest와 실제 원격 소스 해시도 대조한다.
현재 빌드 성공 근거는 로컬 WSL과 MSVC 시험뿐이며 G1 빌드 성공을 미리 주장하지 않는다.

## 이번 패치가 바꾸는 것

- 기존 policy CSV 끝에 LowState 진단124열 추가.
- 최초 latch 상태를 메모리에 보존하고 송신 종료 후 `<policy CSV>.stop.csv`에219열 저장.
- R1, ready, 속도, gain, feedforward, 정책 feedback 및 중단 조건은 변경하지 않는다.

이 패치는 **관측 정보 보강**이다. 현재 ready 실패를 해결하거나 VR 조작을 허용하는 패치가 아니다.
실제 시험은 별도 범위/준비 확인이 필요하며 이전 물리 승인은 재사용하지 않는다.
강제 종료/전원상실/handoff전 예외의 기록은 보장하지 않는다.

## 정리 의무

원격 임시 폴더는 추후 삭제 대상이다. 새 patch archive, manifest, 헤더, build 및 향후
CSV/stop.csv도 포함한다. 필요한 로그를 로컬로 복사·검증한 뒤 대상 절대경로와 실행 중인
프로세스 부재를 확인하고 정리한다. 이번에는 삭제하지 않았다.

이 패키지를 만든 뒤 소스를 수정하면 기존 archive를 최신이라고 쓰지 말고 새 버전으로 다시 묶는다.
