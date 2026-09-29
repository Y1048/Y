# G1 Teleop Current Handoff

최종 갱신: 2026-09-29

## 현재 기본 상태

```bat
tools\START_G1_VR_TELEOP.bat
```

```text
bilateral IK + Omni observation + LowState observation + front camera
NO MOTOR OUTPUT
```

오른팔 단독 운영 경로는 current workflow가 아니다.

## Bilateral IK

- 항상 14 arm joints
- 하나의 MuJoCo configuration
- 좌/우 task를 같은 QP에서 동시에 solve
- proximal 90 deg/s
- wrist 180 deg/s
- acceleration 90 deg/s^2
- IK tracking rate 1.0 s
- compute 60 Hz

공용 helper는 `g1_mink_shared.py`, `g1_arm_common.py`로 분리했고 과거 single-arm prototype/common 의존성은 제거했다.

## Camera

source checkout과 Desktop 실행본을 동일하게 맞췄다.

```text
1920x1080 JPEG
15 fps target
16:9 PiP
PiP parent = G1 RobotRoot
SSH transport only
```

Desktop의 2 fps 구버전은 제거했다. G1 stock `videohub_pc4`는 1080p15이고 임시 `/tmp` 30fps binary에서 VideoClient 약 27 fps를 확인했지만 stock binary는 변경하지 않았다.

## Cleanup

2026-09-29 cleanup에서 제거한 범주:

- Twist2/right-arm manual experiment tree
- MJLab independent locomotion
- Gate5/6/7 hardware trials
- PD/sysid/startup-recovery experiments
- old test BAT/PS1 wrappers
- WSL camera fallback
- old backend g1_teleop/config/TeleImager stack
- old GitHub PD workflows
- unused Unity scripts/editor setup helpers
- lower-body/reference archives

현재 repository는 integrated runtime + current regression + setup/maintenance에 집중한다.

## Replay 기준

`G1.zip` strict replay 기준:

- input rows: 7,837
- accepted: 7,836
- state/q rows: 46,570
- mismatch: 0
- max q difference: 약 2.0e-13 rad

`g1_bimanual_session_report.py --replay --strict`가 최종 replay gate다.

## 현재 테스트

- backend current regression
- hardware Omni/Ruckig regression
- SSH camera/launcher/dependency regression
- Unity validator는 일반 Editor compile/Play로 최종 확인 필요

## 알려진 경계

- SampleScene의 5005/5006 serialized compatibility wiring 일부는 남아 있다.
- current bimanual sender는 5005 sender를 비활성화하고 5020을 사용한다.
- v1 packet decode는 regression fixture 재생 때문에 유지한다.
- physical bilateral motor control은 default launcher scope가 아니다.

## 작업 원칙

1. current runtime graph를 먼저 확인한다.
2. 기존 dirty/untracked를 reset/clean하지 않는다.
3. 변경 후 backend/hardware regression과 strict replay를 다시 실행한다.
4. physical actuation은 별도 승인 전 시작하지 않는다.
