# Quest UDP 카메라 pan/tilt 추종 (2026-10-01)

## Windows

`START_G1_VR_TELEOP.bat` → bundled Python → `tools/G1_PORTABLE.py teleop`
→ `tools/G1_VR_TELEOP_LAUNCH.py` 경로를 사용한다. BAT는 기존 3줄 shim을 유지한다.
Unity와 PC gateway를 재시작해야 새 pitch 필드가 적용된다.

Unity HMD forward의 elevation을 `atan2(y, sqrt(x*x+z*z))`로 계산한다.
위를 보면 양수이며 Unity Euler X를 그대로 쓰지 않는다.

2026-10-02부터 카메라 PTZ 자세는 locomotion 정렬 heartbeat와 분리한다. Unity는
`g1.unity.quest.camera.v1`을 loopback UDP 55075에 20 Hz로 보내고,
`G1_CAMERA_FOLLOW_LAUNCH.py`가 이를 엄격히 검증한 뒤 기존 SSH 연결의 stdin으로 운반해
G1 loopback UDP 15103으로 전달한다. 카메라 `ready`는 initial HMD alignment 이후
orientation tracked+valid만 요구하며 위치 tracking과 Omni `FRESH_LIVE`/calibrated 상태는 요구하지 않는다.
기존 UDP 55074의 Omni/locomotion READY·STALE zero-hold 계약은 그대로 유지한다.

## 실행 순서

기본 `START_G1_VR_TELEOP.bat`은 camera worker와 camera_follow worker를 함께 관리한다.
GROOT를 시작하든 `--no-groot-actuation`을 쓰든 PTZ pose 경로는 동일하며 heading
controller를 카메라 때문에 별도로 실행할 필요가 없다. `--check-only`는 계획만 확인한다.

카메라만 시각 테스트할 때는 Unity Play + `G1_PORTABLE.py camera`로 영상 스트림을 띄우고,
PTZ만 추가로 검증하려면 별도 콘솔에서 다음을 실행할 수 있다.

```bat
runtime\python\python.exe -I -u -B tools\G1_CAMERA_FOLLOW_LAUNCH.py --host 192.168.10.165
```

remote follower는 기존 onboard 스크립트를 다음 전용 포트로 실행한다.

```bash
python3 -B -u ~/groot_onboard_runtime/receive_mink_ik_udp.py \
  --camera-follow --pan-sign 1 --no-camera-stream --port 15104 --quest-port 15103
```

`15104`는 camera follower 전용 dummy Mink receive port라 기존 5014 receiver와 충돌하지 않는다.
같은 camera-follow 옵션은 재사용하고, 다른 camera-follow 옵션이나 수동 keyboard PTZ는
자동 종료하지 않고 fail-closed한다.

## 카메라 동작

- `Unity HMD -> localhost 55075 -> camera_follow SSH stdin -> G1 localhost 15103 -> PTZ`.
- 영상은 별도 camera worker가 Insta360 `video-index0`을 소유하므로 PTZ follower는 `--no-camera-stream`을 유지한다.
- camera pose가 ready이고 yaw/pitch가 0.5초 범위 5° 안에서 안정되면 영점을 포착한다.
- 영점 포착 시 카메라 pan=0, tilt=0 명령이 나가며 이후 상대 yaw/pitch를 추종한다.
- 키보드 방향과 동일: D=pan 양수, W=tilt 양수, C=(0,0).
- `--pan-sign -1`은 pan 반전, 필요시 `--tilt-sign -1`은 tilt 반전.
- HMD pose가 stale되면 마지막 PTZ 목표를 유지하고 새 명령을 멈춘다. 로봇 DDS/모터 명령은 보내지 않는다.
- `link2_keyboard.py`와 자동 추종기를 동시에 실행하지 않는다.
- USB/UVC 오류나 재열거는 별도 failure domain이다. follower는 set_ctrl 실패 시 device를 버리고 by-id/capability 기반으로 다시 찾는다.

카메라를 움직이지 않는 확인:

```bash
python3 -u receive_mink_ik_udp.py --camera-follow --pan-sign 1 --dry-run
```

드라이런은 v4l2 호출 및 카메라 스트림 시작을 하지 않는다.
실제 방향은 사람이 HMD를 좌우/위아래로 조금씩 움직여 확인하는 것이 가장 빠르다.

## 검증

2026-10-02 source 회귀와 portable live 경로를 함께 검증했다. Unity C#은 portable Editor에서
실제 `Assembly-CSharp.dll` 재컴파일/domain reload PASS. direct camera packet validation과
camera follower launcher 테스트도 PASS했다.

실기에서는 GROOT/Omni/UDP 55070 없이 camera-only + camera_follow만 실행한 뒤 합성 pose를
`0° -> +8° -> 0°`로 보냈다. 결과는 `[ZERO CAPTURED]`, `[CAMERA CMD] pan=+8`,
`[CAMERA CMD] pan=+0`, 이후 `[QUEST STALE] hold last pan/tilt`까지 확인했다.
즉 Unity용 localhost 55075 -> SSH stdin -> G1 localhost 15103 -> Insta360 V4L2 PTZ가
robot actuation 없이 end-to-end PASS다. 실제 HMD 방향 검증 시에는 헤드셋 orientation tracking이
유효해야 하며 initial HMD alignment 후 정면을 약 0.5초 안정시켜 zero를 잡는다.

## 로그 확인법 (카메라가 안 움직일 때)

순서대로 확인한다. Omni/GROOT 로그는 더 이상 PTZ 선행 조건이 아니다.

1. Unity `Unity_G1_VR/Logs/Editor.log`
   - `[QUEST HEAD] ... camera_ready=... orientation_tracked=... position_tracked=... yaw=... pitch=...`.
   - `camera_ready=False`이면 initial HMD alignment 또는 orientation tracking부터 확인한다. 위치 tracking만 false인 것은 PTZ를 막지 않는다.
2. PC camera follower 콘솔/`camera_follow.log`
   - `[QUEST CAMERA BRIDGE] rx=... forwarded=... waiting=... rejected=...`.
   - `rx=0`: Unity 55075 heartbeat가 없음. `waiting` 증가: heartbeat는 오지만 camera_ready가 false. `rejected` 증가: schema/range/session 검증 실패.
3. G1 follower 상태
   - `[ZERO CAPTURED]`: 안정된 정면 zero 포착.
   - `[CAMERA CMD] pan=... tilt=...`: 실제 V4L2 명령.
   - `[QUEST STALE]`: 새 pose가 0.6초 이상 끊겨 마지막 목표 hold.
   - `[CAMERA LOST]`/`[CAMERA WAIT]`: USB/UVC device 재탐색 중.

## USB 끊김 대응 (2026-10-02)

- 실측: 과거 Insta360이 G1의 USB 2.0 허브(1-2.3, Wi-Fi 동글과 같은 허브)에서 스트리밍/PTZ 중
  `uvcvideo: Non-zero status (-71)` 후 `USB disconnect`되고 다른 `/dev/videoN`으로 재연결된 기록이 있다.
  2026-10-02 현재 세션에서도 `uvcvideo: Non-zero status (-75) in video completion handler`가 별도로 관측됐다.
  케이블/전원(모터 구동 전류) 문제로 추정. 전원 공급 USB 허브나 USB 3 포트 직결 권장.
- 추종기는 카메라가 사라져도 종료하지 않는다. `[CAMERA LOST]` → 1초마다 재탐색(`[CAMERA WAIT]`)
  → 새 번호로 `[CAMERA] Link 2 Pro device …` → 스트림 재시작 → 마지막 목표 재전송 `(resend after reconnect)`.
- `~/link2_keyboard.py`도 번호 자동 탐색(인자로 `/dev/videoN` 지정 가능). 백업: `link2_keyboard.py.before_auto_device_20261002`.
- 커널 확인: `journalctl -k --since "10 min ago" | grep -iE "usb 1-2.3|uvc"`
