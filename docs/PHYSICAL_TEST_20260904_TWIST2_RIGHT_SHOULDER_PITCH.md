# TWIST2 오른쪽 어깨 pitch 물리 시험 기록

시험일: 2026-09-04

## 시험 목적

기존 TWIST2 static-stand 제어 구조에서 왼팔 인덱스만 오른팔 `22..28`로
옮긴 실험본을 사용해 다음 항목을 확인했다.

- 키보드 명령 부호와 실제 오른쪽 어깨 pitch 동작 방향
- `rt/lowcmd` 명령에 대한 `rt/lowstate` 관절 응답
- TWIST2 하체 정책과 상체 직접 목표를 합친 단일 29관절 writer의 주기
- 조작하지 않은 하체·허리·팔 관절의 관측 변동

이 시험은 오른쪽 어깨 pitch 한 축의 부호와 응답을 확인한 시험이다.
오른팔 7축 전체의 충돌 안전성이나 통합 텔레오퍼레이션을 승인한 시험이 아니다.

## 실행 조건

```text
G1 interface       : eth0
motion mode        : form=0, name=ai
policy             : twist2_1017_20k_torchscript.pt
policy SHA-256     : 463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015
policy update      : 50 Hz
rt/lowcmd writer   : 500 Hz
manual target step : 0.02 rad (약 1.146 deg)
```

실행 파일은 G1의 다음 실험 전용 경로에서 빌드했다.

```text
/home/unitree/g1_right_arm_trial/build/g1_twist2_cpp_right_arm_trial
```

시험은 사용자의 명시적 승인 후 한 번 실행했다. 프로그램은 G1에 CSV 로그를
생성했으며, 종료 후 Windows 프로젝트로 복사했다.

## 실제 키 입력과 방향

로그의 `desired_target_22` 변화를 기준으로 복원한 입력은 다음과 같다.

```text
Q 4회 -> Z 8회 -> A 1회 -> Q 1회 -> P 종료
```

| 키 | 관절값 변화 | 실제 관측 방향 |
| --- | --- | --- |
| `Q` | 오른쪽 shoulder pitch `q` 증가 | 팔이 뒤쪽으로 이동 |
| `Z` | 오른쪽 shoulder pitch `q` 감소 | 팔이 앞쪽으로 이동 |
| `A` | 목표를 절대 `0 rad`로 설정 | 시작 자세 기준 증감이 아닌 큰 이동 |

따라서 실제 부호는 소스의 `kForwardShoulderPitchSign = -1.0F`와 일치한다.
로봇의 원시 관절값은 반전하지 않는다. UI에서 전방 이동을 양수 의미로 표시하려면
UI 의미 계층에서만 `forward -> negative q`로 변환해야 한다.

## 측정 결과

원본 CSV:

```text
logs/physical_tests/g1_twist2_right_arm_trial_1787638008.csv
SHA-256: 71B2ACB745FB79D9D88BEF8C700A794E524538CFBE5488DD4A4E9345E002CDEC
rows: 1538
elapsed: 0.020 s .. 30.760 s
```

| 항목 | 결과 |
| --- | ---: |
| 시작 측정 `q22` | 0.290641 rad, 16.653 deg |
| 목표 `q22` 범위 | 0.000000 .. 0.370629 rad |
| 측정 `q22` 범위 | 0.042316 .. 0.337260 rad |
| 마지막 측정 `q22` | 0.049495 rad, 2.836 deg |
| 마지막 목표 `q22` | 0.020000 rad, 1.146 deg |
| 평균 절대 추종 오차 | 0.020528 rad, 1.176 deg |
| 95% 절대 추종 오차 | 0.038599 rad, 2.211 deg |
| 최대 절대 추종 오차 | 0.049333 rad, 2.827 deg |
| 최대 측정 `dq22` | 0.131922 rad/s, 7.559 deg/s |
| LowCmd 평균 주기 | 500.003 Hz |
| LowCmd interval p99 / max | 2.163 / 3.275 ms |
| 정책 추론 mean / p99 / max | 2.603 / 2.811 / 3.724 ms |
| 최대 예측 토크 | 14.815 Nm |
| torque limiter 동작 비율 | 0.000 |
| IMU 최대 roll / pitch | 1.036 / 3.222 deg |
| LowState age 최대 | 2.368 ms |

조작하지 않은 관절의 로그상 최대 범위:

| 영역 | 최대 관측 범위 |
| --- | ---: |
| 하체 `0..11` | 0.009852 rad, 0.564 deg (joint 6) |
| 허리·왼팔 `12..21` | 0.004897 rad, 0.281 deg (joint 14) |
| 나머지 오른팔 `23..28` | 0.008041 rad, 0.461 deg (joint 23) |

프로그램은 keyboard stop으로 종료됐고 3초 damping tail을 보냈다. 출력의
`completed`는 AI standing 복귀를 뜻하지 않는다. 실제 시험 후에는 승인된 조종기
절차로 Regular 상태를 복구해야 한다.

## 판정

확인됨:

- 오른쪽 shoulder pitch의 Q/Z 명령 부호와 실제 움직임 방향이 일치한다.
- 측정 관절값이 목표 변화 방향을 추종했다.
- 시험 중 500 Hz LowCmd 주기와 50 Hz 정책 추론이 유지됐다.
- 로그에서 torque limiter 개입과 큰 roll/pitch 이상은 관측되지 않았다.

확인되지 않음:

- 오른팔 나머지 6축의 실제 부호와 응답
- 다축 조합의 self/body/environment collision 안전성
- acceleration/jerk 제한과 Cartesian workspace
- writer 예외 시 확정적인 damping 전환
- 종료 후 안정적인 제어권 handback
- LowState와 freshness timestamp의 단일 snapshot 결합

위 미확인 항목은 각각 기존 finding `R43`, `R44`, `R45`, `R49` 범위에 남아 있다.

## 시험 해석 제한

이 실행에는 `A` 절대 0 rad 입력과 여러 번의 Q/Z 입력이 포함됐다. 따라서
이번 결과는 엄격한 시작 자세 기준 `+1 step / -1 step` 시험이 아니다. 부호와 실제
응답은 확인했지만, 반복성·대칭성·작은 명령 추종 오차를 비교하려면 다음 시험에서
`A`, 속도 배율 키와 다른 관절 키를 잠그고 Q/Z 각각 한 번만 사용해야 한다.

## PC 모델 부호 재생 준비

다음 로컬 실행 파일을 추가했다.

```text
experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat
```

이 실행 파일은 위 CSV의 실측 `q_0..q_28`을 canonical G1 motor order 그대로
MuJoCo에 재생한다. Unitree SDK, DDS, 네트워크 소켓 및 로봇 명령을 사용하지 않는다.
CSV 1,538행의 형식·유한값·시간 순서와 MuJoCo 29관절 주소 적용은 자동 검사에서
통과했다. 2026-09-04 재생 화면을 실제 G1 동작과 비교해 Q=뒤쪽, Z=앞쪽 방향이
동일한 것을 확인했다. 이는 오른쪽 shoulder pitch 한 축의 실측 부호 일치만
확인한 결과이며, 나머지 6축과 다축 조합의 물리 응답을 의미하지 않는다.
