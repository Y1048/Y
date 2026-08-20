# MuJoCo G1 Controller

이 폴더에는 G1 29DoF 모델과 오른팔 UDP IK 제어 코드가 있다.

## 현재 실행 경로

전체 Quest 3S 테스트는 이 폴더의 개별 파일이 아니라 프로젝트 루트에서 실행한다.

```text
..\START_VR_HAND_TO_MUJOCO.bat
```

Quest 없이 UDP 입력만 시험하려면 다음 파일을 실행한다.

```text
..\tools\TEST_FAKE_VR_TO_MUJOCO.bat
```

`launchers/active/START_MUJOCO_AND_UNITY.bat`은 예전 경로와의 호환을 위해 남겨 둔 래퍼다.

## 폴더

| 경로 | 용도 |
| --- | --- |
| `scripts/g1_right_arm_udp_ik_demo.py` | 현재 사용하는 G1 오른팔 UDP position/orientation IK |
| `scripts/udp_fake_vr_sender.py` | Quest 없이 UDP 입력을 만드는 테스트 송신기 |
| `scripts/g1_*`, `scripts/two_link_*` | 현재 방식에 도달하기 전 모델/IK 학습 및 동작 실험 코드 |
| `data` | 가짜 hand tracking CSV 등 입력 데이터 |
| `docs` | 연구실 코딩 규칙 |
| `external/unitree_mujoco` | Unitree 공식 MuJoCo 참고 저장소와 G1 모델 |
| `unity` | 초기 Unity-UDP 연동 실험 자료. 현재 Unity 구현은 프로젝트 루트의 `Unity_G1_Quest3S`에 있음 |

## 현재 흐름

```text
Quest wrist pose
-> Unity calibration and UDP JSON
-> scripts/g1_right_arm_udp_ik_demo.py
-> G1 right-arm IK in MuJoCo
```

## 오른팔 IK 기준

- `right_wrist_roll_link` 위치는 어깨 3축과 팔꿈치 1축으로 계산한다.
- `right_wrist_yaw_link` 자세는 손목 3축으로만 계산한다. 따라서 손목만 돌릴 때 팔꿈치가 따라 움직이지 않는다.
- 팔꿈치와 손목에는 몸통 바깥쪽 안전영역을 적용한다.
- 각 관절 업데이트 뒤 오른팔-몸통 접촉을 검사한다. 접촉이 예상되면 스텝을 줄여 재시도하고, 안전한 스텝이 없으면 이전 자세를 유지한다.
- 위치와 회전 입력에는 저지연 필터를 적용하며, 추적이 끊기면 마지막 안전 자세를 유지한다.
