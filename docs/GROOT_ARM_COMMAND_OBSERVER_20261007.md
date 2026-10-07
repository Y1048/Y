# 양팔 최종 명령 계측 — 2026-10-07

현재 G1 원본 CSV는 q/dq/tau_est 29축을 기록하지만 명령은 하체·허리 0..14만 기록한다.
따라서 PC IK와 실제 손목의 정지 오차를 PD 문제로 확정할 수 없다. 이를 비교할 수 있도록
기존 제어기에 선택적으로 연결하는 관찰용 C++ 로거와 오프라인 parser를 만들었다.
PD, 속도·가속도 제한, IK, UDP 형식, 상태 전이, 기존 CSV, publisher 개수는 변경하지 않는다.

## 제공 파일

- `tools/onboard/groot_command_observer.hpp`: SDK/소켓 의존성 없는 비동기 로거.
- `tools/onboard/groot_command_observer.patch`: 회수한 특정 G1 소스에 대한 관찰 hook.
- `tools/onboard/prepare_groot_command_observer.py`: 원본 SHA256 대조 후 별도 후보 생성.
- `tools/onboard/read_groot_command_observer.py`: 누락·비정상 데이터·순서 오류를 거부하는 reader.

기준 G1 소스 `src/g1_balance_actuator.cpp`의 LF 정규화 SHA256:
`882c661dba7478519ea5dab0cd4cd57c7fb2da58cc5b32514dc476eb5706d311`.
내용이 바뀌면 preparation이 거부한다. Windows CRLF 변환만 허용한다.
기준 전체 소스는 로컬 회수 증거이며 Git에 포함하지 않는다. 해당 소스를 다시 회수하거나
직접 확인해야 후보를 생성할 수 있다. 생성은 원본 파일을 덮어쓰지 않는다.

## 기록 내용 및 의미

스키마 `groot.command.observation.v1`, CSV 첫 행에 단위와 clock 설명을 포함한다.
29축 순서는 왼다리 0..5, 오른다리 6..11, 허리 yaw/roll/pitch 12..14,
왼팔 15..21, 오른팔 22..28이다. 다리는 hip_pitch/hip_roll/hip_yaw/knee/ankle_pitch/ankle_roll,
팔은 shoulder_pitch/shoulder_roll/shoulder_yaw/elbow/wrist_roll/wrist_pitch/wrist_yaw.
정확한 이름 배열은 parser의 `JOINT_NAMES`에도 있다.

| 필드 | 의미 |
|---|---|
| received_q15..28 | G1 C++가 정책 tick에서 관찰한 외부 양팔 목표 |
| target_q0..28 | 정책·팔 slew 처리 이후 writer에 전달된 DesiredCommand |
| sent_q/sent_dq/kp/kd/tau_ff0..28 | 기존 Write에 넘긴 LowCmd를 const로 읽은 값 |
| measured_q/measured_dq/tau_est0..28 | 해당 writer tick에서 사용한 LowState cache |
| input_sequence, input_source_timestamp | 기존 입력 sequence 및 불투명한 producer timestamp |
| input_observed_ns | 정책 loop가 command_snapshot을 읽은 시각; UDP 도착 시각 아님 |
| target_created_ns | 기존 desired.created: 명령 생성 시작 시각; Unity 목표 생성 시각 아님 |
| state_received_ns | 사용된 정상 CRC LowState가 cache에 저장된 시각 |
| write_begin_ns / write_end_ns | 기존 publisher Write 호출 직전 / 정상 반환 직후 |
| writer_sequence | 기존 write_count; 누락 검출 기준 |
| input_valid/arms_specified/arms_active/state_available | 원래 snapshot 유효성 |
| safe_stand/damping | 관찰 당시 상태 flag; 전이와 동시에 읽으면 LowCmd의 gain이 직접 근거 |
| dropped/invalid/nonmonotonic/gap_total | 큐·데이터·순서 문제 진단 |

G1 내부 ns는 모두 `std::chrono::steady_clock` 기준이다. PC 및 producer clock과
offset을 같다고 가정하지 않는다. Write 반환은 모터 수신/실행 증거가 아니며 acceptance는 unknown.
기존 초기 handoff의 동기 Write는 제외하고 이후 periodic writer만 기록한다.
IMU/온도/status 및 Unity raw 생성 timestamp는 이번 최소 hook에 포함하지 않는다.

## 실행 영향 제한

기본 비활성. 나중에 검토·ARM 빌드·배포한 후보를 실행할 때만 기존 실행 환경에
`GROOT_COMMAND_OBSERVER_DIR`을 지정하면 기록한다. 경로는 미리 존재해야 한다.
현재 launcher에 이를 설정하지 않았으며 기존 로봇 실행본도 교체하지 않았다.

255개 유효 슬롯 SPSC 큐를 사용한다. producer는 파일 접근·문자열 변환·할당·mutex 대기 없이
고정 크기 snapshot을 복사한다. 별도 consumer가 float를 복원 가능한 precision으로 기록한다.
큐가 차면 로그만 drop하며, nonfinite도 로그만 거부한다. 파일/스레드 오류는 제어기로
throw하지 않는다. source와 sent 값은 수정하지 않는다. 큐에 쌓인 마지막 sample을
소비한 후 footer를 기록한다. 강제 종료·disk stall 시 완전한 footer를 보장하지 않는다.
parser는 미완료 파일, 누락 sample, nonfinite, 순서 오류, measured-state 부재를 거부한다.
모든 500 Hz writer sample과 29축을 기록하므로 로그 용량·ARM 저장장치 부하는 별도 확인해야 한다.
기존 동기 CSV 기록은 보존했다. 이번 작업이 기존 loop의 전체 I/O를 비동기로 바꾼 것은 아니다.

## 검증 범위

실행한 검사는 Windows/MSVC의 SDK 없는 fixture와 Python synthetic fixture다.
큐 full/wrap, 동시 producer/consumer 100,000 sample 순서, nonfinite, async drain,
비활성 및 파일 열기 실패, CSV round-trip, 29축 순서, gap/nonmonotonic, 누락/미완료 거부를 검사했다.
회수한 baseline에서 후보 생성 및 PD/rate limiter/LowCmd composer/기존 CSV 함수의
바이트 동일성을 확인했고 새 publisher/Write call 수 증가가 없음을 확인했다.

G1 ARM 통합 빌드, 기존 SDK/CMake link, 실제 500 Hz loop 부하 및 새 물리 측정은 아직 미검증이다.
이번 단계에서 G1 SSH/SDK/DDS 초기화/모터 실행/전송/실제 gain 변경을 하지 않았다.
현재 gain은 회수 소스 기준 pitch·roll 100/5, yaw·elbow 40/2, wrist 20/2이며 수정하지 않았다.
`recommended_hardware_gains = null`; 실제 최종 송신 로그를 얻기 전 PD 재최적화를 주장하지 않는다.

다음 단계는 후보의 ARM 통합 빌드를 확인하고 별도 실행에서 이 로그를 회수하는 것이다.
이후 received→sent→measured를 분리 비교한다. 같은 데이터로 모델 fit과 validation을 하지 않는다.

## 후속: G1 ARM 통합 컴파일 완료

사용자 별도 승인으로 2026-10-07 G1 유선 SSH에서 기준 소스 SHA256을 재확인한 뒤,
`/home/unitree/groot_command_observer_build_20261007_9dd21a6`에 src/include/CMakeLists를
복사하고 계측 후보만 적용했다. 기존 `/home/unitree/groot_onboard_runtime`에는 쓰지 않았다.
기존 CMake와 SDK/Torch/TensorRT로 `cmake --build ... --target groot_balance_actuator -j1`
링크까지 완료했다. 후보는 ARM aarch64 ELF이며 SHA256은
`d44651d39c38ff4e46165efd0668dfb9a6ac000ea7afa22b1d2e4fb7f8f46bc5`.
원본 소스·원본 바이너리의 컴파일 전후 SHA256 일치를 확인했다.
후보 바이너리 실행, SDK/DDS runtime 초기화, LowCmd 출력, launcher 교체는 하지 않았다.

컴파일의 SDK/DDS/Torch dependency 경고는 남아 있으나 fatal error 없이 target이 완료됐다.
Windows SSH 출력 회수 wrapper에서 cp949 decode 오류가 발생해 remote compile.log를
UTF-8로 다시 회수했다. 이는 wrapper 출력 처리 실패였으며 remote compile 성공은
`[100%] Built target groot_balance_actuator`, ELF 및 원본 보존 검사로 별도 확인했다.
원본 compile evidence는 로컬 `logs/test_results/builds_20261007/arm_compile_verified.log`.
실제 500 Hz 기록 부하와 최종 명령 비교 측정은 여전히 남아 있다.
