# G1 Bilateral Hardware Bridge

이 폴더는 simulation/observation과 실제 Unitree G1 motor authority 사이의 하드웨어 안전 경계다.

> **현재 운용 원칙: 양팔만 사용한다. 오른팔 단독 control path는 더 이상 지원하지 않는다.**
> `tools\START_G1_VR_TELEOP.bat`은 양팔 14축 IK/Omni/LowState/camera 관찰만 실행하며 motor output이 없다.

## 현재 상태

- 기본 bimanual simulation/observation: 활성
- read-only LowState: 사용 가능
- dual-arm measured-pose HOLD contract: 코드 존재
- live bilateral Mink -> physical arm tracking: **아직 미완성**
- right-arm-only live tracking contract: **deprecated / 사용 금지**
- Gate 6/7 hardware authorization config: 현재 모두 `false`

따라서 현재 source tree에서 실제 live arm tracking을 시작하면 안 된다. 먼저 right-arm-only live contract를 bilateral 14-joint contract로 교체해야 한다.

## 양팔 joint mapping

Unitree G1 arm indices:

| Indices | Arm | Joints |
| --- | --- | --- |
| `15..21` | left | shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw |
| `22..28` | right | shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw |

`arm_sdk_hold_contract.py`의 현재 source of truth:

```text
LEFT_ARM_INDICES  = 15..21
RIGHT_ARM_INDICES = 22..28
DUAL_ARM_INDICES  = 15..28 (14 joints)
```

## Read-only LowState

`read_only_lowstate.py` 계열은 command publisher 없이 G1 state를 읽는 경로다.

대표 기능:
- 29-joint q/dq observation
- stale/fault detection
- optional measured-state forwarding
- MuJoCo/Unity read-only display

read-only observation은 motor authority가 아니다.

## Dual-arm HOLD

`arm_sdk_hold_contract.py`는 Arm SDK weight가 양팔을 한 단위로 blend한다는 전제에서 **14개 arm joint를 모두 검증**한다.

이 contract는 left/right joint limits와 measured/target dual-arm vector를 함께 검증한다.

현재 관련 hardware config는 다시 잠겨 있다.

```text
config/g1_gate6_hold.json                       hardware_output_authorized=false
config/g1_gate6_interrupt_release_test.json     hardware_output_authorized=false
config/g1_gate7_*_hardware_output.json          hardware_output_authorized=false
config/g1_gate7_*_mink_arm_sdk.json             hardware_output_authorized=false
```

## Live tracking blocker

`arm_sdk_teleop_contract.py`는 현재 이름과 내부 계약이 과거 right-arm 단계에 남아 있다.

확인된 현재 코드:

```text
input schema  = g1.mink.right_arm.state.v1
active sample = right-arm target 7 joints
left arm      = measured/held side
state name    = TRACK_MINK_RIGHT
```

이 동작은 현재 프로젝트 원칙인 **bilateral-only**와 맞지 않는다.

따라서 다음은 현재 실행 경로로 사용하지 않는다.

- right-arm-only Gate 7 live tracking
- `g1_right_arm_jog.py` 기반 단독 arm motion
- 오른팔 7축만 publish하는 bounded interactive trial
- `g1.mink.right_arm.state.v1`을 live command source로 사용하는 물리 tracking

파일은 historical regression/reference 때문에 남아 있을 수 있지만 **사용 가능한 current physical path로 문서화하지 않는다.**

## Bilateral live tracking 완료 조건

물리 live tracking을 다시 허용하려면 최소한 다음을 먼저 만족해야 한다.

1. bimanual source가 left/right 14-joint target을 명시적으로 제공
2. hardware contract가 14-joint active target을 검증
3. left/right 모두 velocity/acceleration/joint-limit validation
4. inter-arm collision과 robot collision validation
5. tracking loss/pinch/fault 시 dual-arm HOLD/return
6. measured LowState와 command target의 bilateral tracking error 확인
7. offline replay/regression 통과
8. 명시적인 hardware authorization 별도 승인

## Gate 7 source에 대한 현재 해석

`gate7_live_arm_sdk.py` 자체에는 `DUAL_ARM_INDICES`와 dual-arm HOLD/return 코드가 존재하지만, active live target source가 아직 right-arm contract에 의존한다.

따라서 **부분적으로 dual-arm인 것과 bilateral live teleoperation이 완성된 것은 다르다.**

## 기본 bimanual runtime과의 관계

현재 기본 개발 경로:

```text
Quest left/right
 -> Unity UDP 5020
 -> g1_bimanual_runtime.py
 -> 14-DoF Mink/MuJoCo
 -> observation only
```

physical path는 이 14축 결과와 동일한 bilateral 의미를 가져야 하며 오른팔만 떼어내서 실행하지 않는다.

## 실제 출력 전 필수 문서

[HARDWARE_BRINGUP_CHECKLIST.md](HARDWARE_BRINGUP_CHECKLIST.md)를 따른다.

현재 checklist에서 right-arm-only legacy 절차는 current authorization으로 인정하지 않는다.

## 파일 분류

현재 유지:
- `arm_sdk_hold_contract.py`: dual-arm HOLD foundation
- `read_only_lowstate.py`: read-only source
- `gate7_live_arm_sdk.py`: future bilateral refactor 기반 일부

deprecated/currently unsupported:
- `arm_sdk_teleop_contract.py`의 right-arm active tracking contract
- `g1_right_arm_jog.py` 및 오른팔-only physical trial
- right-arm-only packet schema를 live motor source로 쓰는 launcher

소스 삭제/리팩터링은 별도 코드 변경 승인 후 진행한다.
