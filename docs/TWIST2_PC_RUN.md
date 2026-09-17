# PC에서 실행하는 TWIST2 후보

현재 실행 주체는 Windows PC의 WSL(x86_64)이다. G1 SSH/별도설치 없이 기존 DDS 통신을
사용한다. G1의 두 VR 임시폴더는 삭제했고 PC에 전체백업·해시검증했다.
기존 G1 SDK/정책/원래 오른팔 프로그램은 이번VR작업 이전 파일이므로 보존했다.

## 실행 흐름

Quest/Unity → Windows Mink → Windows loopback5008 relay → WSL loopback5013
→ PC의 C++ 정책추론/전신명령 합성 → 유선DDS → G1 기존 모터제어.
500Hz writer와 50Hz 정책이 PC에서 돌아간다. 원격SSH 프로세스는 필요 없다.

## 기본 점검: 모터 출력 없음

프로젝트 루트의 PowerShell:

```powershell
.\tools\RUN_PC_TWIST2.ps1
```

WSL route, x86 실행파일, 정책 SHA만 확인하고 native 바이너리는 실행하지 않는다.
현재 연결은 eth3 / 192.168.123.99 / G1 192.168.123.164이며 인터페이스는 route에서 찾는다.
WSL mirrored 설정은 확인했으나 이 확인만으로 DDS 패킷 수신/지연을 검증한 것은 아니다.

## 사용자가 직접 시작하는 준비 시험

PC 경로의 LowState 수신/타이밍을 먼저 확인한 뒤 사용한다. G1에서의 과거 성공을
PC 경로의 물리 검증으로 간주하지 않는다. 지지/양발하중/안정적인 AI 상태 및 R1 유지 필요.

```powershell
.\tools\RUN_PC_TWIST2.ps1 -Mode Readiness
```

capture1초 + blend4초 + policy3초, 계획 damping3초. native P 확인 전에는 DDS를 초기화하지 않는다.
이 명령은 물리명령을 전송하며 AI를 해제한다. R1해제/Select/B 중단, 자동 AI복귀 없음.
오류 damping은 Ctrl+C까지 지속 가능. 지지는 종료 이후에도 유지한다.
PC/네트워크 단절 시 PC가 보낸 damping 자체가 도달하지 않을 수 있다. 이 경로의 단절 대응은
아직 실측 검증되지 않았으며, G1에서 실행하던 경우와 같은 보장을 주장하지 않는다.

## VR 연결 설정

기존 gate7_mink_wsl_relay.py의 target-host를 G1 IP에서 127.0.0.1로 바꾼다.
listen127.0.0.1:5008, target127.0.0.1:5013이며 WSL native도127.0.0.1에 bind한다.
Unity simulation 표시와 실제LowState로 초기화한 live Mink 경로를 사용한다.
저장/simulation 패킷을 live로 위장하지 않는다. relay와 native는 동일한 새 token을 사용해야 한다.

WSL에서 token을 설정한 뒤 run_pc_twist2.sh --vr 실행 가능하며 기본 policy10초,
G1_PC_POLICY_SECONDS로2..20초 명시 가능. 실제VR사용 전 Windows→WSL loopback수신과
최신LowState 정렬을 확인해야 한다. 현재턴에는 VR/정책/DDS/모터실행을 하지 않았다.
PowerShell에서는 -Mode Vr -RelayToken <동일한새토큰> -PolicySeconds 10으로 전달한다.
토큰이 없거나 형식이 다르면 바이너리 실행 전에 거부한다.

## 파일 위치와 재빌드

- 소스: experiments/twist2_right_arm_manual/twist2_vr_native_draft.cpp
- WSL ELF: /home/user/twist2-vr-build-20260907/build/g1_twist2_vr_split_candidate
- 정책: references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt
- 향후 CSV: logs/test_results/pc_twist2_runs

```sh
/home/user/.venvs/twist2-vr-build/bin/cmake --build /home/user/twist2-vr-build-20260907/build --target g1_twist2_vr_split_candidate -- -j1
```

코드 수정 후에는 PC target을 재빌드한다. G1에 파일을 전송하지 않는다.
