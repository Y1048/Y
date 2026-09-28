# G1 Bilateral Physical Hardware Bring-Up Checklist

현재 프로젝트의 physical arm control은 **항상 양팔 14축**이어야 한다. 오른팔 단독 control은 더 이상 허용하지 않는다.

> 기본 `START_G1_VR_TELEOP.bat`은 observation/simulation이며 **NO MOTOR OUTPUT**이다.
> 현재 live Gate 7 source에는 right-arm-only contract가 남아 있으므로 bilateral refactor 전에는 live tracking을 승인하지 않는다.

## Gate 0 — Platform / network

- [ ] Windows/Python/Unity environment 정상
- [ ] G1 전용 Ethernet/closed network 정상
- [ ] SSH/read-only transport 정상
- [ ] 현재 checkout과 commit 확인

**Command authority: NONE.**

## Gate 1 — Read-only LowState

- [ ] `rt/lowstate` 연속 수신
- [ ] 29-joint q/dq finite
- [ ] stale timeout 검증
- [ ] publisher 없음
- [ ] command output disabled

**Command authority: NONE.**

## Gate 2 — Bilateral arm mapping

양팔 mapping을 함께 검증한다.

```text
left  = indices 15..21
right = indices 22..28
total = 14 arm joints
```

- [ ] left shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw mapping 확인
- [ ] right shoulder pitch/roll/yaw, elbow, wrist roll/pitch/yaw mapping 확인
- [ ] model/hardware coordinate convention 일치
- [ ] 양팔 q/dq continuity 확인

오른팔 22..28만 확인한 과거 Gate는 현재 bilateral Gate 2를 대체하지 않는다.

**Command authority: NONE.**

## Gate 3 — Bilateral measured pose synchronization

- [ ] fresh 29-joint snapshot 확보
- [ ] left/right 14 arm joints 모두 동일 measured q로 초기화
- [ ] Unity preview와 MuJoCo가 동일 bilateral pose 표시
- [ ] engage 시 어느 팔도 target jump 없음

**Command authority: NONE.**

## Gate 4 — Bimanual offline replay

현재 Unity/Mink 경로와 동일한 bilateral input을 offline에서 검증한다.

- [ ] 14-joint output
- [ ] 90/180 deg/s limits
- [ ] 90 deg/s² acceleration
- [ ] inter-arm clearance
- [ ] robot collision clearance
- [ ] near-hands handling
- [ ] staged return
- [ ] tracking loss/pinch/fault dual-arm behavior

현재 bimanual regression baseline: `116/116 PASS`.

**Command authority: NONE.**

## Gate 5 — Physical command contract compatibility

현재 가장 중요한 blocker다.

`arm_sdk_hold_contract.py`는 dual-arm 14-joint HOLD를 지원하지만 `arm_sdk_teleop_contract.py`의 active tracking source는 아직 right-arm-only다.

아래가 모두 완료되기 전에는 통과할 수 없다.

- [ ] live input schema가 bilateral 14-joint로 변경됨
- [ ] active tracking이 left/right 모두 갱신
- [ ] right-arm-only state/reason 제거 또는 historical-only 격리
- [ ] bilateral command error guard
- [ ] bilateral collision guard
- [ ] dual-arm recovery/return regression

**Command authority: NONE until all items pass.**

## Gate 6 — Measured-pose dual-arm HOLD

14-joint HOLD foundation은 `arm_sdk_hold_contract.py`에 존재한다.

하지만 현재 config authorization은 `false`다.

- [ ] current session measured pose와 target 일치
- [ ] all 14 arm joints inside limits
- [ ] non-arm motors disabled by contract
- [ ] command weight/config explicitly reviewed
- [ ] interrupt/release behavior verified

별도 승인 없이 config flag를 켜지 않는다.

## Gate 7 — Bilateral live tracking

현재 **BLOCKED**.

이 Gate는 right-arm-only live contract를 재사용해서 통과 처리하면 안 된다.

필수 조건:

1. current bimanual target source와 physical contract 연결
2. 양팔 14축 command generation
3. measured bilateral feedback comparison
4. bilateral fault/HOLD/return
5. full offline + dry-run replay
6. explicit human approval

## Deprecated procedures

다음 항목은 current physical authorization으로 사용하지 않는다.

- right-arm 7DoF interactive publish
- right-arm-only jog
- `g1.mink.right_arm.state.v1` live tracking
- active sample이 오른팔만 갱신하는 Gate 7 contract

필요하면 historical regression으로만 보존한다.

## Current authorization state

현재 repository의 Gate 6/7 hardware config는 모두 `hardware_output_authorized=false`다.

따라서 현재 문서 기준으로 승인된 live bilateral motor tracking은 없다.

## Stop conditions

다음 중 하나라도 발생하면 command path를 활성화하지 않는다.

- stale/invalid LowState
- NaN/Inf
- joint mapping mismatch
- unilateral-only target source
- collision/clearance failure
- unexpected target jump
- tracking state disagreement
- authorization mismatch

항상 양팔을 하나의 제어 계약으로 취급한다.
