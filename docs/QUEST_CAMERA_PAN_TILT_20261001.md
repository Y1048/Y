# Quest UDP 카메라 pan/tilt 추종 (2026-10-01)

## Windows

`START_G1_VR_TELEOP.bat` → bundled Python → `tools/G1_PORTABLE.py teleop`
→ `tools/G1_VR_TELEOP_LAUNCH.py` 경로를 사용한다. BAT는 기존 3줄 shim을 유지한다.
Unity와 PC gateway를 재시작해야 새 pitch 필드가 적용된다.

Unity HMD forward의 elevation을 `atan2(y, sqrt(x*x+z*z))`로 계산한다.
위를 보면 양수이며 Unity Euler X를 그대로 쓰지 않는다.
`quest_pitch_deg`를 localhost 55074 정렬 heartbeat에 추가하고 gateway가
`unity_quest_pitch_deg`로 live observation payload에 보존한다. yaw와 동일한
실시간 관측 경로를 사용하며 JSONL은 제어 입력으로 읽지 않는다.
구형 Unity가 pitch를 보내지 않으면 None을 보존한다. 이동/팔 readiness는
유지하지만 새 카메라 수신부는 pitch 누락을 표시하며 영점을 잡지 않는다.

## 실행 순서

### 기존 수동 Ubuntu 컨트롤러를 사용하는 경우

Windows에서는 다음으로 시작한다.

```bat
START_G1_VR_TELEOP.bat --no-groot-actuation
```

Ubuntu 터미널 1:

```bash
cd ~/groot_onboard_runtime
python3 tools/g1_omni_heading_controller.py --yaw-sign -1
```

이미 실행 중인 heading controller가 있으면 재실행하지 않는다.
이 옵션은 기존 GROOT 프로세스를 정지시키는 옵션이 아니라 새로 시작하지 않는 옵션이다.

카메라 추종기는 이제 BAT가 자동으로 SSH 실행한다.
`G1_CAMERA_FOLLOW_LAUNCH.py`가 아래 옵션으로 실행한다. Link 2 Pro는 영상 스트림이 열려 있을 때만 PTZ가 동작하므로 추종기가 무음 keep-awake 스트림(`v4l2-ctl --silent --stream-mmap=4 --stream-to=/dev/null`, 출력 전부 /dev/null)을 직접 열고 종료 시 닫는다. Windows PiP는 Unitree 헤드 카메라라 Insta360을 깨우지 않는다. 장치는 자동 탐색(`--device auto`).

```bash
python3 -B -u ~/groot_onboard_runtime/receive_mink_ik_udp.py --camera-follow --pan-sign 1
```

같은 옵션의 추종기가 있으면 재사용한다. 수동 키보드 또는 다른 옵션의 수신기가
실행 중이면 보존하고 오류를 표시한다. 정상 종료하거나 SSH 연결이 끊기면
이번 실행이 시작한 카메라 추종기만 정리하며, 재사용한 프로세스는 종료하지 않는다.
로그는 `logs/test_results/teleop_background/<시각>/camera_follow.log`에 저장된다.
`--show-consoles`에서는 추종기 콘솔을 별도로 표시한다.

### 기본 BAT로 GROOT까지 실행하는 경우

기본 `START_G1_VR_TELEOP.bat`은 기존대로 ACTUATE 확인을 거쳐 onboard supervisor와
heading controller를 시작할 수 있다. 이때 heading controller나 카메라 추종기를
추가로 수동 실행하지 않는다. `--no-groot-actuation`에서도 카메라 추종기는 자동으로
시작하지만, heading controller는 기존 수동 프로세스가 필요하다.
`--check-only`는 계획만 확인하며 추종기/SSH/카메라/모터를 시작하지 않는다.

## 카메라 동작

- `55070 원본 패킷 → 메모리 복제 → localhost 15102 → 카메라 추종`.
- 기존 Mink UDP 5014 수신도 유지. 외부 수신부는 Ubuntu에서 직접 수정되었으므로
  Windows 프로젝트 압축만으로 Ubuntu 변경까지 배포되는 것은 아니다.
- READY + calibrated + fresh이며 yaw와 pitch가 1.5초 안정되면 둘 다 영점 포착.
- 영점 포착 시 카메라 pan=0, tilt=0 명령이 나간다. 이후 상대 yaw/pitch를 추종한다.
- 키보드 방향과 동일: D=pan 양수, W=tilt 양수, C=(0,0).
- `--pan-sign -1`은 pan 반전, 필요시 `--tilt-sign -1`은 tilt 반전.
- 데이터 단절 시 양축 마지막 목표 유지. 카메라 수신부는 로봇 DDS/모터 명령을 보내지 않는다.
- `link2_keyboard.py`와 자동 추종기를 동시에 실행하지 않는다.
- 현재 기존 프로토콜의 fresh Omni/정렬 관측 조건을 사용한다. Omni 관측이 stale이면
  카메라도 마지막 목표를 유지한다. 이번 변경은 하체의 freshness 판정을 바꾸지 않는다.

카메라를 움직이지 않는 확인:

```bash
python3 -u receive_mink_ik_udp.py --camera-follow --pan-sign 1 --dry-run
```

드라이런은 v4l2 호출 및 카메라 스트림 시작을 하지 않는다.
실제 방향은 사람이 HMD를 좌우/위아래로 조금씩 움직여 확인하는 것이 가장 빠르다.

## 검증

Windows gateway pitch 전달/범위/구형 패킷/stale 테스트, runtime C# 컴파일과
Ubuntu의 양축 UDP 드라이런 테스트를 사용한다. 실제 G1/카메라/Unity Play 자동 실행 없음.

검증 결과: Windows gateway 18개, Ubuntu pan/tilt 5개 테스트 통과.
Windows gateway → live audit envelope → Ubuntu parser 통합 확인(yaw=-20°, pitch=+15°) 통과.
Unity runtime C# 컴파일 성공. 기존 DevAgentSettings.asset 변경은 보존했다.

## 로그 확인법 (카메라가 안 움직일 때)

순서대로 확인한다. 앞 단계가 끊기면 뒤 단계는 볼 필요가 없다.

1. Unity `Unity_G1_VR/Logs/Editor.log`
   - `[OMNI ALIGNMENT] ALIGNED`: Quest 정렬 완료.
   - `[QUEST HEAD] aligned=… finite=… hmd_tracked=… focused=… yaw=… pitch=…`: 1초마다 + 상태 변화 즉시.
     `finite=False`(각도 NaN)나 `hmd_tracked=False`이면 Unity가 머리 자세를 잃은 것.
2. PC gateway `logs/test_results/teleop_background/<시각>/omni.log`
   - `[OMNI UNITY GATE] status=READY/STALE`: Unity 하트비트 수신 상태.
   - `[OMNI UNITY REJECT] count=… reason=… raw=…`: Unity 패킷을 거부한 이유(예: `unity_alignment_yaw` = NaN 각도).
3. G1 추종기 `logs/test_results/teleop_background/<시각>/camera_follow.log`
   - `[CAMERA STREAM] keep-awake stream pid=…`: Link 2 Pro 깨움(PTZ는 스트림이 열려 있어야 동작).
   - `[ZERO CAPTURED]`, `[CAMERA CMD] pan=… tilt=… stream=on`: 실제로 보낸 명령.
   - 상태줄 `last_rejection=`: `unity_alignment=STALE`(Unity 하트비트 끊김), `omni_status=…`, `omni_not_calibrated`.

## USB 끊김 대응 (2026-10-02)

- 실측: Insta360이 G1의 USB 2.0 허브(1-2.3, Wi-Fi 동글과 같은 허브)에서 스트리밍/PTZ 중
  `uvcvideo: Non-zero status (-71)` 후 `USB disconnect`되고 다른 `/dev/videoN`으로 재연결됨.
  케이블/전원(모터 구동 전류) 문제로 추정. 전원 공급 USB 허브나 USB 3 포트 직결 권장.
- 추종기는 카메라가 사라져도 종료하지 않는다. `[CAMERA LOST]` → 1초마다 재탐색(`[CAMERA WAIT]`)
  → 새 번호로 `[CAMERA] Link 2 Pro device …` → 스트림 재시작 → 마지막 목표 재전송 `(resend after reconnect)`.
- `~/link2_keyboard.py`도 번호 자동 탐색(인자로 `/dev/videoN` 지정 가능). 백업: `link2_keyboard.py.before_auto_device_20261002`.
- 커널 확인: `journalctl -k --since "10 min ago" | grep -iE "usb 1-2.3|uvc"`
