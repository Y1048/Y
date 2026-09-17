# 첫 VR 물리 시험 제안 — 아직 실행 승인 전

2026-09-08. 사용자는 넘어짐 지지와 별도 리모컨 담당을 준비할 수 있다고 확인했다.
이번 제안은 한 번의 시험이며 재시도/제한 완화/자동 AI 복귀를 포함하지 않는다.

## 정확한 범위

- G1 임시 폴더 `/home/unitree/g1_vr_native_review_20260908`에서 native draft 실행.
  새 ELF SHA256 `ef24e2038d1379dd1699071c475ff6166dcd7912600cd4e81101033a12718dba`.
- 정책 `/home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt`, 검증 SHA256
  `463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015`.
- `eth0`, 명시적 `--policy-seconds 10 --vr-right-arm`.
  capture1초 + blend4초 + policy최대10초 = 최대15초 후 계획 damping3초.
  preflight 대기는 별도이며 시작 실패/오류는 이 시간으로 정상 종료되지 않을 수 있다.
- 단일 native rt/lowcmd publisher 생성, CheckMode/ReleaseMode 후 전신 제어.
  하체0..11 정책, 허리/왼팔12..21 capture 유지, 오른팔22..28 VR 최대0.08rad/s.
  현재폴더에 `g1_twist2_right_arm_trial_<timestamp>.csv` 생성 후 로컬 증거로 복사.
- Windows fresh LowState seed→live Mink(hardware-guarded/vanilla)→relay5008→G1:5013.
  Windows 출발192.168.123.99, G1 bind192.168.123.164, 양쪽 동일한 새 relay token.
  simulation_only/replay 입력은 사용하지 않는다. Unity display는simulation 유지.

## 실행 직전 / 사람 역할

1. 지지 상태와 별도 리모컨 담당이 실제로 준비됐는지 확인한다.
2. 신선한 LowState/AI 모드/관련 프로세스/5013 점유를 다시 확인한다.
   프로세스 이름 목록만으로 모든 DDS 송신자 부재를 보장하지 않는다.
3. 새 실측 seed로 Mink 초기화, 손은 engage 영역 밖에서 대기.
4. 승인 범위에서 P 확인 및 시작. 리모컨 담당은 R1을 계속 유지한다.
5. native `vr_ready` 확인 후에만 engage, 손1~2cm 천천히 움직이고 pinch 해제.
   초기 실측 오차/ready/시간 제한을 통과하지 못하면 중단하고 임의로 완화하지 않는다.

## 중단 의미

- pinch/계획시간 종료: 계획 damping3초 뒤 송신 종료. AI 자동복귀 없음.
- R1 해제 또는 Select/B, 상태/입력 오류: damping latch.
  오류 damping은 Ctrl+C 전까지 계속될 수 있다. Ctrl+C는 AI 복귀 명령이 아니다.
- 지지는 damping 및 송신 종료 이후에도 유지해야 한다.
- ReleaseMode 실패/응답 유실: 제어권 UNKNOWN, VR active 진입 안 함.
  자동 재시도/경쟁 publisher를 만들지 않고 실제 모드/지지를 확인한다.

## 파일 정리

임시 폴더 전체는 추후 삭제 대상이다. 이번에 추가된 tick_patch.tar.gz와
native_state_tick.hpp, 빌드 산출물/향후 CSV도 포함한다. 로컬 증거는 보존한다.
기존 `/home/unitree/g1_right_arm_trial` 및 SDK/Torch/정책 원본은 변경/삭제하지 않는다.
