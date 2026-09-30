# G1 Teleop Code Guide

## Portable entry layer

- `runtime/python/python.exe`: bundled CPython Embedded 3.11.9
- `runtime/python/RUNTIME_MANIFEST.json`: runtime identity/core hashes/package pins
- `tools/G1_PORTABLE.py`: 남은 사용자용 BAT와 개발/QA subcommand의 Python dispatcher
- `tools/g1_embedded_runtime.py`: project-relative runtime path/identity helper
- `tools/g1_teleop_dependencies.py`: install 없이 bundled runtime 검증
- `tools/START_G1_VR_TELEOP.bat`: 3-line double-click shim

## Integrated launcher

- `tools/G1_VR_TELEOP_LAUNCH.py`: worker/Unity/camera/GROOT orchestration and one-time actuation confirmation
- `tools/G1_INPUT_OBSERVATION_LAUNCH.py`: observation-only send/receive/Omni/arm worker command; motor flags remain forbidden here
- `tools/G1_GROOT_REMOTE_LAUNCH.py`: onboard heading + balance actuator SSH supervisor
- `tools/g1_quiet_observation.py`: integrated child lifetime; owns only children started by the current invocation
- `tools/g1_process_lifetime.py`: Windows kill-on-close job helper

모든 local Python child process는 현재 `sys.executable`, 즉 bundled `runtime/python/python.exe`를 이어받는다. GROOT supervisor는 G1의 existing `python3`와 compiled actuator를 SSH로 실행한다.

## Bilateral IK

- `g1_bimanual_runtime.py`: runtime wrapper/provenance
- `g1_bimanual_unity_sim.py`: packet validation + cycle state; target math is delegated
- `g1_bimanual_target.py`: canonical `unity_display_world_v1` pose → MuJoCo SE3
- `g1_bimanual_legacy_input.py`: historical relative-frame smoothing/mapping only
- `g1_bimanual_profile.py`: current behavior-shaping constants in one read-only profile
- `g1_bimanual_sim.py`: shared bilateral QP orchestration; safety math is delegated
- `g1_bimanual_motion_policy.py`: soft IK preferences/heuristics
- `g1_bimanual_safety.py`: hard limits, collision/acceleration/braking QP bounds, geometry clearance and checked stopping-tail validation
- `g1_bimanual_return.py`: return-only Ruckig state machine
- `g1_bimanual_limits.py`: primitive motion-limit constants
- `g1_mink_shared.py`
- `g1_arm_common.py`

MuJoCo default engine root는 `runtime/python/Lib/site-packages`다.

### 한 프레임을 따라가는 순서

현재 canonical 경로만 볼 때는 아래 순서만 읽으면 된다.

```text
Quest wrist pose
  -> G1ExistingHandTargetBinder
       tracked wrist + anatomical wrist rotation
  -> G1BimanualSimulationSender
       serialize absolute world pose
  -> g1_bimanual_unity_sim.py
       packet/session/tracking state only
  -> g1_bimanual_target.py
       Unity world -> MuJoCo SE3, exactly one basis conversion
  -> g1_bimanual_motion_policy.py
       wrist task + named soft preferences
  -> mink.build_ik
  -> g1_bimanual_safety.py
       hard limits / collision / braking / checked stop tail
  -> QP solve
  -> q_next
```

Return 요청은 live wrist IK와 분리되어 `g1_bimanual_return.py`로 간다.

### motion policy에서 남겨둔 계산

ablation으로 역할을 확인한 뒤 남긴 항목이다.

- elbow assist: torso-front/low-elbow 구간의 boundary posture helper. 제거 시 recorded active interval에서 checked braking 18회 증가.
- wrist priority: wrist-only rotation을 shoulder/elbow가 대신하지 않도록 joint allocation을 유도.
- shoulder comfort: 평범한 reach에는 개입하지 않고 high reach에서 과도한 shoulder roll/yaw를 억제.
- dynamic orientation priority: constraint 구간에서 rotation을 일부 양보해 position tracking과 braking을 개선.
- shoulder-yaw envelope: normal trajectory에는 영향이 없었지만 +/-150 deg hard model range 안의 +/-90 deg fallback으로 SafetyEnvelope에 유지.

torso target projection은 제거했다. operator target을 pre-IK에서 숨겨서 바꾸지 않고, 불가능한 torso command는 SafetyEnvelope가 명시적으로 제한/감속한다.

상체 수치의 source of truth는 `g1_bimanual_profile.py`다. 새 gain/limit/threshold를 다른 파일에 literal로 추가하지 않는다.

## Camera

- `tools/G1_CAMERA_LAUNCH.py`
- `tools/g1_camera_ssh.py`
- `Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs`

camera worker는 `START_G1_VR_TELEOP.bat` 통합 launcher가 시작·재사용한다.
camera 단독 BAT는 유지하지 않는다.

## Network administration

- `CONFIGURE_G1_ETHERNET.bat` → `G1_PORTABLE.py ethernet-configure`
- `RESTORE_G1_ETHERNET_DHCP.bat` → `G1_PORTABLE.py ethernet-restore`
- `*_ADMIN.ps1`, `G1_ETHERNET_DNS.ps1`, `G1_ETHERNET_TRANSACTION.ps1`: Windows 관리자 transaction helper

## Runtime policy

1. system Python을 호출하지 않는다.
2. `.venv-teleop`을 사용하지 않는다.
3. operator PC에서 pip install/repair를 하지 않는다.
4. BAT 안에 orchestration 로직을 넣지 않는다.
5. relocation test가 통과해야 portable로 인정한다.
6. PC observation/IK worker에 motor publisher를 섞지 않는다. 현재 승인된 motor-output integration은 `G1_GROOT_REMOTE_LAUNCH.py`의 onboard GROOT supervisor 경계에만 두고, 새 supervisor 시작 전 `ACTUATE` 확인을 유지한다.
