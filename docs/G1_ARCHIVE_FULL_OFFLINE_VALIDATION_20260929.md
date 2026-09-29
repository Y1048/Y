# G1.zip 전체 세션 오프라인 검증 — 2026-09-29

검증 대상:

`C:\Users\user\Desktop\G1.zip`

검증은 네트워크 연결, G1 명령 출력, Quest/Omni 실장치 접근 없이 수행했다.
현재 portable embedded Python과 최신 소스에서 archive 내부 로그만 사용했다.

## 최종 판정

**PASS**

- archive manifest: 27/27 file size + SHA256 일치
- captured source commit: `2b99f68a02e94558ba7a19cc252ab690439c4e5d`
- bimanual exact replay: PASS
- Omni raw→velocity replay: exact PASS
- LowState stream/clock integrity: PASS
- Unity diagnostic trace pairing: PASS
- Quest trace→bimanual input cross-link: PASS
- PC observation→G1 received observation cross-link: PASS
- G1 heading command→GROOT telemetry cross-link: PASS

실행 명령:

```bat
runtime\python\python.exe -I -B tools\G1_PORTABLE.py archive-validate "C:\Users\user\Desktop\G1.zip" --strict
```
## Bimanual

archive 내부 실제 세션:

`PC/logs/test_results/bimanual/unity_20260923_152640_019472.jsonl`

- state rows: 46,570
- input rows: 7,837
- accepted inputs: 7,836
- accepted mismatch: 0
- state mismatch: 0
- reason mismatch: 0
- maximum logged-q difference: `2.000621890374532e-13 rad`
- minimum replay clearance: `5.2317879975 mm`
- final state/reason: `ready / pinch`
- exact replay: `true`
- current validation: `true`

기록 당시 source hash와 현재 source hash는 다르지만 motion limits가 동일하고,
실제 입력을 현재 simulator에 다시 넣었을 때 state/reason/q trajectory가 exact gate를 통과했다.

## Omni

PC Omni CSV 11,042행의 `raw_json_text`를 현재 `OmniVelocityMapper`에 다시 입력했다.

- raw value mismatch: 0
- calibration mismatch: 0
- skipped-sample accounting mismatch: 0
- **vx/vy/yaw_rate 최대 재계산 오차: 0.0**

따라서 당시 기록된 Omni mapping 결과는 현재 코드로 정확히 재현된다.

## Camera log

archive에는 JPEG frame payload 자체는 없고 camera SSH bridge 실행 로그만 있다.

- `[STREAMING]` progress update: 207회
- 최종 frame counter: 426
- frame byte size: 양수
- `[ERROR]` / `FAILED`: 0건
- JPEG payload archived: `false`

따라서 당시 camera bridge가 Unity 쪽으로 frame을 전달한 실행 증거는 확인되지만,
영상 내용·해상도·실제 PiP 렌더링을 archive만으로 재생하거나 시각 검증할 수는 없다.

## LowState와 PC clock

LowState 유효 record: 45,725행.

- invalid rows: 0
- ordering failure: 0
- source gaps: 0
- max transport age: `0.185411416 s`
- observed rate: 약 `58.45 Hz`
- G1 monotonic→PC monotonic 선형 clock-fit residual p95: `9.295 ms`

PC 기준으로 bimanual 시작 후 LowState 시작은 약 31 ms,
bimanual 종료 전 LowState 종료는 약 47 ms다.
따라서 LowState가 사실상 bimanual 전체 구간을 덮는다.

## Unity / Quest trace

`live_quest_trace.csv`와 `rotation_trace_*.jsonl`은 각각 7,778행이다.

- tracked mismatch: 0
- row time error p95: 약 `0.066 ms`
- wrist quaternion max component error: 약 `5.50e-7`
- head quaternion max component error: 약 `5.50e-7`

Unity trace를 bimanual sender packet의 `sender_time_s`와 nearest-frame으로 연결했을 때:

- matched: 7,777 / 7,778
- tracked mismatch: 4 / 7,777
- wrist position error p95: `7.175 mm`
- wrist quaternion L2 p95: `0.01735`
- HMD position error p95: `3.944 mm`
- HMD quaternion L2 p95: `0.00694`

두 로그의 기록 주기가 다르므로 max outlier가 아니라 p95 + tracking consistency로 판정했다.
## PC → G1 observation cross-link

G1 heading log의 `observation_rx` 13,592건을 raw SHA256부터 다시 검증했다.

- raw SHA mismatch: 0
- rejected observation: 0
- arm observation matched to PC bimanual state: 13,567 / 13,592
- matched arm q max error: `0.0 rad`
- matched arm state/reason mismatch: 0
- Omni observation matched to PC Omni row: 13,592 / 13,592
- Omni velocity max error: `0.0`
- Omni source timestamp max error: `0.0 s`

arm 25건은 G1 observation log가 PC bimanual JSONL 종료 직후까지 조금 더 지속된 tail이다.
매칭 가능한 구간의 q/state/reason은 정확히 일치한다.

## G1 heading → GROOT

GROOT telemetry:

- rows: 9,768
- duration: `195.3400578 s`
- observed rate: 약 `50.000 Hz`

G1 heading controller의 ACTIVE command와 `g1_state_sequence`를 GROOT row에 연결했다.

- ACTIVE command: 9,775
- state sequence coverage: `0..9767`
- clock alignment residual p95: `0.822 ms`
- velocity command의 best alignment: **GROOT +1 row**
- +1 row에서 vx/vy/wz p95 error: `4.871372397e-8`

즉 robot-side command와 GROOT telemetry는 약 한 state-row 지연을 두고 사실상 동일하게 이어진다.
## 오프라인 검증의 한계

이번 PASS가 의미하는 것은 **기록된 데이터 흐름과 현재 계산 경로의 재현성**이다.

검증하지 않은 것:

- 실제 Quest 장치가 지금도 동일 packet을 생성하는지
- 현재 Omni Connect 실시간 WebSocket 연결
- 현재 G1 Ethernet/SSH 연결
- 실제 G1 camera JPEG 영상 내용과 Unity PiP 렌더링
- 실제 하드웨어가 동일한 물리 운동을 다시 수행하는지
- Unity 화면상의 체감 latency/시각 품질

특히 bimanual arm 경로는 기록 당시에도 `simulation_only=true`,
`hardware_output_authorized=false`였다. LowState는 실제 G1 상태 관측 로그이며
bimanual simulation joint trajectory를 실제 팔 motor output으로 보낸 증거가 아니다.

반면 G1 heading/GROOT 로그는 robot-side command/telemetry 연결을 오프라인에서
교차 검증한 것이다. 이번 검증에서는 어떤 command도 새로 전송하지 않았다.

## 유지 규칙

향후 portable 변경 후에는 최소한 다음을 다시 실행한다.

1. embedded runtime/backend/hardware regression
2. `G1_ARCHIVE_OFFLINE_VALIDATE.py ... --strict`
3. 실제 장비 사용 가능 시에만 별도 live smoke test

archive validator가 FAIL하면 기존 `G1_Teleop_Project`를 지우거나
portable 후보를 최종 실행 폴더로 승격하지 않는다.
