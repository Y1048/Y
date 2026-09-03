# G1 머리 카메라 로컬 표시와 원격 확장

## 현재 목적

실제 G1 전면 카메라를 Unity의 시야 고정 PiP에 표시한다. 영상 경로는 팔 제어와
완전히 분리한다. 카메라가 끊겨도 engagement, IK, Safety Gate 또는 로봇 명령은
변하지 않는다.

## 현재 로컬 경로

```text
G1 front camera
-> Unitree SDK2 VideoClient.GetImageSample()
-> CycloneDDS domain 0 / videohub request-response
-> WSL read-only JPEG bridge (20 Hz)
-> G1CM header + complete JPEG
-> TCP 127.0.0.1:5011
-> Unity G1HeadCameraPiP
-> Texture2D / RawImage
```

`GetImageSample()`은 최신 카메라 프레임을 JPEG 바이트로 반환한다. 브리지는
JPEG 파일을 디스크에 저장하지 않는다. SOI/EOI marker와 최대 크기를 검사한 뒤
다음 24-byte network-order header를 붙인다.

```text
magic(4) + version(4) + sequence(4) + timestamp_ns(8) + payload_size(4)
```

Unity는 header와 payload를 정확히 읽고 `ImageConversion.LoadImage()`로
`Texture2D`에 디코딩한다. 현재 활성 경로에는 WebRTC, ROS 2 또는 OpenCV 표시
창을 사용하지 않는다.

## Unity PiP

`G1HeadLockedCamera`가 Play 시작 시 `CenterEyeAnchor` 아래에
`G1_Head_Camera_PiP`를 생성한다. 창은 시야 정중앙에 고정된다.

- 회색: 수신기 정지
- 노란색: TCP listener가 영상을 기다림
- 초록색: 1초 이내의 새 JPEG가 표시됨
- 빨간색: decode 오류, 연결 오류 또는 stale frame

영상 상태는 관절 목표나 안전 상태로 전달되지 않는다.

## 실행

전체 로컬 통합 테스트:

```powershell
.\START_VR_HAND_TO_MUJOCO.bat
```

G1 Ethernet과 `192.168.123.164` 응답이 확인되면 카메라 브리지를 자동으로
시작한다. Unity에서 Play를 시작하면 TCP 5011이 열리고 대기 중인 브리지가
자동으로 연결된다.

카메라만 별도로 실행:

```powershell
.\tools\START_G1_CAMERA_TO_UNITY.bat
```

## 오프라인 카메라 기반 검증

G1 없이 실제 Unity TCP/PiP 표시 경로를 실행:

```powershell
.\tools\TEST_CAMERA_REPLAY_TO_UNITY.bat
```

Unity에서 Play를 누르면 중앙 PiP가 초록색으로 바뀌고, `OFFLINE REPLAY` 문구와
움직이는 초록 표식이 보여야 한다. 합성 프레임은 실제 카메라와 같은 `G1CM`
header와 완전한 JPEG payload를 사용한다. 이 프로세스는 Windows loopback만 열며
Unitree SDK 또는 DDS를 import하지 않는다. 종료 결과는
`logs/camera/camera_offline_replay_*.json`에 저장된다.

카메라 모델과 공유메모리 형식을 정적으로 검증:

```powershell
.\tools\VERIFY_HEAD_CAMERA_FOUNDATION.bat
```

이 검증은 G1 공식 장착 좌표, 640 x 480 비어 있지 않은 BGR frame 및 Unitree
공유메모리 round-trip을 확인한다. 실제 `videohub` 네트워크 경로를 대신하지는
않는다.

## 로컬 인수검사

1. PiP 상태등이 초록색인지 확인한다.
2. G1 카메라 앞 물체의 움직임이 PiP에 연속 반영되는지 확인한다.
3. Quest 머리를 돌려도 PiP가 시야의 같은 위치에 남는지 확인한다.
4. 3분 이상 실행해 빨간 상태, 장시간 정지 또는 반복 재연결이 없는지 확인한다.
5. Quest 손목 텔레옵과 카메라를 동시에 실행하되 실제 G1 command는 잠근다.

## 원격 운용 전환

현재 JPEG/TCP는 로컬 검증 경로다. 약 220 KB JPEG를 20 Hz로 보내면 대략
35 Mbps이므로 외부 원격 운용에는 적합하지 않다. 원격 단계에서는 PiP UI를
유지하고 영상 source만 다음과 같이 교체한다.

```text
robot-side camera source
-> H.264 hardware/software encoder
-> authenticated WebRTC transport
-> Unity WebRTC camera source
-> existing PiP display
```

G1 SDK2/CycloneDDS와 Safety Gate는 로봇 옆 현장 PC에 둔다. 공인망에 DDS 또는
TCP 5011을 직접 노출하지 않는다.

## 안전 경계

- `g1_camera_tcp_bridge.py`는 `VideoClient.GetImageSample()`만 호출한다.
- `g1_camera_replay_tcp.py`는 합성 JPEG만 만들며 G1 SDK/DDS를 import하지 않는다.
- motor, mode, camera-setting command와 DDS publisher를 만들지 않는다.
- TCP 출력은 loopback만 허용한다.
- 카메라 손실은 실제 G1의 명령 상태를 변경하지 않는다.
