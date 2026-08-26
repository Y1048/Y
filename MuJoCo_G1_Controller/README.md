# MuJoCo / Mink G1 Right-Arm Controller

이 폴더는 Unitree G1 MuJoCo 모델과 Mink 기반 오른팔 differential QP IK를 담당한다.

현재 최신 실험 정책은:

```text
scripts/run_mink_g1_right_arm_virtual_center_live.py
```

이며 실행은 프로젝트 루트에서:

```powershell
.\START_VR_HAND_TO_MUJOCO.bat --smooth
```

으로 한다.

## 1. 먼저 볼 파일 3개

| 파일 | 역할 |
| --- | --- |
| `scripts/run_mink_g1_right_arm_virtual_center_live.py` | 현재 IK 정책: virtual center, role split, wrist-limit assist |
| `scripts/run_mink_g1_right_arm_prototype.py` | 공통 Mink QP, UDP, collision, state packet 기반 |
| `scripts/g1_right_arm_common.py` | G1 joint/frame/model/좌표계 공통 정의 |

Legacy custom DLS/Jacobian controller인 `g1_right_arm_udp_ik_demo.py`는 참고용으로 남아 있지만 현재 Mink controller는 이 파일을 import하지 않는다.

---

## 2. 현재 IK 구조

정확한 표현은 **Virtual-Wrist-Center Role-Separated Differential QP IK**다.

```text
Quest hand pose
     ↓ clutch-relative mapping
Translation target ──→ right_wrist_roll_link
Orientation target ─→ right_wrist_yaw_link
     ↓
Mink tasks + limits + constraints
     ↓
QP
     ↓ DAQP
Δq
     ↓ / dt
joint velocity v
     ↓ integrate
next configuration q
```

### Translation task

```python
position_task = mink.FrameTask(
    frame_name="right_wrist_roll_link",
    frame_type="body",
    position_cost=base.POSITION_COST,
    orientation_cost=0.0,
    gain=base.FRAME_GAIN,
    lm_damping=base.LM_DAMPING,
)
```

`right_wrist_roll_link`를 virtual wrist center로 사용한다. 이 frame은 wrist pitch/yaw보다 upstream에 있으므로 손목 회전에 따른 위치 coupling을 줄인다.

### Orientation task

`VirtualCenterOrientationTask` 내부에서:

```python
self.inner = mink.FrameTask(
    frame_name="right_wrist_yaw_link",
    frame_type="body",
    position_cost=0.0,
    orientation_cost=1.0,
    ...
)
```

를 사용한다. 따라서 손의 최종 orientation 기준은 `right_wrist_yaw_link`다.

---

## 3. G1 오른팔 7DoF

`g1_right_arm_common.py`의 순서가 controller 전체에서 기준이다.

```python
RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]
```

```text
Proximal group = joints[:4]
  shoulder pitch / roll / yaw + elbow

Wrist group = joints[4:]
  wrist roll / pitch / yaw
```

Hardware motor indices는 `22..28`이다.

---

## 4. Role separation은 어떻게 구현되는가

핵심은 `VirtualCenterOrientationTask.compute_jacobian()`이다.

```python
def compute_jacobian(self, configuration):
    jacobian = self.inner.compute_jacobian(configuration).copy()
    jacobian[3:6, self.proximal_dofs] *= self._assist_gain(configuration)
    return jacobian
```

Mink FrameTask의 6D Jacobian row는 개념적으로:

```text
row 0..2 = translation X/Y/Z
row 3..5 = rotation Rx/Ry/Rz
```

이다.

평상시 `_assist_gain()`은 `0.0`이므로:

```text
orientation Jacobian × shoulder/elbow columns = 0
```

이 된다. 따라서 평상시 orientation error는 wrist roll/pitch/yaw가 담당한다.

### Wrist-limit assist

손목이 관절 한계에 몰렸을 때 orientation을 완전히 잃지 않도록 proximal assist를 제한적으로 허용한다.

```python
ASSIST_ENTER_MARGIN_DEG = 10.0
ASSIST_RELEASE_MARGIN_DEG = 18.0
ASSIST_FULL_MARGIN_DEG = 3.0
ASSIST_LATCH_FLOOR = 0.03
ASSIST_MAX = 0.14
```

동작:

```text
wrist limit margin > 10°
→ proximal orientation assist = 0%

margin <= 10°
→ assist latch ON

limit에 매우 가까움
→ 최대 14%

margin >= 18° 회복
→ latch OFF
```

10°/18° 두 threshold를 둔 이유는 경계에서 assist가 반복적으로 켜졌다 꺼지는 chatter를 막기 위한 hysteresis다.

**손 속도를 기준으로 mode를 바꾸지 않는다.** 느린 millimetric translation도 항상 정상 position task로 처리한다.

---

## 5. Clutch-relative target mapping

Engage 순간 Quest와 G1의 pose를 기준으로 저장한다.

### Position

```python
target_center_position = (
    clutch_reference["center_position"]
    + raw_target
    - clutch_reference["input_position"]
)
```

수식:

```text
p_target = p_G1_engage + (p_hand_current - p_hand_engage)
```

Quest의 절대 세계좌표를 G1에 직접 넣는 것이 아니라 engage 이후의 상대 이동량을 사용한다.

### Orientation

```python
rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
target_rotation = rotation_delta @ clutch_reference["yaw_rotation"]
```

수식:

```text
R_delta  = R_hand_current · R_hand_engage^T
R_target = R_delta · R_G1_engage
```

현재 orientation mapping은 `clutch_relative`다. Quest semantic frame을 G1 yaw frame에 절대적으로 직접 대입하지 않는다.

---

## 6. Mink `solve_ik()`에서 실제로 하는 일

우리 코드는 Mink 라이브러리의 `mink.solve_ik()`를 호출한다.

```python
velocity = mink.solve_ik(
    configuration=configuration,
    tasks=[
        position_task,
        orientation_task,
        posture_task,
        damping_task,
    ],
    dt=base.DT,
    solver=solver,
    damping=base.QP_DAMPING,
    limits=limits,
    constraints=constraints,
)
```

Mink 내부의 QP는:

```text
minimize   1/2 Δqᵀ H Δq + cᵀ Δq
subject to G Δq ≤ h
           A Δq = b
```

형태다.

### Objective: `H, c`

각 task의 weighted Jacobian/error를 합쳐:

```python
W = np.vstack(weighted_jacobians)
H = W.T @ W
c = -(np.concatenate(weighted_errors) @ W)
```

로 만든다.

우리 controller에서 objective 쪽에 들어가는 것은:

```text
position_task
orientation_task
posture_task
damping_task
```

이다.

### Inequality: `G Δq <= h`

`limits`에서 생성한다.

```text
ConfigurationLimit
VelocityLimit
CollisionAvoidanceLimit
```

이 여기에 들어간다.

### Equality: `A Δq = b`

현재 non-right-arm DOF freeze가 exact equality constraint로 들어간다.

```python
constraints = [
    mink.DofFreezingTask(
        model=model,
        dof_indices=frozen_dofs,
    )
]
```

즉 오른팔 7DoF 외에는 `Δq = 0`이다.

### DAQP 역할

Mink가 `H,c,G,h,A,b`를 구성하고 `qpsolvers`를 통해 QP backend에 넘긴다. 현재 우선 backend는 DAQP다.

```text
Mink = IK/QP formulation
qpsolvers = common interface
DAQP = numerical QP solver
```

Mink가 얻은 `Δq`는:

```python
v = delta_q / dt
```

로 velocity가 되어 반환되고 live controller가:

```python
configuration.integrate_inplace(velocity, base.DT)
```

로 다음 configuration을 만든다.

---

## 7. QP Task와 주요 파라미터

기본값은 `run_mink_g1_right_arm_prototype.py`에 있다.

```python
CONTROL_HZ = 60.0
POSITION_COST = 8.0
ORIENTATION_COST = 2.0
POSTURE_COST = 0.04
FRAME_GAIN = 0.35
LM_DAMPING = 1e-5
QP_DAMPING = 1e-8
```

Virtual-center live controller는 추가로:

```python
MAX_JOINT_VELOCITY_DEG_S = 45.0
base.PROXIMAL_DAMPING_COST = 0.03
base.WRIST_DAMPING_COST = 0.015
```

를 사용한다.

| 값 | 의미 | 크게 하면 |
| --- | --- | --- |
| `POSITION_COST` | 위치 error weight | 위치를 더 강하게 추종 |
| `ORIENTATION_COST` | 회전 error weight | 회전을 더 강하게 추종 |
| `POSTURE_COST` | engage posture 선호 | 원래 팔 자세를 더 유지 |
| `FRAME_GAIN` | task feedback gain | 수렴 반응 증가 |
| `PROXIMAL_DAMPING_COST` | shoulder/elbow motion penalty | proximal 움직임 억제 |
| `WRIST_DAMPING_COST` | wrist motion penalty | wrist 움직임 억제 |
| `MAX_JOINT_VELOCITY_DEG_S` | 관절속도 제한 | 최대 추종속도 증가 |

Cost는 strict priority가 아니다. QP objective에서 weighted compromise를 만든다. 반면 joint limit/collision/freeze와 같은 constraint는 별도의 제한조건이다.

---

## 8. Joint limits

MuJoCo model의 joint range를 `mink.ConfigurationLimit`이 사용한다.

프로젝트에서 elbow는 별도의 operational policy를 추가한다.

```python
RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES = {
    "right_elbow_joint": (5.0, 120.0),
}
```

Virtual-center live에서는 오른팔 7축 최대속도를 `45 deg/s`로 제한한다.

---

## 9. Collision avoidance

공통 prototype에서 collision pair를 만들고 Mink에 넘긴다.

```python
mink.CollisionAvoidanceLimit(
    model=model,
    geom_pairs=collision_pairs,
    minimum_distance_from_collisions=0.012,
    collision_detection_distance=0.040,
    gain=0.85,
    broadphase=True,
)
```

현재 의미:

```text
detection distance = 40 mm
minimum clearance  = 12 mm
```

MuJoCo collision-enabled geom의 거리와 distance Jacobian을 사용해 QP inequality를 만든다.

### Collision pair 구성

오른팔 body와 다른 robot collision geom 사이 pair를 구성한다. body tree상 구조적으로 매우 가까운 link는 제외한다.

```python
STRUCTURAL_NEIGHBOR_DISTANCE = 2
```

### Hand collision geom

`_prepare_mink_xml()`에서 실제 hand mesh 기반 collision geom을 추가한다.

```text
name = mink_right_rubber_hand_collision
mesh = right_rubber_hand
pos  = 0.0415 -0.003 0
```

### 확인된 실제 충돌

Virtual-center에서 collision을 끄고 pure yaw를 추적한 결과, hand와 right hip의 최소거리는:

```text
yaw 40° : +24.95 mm
yaw 50° :  +0.40 mm
yaw 60° : -20.21 mm
yaw 70° : -31.42 mm
```

였다. 따라서 큰 positive yaw에서 collision avoidance가 shoulder/elbow를 움직이는 것은 실제 hand-hip penetration을 피하기 위한 정상 동작이다.

---

## 10. 왜 Virtual Wrist Center를 사용했는가

기존 yaw-link 6D pose task에서는 wrist pitch 회전만 줘도 shoulder/elbow가 움직였다.

Collision ON/OFF 진단:

```text
pitch +30° : OFF 3.52°  / ON 3.52°
pitch -30° : OFF 34.20° / ON 34.20°
pitch +60° : OFF 12.03° / ON 12.03°
```

collision과 무관했기 때문에 `right_wrist_yaw_link` 위치를 고정하려는 kinematic coupling이 원인이었다.

Virtual-center로 바꾼 뒤:

```text
pitch +30° : proximal 0.00°
pitch -30° : proximal 0.00°
pitch +60° : proximal 0.00°
```

를 오프라인에서 확인했다.

---

## 11. Unity 외부 frame 계약

내부 translation frame은 `right_wrist_roll_link`지만 Unity에 보내는 wrist state는 계속 `right_wrist_yaw_link`다.

```python
center_error = target_center_position - roll_pose.translation()
external_target_position = yaw_pose.translation() + center_error
```

순수 wrist rotation에서 center error가 0이면 Unity-visible target도 실제 yaw wrist와 같은 위치를 유지한다. 이전 split-frame 실험에서 발생했던 Unity/MuJoCo position baseline 불일치를 막기 위한 구조다.

---

## 12. Offline 테스트

VR 없이 IK를 검증할 수 있다.

```powershell
.\tools\TEST_MINK_ROLE_SPLIT_REGRESSION.bat
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_COMPARE.bat
.\tools\TEST_MINK_VIRTUAL_WRIST_CENTER_SWEEP.bat
.\tools\TEST_MINK_BASELINE_COLLISIONS.bat
.\tools\TEST_MINK_COLLISION_INFLUENCE.bat
.\tools\TEST_MINK_VIRTUAL_CENTER_COLLISION_INFLUENCE.bat
.\tools\TEST_MINK_VIRTUAL_CENTER_YAW_COLLISION_GEOMETRY.bat
```

A/B 소규모 비교에서는 virtual-center가 평균 proximal wrist-rotation motion을 약 67% 줄였다. 광범위 sweep에서도 평균 proximal motion은 current formulation보다 virtual-center가 낮았다. 단, sweep의 `tracking/collision` 집계 일부는 trajectory collision flag와 tracking pass가 결합된 진단용 지표였으므로 단독 안전성 지표로 사용하지 않는다.

---

## 13. 코드를 수정할 때 먼저 찾을 부분

`run_mink_g1_right_arm_virtual_center_live.py`에서 IDE 검색으로 다음을 순서대로 찾으면 전체 흐름을 빠르게 읽을 수 있다.

```text
class VirtualCenterOrientationTask
compute_jacobian
position_task =
orientation_task =
target_center_position =
rotation_delta =
mink.solve_ik(
CollisionAvoidanceLimit
external_target_position
```

전체 실행 흐름은:

```text
UDP hand pose
→ clutch-relative target
→ position/orientation task target 설정
→ mink.solve_ik()
→ DAQP solves Δq
→ velocity = Δq/dt
→ configuration.integrate_inplace()
→ MuJoCo forward
→ UDP 5006 Unity state
→ UDP 5008 safety dry-run
```

이다.
