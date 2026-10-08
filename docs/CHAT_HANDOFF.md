## 2026-10-08 Actual Player hand retest: runtime unavailable; Editor works

Actual Windows_wrist_fix_20261008 operator Player log: 9 raw diagnostic samples, all development=True/focused=True, runtime_hands_enabled=True count 0, left/right query success count 0. User confirms same Quest/Link works in Editor and corrected cyan markers are now at wrist. This isolates Windows Player raw input availability from the separate bone-ID bug. Development build alone is falsified as a solution; do not repeat build toggles without new evidence.

Meta hand-specific official documentation states Windows-over-Link hand tracking is supported only in Unity Editor for iteration: https://developers.meta.com/vr/documentation/unity/unity-handtracking-overview/ . Generic Link documentation describes standalone PC app tracking but does not establish standalone hand support. Earlier assurance that PC EXE packaging would directly retain Quest hands was too broad; withdrawn. No claim that all possible PC runtimes cannot expose hands.

Current usable path: existing Editor hand tracking and PC Mink. For supported editor-independent distribution, use Quest-native APK hand tracking and exchange input/state with PC; architectural work remains separate. Do not treat APK input alone as preserving PC Link rendering simultaneously. No SDK migration, runtime config registry change, or motor launch attempted in this diagnosis.

Local evidence: windows_link_20261008/wrist_fix_player_no_hands.log and wrist_fix_hand_summary.json (actual operator data, not synthetic). Physical gain recommendation remains null.
## 2026-10-08 OpenXR palm incorrectly used as wrist — mapping fix

Same current Quest/Link connection: user confirms Editor hands work while Windows Player hands still absent. Editor screenshot shows cyan wrist markers at palm center. Installed SDK reports OpenXR skeleton; SDK enum Hand_WristRoot=0 aliases XRHand_Palm=0, while XRHand_Wrist=1. Existing binder and separate bimanual sender selected Hand_WristRoot without skeleton-type context; anatomical finger bases also used legacy IDs.

Added G1HandSkeletonMapping to choose wrist and index/middle/little proximal bases from OVRSkeleton.GetSkeletonType, preserving legacy OVR semantics, selecting OpenXR semantics for XRHandLeft/Right, rejecting unsupported types. Applied to binder and separate bimanual Wrist reader. No arbitrary position offset, mesh/IK/gain/network change. This corrects the input position and anatomical rotation as well as marker display.

Actual C# mapping fixture passes: both hands and formats, overlapping palm/wrist numbers, anatomical base indices, unsupported body/none and invalid joint. User confirmed Play stopped. Portable original consumer files matched source baseline before replacement, copies backed up in local live_wrist_fix_backup; new helper/meta and two consumers copied byte-identically. Windows_wrist_fix_20261008 Windows64 build succeeded with batch exit 0 and matching SHA256 sidecar; visual wrist alignment retest pending. Windows EXE no-hands issue remains separately unresolved; raw-runtime diagnostic candidate still needs operator run.
## 2026-10-08 Development Player still has no hands; splash removal and raw diagnosis

Operator retest of Windows_link_candidate_20261008 failed hand recognition. Actual Development Player log confirms valid HMD tracking but both hand binders remain tracked=false. Therefore Development build alone is not a confirmed fix. Original Release and Development logs remain preserved under local logs/test_results/windows_link_20261008.

Windows BuildWindows now disables both SplashScreen.showUnityLogo and SplashScreen.show. Added G1LinkHandDiagnostics, read-only OVRPlugin hand-enabled/query-status/active-controller diagnostics every 2 s in Editor and Player. It does not enable features, publish packets, alter poses, or change IK/control. This distinguishes raw runtime hand-state absence from binder/skeleton failures. No undocumented runtime configuration or registry changes.

New candidate: Portable/Builds/Windows_link_no_splash_20261008/G1Teleop.exe. Runtime hand recognition still requires actual retest; ask whether Editor hands work on the same current connection. No motor program executed. Real C# sanitizer helper regression passed (1 test); Windows64 build succeeded, candidate exe SHA256 sidecar matched, and generated project splash flags are both 0. Operator visual/startup and raw hand-status retest pending.
## 2026-10-08 Windows Link hand tracking — Development candidate

Release Player actual operator log: HMD orientation/position and XR session valid, both OVR hand binders continuously tracked=false. Backend also waiting; launching Player alone does not launch Python IK.

Installed Meta SDK OVRManager.cs calls SetDeveloperMode(Debug.isDebugBuild) outside UNITY_EDITOR. Prior BuildWindows used BuildOptions.None, so Release disables developer features. This is a source-backed suspected cause of absent Link hands, not yet an operator-confirmed root cause.

Windows builder now uses BuildOptions.Development without ScriptDebugging. Android builder, XR packages, input/IK/gains and robot launchers remain unchanged. Official Meta documentation requests Link Developer Runtime Features. Operator screenshots of installed Link 208.0.0.74.535 show only Account/General tabs and no Developer/Beta entry; runtime setting status is unknown. Do not assert that this missing menu is disabled or advise undocumented registry changes. Development build does not prove runtime permission.

Separate candidate: Portable/Builds/Windows_link_candidate_20261008/G1Teleop.exe. Release artifact and operator log preserved. Development Windows64 build succeeded; SHA256 sidecar matched and real C# sanitizer helper regression passed (1 test). Actual Quest retest remains pending; no hardware validation claimed. Do not launch G1 controller merely to test Player hands. Start local IK separately only after valid hands.
## 2026-10-07 Windows Player 및 G1 ARM 통합 컴파일 완료

사용자 승인으로 기존 Quest Link/Windows 구조의 Unity Player를 빌드하고, G1 관찰 hook
후보를 별도 G1 폴더에서 ARM 컴파일했다. APK/손 추적/IK/실제 gain을 변경하지 않았다.

Windows 첫 빌드는 Meta DevAgent post-build 복구 때문에 기존 sanitizer의 주소 exact count가
0이 되어 실패했다. 실제 빌드 직전 SerializedObject 값을 마지막 preprocess hook에서
캡처하도록 수정하고 재빌드했다. SDK package를 직접 수정하거나 검사 기준을 완화하지 않았다.
실제 Windows64 build 및 Unity batch exit 0, exe SHA256, token/injected address 제거 확인 PASS.
실제 C# sanitizer helper 컴파일/실행 테스트 PASS. 첫 실패 증거는 삭제하지 않았다.
Portable 후보: `Builds/Windows_candidate_20261007/G1Teleop.exe` (폴더 전체 231파일 약244 MB).
기존 Player는 덮어쓰지 않았다. 후보 Player 실행/Quest 실착 hand tracking은 아직 미검증이다.
원래 source dirty DevAgentSettings.asset SHA256은 그대로이며 build가 자동 변경한 isolated
worktree DevAgentSettings/ProjectSettings/TagManager/coverage settings는 커밋하지 않는다.
실행 중인 Portable Editor와 프로젝트에 수정본을 자동 설치하지 않았다.
상세: `docs/G1_WINDOWS_PLAYER_BUILD_20261007.md`.

G1: `/home/unitree/groot_command_observer_build_20261007_9dd21a6/build/groot_balance_actuator`
CMake ARM aarch64 링크 완료. SHA256
`d44651d39c38ff4e46165efd0668dfb9a6ac000ea7afa22b1d2e4fb7f8f46bc5`.
원본 `/home/unitree/groot_onboard_runtime` 소스/바이너리 해시 보존 확인.
새 바이너리 실행, SDK/DDS runtime 초기화, LowCmd 출력, launcher 교체는 하지 않았다.
SSH 출력 wrapper의 cp949 오류 후 원본 compile.log를 UTF-8로 재회수해 성공을 별도 검증했다.
상세: `docs/GROOT_ARM_COMMAND_OBSERVER_20261007.md`.

남은 항목: standalone Player의 Quest 양손 입력 실제 확인, G1 후보 선택/기록 부하 및
received→sent→measured 비교 측정. 배포·계측 실행은 자동으로 진행하지 않았다.
`recommended_hardware_gains = null`.

## 2026-10-07 양팔 최종 명령 관찰 hook — 별도 후보

사용자 승인으로 `codex/g1-arm-command-observer-20261007`의 isolated worktree에서
선택적 비동기 C++ 로거, hash-pinned 원본 source patch/preparer, fail-closed CSV reader를
구현했다. 최신 main/origin/main은 시작 당시 05c8735로 일치했고 원래 dirty
DevAgentSettings.asset 및 기존 worktree/runtime는 변경하지 않았다.

수신 양팔 14축 목표와 slew 이후 desired q, 기존 writer가 Write에 넘긴 실제 q/dq/Kp/Kd/tau
29축 및 대응 LowState q/dq/tau_est를 관찰한다. 내부 steady-clock timestamp와 입력 seq,
큐 drop/invalid/gap을 기록한다. Write 반환은 motor acceptance가 아니다.
PC/producer clock 정렬이나 실제 Unity 목표 생성 시각을 만들어내지 않는다.
기본 비활성이며 기존 제어/PD/속도제한/publisher/launcher는 그대로다.

실행 검증: Python fixture 8/8 PASS, Windows MSVC C++ fixture PASS
(100,000 concurrent samples, bounded full/wrap queue, CSV drain, 비활성 및 file-open 실패),
C++ CSV→Python round-trip PASS. pinned source 후보 생성 및 PD/rate/LowCmd composer/기존
CSV 함수 보존, publisher/Write 개수 보존을 확인했다. 이는 synthetic/offline 검사다.
G1 소스 전송/ARM 통합 빌드/SDK/DDS 초기화/모터 실행/물리 gain 변경은 하지 않았다.
완성 patch와 header는 저장소에 있으며 회수 baseline 전체는 로컬 evidence다.

남은 항목: G1 ARM SDK/CMake 통합 컴파일, 500 Hz 실제 기록 부하, 최종 명령 비교 측정.
새 로그로 received→sent→measured를 나눈 뒤 모델 식별과 별도 episode 검증을 진행한다.
`recommended_hardware_gains = null`. 자세한 필드·활성화 방식·한계:
`docs/GROOT_ARM_COMMAND_OBSERVER_20261007.md`.

## 2026-10-07 Transient hand-loss grace — current update

사용자 승인에 따라 손 추적 손실에 의한 자동 복귀 기준만 **0.35 → 1.5 s**로 변경했다.
최신 `unity_20261007_165710_963962.jsonl`의 세 복귀는 모두 left tracked=false / right
tracked=true인 `tracking_lost`였다. 손실 전체 길이는 0.828/0.407/1.359 s였고, 각 복귀
시점에는 engage=true, return_home=false, input_age=0였다. 이 길이를 견디도록 선택한
operator grace이며 Quest sensor 또는 실제 G1 안전성이 검증된 임계값이 아니다.

손실 중 기존 checked braking을 사용하고 양팔의 새 목표를 풀지 않는다. 유효한 양손
추적이 회복되면 loss timer를 reset하고 같은 engagement에서 재개한다. 1.5 s 이상
지속 손실에는 기존 safe return을 사용한다. 입력 통신 timeout 0.75 s, pinch/명시적
해제, session 변경, joint/collision/motion limits와 outlier 검사는 그대로다.
실행 헤더에 `tracking_loss_return_delay_s`를 기록한다. Unity 코드 변경은 없다.

관련 state-machine/real IK 모의 검사 **17/17 PASS**: 로그에서 추출한 손실 길이,
감속 중 invalid 목표 미사용, 양손 재획득, 지속 손실 경계, timer 초기화, pinch,
통신 timeout, 실제 solver의 속도·가속도·범위·clearance 검사 포함.
이는 원본 전체 operator 세션을 재생해 새로운 UI 피드백까지 검증한 결과가 아니다.
원본 Unity 입력은 과거 복귀 응답에 따라 engage를 해제하므로 counterfactual operator
flow는 새 Quest 시험이 필요하다. 실제 G1 실행·SSH·gain 변경은 하지 않았다.
전체 backend **349/349 PASS**, hardware mock/fixture **44/44 PASS**.
지속 손실 회귀는 새 1.5 s 조건을 사용하며, 과거 로그와 q/state를 정확히 비교하는
historical 검사에만 당시 0.35 s 기준을 명시했다. current-profile replay에는 새 기준을
사용한다. 최초 회귀의 두 historical 기대값 실패 로그도 삭제하지 않고 보존했다.
evidence: `logs/test_results/tracking_grace_20261007/` (`backend_final.log`, `hardware.log`).
Portable 대상 Python/tests/docs 6파일을 백업·hash 대조하여 반영했고 관련 검사
17/17 PASS도 확인했다. Unity 코드와
로컬 settings는 변경하지 않는다. 실행 중인 입력 프로세스가 없음을 확인했으며,
다음 입력 세션부터 새 기준을 사용한다. Quest에서 실제 재획득 사용감은 별도 확인한다.

## 2026-10-07 Bilateral feasible IK goal display — current update

사용자 승인에 따라 초록 구의 소스를 checked-stop endpoint에서 목표 방향의 검증된
3틱 look-ahead FK로 교체했다. 별도 private process에서 동일 양팔 solver/제약/감속
검사를 실행하며, 실제 command q와 tracking/return 상태는 수정하지 않는다.
actual IK/command는 60 Hz 유지, 표시 계산만 최대 10 Hz, 생성 시점 기준 200 ms 이후
숨긴다. 초록 구는 global reachable workspace나 실제 G1 도달 위치를 증명하지 않는다.
LowState 29관절 실측 표시, READY 측정 초기화, authored home/return은 보존했다.

backend **344/344**, hardware fixture **44/44**, native Unity edit-mode 신규 **24 checks**,
기존 measured display **155 checks** 및 measured start **17 checks** PASS.
기록 입력 재생 645개에서 live command 차이 0 rad, private goal-prefix FK 차이 0 m,
부모 solver 상태 변경 없음. 최종 cadence 비교에서 loop p95는 예측 없는 앞/뒤
12.785/12.362 ms, 예측 포함 13.050 ms였으며 모든 60 Hz deadline 보장은 아니다.
실제 G1/Quest 표시 재시험은 하지 않았다. 불리했던 20/30 Hz 후보 결과도 보존한다.

Play 정지 확인 후 Portable에는 관련 13파일만 백업·해시 확인하여 반영했다.
Portable predictor 테스트 23/23 PASS. Unity Play를 자동 시작하지 않았다.
기존 dirty `DevAgentSettings.asset`과 live solver/safety/return/gain 파일은 보존한다.
이번에 SSH/SDK/DDS/모터 실행은 하지 않았다. 다음 범위는 Quest에서 초록 목표와
실측 손목 표시 구분을 확인하고 추종오차·지연을 계측하는 것이다. continuous
LowState reseeding은 이번 변경에 포함하지 않으며 별도 설계가 필요하다.
세부 근거와 한계: `docs/G1_FEASIBLE_GOAL_DISPLAY_VALIDATION_20261007.md`.

## 2026-10-07 Measured initialization before engagement — current update

참여 전 구와 실측 손목의 약 7.3 cm 어긋남을 수정했다. canonical Unity 입력은 v5이며, 최초 HMD 정렬 후 정상 LowState가 정지·최신성 조건을 통과하면 READY/inactive 모델을 한 번 초기화한다. backend가 초기화 revision을 알리고 Unity가 같은 기준을 준비한 뒤에만 기존 양손 정렬·참여가 가능하다. 추종/귀환 중 실측값으로 IK를 덮어쓰지 않는다. 실측 팔·허리 자세를 포함한 모델 초기화이며 원래 HMD anchor와 authored arm home/return 목표는 유지한다. Omni는 선택 사항이지만 v5 참여에는 G1 실측 상태가 필요하다.

최종 offline backend 321/hardware 44 테스트와 실제 Unity edit-mode 기존 155개+새 18개 검사가 통과했다. 기록 자세 재현에서 양쪽 구·손목 오차가 수치상 0으로 일치했으며 실제 구동 검증은 아직 하지 않았다. 데이터 최신성 값은 절대 동기 지연이 아니고, body 15관절은 cycle 시작 snapshot으로 고정되므로 continuous measured-feedback IK로 해석하지 않는다. `docs/G1_MEASURED_START_VALIDATION_20261007.md`의 조건·단계·한계를 따른다. 다음 확인은 기존 세션을 정상 종료하고 컴파일 완료 후 `START_G1_VR_TELEOP.bat --no-groot-actuation`으로 한다. 이 옵션은 이미 켜진 GROOT를 끄지 않는다.

## 2026-10-07 Measured display and independent diagnostics — current update

실측 수신과 모델 적용이 달랐던 양팔 표시 분기를 수정했다. 첫 정상 LowState 이후 화면의 29관절은 실측값을 적용하고, stale 상태에서는 마지막 실측 자세를 유지한다. 아직 실측을 한 번도 받지 못한 경우에만 IK 시뮬레이션임을 명시한다. HMD 상태창의 별도 행은 수신 여부가 아니라 실제 모델 적용 출처를 표시한다.

명령 기준과 표시 기준을 분리했다. `G1BimanualCommandFrame`은 기존 rig로 명령 FK를 임시 평가하고 표시 자세를 즉시 복원한다. 초기 HMD 정렬, 양손 engage 기준 및 기존 송신 world-frame 진단값에는 실측 팔/허리 움직임을 주입하지 않는다. 실제 모델 관절은 LowState지만 root 위치/Omni yaw는 기존 표시 기준이다. `logs/test_results/measured_tracking/`에 5 Hz로 실측 q/dq, 명령 q, 각 source/sequence/receipt age 및 유효한 비교 오차를 분리 기록한다. 절대 지연 측정이나 물리 정지 증명은 아니다.

이번 단계는 표시 수정 + 독립 진단 기반이며, 실측값으로 IK 상태를 매 틱 덮어쓰거나 engage 시 자동 재동기화하지 않는다. Python IK·안전·귀환·관절범위·카메라·Omni 로직은 변경하지 않았다. 실제 Unity edit-mode 프리팹 10개 시나리오/155개 검사, backend 305/hardware 44 테스트를 통과했다. 실제 Quest/G1 렌더·새 진단 로그의 실기 확인은 별도다. 자세한 구조와 검증 한계: `docs/G1_MEASURED_DISPLAY_VALIDATION_20261007.md`.

## 2026-10-07 PC/G1 joint-range contract — current update

PC IK now intersects all 14 arm model/operational position ranges with the deployed G1 C++ acceptance limits (raw bounds plus/minus 0.05 rad, plus 1e-6 rad numerical reserve). Applied before Mink range caches; no output clipping or G1 safety-guard relaxation. Position/rotation rates 12/1.5 and tracking/return limits are unchanged. 09:56 exact baseline replay reproduced the mismatch; candidate output and checked tails contain zero receiver-bound violations and both returns complete. Full validation, holdout, numerical bounds and remaining physical limitations: `docs/G1_JOINT_RANGE_RECONCILIATION_20261007.md`. Status remains OFFLINE_VALIDATED_LIVE_UNVERIFIED for this repair. Historical replay uses historical ranges only in tests.

## 2026-10-06 Windows standalone 기본 실행 — 과거 기록, 현재 경로 아님

> 이 절은 당시 시도의 기록이다. 이후 양손 추적 실패로 기본 경로를 자동 Unity Editor 실행으로 복귀했다. 아래 현재 실행 절이 우선이며, 이번 실측 표시 수정은 기존 standalone 실행 파일에 재빌드되지 않았다.

당시 시도한 기본 사용자 실행은 Unity Editor + Play가 아니라 `Builds/Windows/G1Teleop.exe`였다.
`START_G1_VR_TELEOP.bat`가 standalone player를 자동 시작하고, 동일 player가 이미
실행 중이면 재사용한다. 개발용 기존 Editor 경로는 `--unity-editor`, Unity 없이
workers만 실행하는 경로는 `--no-unity`로 보존한다. standalone과 Editor가 동시에
같은 loopback port를 소유하지 않도록 서로 충돌하면 fail closed한다.

2026-10-06 standalone smoke에서 player가 6초 이상 정상 유지됐고 Oculus XR input/display
provider 등록, display start, eye texture 생성까지 확인했다. G1 motor command는 사용하지
않았다. smoke log의 유일한 XR 오류 문자열은 optional MRUK PcaCamera 기능의
`XR_ERROR_FUNCTION_UNSUPPORTED`였고 player 종료이나 G1 teleop runtime 오류는 아니었다.

초기 Windows build의 `resources.assets`에 로컬 Meta DevAgent access token/server address가
포함된 것을 발견해 해당 build는 그대로 배포하지 않았다. 현재 `Builds/Windows` 전체를
source 원본 token/address로 재검색해 둘 다 0 occurrence를 확인했고 이 상태에서 standalone
smoke PASS했다. `G1VRBuild.BuildWindows()`에도 post-build fail-closed sanitization을 추가해
향후 build가 `resources.assets`의 DevAgent token/address를 유일하게 찾지 못하거나 제거하지
못하면 성공으로 판정하지 않는다. source의 `DevAgentSettings.asset` 로컬 값은 변경/commit하지
않는다.

현재 이 PC의 Unity batch mode는 Package Manager IPC startup failure로 새 build가 중단되는
환경 이슈가 있다. `-noUpm`은 OVR/UGUI/Newtonsoft package assembly reference가 빠져 사용할
수 없다. 따라서 현재 검증된 prebuilt player를 기본 사용하며, UPM이 정상화된 환경에서
`G1VRBuild.BuildWindows()`로 재빌드한다.

## 2026-10-02 Quest PTZ intermittent 원인 및 분리 수정

기존 PTZ는 `Unity -> Omni gateway -> UDP 55070 -> g1_omni_heading_controller.py -> localhost 15102 -> camera follower`에 의존했다. 따라서 GROOT heading controller가 없는 camera-only/`--no-groot-actuation` 세션, heading controller 시작 전, Omni WebSocket/보정이 준비되지 않은 구간에서는 follower가 살아 있어도 Quest pose `rx=0` 또는 rejection이 되어 카메라가 움직이지 않았다. 이 시작 순서 의존성이 "될 때도 있고 안 될 때도"의 소프트웨어 원인이었다.

수정 후 Unity는 initial HMD alignment 이후 orientation tracked+valid만으로 camera-only schema를 `127.0.0.1:55075`에 20 Hz 전송한다. 위치 tracking이나 Omni readiness는 PTZ에 필요하지 않다. 카메라 pose는 55074 Omni heartbeat와 별도 `UdpClient`를 사용해 camera-only 세션의 닫힌 55074 포트 오류에도 영향받지 않는다. `G1_CAMERA_FOLLOW_LAUNCH.py`가 이를 검증하고 SSH stdin을 통해 G1 `127.0.0.1:15103`으로 전달하며, onboard `receive_mink_ik_udp.py`는 `--camera-follow --pan-sign 1 --no-camera-stream --port 15104 --quest-port 15103`으로 실행된다. 기존 non-camera Mink receiver는 보존/공존하고, manual keyboard PTZ나 다른 camera-follow 옵션은 계속 fail-closed한다. locomotion의 UDP 55070/55074 READY·STALE zero-hold는 변경하지 않았다.

별개로 2026-10-02 16:00:39 G1 kernel에 `uvcvideo: Non-zero status (-75) in video completion handler`가 실제 기록됐다. 따라서 USB/UVC 불안정은 두 번째 독립 원인이며, 기존 Link 2 Pro device rediscovery/set_ctrl retry 로직을 유지한다.

## 2026-10-02 G1 live Insta360 / SSH 검증

G1 closed network `192.168.10.165`에서 실기 확인했다. Insta360 Link 2 Pro는
`/dev/v4l/by-id/...video-index0 -> /dev/video6`, metadata `video-index1 -> /dev/video7`이며
D435i는 `/dev/video0..5`로 분리된다. index0은 1920x1080 MJPEG 30/60 fps를 지원하고
30 fps 설정 실캡처에서 camera-side 약 30.3~31 fps를 확인했다. PTZ receiver는
`--camera-follow --pan-sign 1 --no-camera-stream --dry-run`으로 정상 기동하고 영상 장치를
점유하지 않은 채 Quest 입력 전 `WAIT_ZERO`로 대기한다.

현재 PC의 `C:\Windows\System32\OpenSSH\ssh.exe`는 `ssh -V`도 정상 동작하지 않는
실행 불능 상태였지만 G1/키 문제는 아니었다. `tools/g1_ssh_login.py`가 OpenSSH를 실제
health-check한 뒤 자동 탐색에서 깨진 Windows OpenSSH를 건너뛰고
`C:\Program Files\Git\usr\bin\ssh.exe`를 선택하도록 수정했다. `SSH_EXE`가 있으면
그 경로를 엄격히 사용한다. 현재 자동 선택값으로 G1 key probe PASS, 통합
`--check-only --no-groot-actuation --no-unity` PASS.

카메라 전송 성능은 closed-network Wi-Fi에서 camera 자체 30 fps와 분리해 기록한다.
직접 MJPEG->SSH는 약 27.7 fps, 현 G1CM->SSH->PC 경로는 약 24.6 fps였다. G1 wlan0은
-37 dBm / 1.2 Gbps PHY였고 eth0은 1 Gbps Full Duplex link-up이지만, PC Realtek Ethernet은
당시 Disconnected였다. 따라서 정확한 30 fps end-to-end 검증은 유선 `192.168.123.164`
경로 연결 후 다시 측정한다. 15 fps 이상이라는 기존 최소 체감 목표는 현재 무선에서도 넘는다.

## 2026-10-01 BAT 카메라 추종 자동 시작

기본 BAT의 launcher가 camera_follow worker도 시작한다. Ubuntu 수신부는
--camera-follow --pan-sign 1 --no-camera-stream 옵션이다. Insta360 Link 2 Pro 영상은
별도 camera worker가 /dev/v4l/by-id/*Insta360*video-index0을 단독 소유해 1920x1080
MJPEG 30 fps를 재인코딩 없이 기존 G1CM/TCP 5011로 보낸다. Unity PiP는 HMD-follow다.
동일한 원격 프로세스는 재사용, 다른 옵션/수동 키보드는 보존하고 오류 표시.
SSH stdin 종료 시 이번에 생성한 카메라 자식만 정리한다. 로봇/GROOT 동작은 변경 없음.
--check-only는 기존대로 실행 없이 계획 검사. 2026-10-02 실기에서 Insta360 discovery/capture, PTZ dry-run, SSH transport 및 통합 check-only까지 검증함.

## 2026-10-01 Quest 카메라 pan/tilt 실시간 UDP

압축 대기 시간 이후 Windows HMD pitch heartbeat와 gateway passthrough를 추가.
위쪽 양수 elevation → quest_pitch_deg → unity_quest_pitch_deg. 기존 yaw/이동/팔
계산은 유지. Ubuntu receive_mink_ik_udp.py는 별도로 pan/tilt 구현 및 테스트 완료.
BAT의 위임 경로 launcher에 실행 명령을 표시하며 자동으로 카메라 추종을 시작하지 않는다.
실행 순서는 docs/QUEST_CAMERA_PAN_TILT_20261001.md 참조. Unity/gateway 재시작 필요.

# G1 Teleop Current Handoff

최종 갱신: 2026-10-07

## 현재 실행

```bat
START_G1_VR_TELEOP.bat
```

BAT는 bundled `runtime/python/python.exe`로 `tools/G1_PORTABLE.py teleop`을 호출하는 3줄짜리 shim이다.

2026-10-06 standalone 실기에서 HMD tracking, Oculus XR, Insta360/PiP는 정상이나 `OVRHand` 좌/우가 세션 전체에서 `tracked=false`, `high_confidence=false`였고 시작 로그에 `Failed to set multimodal hands and controllers mode!`가 기록됐다. 따라서 Windows standalone은 기본 teleop 경로에서 제외하고 `--standalone` 진단용으로만 유지한다. 현재 기본 사용자 경로는 Unity Editor를 launcher가 자동 실행하고 `Library/G1TeleopAutoPlay.request`를 Editor-only helper가 소비해 자동 Play mode로 진입하는 방식이다. 사용자는 Play 버튼을 누를 필요가 없다. 최종 제품 목표는 Quest APK가 HMD/양손 tracking을 on-device에서 수행해 PC Portable로 pose를 전송하도록 바꾸어 운영 PC의 Unity Editor 의존성을 제거하는 것이다. 일반 실행은 camera worker와 onboard GROOT pair도 통합하며, 새 GROOT supervisor를 시작할 때만 local console에서 `ACTUATE` 확인을 요구한다.

2026-10-06 Ethernet portability도 일반화했다. `CONFIGURE_G1_ETHERNET_ADMIN.ps1`/`RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1`는 더 이상 ASIX AX88772A 이름을 하드코딩하지 않고 공통 `G1_ETHERNET_ADAPTER.ps1` selector를 사용한다. 자동 configure는 물리 non-virtual 802.3 NIC만 후보로 하며 이미 `192.168.123.99/24`인 NIC를 우선, 아니면 링크가 Up인 유선 NIC가 정확히 하나일 때만 선택한다. 자동 restore는 G1 IP가 설정된 물리 NIC를 링크 상태와 무관하게 찾는다. 후보가 여러 개거나 식별이 불가능하면 fail-closed하고 `--interface-index`를 요구한다. 기존 IPv4/DNS snapshot·검증·rollback transaction은 그대로 유지한다. teleop host 선택은 기존대로 `192.168.123.164` 유선을 먼저 시도하고 폐쇄망 `192.168.10.165`로 fallback한다.

2026-10-01 실제 G1 로그에서 첫 통합 버전의 원격 실행 실패 원인을 확인했다. 기존 launcher가 `ssh -T`와 remote background child를 사용해 두 프로그램 모두 interactive-terminal 검사에서 종료됐다: actuator는 `walk keyboard requires an interactive terminal`, heading controller는 `controller requires an interactive terminal`이었다. Portable Python 자체의 문제가 아니다.

현재 contract는 예전에 성공했던 수동 SSH 2개 구조를 자동화한다.

```text
SSH/PTTY A (-tt), foreground:
  cd ~/groot_onboard_runtime
  python3 -u tools/g1_omni_heading_controller.py --yaw-sign -1

SSH/PTTY B (-tt), foreground:
  cd ~/groot_onboard_runtime
  ./build/groot_balance_actuator --normal --enable-actuation --acknowledge-harness --accept-handoff-risk --supervisor-off --external-controller --interface eth0 <duration-mode>
```

각 remote process는 통합 세션 owner ID로 태그된다. 정상 종료는 main manager 또는 GROOT console에서 **Enter**를 눌러 요청한다. supervisor가 자신이 시작한 actuator에 먼저 SIGINT를 보내고 controlled damping 완료를 최대 12초 기다린 뒤 heading controller에 SIGINT를 보낸다. 정상 종료를 위해 창의 X 버튼으로 강제 종료하지 않는다.

Actuator duration은 remote binary capability를 자동 검사한다. `--unlimited-duration`을 지원하면 무제한을 사용하고, 아직 지원하지 않으면 현재 binary 호환을 위해 `--duration 300`으로 fail-compatible 동작한다. G1 onboard source용 패치는 `tools/GROOT_ONBOARD_UNLIMITED_DURATION.patch`에 있다. 이 패치는 NORMAL 모드에만 unlimited를 추가하며 signal/emergency damping은 유지한다.

`--check-only`은 remote login/actuation을 하지 않는다. 기존 observation-only 동작이 필요하면 `START_G1_VR_TELEOP.bat --no-groot-actuation`을 사용한다. exact existing remote process는 보존하고 다른 옵션/duplicate는 자동 종료하지 않고 fail closed한다.

## 2026-10-07 Omni 미연결 수신 지원

G1 onboard `tools/g1_omni_heading_controller.py`가 PC의 최초 Omni `WAIT` 상태를 잘못 거부하던 문제를 수정했다. Omni를 처음부터 연결하지 않아도 정상적인 최신 양팔 목표는 처리하며, 이동·회전 명령은 0으로 유지한다. 정상 Omni 입력의 시간·보정·수치 검증, 양팔 입력 검증, 재연결 시 heading reference 유지, C++ Balance/Walk 로직은 바꾸지 않았다. 임의의 잘못된 Omni 데이터를 미연결로 간주하지 않는다.

원본 백업 후 G1 파일 한 개에 반영했고 native self-test 및 backend 288/hardware 44 테스트를 통과했다. 정상·stale 입력 1,000건과 양쪽 yaw 부호의 기존 제어 루프 출력도 수정 전후 동일했다. 실제 모터 구동은 수행하지 않았다. 저장소/Portable용 source mirror는 `tools/onboard/g1_omni_heading_controller.py`이며 Windows launcher가 실행하는 새 worker가 아니다. 현재 상태와 원본/설치 해시, rollback, 미검증 범위는 `docs/G1_OMNI_OPTIONAL_VALIDATION_20261007.md` 참고.

## Portable Python

- CPython Embedded 3.11.9 x64 bundled
- exact 16 package pins bundled
- no system Python
- no `py -3.11`
- no `.venv-teleop`
- no runtime pip repair
- `RUNTIME_MANIFEST.json`으로 base/core/package contract 검증

다른 Windows PC로 옮길 때 프로젝트 폴더 전체를 복사하면 Python 환경도 같이 이동해야 한다.

## Bilateral IK

- 14 arm joints, one MuJoCo configuration, left/right tasks solved in the same QP
- live position task rate: 12.0 s^-1
- live orientation task rate: 1.5 s^-1
- live proximal/wrist velocity caps: 150/180 deg/s
- live tracking acceleration: 300 deg/s^2
- shoulder yaw comfort: +/-15 deg, cost 1.2
- wrist-rotation proximal damping scale: 14.0
- staged return remains conservative: proximal/wrist 90/180 deg/s, acceleration 90 deg/s^2, jerk 1.28 rad/s^3
- tracking-to-return prefers a checked 90 deg/s^2 stop; an unsafe slower alternative never discards the verified tracking tail. That inherited tail can retain the tracking envelope until rest. Above-return-cap speed is stopped before seeding the conservative return generator.
- compute 60 Hz

### 2026-10-06 low-latency split tracking

Status: **OFFLINE_VALIDATED_LIVE_UNVERIFIED**. Detailed gates and limitations: `docs/G1_SPLIT_TRACKING_VALIDATION_20261006.md`.

Single-rate `1.5 -> 3.0` was rejected: pure wrist rotation pulled proximal joints to about 18 deg and violated the existing `<10 deg` wrist-dominance gate. The accepted architecture therefore splits position and orientation into two FrameTasks instead of raising one shared SE(3) gain.

Reference session: `logs/test_results/bimanual/unity_20261006_153832_043972.jsonl`.

Before this change, exact replay of that session produced about 500/516.7 ms simulated wrist lag (L/R), 66.73/70.22 mm mean position error, and 10.963 mm minimum clearance. The implemented split controller replays the same inputs at 150.0/166.7 ms simulated lag, 40.37/42.55 mm mean error, 11.147 mm minimum clearance, 23 braking ticks, zero solver-error ticks, 129.15 deg/s peak proximal speed and 156.91 deg/s peak wrist speed.

The earlier ~105 ms LowState trajectory-alignment estimate is not an independently measured physical/transport delay: the source and PC clocks are not synchronized, and minimum-offset correction removes excess jitter rather than proving absolute latency. Do not add it to the new replay lag to claim 255/272 ms end-to-end performance. The timestamp-based, fixed-comparison-window replay fit is 165/180 ms (L/R); the earlier sample-index method remains 150/166.7 ms. Both are simulated trajectory-alignment estimates, not live G1 measurements. See `docs/G1_SPLIT_TRACKING_VALIDATION_20261006.md`.

Historical September fixtures remain isolated by `backend/tests/bimanual_replay_profiles.py`; exact historical replay still uses the old combined SE(3) task/profile.

## Camera

```text
Insta360 Link 2 Pro UVC MJPEG
1920x1080 / 30 fps target
stable by-id video-index0 auto-discovery
PiP parent = HMD CenterEyeAnchor
PTZ follower uses --no-camera-stream
SSH transport only
```

## Regression gates

- backend current regression
- hardware Omni/Ruckig regression
- `G1.zip --replay --strict` exact replay
- portable relocation check from a different directory
- 남은 사용자용 BAT 4개 전수 embedded-shim 감사
- operator runtime source의 machine-local Python 경로 금지

2026-09-29 전체 archive validator 추가 후 재검증: backend 219/219 PASS, hardware 38/38 PASS,
code index PASS, no-system-Python startup check PASS. Backend 회귀는 `.git` 없는 export에서도 실행 가능하다. `G1.zip`은 bimanual exact replay뿐 아니라 Quest/Unity, Omni, LowState, PC→G1 observation, G1→GROOT까지 전체 offline strict validation PASS했다.
상세 근거: `docs/G1_ARCHIVE_FULL_OFFLINE_VALIDATION_20260929.md`.

2026-09-30 R1a 재검증: backend 223/223 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` PASS, bimanual exact replay state/reason/accepted mismatch 0, max q difference `2.00062189037453e-13 rad`. 변경 C# 3개는 Roslyn syntax error 0. Unity batch validator는 코드 오류가 아니라 기존 Package Manager IPC startup failure로 실행 전 종료되었고, 오래된 `.csproj` 직접 build는 이미 삭제된 과거 C# 파일 4개를 참조해 유효한 semantic compile gate가 아니다.

2026-09-30 R1c 재검증: backend 226/226 PASS, hardware 38/38 PASS, `G1.zip archive-validate --strict` exact PASS, accepted/state/reason mismatch 0, max q difference `2.00062189037453e-13 rad`. `g1_bimanual_safety.py`가 hard geometry clearance, Mink collision bound, acceleration/joint-limit/yaw braking bounds와 checked stop-tail을 소유한다. `g1_bimanual_sim.py`에는 기존 테스트/진단 호환용 `limits`, `clearance()`, `checked_stop_plan()` proxy/alias만 남긴다.

## External dependencies

현재 Quest Link 양손 실기 개발 경로의 외부 dependency는 Unity Editor, working OpenSSH, Quest/Link tooling·driver, Omni Connect, G1 network다. launcher는 `ProjectVersion.txt`의 `m_EditorVersion`을 자동 탐색하며 `UNITY_EXE` override를 지원한다. 사용자는 Editor를 직접 조작하지 않는다. `--standalone`은 손 tracking이 필요 없는 진단용이다. 최종 운영 목표는 Quest APK on-device tracking으로 Unity Editor를 runtime dependency에서 제거하는 것이다. OpenSSH는 Windows/Git 구현을 health-check해 선택하며 `SSH_EXE` override를 지원한다. Python package dependency는 project-local로 고정한다.

## Upper-body simplification discussion

상체 제어 구조를 수정하거나 gain/limit를 재튜닝하기 전에 `docs/G1_UPPER_BODY_CONTROL_SIMPLIFICATION_AUDIT_20260929.md`를 먼저 읽는다. 2026-09-30 R1a에서 dead Python members를 제거하고, current `unity_display_world_v1` target mapping을 `g1_bimanual_target.py`, historical relative input을 `g1_bimanual_legacy_input.py`, 현재 tuning을 `g1_bimanual_profile.py`로 분리했다. R1b에서는 dormant right-arm sender/preview 분기를 제거했고, R1c에서는 hard safety 계산을 `BimanualSafetyEnvelope`로 이동했다. 이후 heuristic ablation을 완료했다. torso target projection은 연속 입력에서 약 296 mm hidden target jump를 만들면서 hard safety와 역할이 중복되어 제거했다. elbow assist, wrist priority, shoulder comfort, dynamic orientation priority는 제거 시 posture/clearance/braking 또는 joint allocation이 악화되어 유지한다. shoulder-yaw envelope는 ordinary trajectory 영향은 없었지만 independent fallback이라 SafetyEnvelope 안에 유지한다. 실제 replay profile에서는 QP solver 자체보다 checked stop-tail/geometry 검증이 지배적인 계산비용이다. 다음 단계는 gain 재튜닝이 아니라 safety hot path를 하나씩 offline ablation하는 것이다. checked stop-tail은 마지막 안전 gate로 유지한 상태에서 앞단의 겹치는 constraint가 실제로 무엇을 추가하는지 측정한다. Safety ablation에서는 collision stopping-headroom과 joint-limit stopping bound 제거를 REJECT했고, MuJoCo 3.11-era zero-distance QP witness repair는 current 3.12 runtime에서 G1.zip/5,000 synthetic posture 모두 0 activation이며 제거 후 exact replay PASS라 제거를 ACCEPT했다.

## 작업 원칙

1. BAT는 shim 외 로직 금지.
2. 새 Python dependency가 필요하면 bundled runtime과 manifest를 같이 갱신.
3. 기존 dirty/untracked를 reset/clean하지 않는다.
4. 변경 후 embedded runtime에서 회귀 실행.
5. relocation test 없이 portable 완료로 판정하지 않는다.
## 2026-10-06 G1 dedicated Ethernet address drift

On the Desktop portable runtime, the dedicated ASIX adapter was initially up at manually assigned `192.168.50.2/24`, while the G1 wired endpoint remained `192.168.123.164`. The existing config helper's read-only snapshot failed because this Windows build exposes DHCP state only in ActiveStore, not PersistentStore. The adapter later showed `192.168.123.99/24` and TCP/22 to G1 was reachable from that source; the time/cause of the address change was not established. The teleop dispatcher now checks the dedicated ASIX interface before any worker or motor-owner launch and requests UAC repair only for auto host selection with a connected adapter lacking `192.168.123.99/24`. The transaction verifies G1 TCP/22 after the change and attempts rollback to the previous IPv4/DNS settings on failure. This code is network-only; physical robot execution was not used as validation.

Validation: 5 new offline auto-repair tests and 49 existing portable/launcher/dependency tests passed; PowerShell parser and code index checks passed. The four changed runtime scripts were copied into `C:\Users\user\Desktop\G1_Teleop_Portable` after confirming each prior portable copy matched the source commit, and copy hashes were verified. Read-only checks there reported `needs_repair=None`, selected wired host `192.168.123.164`, and a matching `192.168.123.99` adapter snapshot. The elevated address-change/rollback path could not be exercised while the live address was already correct; actual teleop and motor control were not launched.

## 2026-10-08 Quest native APK input observation foundation

User authorized the first migration stage: native Quest hand/head tracking to a dedicated PC observation recorder. Created isolated worktree `C:\Users\user\Documents\Codex\2026-10-08\g1-quest-input-apk` from verified origin/main `ebb0fa581b5c33f7c0b3bc716d955b108118534b`; compared existing worktrees and preserved the canonical dirty DevAgentSettings asset (SHA256 `B6E9370ED187FB9012728C26989D6A92EE0DCDEEF89F586BB771DF2FCFC2900F`). Existing Editor hand tracking remains the working operator path; do not claim the Windows EXE raw-hand failure has been fixed.

Added an independent APK scene/builder with SDK hand/head tracking and wrist IDs selected by actual legacy/OpenXR skeleton type. APK uses UDP **55100 only**, LAN discovery with a unique receiver requirement, target 60 Hz latest-pose sampling, and recorded-sample ACK freshness. Added Python stdlib receiver, fail-closed schema/order/nonfinite validation, original JSON + PC monotonic timestamp + sequence-gap JSONL recording, and install/record BAT shims. No existing IK input/control ports, Omni path, G1 SDK/DDS or command construction changed. PC clock and Quest clock are **not synchronized**; ACK is PC validated/buffered observation only. See the self-contained `docs/QUEST_INPUT_OBSERVATION_20261008.md`.

Actually executed: observer generated-fixture tests **15/15 PASS**, including real PC UDP loopback; existing real C# skeleton enum/mapping compile test **1/1 PASS**; PowerShell installer parse PASS; bundled Portable Python start/stop smoke PASS; existing tracked hardware/backend/tools/teleop/SampleScene/model preservation PASS. Unity **6000.5.4f1 Android ARM64 IL2CPP Release build succeeded**, SDK editor-agent credential-removal guard ran, AAPT manifest confirmed hand tracking/internet permission and API 32/36. These are local/build checks, not measured Quest/G1 acceptance.

Local APK: `C:\Users\user\Desktop\G1_Teleop_Portable\Builds\Quest_input_observation_20261008\G1QuestInputObservation.apk`, **60,865,008 bytes**, SHA256 `46FE0CC63B40B413D952A17177059ADEFF0BB1DC196F1715A2E5A4D88373AAC7`. APK/build logs are ignored local artifacts, not in Git. Observer + record/install shims and the guide were added to Portable only after checking destination collisions and verifying copy hashes. Original live Unity scripts/scenes were not overwritten.

Remaining: user connected USB but could not find debugging approval. Windows sees Meta USB interfaces; **ADB device list is still empty**, so no install or native hand/network test has occurred. Official setup is the phone Meta Horizon app → headset → Headset Settings → Developer Mode, then approve USB debugging inside Quest (Developer → MTP Notification if prompt is absent). User guidance source: `https://developers.meta.com/vr/documentation/unity/unity-env-device-setup/`. Once authorized, install the APK, exit Link, run native app on the same LAN as PC recorder and confirm actual head/left/right tracking + raw samples. Only after that connect a PC Unity network adapter to existing IK; full Quest robot/camera rendering is a later migration stage. No G1 connection, gain change, publisher, motor output, or hardware validation occurred.

## 2026-10-08 Continue working Editor path; APK and packaging deferred

User cannot access the Quest owner account and chose to prioritize functionality in the existing Unity Editor + Link path. APK migration, source-concealing packaging and USB deployment preparation are deferred. Keep the independent APK foundation; do not replace the working Editor input pipeline. Do not distribute local credentials/tokens.

Fetched origin/main and compared canonical/other worktrees at `7a54eddafcd1412fc91fedcad0d92289219c899a`; canonical local DevAgentSettings modification remains untouched. Documentation continuation is isolated in `codex/g1-editor-continuation-20261008`.

Actually executed on the current Portable: `G1_PORTABLE.py check-runtime --pc-only` PASS and `teleop --check-only --no-groot-actuation --host 192.168.123.164` PASS. Neither starts Unity/workers, performs SSH login, initializes camera SDK or starts a motor controller. Executed launcher, Omni transport recovery and real C# skeleton-mapping regression modules: **41/41 PASS**. These checks do not establish live Quest/Omni/G1 acceptance.

Inspected existing Portable session `teleop_background/20261007_172058_852840`: arm recorded tracking → returning(pinch) → ready; Omni recorded repeated connection TimeoutError retries. At the current read-only check no Omni Connect process or TCP 32123 listener was present, and Unity Editor/teleop Python workers were not running. This explains why a live Omni test cannot begin in that snapshot; it does not prove the cause of the historical session timeouts. Next: confirm available devices, start Omni Connect, verify fresh WebSocket input, then check Editor bilateral/Omni/camera/LowState flow without starting a new motor owner. Do not change IK, gains, limits or transport merely to mask absent hardware/services.

After the user started Omni Connect, verified TCP `127.0.0.1:32123` listening and a read-only 5-second WebSocket capture: 476 valid messages, zero parser rejects, receipt rate 95.40 Hz over first/last samples, max receipt gap 148.78 ms. Last sample was stationary mx/my=0 with armYaw=112.75 deg. Saved original messages in Portable `logs/test_results/omni_connection_check/raw_20261008_103006_855260.jsonl`; no G1 transport created. A separate 8-second existing clocked gateway dry-run at 60 Hz with a local alignment receiver on diagnostic port 55076 completed: 477 ticks, 728 raw messages, 216 processed-new samples, 512 superseded raw messages, 3 missed processing deadlines, no reader/transport error. Unity was not running, so alignment correctly remained WAIT with no offset capture and zero mapped velocity. These are stationary Omni receipt checks, not a directional walking test or proof of 60 Hz fresh output. The diagnostic receiver stopped after the bounded check; live integrated alignment must use the normal launcher port.

Continued live PC input session `teleop_background/20261008_103713_383781` with only arm/Omni workers and Portable Editor; no sender, camera, GROOT or motor publisher. Correction: the current same-scene v5 path requires a real LowState start snapshot even for PC input testing. Missing measurements blocked engage. After user connected G1, started only the existing SSH `rt/lowstate` subscriber bridge; its first stream ended, then reconnected and verified fresh Unity feedback. User subsequently engaged and pinched; arm log records tracking → returning(pinch) → ready. LowState subscriber logs are in Portable `logs/test_results/lowstate_view/20261008_104501_25932.jsonl` and `20261008_105620_18700.jsonl`; these do not prove actuation/physical tracking.

User saw green markers move in steps. Measured this tracking interval: 442 IK ticks, tick p95/max 14.65/22.76 ms, state gap p95/max 31/47 ms; checked preview had 71 distinct updates (~9.16 Hz), preview gap p95/max 125/141 ms. The existing preview worker intentionally submits at 10 Hz. Integrated launch uses the same path and does not remove this stepping by itself.

Added display-only `G1GoalMarkerInterpolation`: interpolate positions from the currently displayed point to each new checked prefix with observed update interval clamped to 50–150 ms. First/gapped frame snaps; duplicate source sequence does not restart interpolation; reversed/nonfinite data resets; positions never extrapolate beyond the endpoint. Existing 200 ms source-age hiding, tracking state gate and outgoing q/input/IK/LowState contracts remain unchanged. Interpolated visual segments are not new checked IK trajectories or motor commands; added display smoothing can add up to 150 ms of visual convergence and does not reduce actual IK latency. Rotation stays sourced from the original checked preview.

Validation: real helper compiled/executed in C# fixture (bounds, duplicate handling, source-array preservation, gap/reset/nonfinite/backward clock); existing preview and marker regressions also run. Portable sender baseline matched HEAD after line-ending normalization; copied only sender/helper/meta with a prior sender backup and SHA256 post-checks. Unity's actual Editor response-file Roslyn semantic compilation of the changed runtime assembly PASS (exit 0), output isolated under Portable `logs/test_results/goal_marker_interpolation/20261008/compile`. Initial fixture invocation errors were compiler syntax/float literal and sibling-test import issues, repaired before acceptance. User confirmed Play stopped before copy. Actual visual smoothness remains to be checked by the user; no physical G1 control was run.

### Superseding decision: green sphere is current IK input, not a preview

User clarified the green marker must show the current IK target without the look-ahead/display smoothing delay. Removed the just-added interpolation helper/test and all marker interpolation/preview gating from the sender. In same-scene mode `TryGetIkTarget` now returns `leftWorldTarget/rightWorldTarget`, sourced from each feedback's `*_ik_target_world_m`; right orientation uses the matching `right_ik_target_world_wxyz`. These are effective targets actually supplied to the current solver, not future FK, actual measured wrist position or a reachability certification. Keep tracking/fresh command/valid-target gates: invalid/braking/return targets are not shown. No IK or outgoing command construction changed, and no extrapolation/display filter remains. Optional preview backend data is retained for compatibility but does not drive these green markers.

Updated existing Unity edit-mode validation to require current IK input position/orientation, independence from optional preview validity, and unchanged outgoing packet/joint array. Applied sender/validator to Portable while Play was stopped; prior interpolating sender/helper are backed up only in local logs, and the added runtime helper/meta were removed. Unity actual response-file semantic compile PASS for both runtime and Editor assemblies; artifacts under Portable `logs/test_results/goal_marker_interpolation/20261008/current_goal_compile`. Current preview/marker Python regressions **29/29 PASS** after updating the superseded marker-source architecture assertion. Unity edit-mode validation source compiled but its engine-executed checks were not run in this step. Earlier 30-test interpolation candidate is superseded, not the current accepted behavior. Current target changes still arrive at the actual backend feedback rate (60 Hz scheduled, not guaranteed); eliminating preview gating does not prove zero end-to-end latency. Final visual verification of this correction remains pending.
### 2026-10-08 Engage blocked again: measured-start freshness and visible preparation

- Latest operator attempt in `unity_20261008_103713_383781.jsonl` did not engage: last 45 seconds with fresh input contained 811 `waiting_fresh_measurement`, 494 `settling_measurement`, and only 58 `synchronized` ACKs. Editor also recorded hand `tracking-unavailable` at the end; hand alignment is a separate requirement. Backend readiness alone does not imply engagement readiness.
- Read-only LowState bridge remained alive. Its excess-delay estimate rose from median 8.93 ms in the first 600 samples to median/p95 71.05/78.35 ms during the last attempt. This plus local receipt/render processing can exhaust the unchanged 100 ms start freshness budget. PC/source offset changed about 75 ms over this connection. Clock drift versus transport latency is not yet isolated; these are not absolute synchronized latency measurements.
- Stopped only our owned read-only bridge session and restarted it, without command publisher or motor output. New log `lowstate_view/20261008_113112_44248.jsonl` resumed receipt, observed about 20 ms excess-delay estimate after restart. This rebaseline is a diagnostic/recovery step, not a permanent clock-alignment correction or hardware acceptance.
- Added a head-visible preparation card above the camera while model/IK/measured initialization is pending, with separate Korean loading, connection, fresh-measurement, settling, and head-alignment reasons. Initializes immediately when the status canvas is created; returns to the existing camera-underlay status location once prepared. No engagement condition, freshness limit, command format, gain, IK behavior, or G1 controller was changed.
- Added tests compiling and running the actual pure C# preparation message method through PowerShell, including stage priority and clearing at ready; source guard verifies UI does not modify command/engagement fields. Final related test run: **38/38 PASS**. First invocation through Python stdin failed the multiprocessing spawn fixture because `<stdin>` is not an importable path; rerun through `python -c` passed. Both Portable runtime and Editor sources semantically compiled using actual Unity Roslyn references. Visual acceptance and successful re-engage after this change remain pending.
- Runtime UI sources backed up before copying; previous green-marker fix retained. No commit/push in this step.
### 2026-10-08 Final marker decision: restore checked IK prefix, increase display scheduling

- Operator successfully engaged after read-only LowState reconnection. Reported green marker followed the hand beyond reachable extension. This was caused by our previous change displaying `effective_target_position`, which is a requested IK goal, not an achieved/checked pose. That marker semantic change is superseded.
- Restored green position/orientation to `G1GoalPreviewState` checked three-step IK rollout; invalid/stale previews hide, never fall back to the requested hand or current wrist. The blue hand remains the operator goal. This is a local checked IK prefix, not a global maximum-workspace solver or proof of physical G1 arrival. Existing prepared-start overlay is retained.
- Changed optional worker submit interval from 100 ms to 1/60 s. Retained one low-priority isolated process, one in-flight calculation, no backlog/no waiting, three-step horizon and 200 ms source freshness. Actual completed result rate is computation-dependent, not guaranteed 60 Hz. Previous operator logs contained 125 distinct preview calculations with compute p50/p95/max 21.79/43.91/56.78 ms; the fixed 100 ms interval was additional delay.
- Restored Editor marker behavioral validation to its original checked-prefix semantics. Related regression run **38/38 PASS**, including held unreachable goal settling without presenting the request as achieved. New cadence/no-backlog test **1/1 PASS**; 39 related tests total. Runtime and Editor semantic compilation **PASS** after installation. No claim of engine edit-mode validator execution, current visual acceptance, or physical robot validation.
- User confirmed Play stopped. Backed up three Portable files under `goal_marker_interpolation/20261008/checked_goal_restore`, installed the source changes, stopped only our local arm/Omni manager and restarted local arm/Omni with no G1 sender, camera or motor controller. New session logs: `teleop_background/20261008_113945_462788`. Read-only LowState subscriber remains separate. Git commit/push not performed.
### 2026-10-08 Latest operator marker audit and Git history comparison

- Audited `unity_20261008_113945_462788.jsonl`: 1,015 tracking samples over 17.781 s; 932 tracking and 83 checked-braking ticks. Successful engage, pinch return, final backend ready recorded. No motor commands from this session.
- Green preview versus effective requested wrist position: left median/p95/max 64.57/203.57/237.95 mm, right 52.41/184.85/222.24 mm. Preview versus PC command FK: left median/p95/max 0.80/7.66/14.45 mm, right 1.08/8.44/19.12 mm. Thus the current short checked prefix is very near the current command wrist and is not a geometric reachable-goal projection.
- Held-goal subset (target stays within 5 mm for the preceding 0.5 s, at least 20 samples spanning >0.45 s): left 129 samples, median/p95/max gap 39.27/202.07/202.83 mm; right 154 samples, 23.80/120.26/121.37 mm. Therefore motion-only display delay does not explain all discrepancy. This subset does not itself establish geometric reachability.
- 490 distinct preview calculations, approximately 29.92 completed updates/s; source age p50/p95/max 32.56/72.25/144.73 ms. Compute p50/p95/max 15.13/39.45/80.77 ms. Control computation p50/p95/max in valid-preview tracking subset 5.93/15.25/28.70 ms. Configured 60 Hz submission is not achieved 60 Hz display, nor a timing acceptance claim.
- `git fetch origin main` confirmed local baseline and current origin/main both `7a54edd`. `2c8ae55` (2026-10-07) introduced the private three-tick checked rollout. `b5bc189` previously displayed the checked stopping endpoint. Archived single-arm `335f62e` used `FeasibleTargetPlanner`/single-arm trajectory; it was a different solver path (including an upstream branch using the current applied trajectory pose), not a global reachable-workspace solve. Do not claim the current bilateral prefix recreates all prior right-arm visual behavior.
- Today's raw-hand display substitution is already reverted. Raising refresh frequency fixes an extra sampling delay, not the spatial semantic mismatch. Next design must distinguish requested hand, geometric feasible goal, and speed-limited command FK; replacing the green sphere with raw hand alone or extending stale preview life would mask this issue. No further controller/display edits or runtime restart in this audit.

### 2026-10-08 Geometric green goal installed; difficult tracking errors remain open

- User authorized fixing the target discrepancy and reducing error, with slower motion acceptable. Work remains in isolated `codex/g1-editor-continuation-20261008`, based on verified `origin/main` / canonical source `7a54edda`. Canonical dirty assets and unrelated worktrees were preserved. No commit/push in this step.
- Supersedes the three-tick green marker above. New `g1_bimanual_geometric_goal.py` computes a **display-only, local geometric IK witness** on a private model with the same coupled-arm collision, joint and shoulder-yaw constraints. Numerical iterations are not physical motion. Position gets priority; orientation is refined while preserving position progress. Every accepted configuration and sampled connecting segment are checked. Partial results explicitly retain residuals; they are not a global workspace boundary or proof that the live controller will reach that pose.
- Green position/rotation now come from FK of that checked witness, schema `g1.bimanual.goal.preview.v2`. Requested blue hand, rate-limited command FK and measured G1 pose remain distinct. No raw-hand fallback, stale lifetime extension or predicted user input. Unity rejects old prefix-schema packets. Worker retains only its last geometric 14-joint seed within the same session/generation; current base/non-arm coordinates are preserved, invalid cached seeds discarded, and cache resets across contexts.
- The separate low-priority worker still has one in-flight job and no queue; the control loop never waits for it or consumes its result. Added a 40 ms **cooperative** solve budget, bounded iterations and cancellation between computations/geometry samples. Only the last fully checked witness is returned on expiration. One native call cannot be preempted; 40 ms is not a hard worst-case latency guarantee. Display source freshness remains 200 ms.
- Exact offline reconstruction of `unity_20261008_113945_462788.jsonl` matched recorded command q with **0 rad** maximum difference and no state/input acceptance mismatches. Six target snapshots and known FK fixtures were tested with long generated holds. At row 15391 the existing controller retained left 32.185 mm / 46.302 degrees after 10 s. A separate static solution with the same frozen body and limits achieves that left pose with 5.307 mm clearance, but no safe path from the current pose to that solution has been established. Do not call all large residuals unreachable, or claim that slower motion alone fixes them.
- Rejected changes, kept only in offline diagnostic scripts: blanket position-rate reductions, balanced position/orientation rates, removal/weakening of posture preferences, strict position-first live QP and Cartesian position-task substitution. Some improve one metric/arm but worsen another. Therefore **live IK tracking tasks, motion caps, safety envelope, gains, command packet/transport and physical controller are unchanged**. Difficult pose/rotation tracking error is **not solved**; geometric marker improvement must not be presented as such.
- At 93 selected recorded tracking samples, bounded geometric recalculation reduced green-to-request median position differences left **66.18 -> 0.181 mm**, right **57.70 -> 0.183 mm**. Samples within 5 mm increased from left 6/right 3 to 62 per arm. This compares previously published asynchronous markers with newly recalculated current-sample geometry and **excludes new worker/transport/display latency**. There were 79 partial and 14 converged pose results, with remaining large-error tails and worse left orientation residuals. Compute median/p95/max: 21.78/40.40/129.82 ms; minimum sampled clearance 5.00012 mm. These are model/input replay measurements, not measured G1 tracking or hardware safety validation.
- Evidence/reproduction scripts are local (ignored logs), under `logs/test_results/measured_ik_error_audit_20261008`: `hold_results.json`, `geometry_results.json`, `witness_results.json`, `basin_results.json`, `slower_results.json`, `cartesian_results.json`, `balanced_rates_results.json`, and `geometric_recorded_comparison_budget40_results.json`. `geometry_initial_diagnostic_unfrozen.json` is a superseded diagnostic, preserved and not used for final claims. Original recordings/failure results were not overwritten.
- Final relevant regression: **105 tests PASS, 0 failures/errors/skips**, using the bundled Python against source tests. Includes 18 new geometric tests, private-state/goal immutability, paired collision, joint ranges, warm-cache reset/fallback, cooperative budget/unfinished-segment rejection, marker freshness, measured start, engage/return protocol and unchanged tracking profile. One of the 105 executes the actual complete C# frame class with 114 assertions through PowerShell 7, using only constructor stubs for Unity vector types; this is not a Unity rendering/JsonUtility test. Real Unity-reference Roslyn runtime and Editor semantic compilation passed. Compile harness initially had wrong source/reference paths; those were corrected before successful compilation, without changing application code. Results: `logs/test_results/geometric_goal_20261008/regression_final.txt` and `compile/`.
- User confirmed Unity Play stopped. Backed up and installed 7 runtime files with SHA256 verification under Portable `logs/test_results/geometric_goal_install/20261008_121231/manifest.json`. Restarted only local arm + Omni workers: `teleop_background/20261008_121244_222873`. Existing read-only LowState session was reconnected to refresh its connection timing baseline: `lowstate_view/20261008_121311_37272.jsonl`. This does not solve clock drift and does not change the 100 ms measured-start freshness threshold. No input sender to G1, audit receiver, motor publisher or actuator process was started.
- Pending: operator visual check of nearby reachable targets, full extension and pinch/re-engage with the new marker. Large residual tracking/rotation needs a separately validated local-basin/path solution; no candidate tried here justified a live tracking change. Hardware validation and final PD gains remain outside this work.

### 2026-10-08 Operator check of geometric marker: persistent offset reproduced

- User reported that green follows blue but stays displaced and requested an IK diagnosis. Frozen input/state snapshot from the currently open `unity_20261008_121244_222873.jsonl` is saved locally at `logs/test_results/goal_offset_audit_20261008/session.jsonl`; active-writer Windows file metadata incorrectly reported zero length, while reading returned approximately 287 MB. No recording was truncated, deleted or overwritten. Frozen subset contains the run metadata and all input/state rows from first input (14,107 rows).
- Current v2 runtime is confirmed by log metadata. All 13 logged Python source hashes match Portable files; four isolated-source files differ only by line endings/BOM, with decoded text equal. No runtime version mismatch was found. This turn made no application-code changes, process restarts or physical robot outputs.
- Observed sequence: tracking -> tracking-lost return -> ready -> re-engage -> pinch return -> ready. There are 1,214 tracking rows with a valid requested goal; 1,208 have a valid displayed preview, representing 599 unique source sequences. Among preview rows, 1,127 are `geometric_goal_partial` and 81 converged. `valid` means a checked geometric witness, **not** that the requested pose was reached.
- For both arms, the blue wrist raw position, outgoing `position_m` and effective IK goal match exactly (0 mm difference in every matched tracking row); engage offsets are zero. The inspected Unity correction/display functions are identities in this path. Actual body yaw was only ±0.16 degrees. A constant engage origin/frame shift does not explain the observed discrepancy.
- Green-to-current-request position error median/p95/max: left **104.13/165.38/180.02 mm**, right **31.08/100.09/109.48 mm**. The solver's own same-source position residual median is left **104.07 mm**, right **25.71 mm**, so substantial error already exists inside geometric IK before display transport. Source age median/p95/max is 33.48/79.88/98.71 ms; worker compute median/p95/max 17.35/41.22/44.88 ms. Age contributes moving-target differences but cannot explain a 134 mm residual with 17 ms age.
- Left pose-held subset is only four samples (preceding approximately 0.5 s within 5 mm and 5 degrees), but retains 133.78 mm median error. At frozen row 5553 / input sequence 1152, the published solver accepted zero iterations, retained a 134.19 mm left residual / 128.18 degree rotation residual, and used 14.56 ms compute, below its 40 ms budget. Its last checked path clearance was 76.92 mm. The exact termination reason is not currently serialized in preview feedback; do not infer `qp_unavailable` versus `local_stationary` from this log alone.
- Exact controller reconstruction at selected rows matches recorded q by 0 rad and state/acceptance with zero mismatches. At row 5772 the published residual was left/right **180.36/71.42 mm**. Re-solving the same requested poses from the engage-reference seed under the same limits, including checked connecting geometry, found **41.57/41.25 mm**, minimum clearance 6.684 mm. Thus the retained geometric seed is unnecessarily poor for both arms in this case. More iterations/removing the time budget did not consistently escape it.
- Source cause identified: `_WORKER_GEOMETRIC_CACHE` is retained indefinitely within a session after valid partial/no-progress results; there is no comparison against an alternate current/reference seed. The prior offline median 0.2 mm result was specific to the earlier sample set and must **not** be generalized to this operator run. The position stage's SE(3)-log translation and joint-range constraints also affect local convergence; neither blanket speed reduction nor a Cartesian-task substitution alone has established a fix.
- Additional offline 12-seed static endpoint searches found best collision-postchecked row 5553 residuals left/right 119.57/46.85 mm, with elbow lower bound 5 degrees and wrist-pitch lower bound approximately -89.635 degrees active. This is evidence of constrained/local stationary solutions, **not proof of global unreachability**, and no joint limits were changed. Exact target reachability and a safe live tracking path remain distinct questions.
- Evidence: `metrics.py` / `metrics.json`, `geometric_stall_analysis.json`, `static_box_feasibility.json` under the local audit directory above. These are PC/model replay results, not G1 measured tracking acceptance. Next correction should compare/recover from stalled geometric seeds within the existing compute budget and preserve explicit residuals; do not change physical gains or slow both arms merely to mask this display-solver problem. Latest visual discrepancy remains open.

### 2026-10-08 Geometric preview cache recovery (local source; visual acceptance pending)

- The user agreed to repair the regression after the source/history diagnosis. Work remains in isolated `codex/g1-editor-continuation-20261008`; `git fetch origin main` still resolves to `7a54edd`. Canonical main's unrelated dirty private settings asset was preserved. No commit/push, remote G1 action, SDK initialization, motor output or controller launch was performed in this step.
- Changed only the **display worker's geometric starting-point selection/recovery**. It compares current-target FK from its previous witness and current command pose, and separately carries a reference/live recovery branch across fresh requests. The entire coupled 14-joint witness is selected; arms from different solutions are never combined. Frozen body coordinates always come from the current snapshot. Actual command IK, velocities/accelerations, gains, joint bounds, collision geometry and transport remain unchanged.
- Candidate ranking uses the existing solver's 1 mm position resolution, requires at least 2 mm improvement in one arm and net improvement above 1 mm, and permits at most 1 mm position difference in the other arm. This fixes a demonstrated veto: left 127.116 -> 41.565 mm improvement was previously rejected because right 41.228 -> 41.250 mm differed by only 0.022 mm. These are display-witness ranking criteria, **not relaxed range/clearance guards**. Rotation is a tie-break only when both candidates already satisfy position tolerance; improved position is not claimed to improve the complete requested pose.
- Primary/recovery searches share one 40 ms cooperative deadline and at most 48 + 16 numerical iterations. A valid unfinished recovery branch can continue on later fresh goals. An expired job hides its result but retains earlier search state for next-request revalidation; it does not refresh an old display timestamp. Session/generation changes reset both branches. Preview feedback now includes termination, selected seed and recovery diagnostics. One native call is still non-preemptible; this is not a hard real-time bound.
- Added portable, compressed real-input regression fixture `backend/tests/fixtures/geometric_goal_operator_20261008.json.gz`: all 618 scheduled display requests from the frozen latest operator session, source SHA256 `31dd21200b55a8cb5d4db6ad330292ac197bd989e66ed6280be648d6ac31f8af`. Each reconstructed snapshot matched original FK, joint/yaw bounds, QP constraints and clearance exactly. Session IDs are anonymized; no local paths or transport credentials are included. This is **actual Quest/Unity input with kinematic model state, not measured G1 tracking data**.
- Matched continuous 30 Hz, 40 ms-budget old/new replay (`new_final_*`): all 618 requests valid; original command q difference **0 rad**, state/input-acceptance differences **0**, range/clearance violations **0**. Minimum sampled clearance 5.090 mm. Position error median L/R **33.40/40.61 -> 18.82/4.46 mm**, p95 **166.40/202.19 -> 136.42/82.78 mm**, maximum **179.97/271.48 -> 163.39/92.09 mm**. Row 5771 improves **178.17/65.49 -> 41.57/41.30 mm**. Six left and fourteen right frames still worsen by over 1 mm; none by over 20 mm. Zero-progress frames fall 193 -> 89. These comparisons use identical input and call schedules, unlike the earlier asynchronous-versus-synchronous selected-snapshot comparison.
- Rotation remains unresolved: right orientation median **44.17 -> 59.64 degrees** is worse, despite lower mean errors. Large position tails also remain. Do not call this restoration of all historical right-arm performance, full-pose convergence, global workspace projection, or validated physical tracking.
- Deterministic replay without wall-clock deadlines uses bounded numerical iterations and preserves the full sequence/cache. The old strict-comparison candidate failed row 5771; the final tolerance candidate passes both-arm <60 mm at that row. A separate held-goal diagnosis recovers a recorded bad seed by the second 40 ms calculation and settles by the third. That hold is generated after an actual snapshot, not a recorded operator hold.
- Actual spawned display-process test, 8 seconds of difficult recorded snapshots: parent 60 Hz / 481 ticks with zero missed deadlines; 214 completed previews (**26.75 Hz**, not 60 Hz), all fresh. Age p95/max **50.26/50.49 ms**, request-call p95/max **0.710/0.805 ms**, parent tick p95/max **1.012/1.223 ms**. No parent q/velocity change or child error. This tests the separate worker, **not full Unity + live IK workload**.
- Local evidence and all failed candidates are preserved under `logs/test_results/goal_recovery_20261008`. The initial terminal test command accidentally imported Portable tests due to embedded-Python search paths; the corrected runner explicitly prepends this worktree and `backend/tests`. A later strict-comparison replay failure and outdated mechanism assertions are preserved separately, rather than overwritten or called successful.
- Runtime installation and operator visual acceptance are pending. A Play-state clarification was requested because installation restarts the existing local input/display worker. Do not run the normal motor-capable teleop launcher for this check. Current tests and final installation evidence will be appended below.
- Final related regression **124/124 PASS, 0 skipped**, including the complete 618-frame real-input fixture, 18 generated recovery-mechanism tests, geometric bounds/segments, private-state preservation, real worker spawn, C# frame behavior, measured-start and engage/return regressions. Result: `logs/test_results/goal_recovery_20261008/regression_accepted.txt` (77.895 s). `git diff --check` passed. No Unity C# source changed in this correction, and no new Unity build/render validation was performed. Final preview source SHA256: `87139e0e239139fc7028c71086e90d116da9283446d4d18322c09ba27cc92f5c`.
- Portable runtime is still the pre-correction version; no input process was restarted in this step. Pending installation is only `MuJoCo_G1_Controller/scripts/g1_bimanual_goal_preview.py`, after backing up and checking its current hash. The existing local arm/Omni manager is session 74729 (PID 23896 when inspected), with read-only LowState separate; verify ownership/current status before any restart. Play-stop response and actual operator visual acceptance are outstanding.

### 2026-10-08 13:37 Portable preview recovery installed after Play stop

- User confirmed Unity Play stopped. Rechecked process ownership and existing file hashes. Gracefully ended only our local arm/Omni manager (session 74729); verified its child processes exited. Backed up and replaced **only** Portable `MuJoCo_G1_Controller/scripts/g1_bimanual_goal_preview.py`. Backup and manifest: Portable `logs/test_results/goal_recovery_install/20261008_133654/manifest.json`. Before SHA256 `336d58bdb0ed24eaa41a3efe769c8a6cd7d2b1bf26fef22f9378edb980867892`; installed SHA256 `87139e0e239139fc7028c71086e90d116da9283446d4d18322c09ba27cc92f5c` matches the tested source. Geometric module and C# v2 contract already match; no Unity asset, project setting, dependency or C# change/recompile was needed.
- Restarted the same **local arm + dry-run Omni only** manager, session 75312. New logs: Portable `logs/test_results/teleop_background/20261008_133714_049776`, recording `logs/test_results/bimanual/unity_20261008_133714_049776.jsonl`. Arm listener ready on loopback 5020; Omni receiving on its observation path. New run metadata confirms the installed hash and `persistent_reference_live_branch`. No G1 command sender, audit receiver, normal teleop launcher or motor controller was started. The manager's generic damping shutdown text does not describe this worker selection; these two workers cannot actuate G1.
- Existing read-only LowState session 45627 had independently ended with `LowState SSH stream ended`; no reader was running when checked. One restart of the existing read-only viewer to `192.168.123.164` also ended without data (`lowstate_view/20261008_133749_44340.jsonl`). Brief TCP/22 probes to both `192.168.123.164` and `192.168.10.165` were unreachable at the check time. No network configuration, authentication setting or controller state was changed. LowState remains disconnected; do not call this a successful measured-start or live operator test. Operator visual acceptance remains pending after G1 connectivity/measurement is available.
- No commit/push in this installation step. The source handoff is updated; canonical dirty work and prior failed evidence are preserved.

### 2026-10-08 14:37 Read-only measurement reconnected for preview retest

- User reported G1 reconnected. Read-only probes found TCP/22 reachable at wired `192.168.123.164`; closed-network `192.168.10.165` was unreachable. Existing local arm/Omni manager remains session 75312, with no command-sender worker. No duplicate LowState viewer was present.
- Restarted the existing `tools/g1_lowstate_view.py --host 192.168.123.164` subscriber only, session **10428**, PID 49244. Log: Portable `logs/test_results/lowstate_view/20261008_143711_49244.jsonl`. Tail check received 29-joint CRC-valid samples, sequence 542, last receive age 16 ms, excess-transport-delay estimate 14 ms, last source gap 0. The delay estimate is not absolute synchronized latency. No new LowCmd publisher or actuation was started, and network settings were unchanged.
- Current arm run `unity_20261008_133714_049776.jsonl` independently confirms preview SHA `87139e0e...`, recovery profile and normal model/listener startup; latest idle state is ready with no solver error. Preview waits for input. Unity Play / operator visual retest has not yet occurred; this is connectivity/runtime readiness only, not visual or physical tracking acceptance.

### 2026-10-08 14:51 Startup waiting: ACK decoding bug and measured pose clearance

- Operator screenshot remained at `IK 연결 기다리는 중`. Inspected existing processes/ports and latest logs without launching any motor-capable path: Unity input reached the local Python backend, and CRC-valid 29-joint LowState reached Unity. This was not a missing IK process or a G1 network failure.
- **Confirmed with actual Unity 6000.5.4f1 JsonUtility** in a separate minimal batch project: explicit Python `session:null` and `body_q_rad:null` decode as an empty string and empty array. The C# revision-0 ACK validator required literal null and silently rejected every pending ACK. This hid the true initialization reason. Fixed only revision-0 empty representation handling; `ready` must still be false, session/body must be absent or empty, and such ACKs can never engage. Revision-positive seed, freshness, range and collision requirements are unchanged.
- Added actual JsonUtility regression cases to `G1MeasuredStartValidation` using the sender's nested Feedback DTO, plus a standalone actual-C# validator regression. The minimal Unity before/after reports are under `logs/test_results/start_wait_20261008/json_probe/`: before explicit-null ACK `Valid=false`; after `Valid=true`, `CanEngage=false`; missing ACK remains invalid. No Play/control sockets in the engine probe. Full scene validator was semantically compiled, not executed here.
- Separate exact replay of this operator attempt found **62/62 initialization attempts rejected for measured-start pose clearance**. Model right hip-pitch geometry versus right wrist-yaw geometry: -2.285 to -2.257 mm, against required +5 mm; left pair approximately 2.62 mm also below the requirement. Authored home/return-waypoint clearance approximately 40.37/57.06 mm passed. Failure-frame maximum speed 0.05485 rad/s and age 39.55 ms satisfy the existing 0.1 rad/s / 100 ms limits. Replay acceptance/state/joint differences are zero. These are geometric-model distances, not proof of physical contact. Evidence/reproducer: `logs/test_results/start_wait_20261008/start_wait_evidence.json` and `analyze_start_wait.py`.
- Preparation UI now names measured-pose/home/waypoint clearance failure, logs its first occurrence, and keeps the last failure visible as a recheck during the backend's settling retry. Readiness and outgoing packet logic are unchanged. No collision margin, IK, gain, geometry, or robot controller change.
- Related tests **25/25 PASS** (actual C# ACK contract, preparation UI, measured-start state machine and marker/input preservation). Runtime and Editor assemblies both semantically compile with Unity's actual response-file references (exit 0); artifacts `logs/test_results/start_wait_20261008/compile`. `git diff --check` passed.
- User reports arms had been close/overlapping and are now separated. This is a new pose, requiring fresh observation; the original failed pose remains preserved in evidence. Backed up and copied only three Unity source files to Portable after Editor logs confirmed Play had exited: `G1MeasuredStartState.cs`, `G1BimanualSimulationSender.cs`, `G1MeasuredStartValidation.cs`. Manifest: Portable `logs/test_results/start_wait_install/20261008_145122/manifest.json`. At 14:52 the live Editor assembly timestamp still predates this copy, so foreground refresh/compilation and a new Play attempt remain pending. Do not claim the operator's engage succeeded yet.
- Existing local arm/Omni manager and read-only LowState subscriber continue; no restart, publisher, actuation, command-sender, or G1 audit listener was added. No commit/push in this step.
- Fresh pose follow-up at **14:52:46**, LowState sequence 54616: current model clearance **27.834 mm**, home 40.373 mm, waypoint 57.063 mm; all 29 joint ranges pass. Last 0.75 s maximum dq 0.07028 rad/s, pose span 0.000348 rad and receive gap 32 ms satisfy existing settling thresholds. Current log replay reaches `synchronized` after 0.360 s with head alignment assumed true. PC receive elapsed 29.88 ms plus bridge excess-delay estimate 26.93 ms totals 56.81 ms at inspection. This resolves the current pose's geometry blocker in offline replay, not a claim of successful Unity engage or physical safety. Evidence: `logs/test_results/start_wait_20261008/latest_lowstate_145246.json`.

### 2026-10-08 Latest operator result and next priority

- User reported the result acceptable and asked what to do next. Inspected the latest actual Unity attempt (measured log `unity_measured_20261008_145436_aa0db4bc3eb64a4a96f4ec312f241ed7.jsonl`, input session `1da3a91d68104c788e1a8a8868fd6862` in the existing arm log). Confirmed READY -> TRACKING -> RETURNING(tracking_lost) -> READY -> TRACKING -> RETURNING(pinch) -> READY. Two tracking intervals, one re-engage; final measured-start synchronized before Play stopped. Do not classify the first return as pinch or claim tracking-loss never occurred. Latest Editor segment has fresh feedback after startup and no matched exception/compile error.
- 1,041 tracking states contain 946 valid preview samples / 410 distinct preview source sequences. **Same-source geometric display solver** position residual median L/R 1.156/1.115 mm, p95 97.60/98.41 mm, max 141.13/125.43 mm. Rotation residual median L/R **22.50/34.30 degrees**, p95 109.18/138.64 degrees. Thus typical position convergence is improved but tail positions and orientation are not solved. These different operator motions are not a matched before/after benchmark.
- Current requested target versus delayed display witness has median gap 15.12/24.61 mm, including motion/transport age. Held-pose selection contains only 6 left / 9 right samples; insufficient for broad stationary accuracy claims. Minimum sampled preview clearance 5.000025 mm. These are PC geometric-display results, **not physical G1 tracking errors or actuation validation**.
- Saved derived tracking subset and metrics under `logs/test_results/start_wait_20261008/accepted_session_tracking.jsonl` and `accepted_session_metrics.json`; original logs unchanged. Next useful work is offline diagnosis of the remaining orientation residual against frame mapping, joint/collision constraints and position-priority solver behavior, using the existing input recording. No immediate additional operator trial is needed for that diagnosis. No new code/runtime/hardware action, commit or push in this audit step.

### 2026-10-08 Offline orientation diagnosis: mapping, solver, and branch selection

- User approved offline investigation of the remaining wrist orientation residual. Reconstructed the latest accepted operator session `1da3a91d68104c788e1a8a8868fd6862`: 4,119 rows, 1,448 input rows; accepted-input/state/joint differences are zero. Exported 504 scheduled private-model snapshots in `logs/test_results/orientation_audit_20261008/latest_frames.json.gz`. These are recorded Quest requests plus reconstructed PC kinematic states, not actual motor-response measurements. Reconstructed synchronous worker caches must not be called the original asynchronous cache, which was not logged.
- Frame audit found no quaternion-order or basis defect: accepted outgoing anatomical rotations match effective IK targets; displayed quaternion errors recomputed against their own source sequence agree with solver residuals within 1.33e-15 rad. Body-yaw rebasing contributed at most 0.25 degrees. Raw sensor wrist axes differ from the deliberately constructed anatomical frame by about 83.29 degrees; this unchanged convention is not evidence of an 83-degree regression. Evidence: `logs/test_results/start_wait_20261008/orientation_mapping_audit.json`.
- Compared current/reference/reconstructed-cache seeds at 40 ms versus 256 iterations without a wall-clock deadline on eight selected latest-session snapshots. Extra time solved one representative (row 3136 left 11.09 -> 0.70 degrees), but seven retained `local_stationary` or `qp_unavailable`. Other representatives reach collision or wrist/elbow constraints. At row 966, a different current seed greatly improves left orientation while keeping comparable position residuals; the existing branch comparator disallows orientation tie-breaking whenever either arm's position exceeds 1 mm. Evidence: `budget_constraint_results.json` in the audit folder. These selected cases are diagnostic, not an unbiased performance benchmark.
- Confirmed a separate native QP tolerance mismatch: on a 177-frame offline replay, 41 position solves reported native success but violated our 1e-7 postcheck, consistent with DAQP's default 1e-6 primal tolerance. Some orientation solves returned much larger violations despite success, so the postcheck must remain. Explicit tighter tolerance/proximal regularization/equality normalization reduced numerical rejections but worsened orientation tails (right p95 97.41 -> 114.84 degrees in that probe). Do not install these rejected numerical variants or claim that removing QP errors solves tracking. Exact failed problems and all rejected results are preserved in `qp_failure_probe*.json` and `qp_exact_ablation.json`.
- `FrameTask`'s translation block is an SE(3)-log task and depends on target orientation away from zero position error. A Cartesian-task alternative and a per-arm acceptance alternative were probed; neither justified a blanket replacement. No coordinate mapping, physical command IK, gain, range, collision margin, runtime dependency, or G1 controller was changed for these probes. Current next candidate is a bounded orientation-aware comparison of complete checked two-arm witnesses; adoption requires both recorded sequences and constraint checks to pass.

#### Completed decisions and minimal correctness fix

- Latest sequences 239/248: the cached witness has roughly 51-degree right rotation residual at micrometre position residual, with both elbow lower bounds and the right shoulder-yaw operational envelope active. Reference-seed solves reduce it to about 28.6--28.8 degrees while keeping both positions within 0.004 mm. This demonstrates a local-branch effect, not proof that the requested orientation is globally unreachable. Collision-checked generated wrist-only FK targets from the same starting pose converge to under one degree in three iterations; this synthetic probe is distinct from measured operator acceptance. Details: `persistent_orientation_limits.json`.
- **Rejected all broad orientation policy candidates.** Compared the old 618-frame and latest 504-frame recordings using complete paired witnesses: broader orientation comparison, always searching on rotation residual, and searching only after stationary/QP failure can improve selected examples but worsen other intervals. A deterministic no-wall-deadline comparator comparison still worsens individual position residuals by up to 4.83/11.55 mm. Forty-millisecond comparisons are additionally sensitive to host scheduling; do not describe their caches or timing as original live traces. Results, exact source copies, and failed runs remain under `orientation_audit_20261008/cache_policy_decision.json` and `cache_policy_comparisons.json`. Do not install these candidates or repeat the same changes as an assumed fix. The orientation issue remains open.
- **One independently reproduced validation omission was corrected in source:** geometric `_checked_segment` now checks `_ranges(sim)`, the same authored-plus-operational shoulder-yaw bounds used for the seed and QP. Previously it checked only authored XML ranges. Native QP numerical residuals could thus pass the final display-witness check slightly outside the operational envelope. Replay captured excursions of 1.01--1.43e-9 rad; these tiny excursions do not explain the large visible orientation error. The existing 1e-9 comparison tolerance and all range values remain unchanged.
- Added three envelope regression tests: previously accepted left/right upper/lower 1e-8-rad excursions now reject; inward segments remain valid; a 1.01e-9-rad boundary excursion also rejects. Added four native-result tests covering 11 cases: native success must still reject nonfinite/wrong-shape results and inequality/equality violations, while a valid equality result preserves tasks/configuration/constraint arrays. These tests exercise the display solver; they are not hardware tests.
- No Portable/runtime file was installed in this turn. The source-only envelope correction needs its usual runtime sync before it can affect the running display, and is not a wrist-tracking fix. No new operator trial, G1 access, motor output, commit, or push was performed. Source preservation manifest covers 17 control/input files; Portable preview/geometric module hashes remain at the previously installed values. Audit fixtures/results are local ignored evidence and will not move between PCs through a normal Git push.
- Final executed regression: **87/87 PASS**, including the full deterministic 618-frame operator replay, geometric/envelope tests, recovery/worker isolation, source-frame/body transforms, runtime publication behavior, and actual-C# ACK/preparation contracts. Log: `logs/test_results/orientation_audit_20261008/final_regression.txt` (72.592 s). `git diff --check` passed; 17 protected control/input source hashes and both installed preview-module hashes were unchanged. These passes confirm the scoped source correction and existing offline contracts, not resolution of all orientation residuals or new visual/physical validation.

### 2026-10-08 Correct green-marker meaning: same exported IK command

- User clarified that the green wrist marker must show the robot's commanded IK target. The independently solved geometric witness introduced earlier does not satisfy that contract because its joint solution is not exported to G1. **Supersede the independent geometric-preview approach for the current world-frame teleop path.** Do not feed that unconstrained-by-live-speed display solver into motor targets. Its source, old tests, rejected candidates and evidence remain available for research but it is removed from the active runtime.
- After each existing `cycle.tick`, one feedback snapshot contains the unchanged checked 14-joint `q_rad` and its existing model wrist FK. The new `command_target` (`g1.bimanual.command.target.v1`, `checked_command_fk`) copies these same FK positions/quaternions. It carries exact input `source_sequence` AND control `feedback_sequence`; input sequence alone can repeat across control ticks. Poses are already in Unity world coordinates, including the same snapshot's body/base yaw. There is no asynchronous body rebase, independent goal solve, extrapolation, or marker interpolation. Checked braking also displays the current checked command, not its future stopping endpoint.
- Unity accepts the marker only with valid joint ordering/data in the same packet, exact matching sequences, and fresh tracking feedback. Wrong/missing/stale command targets hide instead of substituting the operator request or an independently calculated pose. Blue tracked wrists and the LowState-rendered robot remain separate. The legacy `actual_wrist_world_*` packet names still mean PC model/command FK, not actual LowState measurements.
- The marker represents the **PC-exported IK joint target**, including existing command speed/acceleration/collision processing. It does not prove UDP receipt, controller acceptance, final G1-side LowCmd after any additional limiter, or physical arrival. In particular, a moving hand can lead the green marker under the existing limits. Do not restore a more visually responsive but different IK solution merely to close that gap.
- Independent audit of old 618/new 504 snapshot fixtures confirms joint ordering left15..21/right22..28, zero position difference between serialized-command FK and model FK, rotation-matrix error at floating-point scale, and no source-q mutation. Full latest 4,119-row input replay: 1,448 inputs + 2,671 states, command difference **0 rad**, state/acceptance differences **0**. All 1,041 active target frames, including 90 checked-braking frames, match independent FK: position difference **0 m**, rotation-matrix maximum difference **1.33e-15**. Evidence/reproducers: `logs/test_results/command_goal_audit_20261008/latest_full_replay.json`, `verify_command_replay.py`, `command_fk_audit.py`.
- **Remaining actual command-IK issue:** latest 504 scheduled snapshots have command-FK versus mapped operator-goal position median L/R **56.60/54.40 mm** and rotation median **30.28/29.87 degrees**. These moving-input residuals include existing filters/limits and constrained IK; they are not steady-state accuracy measurements, not the previous independent display-witness statistics, and not physical G1 tracking errors. This display correction exposes the actual exported target; it does not claim to repair those residuals. Future accuracy work must evaluate the command IK and measured response separately rather than optimizing a separate green-marker solver.
- Final executed regression after the independent legacy-path review: **65/65 PASS** (20.933 s), including command FK, paired feedback identity, checked braking, measured-start ACK, preparation display and runtime publication checks. The actual C# helper validator executes 88 assertions within that suite. Runtime 18-source and Editor 6-source assemblies also compile with the installed Unity **6000.5.4f1** references, both exit 0. These are semantic compile/offline checks; the full scene validator and visual/physical operator acceptance were not executed. Evidence: `logs/test_results/command_goal_unification_20261008/final_regression.txt` and `compile/compile_report.json`.
- Scope preservation: strict command-FK display is limited to the existing-scene/world teleop path. The separate legacy relative-input path retains its prior position/rotation fallback and display coordinate mapping. Independent review caught and corrected that potential regression before installation.
- Preservation audit: the previous 17-file baseline necessarily differs in four files changed for this task (runner, runtime source manifest, sender display and preview display). The unscoped comparison is retained as `preservation_result.json`; the correctly scoped comparison confirms **13/13 unrelated files unchanged**, with no unexpected changes (`scoped_preservation_result.json`). Command preservation itself is checked by the identical 4,119-row replay, rather than falsely claiming those four edited files retain their hashes.
- Installed only six tested Python/C# runtime files into `C:\Users\user\Desktop\G1_Teleop_Portable`, with original-file backups and SHA-256 comparison for every file. Manifest: Portable `logs/test_results/command_goal_install/20261008_162511/manifest.json`; local source copy: `logs/test_results/command_goal_unification_20261008/install_manifest.json`. Unity's last log records Play stopped. Its foreground asset refresh and rendered marker appearance remain to be checked; semantic compilation alone is not visual acceptance.
- Gracefully stopped only the owned local arm/Omni manager (session 75312), then restarted those same **local-only** roles as session **73988**, manager PID 29528, arm PID 49100, Omni PID 24780. Existing read-only LowState subscriber PID 49244/session 10428 was left unchanged. No G1 sender, motor controller, publisher or normal teleop launcher was started. Arm log confirms model/listener readiness at loopback UDP 5020; Omni reports receiving. New run `unity_20261008_162533_342660.jsonl` confirms `command_target_profile.source=same_snapshot_q_rad_fk` and `extra_ik_solver=false`; the independent preview worker is absent. Helper shutdown text mentions actuator damping generically, but neither selected role owns or operates motors. No commit or push in this step.
- User briefly requested disabling LowState input to IK, then explicitly withdrew it after clarification: **keep the existing measured-start initialization**. No runtime/core changes for disabling it were made; all six installed file hashes still match the validated manifest. Existing v5 remains: a checked inactive measured pose initializes the MuJoCo model; tracking then advances that internal model rather than continuously reseeding from LowState. The isolated four-test v4 experiment is archived under local ignored `cancelled_measured_start_off/`; it is not an adopted mode change. The command-FK marker correction above remains installed.

### 2026-10-08 16:36 integrated startup waits: duplicate LowState source

- Actual operator attempt through `START_G1_VR_TELEOP.bat` reached the IK backend but remained `measured_start:waiting_measurement` / `waiting_fresh_measurement`, revision 0. Unity diagnostics `unity_measured_20261008_163707_7b25e46efb5c4e8a82d3d31cf7e1c984.jsonl` show 230 measured samples, all from old session `b0c5d7c0649d427590f5004f9436a5c8`. Receipt age plus excess-transport estimate min/median/max **155.29/166.00/191.02 ms**; zero meet the unchanged 100 ms initialization criterion. This is not a synchronized absolute latency measurement. Display accepts up to 500 ms, explaining a visible measured robot while initialization still waits. Evidence: `logs/test_results/start_wait_20261008/duplicate_lowstate_1636/diagnosis.json`.
- The earlier assistant-started read-only worker used relative `tools/g1_lowstate_view.py`. Integrated launch recognition only matched absolute paths, so it missed that worker and started a second LowState source (session `8e7b60713ac44d8da491196ed6c1550f`). Its tail had roughly 2--24 ms estimated excess delay, but Unity retained the old session; do not weaken retired-session ordering or freshness checks to hide duplicate senders. The underlying cause of the long-running old stream's delay estimate was not established here.
- Small launcher fix: a running Python worker with a matching relative script name now stops preflight with a clear explanation instead of silently starting a duplicate. Process inventory lacks its working directory, so it is deliberately not treated as a verified reusable process. Absolute-path normal workers retain existing reuse behavior. Separate checkout absolute paths, `-c`/`-m` text and inactive wrapper windows remain unaffected. **40/40 launcher tests PASS**, all process/network operations mocked; no integrated launcher or actuation was executed for testing.
- Installed only the tested launcher file into Portable with backup `logs/test_results/startup_lowstate_fix_20261008/G1_VR_TELEOP_LAUNCH.before.py` and matching hash. User's integrated workers and both LowState readers had already ended. Gracefully stopped assistant-owned local arm/Omni manager session 73988 so the next user launch owns its workers together. No remaining Portable Python worker was found after cleanup. Unity Editor was left open; its log confirms Play ended. Measured initialization and its 100 ms threshold remain enabled; no new robot command, gain, IK, model, or Unity source change. Next operator action is a single normal BAT launch; recovery of readiness still needs that run and is not claimed from offline tests.

### 2026-10-08 16:59 operator acceptance and remaining latency

- User reports this run worked quite well apart from latency. Read existing local logs only; no new runtime, SSH, commands or code changes. Source session `unity_20261008_165938_337404.jsonl`: 2,741/2,741 inputs accepted, one tracking interval (1,147 frames, 19.187 s), one pinch return via safe waypoint/home completed in 5.422 s, final READY. Re-engage was not exercised. No BLOCKED, nonfinite rows, input-timeout return or tracking-loss return. Eighteen checked braking frames (8 QP infeasible / 10 swept clearance) did not terminate the cycle. Static log analyzer failures empty; this is not a current-code replay or physical safety certification.
- Actual PC-side G1 console log confirms preflight PASS, captured-q handoff, 500 Hz writer activation, Balance blend completion and external bilateral targets ACTIVE. Heading console reports arms ACTIVE for tracking and returning, HOLD at ready; reject count reaches 1,341 during initial WAIT/ZERO and then stays constant, stale count 0. PC console tails contain no controlled-shutdown completion marker; no claim about final physical mode. Onboard final CSV was not retrieved.
- Latency evidence: tracking IK tick median/p95/max **5.26/10.32/18.62 ms**, loop period median **16.68 ms**; tracking Unity-input receipt age p95 **31 ms**. Matched tracking diagnostics (90 samples) command receipt age median/p95 **27.02/41.04 ms**; measured receipt age plus excess-delay estimate median/p95 **16.00/31.17 ms**. Single LowState session, 4,896 samples, source sequence gaps 0. These are per-stage receipt/clock estimates, not additive synchronized hand-to-motor latency.
- Latest-receipt measured wrist FK versus command FK during tracking: median left/right **19.61/20.06 mm**, p95 **38.42/45.71 mm**. These include dynamic lag and are not stationary accuracy. No actual wrist quaternion diagnostic is available here, so do not infer physical orientation error. Insta360 stream confirms 1,580 transmitted frames, sampled transmit-fps median **21.0** against target 30; sampled JPEG size median **533.78 kB**. Video throughput/encoding and the existing input filtering are useful next latency diagnostics, but camera causation and full visual latency are not proven.
- Raw-byte runtime metadata differs from this isolated worktree in sim/target/legacy-input/limits hashes. **Later main-sync audit confirms these four differences are CRLF/LF only; code and settings match.** The recorded runtime uses tracking proximal **150 deg/s**, wrists **180 deg/s**, acceleration **300 deg/s^2**, input time constants **60/50 ms**; do not describe it as the older 90/180/60 profile. Existing source/runtime differences were preserved, no overwrite or replay with mismatched settings. Analysis artifacts: `logs/test_results/operator_20261008_165938/session_report.json` and `timing_summary.json` (local ignored evidence).


### 2026-10-08 17:10 KST — onboard logs recovered before power-off

At the user request, retrieved the completed 16:59 session via read-only SSH from `192.168.123.164`. No controller, SDK/DDS, motor output, process stop or mode transition was executed.

- `groot_actuation_1791446382.csv`: 7,234,463 bytes; SHA256 `8ccdc09605bcd05f5436c2a80f8a7ffd90075c0b31b2a365e7269674527939b8`.
- `g1_omni_heading_20261008_165939_5507.jsonl`: 18,761,531 bytes; SHA256 `10ac46a523daa8f7d7502ed66a81ab42fd5098a1049a6db2148c44d4b992d1cd`.
- Saved in `logs/test_results/operator_20261008_165938/g1_onboard/`, with `retrieval_manifest.json` containing exact original paths, retrieval timestamp, sizes and hashes. Both remote before/after hashes and local copy hashes match; remote originals retained.
- Onboard logs are now available for offline latency/tracking analysis; their contents have not yet been analyzed in this retrieval step. Retrieval success does not establish the robot physical mode or shutdown safety.


### 2026-10-08 main publication: Portable/source comparison correction

- Correct the earlier interpretation of different file hashes: all 11 Python files named in the successful 16:59 recording match the current Portable files byte-for-byte; all 11 match this source worktree after CRLF/LF normalization. Four differ only in line endings (sim, target, legacy input, limits). No speed/filter or command-IK setting needs copying or changing. The source already contains tracking 150/180 deg/s and 300 deg/s^2, position/orientation input time constants 60/50 ms. Raw hashes remain useful provenance, but hash inequality alone must not be labeled behavioral drift.
- Compared Git-tracked controller/model, hardware, tools, Unity teleop/editor/scene/package/project settings files that exist in Portable, ignoring only CRLF/LF and excluding private DevAgentSettings. The sole content difference is G1VRBuild.cs: Git already has newer Windows splash/development/build-resource handling. Preserve this Git version; do not overwrite it with the older Portable build tool. Fourteen Git files are absent from Portable: separate Quest/Link observation sources and their metadata/scene, plus onboard command-observer tools. Their absence is not a missing dependency of the accepted Editor teleop session; retain them in Git.
- No new synchronization edit to the runtime was necessary. Publish the already tested command-FK green marker, startup status/ACK handling, duplicate-relative-worker detection, inactive geometric research/regression fixtures and handoff records. Measured initialization stays enabled. This step does not change robot gains, speed limits, models, command ownership or physical robot files.
- Local detailed comparison evidence: `logs/test_results/main_sync_20261008/comparison.json` and `recorded_runtime_comparison.json`. Original operator/onboard logs and large analysis artifacts stay local/ignored; a Git pull does not retrieve those files or the bundled Python/Unity installations. The numeric operator regression fixture under backend/tests/fixtures is versioned and is explicitly not hardware validation.
- An initial regression invocation through Python stdin produced one multiprocessing spawn failure because Windows tried to reopen `<stdin>`. Rerun through a saved script with a main guard; do not change worker code to hide that invocation error.
- Final publication regression: **136/136 PASS, 0 skipped**, using the Portable bundled Python against this source worktree and the saved guarded runner. Includes the 618-frame recorded-input geometric regression, current command-FK contract, C# helper tests, measured-start/preparation checks, runtime provenance and mocked launcher checks. `git diff --check` passes. No Unity/robot actuation was started by this regression. Evidence: `logs/test_results/main_sync_20261008/regression.txt`.
