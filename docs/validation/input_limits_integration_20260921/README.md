# 3/3 양팔 + Omni 입력 전달 검증

2026-09-21. 담당 범위는 입력값 생성·전달이다. PD/실제 제어기/모터 출력은 변경하지 않았다.

## 실행한 검사

- `py -3.11 -B -m unittest backend.tests.test_g1_observation_tap hardware.g1_arm_bridge.test_g1_omni_body_mapping hardware.g1_arm_bridge.test_g1_omni_clocked_observation`: **40/40 PASS**, 1.308초.
- `test_g1_observation_pipeline.py`: **2/2 PASS**, 12.304초. 생성 Unity 입력과 가짜 Omni WebSocket을 실제 계산 프로그램에 전달하고 localhost 수신기까지 통과시켰다.
- 양팔 run/return 메타데이터의 14축 제한이 모두 3 rad/s, 3 rad/s²인지 확인했다. 연속 solver tick의 유한차분도 검사했다.
- 수신 양팔 419개 표본의 14개 관절값·순서가 IK 원본과 정확히 같았다. Omni 415개 표본은 원본 CSV 값과 정확히 같았고, 113개 표본의 world→body 변환은 별도 수식으로 확인했다.
- 생성 fixture 수신 약59.9857Hz, IK 약59.9972Hz, 표시100Hz. ACK와 표시 반복/원본 순번 보존 및 입력별 stale 구분 통과.
- 이 fixture의 최대 관절속도0.279876rad/s·가속도0.591394rad/s². 3/3 경계 도달 시험이나 하드웨어 검증이라고 해석하지 않는다.
- 실행 전 관련 production 파일14개가 source/runtime SHA256 일치. 실제 runtime validation-only도 3/3을 출력했다.

증거: `precheck.json`, `mapping_tap_tests.txt`, `pipeline_tests.txt`.
기존 전체 양팔 회귀를 이번에 다시 실행한 것은 아니다.

## 실제 입력 기록 준비

사용자는 현재 Quest·Omni만 사용할 수 있다고 답했다. 따라서 G1 SSH/카메라 없이
Windows localhost에서 동일 수신 프로그램과 send/omni/arm 생산자를 열었다.
**수신 목적지127.0.0.1:55070이며 G1 수신 성공을 주장하지 않는다.**

- 시작: `20260921_152630_958214`, 프로세스와 명령은 `local_live_launch.json`.
- runtime 수신: `logs/test_results/input_local_live/20260921_152630_958214/received_observation.jsonl`
- 양팔: `logs/test_results/bimanual/unity_20260921_152631_628857.jsonl`
- Omni: `logs/test_results/omni_gateway_readonly/omni_observation_20260921_152631_589019.csv`
- 시작 확인: 양팔·Omni 모두 `FRESH_LIVE`, Omni calibrated=true. 양팔은 ready, Unity 입력은 WAIT였다. 양팔 run 메타데이터14축 모두3/3 확인.
- 사용자의 동시 보행·양팔 움직임·pinch 복귀·재engage 확인을 기다린다. **실착 결과는 아직 미판정**이다.

이번 네 관찰 창은 Ctrl+C/창 닫기로 종료할 수 있다. 나중에 G1을 대상으로 통합 BAT를
실행할 때는 이번 localhost 관찰 창부터 닫아야 한다. 서로 다른 목적지의 send 프로세스를
중복 실행하지 않는다. 무관한 프로세스는 종료하지 않는다. 로그 자동 삭제·압축 없음.

`recommended_hardware_gains = null`. 새 PD 탐색·실제 gain 변경·G1 전송은 하지 않았다.
fetch 후 HEAD/origin은31a5df6으로 같고, 기존 dirty 변경을 보존했다. 이번 commit/push 없음.

### 실입력 확인 결과 (2026-09-21 15:31 스냅샷)

사용자는 시험을 완료했다고 알렸다. 실제 Quest/Unity 입력과 MuJoCo 목표값을
로컬 수신 로그에서 대조했다. 양팔 tracking3회, 재engage2회, pinch복귀3/3완료,
최종READY, BLOCKED/solver/return fault0. 최대목표속도1.364523rad/s,
최대목표가속도3.000000000000469rad/s²(수치오차), tracking계산p95 7.882ms,
최대10.860ms, deadline miss0. 실제 G1관절 측정값이 아니다.

로컬수신seq0..15655(15,656개),59.99877Hz,순번누락/역전/reject/로그drop0.
양팔15,544개·Omni15,647개 전달값이 생산자 원본과 정확일치했다.
다만 Omni원본mx=-0.05,my=0.27이전구간고정,armYaw112.37~112.79°,
vx/vy/yaw_rate모두0이었다. **동시 실제보행은 미확인**이며, 사용자에게
실제 Omni보행 여부를 확인 중이다. 잘못된 방향이라고 단정하거나 동시보행PASS로표시하지 않는다.
Omni계산tick60Hz와 새로운원본처리약28.32Hz를구분한다.

원본파일은 계속 기록될 수 있어 증거JSON에 분석 prefix SHA/byte수/cutoff를 기록했다.
`actual_arm_metrics.json`, `actual_local_receive_metrics.json` 참조.
production코드/실제PD/모터출력은 변경하지 않았고 G1접속·카메라도 실행하지 않았다.
