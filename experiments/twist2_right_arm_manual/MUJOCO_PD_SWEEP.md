# MuJoCo 왕복 PD 비교 — 실기와 분리된 시험기

`tools/RUN_MUJOCO_PD_SWEEP.bat` 또는 `mujoco_pd_sweep.py`를 사용한다.
기존 `START_TWIST2_MINK_CYCLE_CANDIDATE.ps1`, VR/Mink/UDP 경로, 실기 게인과
로봇 바이너리는 변경하지 않는다. SDK, DDS, 릴레이, SSH, 실제 G1 연결이 필요 없다.
시뮬레이션 결과를 실기 설정에 자동 적용하는 기능은 없다.

## 구성과 범위

체크인된 `g1_29dof.xml`을 메모리에서 읽고 pelvis의 free joint를 제거해 골반을 고정한다.
고정하면 달라지는 부모–자식 충돌 필터는 원본의 의미를 유지하도록 보완한다.
질량·관성·마찰·armature·메시와 geometry collision mask는 유지하며 원본 XML과 메시를
수정하거나 생성 모델로 덮어쓰지 않는다. 전신 29개 hinge는 토크로 움직인다.
초기 상태 설정 뒤에는 `qpos`를 직접 지정하지 않고 `mujoco.mj_step`으로 진행한다.

**골반이 고정된 팔 PD 비교용 fixture이며, 서 있는 G1의 균형 시험이 아니다.**
TWIST2 하체 policy와 실제 Regular 서비스는 이 시험에 포함하지 않는다.
다리·허리·왼팔은 고정된 reference를 PD로 추종한다. 모델 파라미터는 실기에서
식별하지 않았고, 구동기는 이상적인 PD 토크 모델이다. 지연·백래시·발열은 재현하지 않는다.

왕복은 기존 C++ `PdSmallSignalTrial`의 Python 포트이며, 테스트에서 실제 C++
header를 컴파일한 출력과 대조한다. 관절 22번만 `ready -> +8도 -> -8도 -> ready`로
움직이고 후보마다 3회 반복한다. 속도 20도/s, 가속도 60도/s²의 quintic 궤적이다.
Kp/Kd는 기존 sweep과 같이 **22~25번에 함께** 적용한다. 다른 관절 게인은 그대로다.
기본값은 Kp=40,48,56 / Kd=5이며 CLI에서 Kd 비교도 명시적으로 추가할 수 있다.

후보마다 `MjData`와 명령 이력을 새로 생성하고 같은 ready 위치·0 속도로 시작한다.
3초 warmup 후 마지막 1초의 양팔 위치 오차 0.1 rad 및 속도 0.1 rad/s 이내를 확인한다.
초기화·gain 변경의 과도응답은 CSV에 남기지만 왕복 RMSE에는 넣지 않는다.

## Windows 설치 — 기존 VR 환경과 분리

저장소 루트에서 한 번만 별도 환경을 만든다. 런처가 패키지를 자동 설치하지 않는다.

```powershell
py -3.11 -m venv .venv-mujoco-pd
.\.venv-mujoco-pd\Scripts\python.exe -m pip install -r .\experiments\twist2_right_arm_manual\mujoco_pd_requirements.txt
```

기본 세 후보를 화면 없이 계산한다.

```powershell
.\tools\RUN_MUJOCO_PD_SWEEP.bat
```

MuJoCo 화면에서 한 후보의 왕복 동작을 본다.

```powershell
.\tools\RUN_MUJOCO_PD_SWEEP.bat --viewer --kp-values 40 --kd-values 5
```

Kp와 Kd의 9개 조합을 같은 조건으로 비교한다.

```powershell
.\tools\RUN_MUJOCO_PD_SWEEP.bat --kp-values 40 48 56 --kd-values 3 5 7
```

Linux에서는 같은 requirements를 별도 venv에 설치하고 다음처럼 실행한다.

```bash
python experiments/twist2_right_arm_manual/mujoco_pd_sweep.py --kp-values 40 48 56 --kd-values 3 5 7
```

기본 결과 경로는 `logs/test_results/mujoco_pd/<UTC 시각>/`이다.
`--output <새 폴더>`도 가능하지만, 기존 폴더를 지정하면 덮어쓰지 않고 거부한다.
GUI 창을 닫으면 그 후보와 sweep을 중단한 상태로 기록한다.
GUI는 로컬 display/OpenGL이 필요하다. headless 계산에는 viewer를 생성하지 않는다.

## 제어식과 시간 해상도

`tau = Kp * (q_cmd - q) - Kd * dq`를 사용한다. `dq_cmd=0`, `tau_ff=0`이다.
기존 PD 구간에 없는 궤적 속도 feedforward나 중력 보상을 추가하지 않는다.
초기 capture/leg blend는 고정 fixture의 별도 warmup으로 대체했으므로 실기 startup 전체의 재현은 아니다.

reference는 50 Hz, writer target은 500 Hz, 물리 적분/이상적인 내부 PD는 기본 1000 Hz다.
`--timestep 0.0005`로 시간 해상도를 바꾸어도 reference/writer 주기는 유지한다.
실제 모터 내부 주파수를 측정한 설정이 아니다. 실기와의 수치 bit 일치도 주장하지 않는다.

writer의 기존 순서인 slew clamp -> joint soft limit -> torque 기반 target clamp ->
joint soft limit을 재현한다. 원본처럼 torque clamp가 앞선 slew 제한을 넘어서는 경우도
별도로 기록한다. 이상적인 모터 출력에는 XML의 hard actuator limit을 적용한다.
여기서 이를 고친다며 원본 로봇 writer의 의미를 바꾸지 않는다.

## 고정 골반 모델의 충돌 필터

MuJoCo는 동적 부모와 바로 연결된 자식 사이의 상시 관절 접촉을 기본적으로 제외한다.
그런데 부모가 world에 고정되면 이 필터가 적용되지 않아, free joint만 제거했던 초기
시험기에는 골반–고관절 조립부의 인공적인 접촉이 생겼다. 접촉 probe로 부위와 힘을
확인한 뒤 `mujoco_pd_fixture.py`에서 원본이 이미 제외하던 세 직접 연결부만 복원했다.

복원 대상은 pelvis와 left_hip_pitch_link, right_hip_pitch_link, waist_yaw_link이다.
팔–몸통 등 비인접 충돌과 obstacle 접촉은 그대로 검사한다. 전체 self-collision을
끄거나 결과의 contact 플래그를 숨기지 않는다. 생성한 세 pair는 `run.json`에도 기록한다.
원본 구조가 달라지거나 parent filter를 명시적으로 끈 모델은 재검토하도록 거부한다.

관련 근거와 실패 결과는 `docs/G1_MUJOCO_PD_VALIDATION_20260911.md`에 남겼다.

## 결과 해석

- `run.json`: 모델/메시/코드 SHA-256, 버전, 주기, 초기값, gain grid, 가정. 실행 시작
  시 저장하는 immutable manifest다. `status=running`은 시작 checkpoint이고 최종 상태는 summary를 본다.
- `candidate_NNN.csv`: 500 Hz의 원래 목표 `ref_j`, 제한 후 명령 `cmd_j`, 응답 `q_j/dq_j`,
  요구 토크 및 실제 시뮬레이터 토크, phase/cycle, 제한·접촉 여부. q/dq는 해당 제어
  계산 직전 상태이며 actual_tau는 그 `mj_step`의 구동기 출력이다. 실기 ACK가 아니다.
- `summary.json`: 후보별 완료/제외 사유, 원래 reference RMSE, command RMSE, 최대 오차,
  끝점 overshoot·정착시간, 속도·토크, 제한 비율, 시뮬레이션 후보 순위.

순위는 제한 후 명령이 아니라 **원래 reference에 대한 22번 RMSE**로 계산한다.
중도 실패, 수치 경고, 접촉 영향, 과도한 토크 제한(기본 arm sample 5% 초과)은
순위에서 제외한다. 이 5%는 비교 정책이지 실기 안전 인증 기준이 아니다.
정착시간은 각 0.5초 hold의 기록된 나머지 구간에서 오차 0.02 rad와 속도 0.1 rad/s
이내로 유지되는 최초 시점이다. 유지되지 않으면 null이다. 짧은 hold 밖의 정착은 판단하지 않는다.
RMSE만으로 전체 성능이나 전역 최적성을 결론 내리지 말고 진동·토크·제외 사유도 본다.

`recommended_hardware_gains=null`, `hardware_config_modified=false`가 유지된다.
exit 0은 sweep이 끝나고 순위에 넣을 후보가 있다는 뜻이다. exit 2는 입력/환경 오류,
중단 또는 적격 후보 없음이다. 실패 후보 결과도 확인해야 한다. 중간 프로세스 종료로
summary가 없으면 run.json만 보고 완료로 판정하지 않는다.

## 검증

```bash
cd experiments/twist2_right_arm_manual
G1_REQUIRE_MUJOCO=1 python -B test_mujoco_pd_sweep.py -v
G1_REQUIRE_MUJOCO=1 python -B test_mujoco_pd_fixture.py -v
```

C++ 원본 궤적 대조에는 g++ 또는 `CXX`에 지정한 C++17 컴파일러가 필요하다.
시험기 실행 자체에는 컴파일러가 필요 없다.
GitHub workflow `MuJoCo round-trip PD offline`은 전체 dynamics 테스트와 3x3 sweep을
실행하고 CSV/JSON을 artifact로 보존한다. sweep 실행 중 Python socket 생성/연결
감사 이벤트를 거부한다. 원본 VR/PD 파일의 blob 해시 보존도 검사한다.
정확한 실행 결과와 남은 미검증 항목은 `docs/G1_REGULAR_HANDOFF_20260910.md`에 누적한다.


## 2026-09-11: 29개 관절의 내부 여유 구간

기본 시험기는 이제 `joint_limit_guard.py`를 항상 사용한다. 모델의 joint range와
limit 활성화 margin, C++에서 읽은 기존 soft limit의 교집합을 사용한다. 여기서
양쪽으로 **추가 0.05 rad**를 남긴 구간만 허용한다. XML이나 실기 제한값을 넓히지 않는다.
`hard`로 기록된 값은 XML range이지 실측한 G1 기계적 스토퍼 위치가 아니다.

왕복 경로의 해석적 최소/최대값을 시작 전에 검사하고, writer 제한을 거친 실제 명령도
검사한다. 명령 감속기가 목표를 바꿔야 할 정도로 접근하면 그 PD 시험은 즉시 제외한다.
변형한 목표로 작은 RMSE를 얻었다고 주장하지 않는다. 매 물리 계산 전후에 29개 관절의
q/dq를 확인하며, 준비 구간과 마지막 적분 상태도 검사한다. 측정 qpos를 clamp하지 않는다.
MuJoCo의 joint-limit constraint가 활성화된 경우도 제외한다.

정지거리 검사는 20 ms 반응 지연, 2 rad/s²의 지연 중 바깥 방향 가속도,
1 rad/s²의 제동 가능 감속도를 가정한다. 이 값들은 **보수적으로 선택한 오프라인 가정**이며
실측 감속도나 지연 보증이 아니다. 여유 부족은 해당 시뮬레이션을 종료하고 원인을 기록한다.
시뮬레이션 종료를 실물의 제동이나 안전한 hold로 해석하면 안 된다. 실기 VR/LowCmd에는
이 보호기를 배포하지 않았으며 기존 경로는 수정하지 않는다.

`joint_limit_guard` 결과에는 관절별 최소 soft/hard 여유, 최소 정지거리 여유,
최소 soft 여유가 나온 시각/q/dq, 최초 거부 사건이 들어 있다. 한 번 거부된 monitor는
계속 거부하며, 다음 별도 후보 시험에서만 새로 생성한다.

이전 718개 조건을 새 기준으로 다시 실행하는 명령은 다음과 같다. 기존 결과를 덮어쓰지 않는다.

```powershell
.\.venv-mujoco-pd\Scripts\python.exe -B experiments/twist2_right_arm_manual/mujoco_pd_limit_replay.py --workers 6 --output logs/test_results/mujoco_pd/limit_replay_new
```

정확한 결과와 한계는 `docs/G1_JOINT_LIMIT_GUARD_20260911.md` 및 기존 handoff에 기록한다.
