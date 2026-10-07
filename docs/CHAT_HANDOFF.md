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
