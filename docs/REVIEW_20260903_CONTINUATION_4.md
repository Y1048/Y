# 정밀 검토 계속 기록 4

기준 branch: `Y1048/Y` `refactor/teleop-architecture`

검토 기준 commit: `7ce76e2a1b699d3a59a97ad9ea667f6809025138`

이 문서는 다음 검토 기록을 잇는다.

- [`REVIEW_20260903.md`](REVIEW_20260903.md): R1~R19
- [`REVIEW_20260903_CONTINUATION.md`](REVIEW_20260903_CONTINUATION.md): R20~R32
- [`REVIEW_20260903_CONTINUATION_2.md`](REVIEW_20260903_CONTINUATION_2.md): R33~R39
- [`REVIEW_20260903_CONTINUATION_3.md`](REVIEW_20260903_CONTINUATION_3.md): R40~R49
- 이 문서: R50~R59

이번 작업도 **검토 전용**이다. Production Python/C#/C++, configuration,
authorization, Unity scene/prefab, Windows network/firewall, G1, WSL runtime을 변경하거나
실행하지 않았다.

## 이번 본문 검토 범위

- Gate 6/Gate 7/right-arm Jog에서 공유하는 physical LowState snapshot과 runtime checks
- startup readiness의 Windows UDP 입력 경계와 launcher
- startup-recovery multi-strategy 및 posture-sweep experiment, runner, viewer와 tests
- Windows G1 Ethernet/firewall/network-capture 관리자 script와 wrapper BAT
- Unity VR APK build/install launcher와 Editor build method

`logs/review/20260903/source_checks.csv`의 117 full-text / 147 static-only 수치는 이번
추가 검토를 아직 반영하지 않는다. 정확한 coverage count는 ledger를 다시 생성한 뒤 갱신한다.

## 우선순위 갱신

기존 P1 묶음에 R50을 추가한다.

```text
release/fault finalization : R1, R34, R46
final/acquire validation   : R2, R33, R40, R41, R42
runtime state supervision  : R50
interruption/provenance    : R3, R15, R35, R51
experimental lowcmd path   : R43, R44, R45
```

현재 repository hardware authorization 값이 잠겨 있다는 사실은 유지된다. 아래 finding은
해당 physical process가 별도로 승인되어 실행될 경우의 project-level safety contract를 검토한 것이다.

## R50 · P1 · Arm SDK physical runtime이 base/IMU와 motor fault 상태를 감독하지 않음

위치:

- `hardware/g1_arm_bridge/gate6_arm_sdk_hold.py`
- `hardware/g1_arm_bridge/gate7_live_arm_sdk.py`
- `hardware/g1_arm_bridge/g1_right_arm_jog.py`
- 관련 Gate 6/Gate 7/Jog tests

세 physical Python path는 공통 `LowStateBuffer`를 사용한다. 이 buffer가 보관하는 값은 다음뿐이다.

```text
local receive time / local sequence
mode_pr / mode_machine
29 joint q / dq
```

LowState에 존재하는 다음 safety-relevant evidence는 snapshot에 들어오지 않는다.

- IMU orientation 및 angular state
- base position/velocity 또는 지지 상태
- motor state/fault code
- motor temperature
- estimated torque
- wireless-remote/deadman state
- LowState CRC 또는 equivalent integrity evidence

실제 publish loop는 local LowState age, mode, arm q/dq, joint limit와 target error를 검사하지만,
base tilt/fall, motor over-temperature/fault 또는 remote state를 project code에서 계속 감독하지 않는다.
외부 firmware가 handheld stop을 독립 처리할 가능성은 있으나, 저장소 source만으로 해당 동작이나
acknowledgement를 증명할 수 없다.

영향:

- q/dq와 mode가 아직 threshold 안에 있는 동안 base stability 또는 motor health가 악화돼도
  project-side command loop가 이를 직접 fault로 전환하지 않는다.
- physical result JSON도 해당 evidence를 남기지 않아 사후에 안전 조건이 유지됐는지 확인하기 어렵다.

조치:

1. 하나의 immutable physical LowState snapshot에 IMU/base, motor fault/temperature/torque,
   remote state와 integrity 결과를 포함한다.
2. publisher 생성 전과 매 write 직전에 profile별 threshold를 fail-closed로 검사한다.
3. external firmware emergency-stop 동작은 별도 integration test와 mode/owner acknowledgement로 기록한다.
4. tilt, motor fault, over-temperature, invalid CRC/integrity, remote release와 정상 state를 fake LowState로
   주입하는 회귀 시험을 추가한다.

## R51 · P2 · startup precheck UDP stream의 송신 provenance가 인증되지 않음

위치:

- `hardware/g1_arm_bridge/check_startup_readiness.py`
- `hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py`
- `tools/CHECK_G1_TELEOP_STARTUP.bat`
- `tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1`

`check_startup_readiness._collect_packets()`는 `recvfrom()`의 sender address를 읽고 버린다.
Packet parser는 schema, mode, topic, self-declared `publisher_present=false`, sequence/session과
payload timestamp를 확인하지만, 실제 `read_only_lowstate.py` instance가 보낸 packet이라는
nonce/token/process binding은 없다.

따라서 형식이 맞는 localhost 또는 허용된 local-subnet sender도 precheck 입력을 만들 수 있다.
이 결과는 `DIRECT_TELEOP_READY`와 `recovery_bypass_allowed=true` artifact가 될 수 있다.
R40에서 확인한 것처럼 이후 publisher boundary의 full-body binding도 완전하지 않으므로,
precheck provenance와 current-state binding은 함께 닫아야 한다.

조치:

- launcher가 forwarder를 시작할 때 one-run nonce를 발급하고 packet/result에 결박한다.
- expected sender/interface와 bridge session을 검증한다.
- source timestamp, local receive time와 forwarder liveness를 하나의 evidence set으로 기록한다.
- synthetic/replay source는 별도 schema/source로 분리하며 physical precheck에서 거부한다.

## R52 · P2 · right-arm Jog settle 완료 시 최신 LowState freshness를 재검사하지 않음

위치:

- `hardware/g1_arm_bridge/g1_right_arm_jog.py`
- `hardware/g1_arm_bridge/test_g1_right_arm_jog.py`

`collect_settled_snapshot()`은 unique local sequence sample 수와 관측 구간의 최대 arm velocity를
확인하지만, 반환 직전 `time.monotonic() - latest.received_monotonic_s`를 timeout과 비교하지 않는다.
초반에 충분한 sample을 받은 뒤 stream이 멈추면 stale snapshot을 반환할 수 있다.

Runtime의 첫 control tick은 다시 age를 확인하므로 stale snapshot에서 즉시 nonzero frame을
반드시 보낸다고 단정할 수는 없다. 그러나 publisher는 그 첫 tick 이전에 이미 생성되며,
startup contract가 주장하는 “fresh settled LowState 후 publisher” 조건은 함수 경계에서 보장되지 않는다.
현재 Jog tests는 settle-window tail stall을 다루지 않는다.

조치:

- settle 반환 직전 최신 snapshot age와 최대 inter-packet gap을 검사한다.
- publisher 생성 직전 fresh snapshot을 다시 가져와 precheck/permit/mode를 한 번에 재검증한다.
- early burst 후 단절, threshold 직전/직후 단절과 정상 continuous stream 시험을 추가한다.

## R53 · P2 · recovery experiment의 model/evidence가 immutable provenance로 결박되지 않음

위치:

- `experiments/startup_recovery_multistrategy/run_experiment.py`
- `experiments/startup_recovery_multistrategy/candidate_runner.py`
- `experiments/startup_recovery_multistrategy/view_selected.py`
- `experiments/startup_recovery_posture_sweep/run_sweep.py`
- `experiments/startup_recovery_posture_sweep/single_pose_runner.py`
- `MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py`

두 experiment는 `controller._prepare_mink_xml()`을 통해 repository 내부의 공용
`_generated_g1_right_arm_udp_ik.xml`을 다시 쓴다. Posture sweep은 이를 “one immutable model”로
준비한 뒤 child process에 environment flag를 주며, child는 파일 존재 여부만 확인하고 rebuild를
건너뛴다. 파일 lock 또는 hash verification은 없다.

또 `--resume-run`은 이전 summary에서 `ERROR`가 아닌 PASS/FAIL/SKIPPED case를 그대로 유지한다.
이전 case result와 현재 controller/model/config/source-state content hash를 비교하지 않으므로,
code나 generated model이 바뀐 뒤 rerun한 ERROR case와 과거 case가 한 summary에 섞일 수 있다.
Multi-strategy summary/selected viewer도 state/model/config/result hash가 아니라 absolute path를 저장한다.
Viewer는 result가 `passed=true`인지 확인하지만 현재 시점의 model을 다시 생성해 재생한다.

영향:

- “같은 model에서 비교한 sweep” 및 selected strategy의 reproducibility가 artifact만으로 증명되지 않는다.
- concurrent controller/experiment가 공용 generated XML을 다시 쓰면 worker별 model이 달라질 수 있다.

조치:

1. run 전용 directory에 generated XML을 만들고 content hash를 고정한다.
2. state/config/controller/validator/model/mesh hash와 tool version을 모든 result/summary에 기록한다.
3. resume 시 provenance가 하나라도 다르면 기존 case를 유지하지 않는다.
4. selected result hash를 summary에 넣고 viewer가 hash와 model identity를 확인한다.
5. concurrent rewrite와 changed-code resume regression test를 추가한다.

## R54 · P3 · posture sweep은 recovery 성공이 0건이어도 process PASS가 될 수 있음

위치:

- `experiments/startup_recovery_posture_sweep/run_sweep.py`
- `experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat`
- `experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat`

Sweep의 exit code는 infrastructure `ERROR` case가 있는지만 본다. 모든 evaluated case가 `FAIL`이거나
모든 case가 joint-limit `SKIPPED`여도 error count가 0이면 `[PASS] Sweep completed`를 출력하고 0을
반환한다. 화면에 `passed/evaluated` 수치가 함께 나오므로 사람이 읽을 때는 구분할 수 있지만,
상위 automation은 “실험 실행 완료”와 “복구 가능한 pose 존재”를 같은 성공 코드로 받을 수 있다.
이는 R20의 구체적인 experiment surface다.

조치:

- `RUN_COMPLETED`, `NO_RECOVERABLE_SAMPLE`, `PARTIAL_MAP`, `INFRASTRUCTURE_ERROR`를 별도 status/exit code로 둔다.
- BAT 문구도 map 생성 성공과 recovery acceptance를 분리한다.
- all-fail, all-skipped, mixed, infrastructure-error test를 추가한다.

## R55 · P3 · multi-strategy runner의 stale artifact와 무한 대기 경계가 약함

위치:

- `experiments/startup_recovery_multistrategy/run_experiment.py`
- `experiments/startup_recovery_multistrategy/test_experiment.py`

기본 output directory는 run별 timestamp directory가 아니며 candidate result/log를 같은 이름으로
재사용한다. `run_candidate()`는 기존 result를 먼저 삭제하지 않고 subprocess timeout도 설정하지 않는다.
Child가 0으로 종료했지만 새 result를 쓰지 않는 비정상 경로에서는 기존 JSON을 읽을 수 있고,
solver/process가 hang하면 전체 comparison이 무기한 멈춘다. 현재 tests는 ranking 함수만 검사하며
stale result, missing rewrite, malformed result와 timeout을 다루지 않는다.

조치:

- run별 directory와 atomic run manifest를 사용한다.
- 시작 전 candidate result 존재를 금지하거나 content run ID를 확인한다.
- per-candidate timeout 및 timeout status를 둔다.
- selected candidate에는 source/model/result hash를 기록한다.

## R56 · P2 · G1 network capture가 pktmon 실패를 성공으로 기록할 수 있음

위치:

- `tools/DETECT_G1_NETWORK_ADMIN.ps1`
- `tools/DETECT_G1_NETWORK.bat`

관리자 script는 `pktmon start`, `stop`, `format`을 호출한 뒤 `$LASTEXITCODE`와 생성 파일을
검증하지 않고 `g1_network_capture.done`을 쓴다. Wrapper는 PowerShell process exit code만 본다.
Windows PowerShell에서는 `$ErrorActionPreference = "Stop"`만으로 native executable의 nonzero
exit가 항상 terminating error가 되는 것은 아니다.

또 script 시작 시 기존 system-wide pktmon session을 정지하고, interface/filter 없이 5초간
host 전체 packet을 capture한다. 이는 다른 진단 session을 중단하고 G1과 무관한 traffic도 ETL에
포함할 수 있다.

조치:

- 각 pktmon 호출 직후 `$LASTEXITCODE`와 ETL/text file 존재·크기를 확인한다.
- done marker는 모든 단계 성공 후에만 atomic하게 쓴다.
- 가능한 경우 G1 adapter/subnet filter를 적용한다.
- 기존 pktmon session이 있으면 임의 정지하지 말고 명시적으로 중단/승인을 요구한다.

## R57 · P2 · Windows LowState firewall rule이 G1 interface/subnet보다 넓음

위치:

- `tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1`
- `tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat`

Rule은 UDP 5007/5009에 대해 `RemoteAddress LocalSubnet`, `Profile Any`를 사용하고
`InterfaceAlias`를 제한하지 않는다. 따라서 G1 전용 Ethernet뿐 아니라 Wi-Fi 등 다른 local subnet의
host도 해당 listener에 packet을 보낼 수 있다. Precheck/Gate monitor가 `0.0.0.0`에 bind하고 packet
source identity를 검증하지 않는 경로와 결합하면 misrouted 또는 synthetic telemetry surface가 넓어진다.

조치:

- ASIX/G1 interface와 `192.168.123.0/24` 또는 실제 필요한 WSL source로 rule을 최소화한다.
- precheck/viewer port가 외부 interface에서 반드시 열려야 하는지 구분한다.
- firewall scope와 application-level session/provenance를 함께 검사한다.

## R58 · P2 · Windows network/firewall 변경 script가 transactional하지 않음

위치:

- `tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1`
- `tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1`
- `tools/ALLOW_G1_DDS_WSL_ADMIN.ps1`
- `tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1`

Ethernet configure는 DHCP를 끄고 기존 IPv4를 제거한 뒤 static address를 추가한다. Restore는
manual address를 제거한 뒤 DHCP를 켠다. Firewall script는 기존 rule을 삭제한 뒤 새 rule을 만든다.
중간 cmdlet이 실패하면 이전 상태를 복원하는 rollback이 없고, first matching ASIX adapter만 사용한다.

영향:

- 실패 exit code는 반환되더라도 adapter가 address 없이 남거나 이전 firewall rule이 사라진
  partial state가 남을 수 있다.
- 같은 model의 adapter가 둘 이상이면 의도하지 않은 first match가 수정될 수 있다.

조치:

- 대상 adapter identity/MAC/interface index를 명시적으로 확인한다.
- 변경 전 IP/DNS/firewall snapshot을 저장하고 실패 시 rollback한다.
- 변경 후 exact final state를 읽어 검증한 뒤 status marker를 쓴다.

## R59 · P3 · APK install이 현재 build artifact와 정확한 Quest device에 결박되지 않음

위치:

- `tools/BUILD_AND_INSTALL_VR_APK.bat`
- `Unity_G1_VR/Assets/Editor/G1VRBuild.cs`

BAT는 Unity process가 0으로 종료된 뒤 APK path가 존재하는지만 확인한다. 기존 APK를 먼저
제거하거나 build 전후 timestamp/hash, Unity BuildReport artifact identity와 현재 source commit을
연결하지 않는다. 매우 드문 비정상 0-exit/no-rewrite 경로에서는 이전 APK가 남아 install 대상이 될 수 있다.

`adb devices` 출력은 화면에만 표시되고, 정확히 한 대가 `device` 상태인지, 해당 serial/model이
승인한 Quest인지 검사하지 않는다. `adb install -r`에도 `-s <serial>`이 없다. 단일 Android device가
연결돼 있으면 Quest가 아닌 device를 대상으로 할 수 있다.

조치:

- build 전에 old output을 격리하고, build 후 mtime/hash/package ID/source commit manifest를 검증한다.
- ADB에서 정확히 한 approved Quest serial/model과 `device` 상태를 요구한다.
- install 후 package/version/hash를 다시 확인한다.

## 검토했으나 이번에 새 finding으로 올리지 않은 사항

- Multi-strategy는 passed candidate가 하나도 없으면 nonzero를 반환하며 hardware-ready라고 표시하지 않는다.
- Posture sweep의 HTML은 sampled map일 뿐 unsampled region을 보증하지 않는다는 경고를 포함한다.
- Ethernet/firewall wrapper BAT는 elevated child process의 nonzero exit를 상위로 전달한다.
- `G1VRBuild.BuildApk()`는 BuildReport가 `Succeeded`가 아니면 exception을 발생시킨다.
- 이번 검토에서 관리자 script, pktmon, ADB, Unity batch build 또는 experiment를 실행하지 않았다.

## 코드 수정과 실행 여부

```text
Production Python/C#/C++ 수정 : 없음
Config/authorization 수정      : 없음
Unity scene/prefab 수정         : 없음
Windows IP/firewall 변경        : 없음
G1 파일/서비스/state 변경      : 없음
WSL/Unity/G1 실행               : 없음
Repository/experiment 실행      : 없음
Hardware publisher 생성         : 없음
```

이번 commit은 이 review 문서만 추가한다. R50은 physical output 확대 전 우선 수정 대상이다.
수정은 review와 별도 작업으로 진행하고, fake LowState/fake publisher fault injection을 먼저 사용한다.
