# G1 머리 카메라 시뮬레이션 및 실제 카메라 전환

## 목적

현재 카메라가 없어도 아래 경로를 먼저 검증한다.

```text
MuJoCo G1 머리 카메라
-> 공통 CameraFrame(BGR, timestamp, intrinsics, frame_id)
-> Unitree 시뮬레이터 호환 공유메모리
-> TeleImager(ZMQ/WebRTC)
-> Quest의 로봇 1인칭 영상
```

실제 D435i가 준비되면 첫 단계만 다음과 같이 교체한다.

```text
RealSense D435i
-> 동일한 CameraFrame 또는 TeleImager 출력
-> 나머지 표시·제어 경로 유지
```

카메라 영상 경로와 팔 제어 경로는 독립적이다. 카메라가 끊겨도 잘못된 팔 명령을 만들지 않으며, 팔 제어가 중지돼도 마지막 영상으로 제어가 계속되는 것처럼 판단하지 않는다.

## 현재 맞춘 조건

- G1 공식 URDF의 `torso_link -> d435_link` 위치와 장착각 사용
  - 위치: `[0.0576235, 0.01753, 0.42987] m`
  - pitch: `0.8307767239493009 rad`
- Unitree Isaac Lab의 G1 전방 카메라 축 정의와 동일한 광학 방향 사용
- D435i RGB 사양을 기준으로 수직 화각 `42.5 deg` 사용
- `640 x 480`, `30 fps`, `BGR8`, 단안 영상
- 공식 `unitree_sim_isaaclab.MultiImageWriter`와 같은 공유메모리 이름·헤더·payload 사용
  - 이름: `isaac_head_image_shm`
  - encoding `0`: raw BGR
- 공식 TeleImager의 `isaacsim`과 `realsense` 설정을 각각 준비
- 카메라 검증 전용 장면에서 점검판, 오른팔, 손목 도구, 표적이 한 화면에 보이도록 구성
- 카메라 검증 표적의 최종 IK 오차 기준: `30 mm 이하`

## 실행 파일

### 전체 자동 검증

`tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat`

다음을 자동 확인한다.

1. 공통 통신·캘리브레이션·watchdog 테스트
2. 공식 G1 카메라 장착 좌표
3. 640 x 480 BGR 프레임 생성
4. 점검 자세의 도달 가능성
5. Unitree 공유메모리 헤더와 실제 픽셀 round-trip
6. 미리보기와 JSON 결과 생성

결과:

- `logs/camera/g1_head_camera_preview.bmp`
- `logs/camera/camera_validation_report.json`

### 실시간 MuJoCo 머리 시점

`tools/START_HEAD_CAMERA_SIMULATION.bat`

- MuJoCo 창 자체가 G1 머리 카메라 시점으로 열린다.
- 같은 영상을 `isaac_head_image_shm`에 30 fps로 내보낸다.
- 기존 UDP 오른팔 제어도 그대로 받을 수 있다.

### 미리보기 한 장

`tools/CAPTURE_HEAD_CAMERA_PREVIEW.bat`

카메라 검증 자세로 팔을 먼저 수렴시킨 뒤 한 장을 저장하고 연다.

## 설정 파일

- `config/camera_profile.json`: 공통 영상 계약과 G1 장착 좌표
- `config/teleimager_simulation.yaml`: MuJoCo 공유메모리 입력
- `config/teleimager_real_d435i.yaml`: 실제 RealSense 입력

두 TeleImager 설정은 카메라 `type`과 실제 장치의 `serial_number`를 제외하고 해상도, fps, ZMQ/WebRTC 포트가 같다.

## 실제 카메라가 도착했을 때

1. Ubuntu의 별도 Python 3.10 환경에 공식 TeleImager와 RealSense 의존성을 설치한다.
2. `teleimager-server --cf --rs`로 D435i serial number를 확인한다.
3. `config/teleimager_real_d435i.yaml`의 `serial_number`에 실제 값을 넣는다.
4. 해당 설정을 TeleImager의 `cam_config_server.yaml`로 적용하고 `teleimager-server --rs`를 실행한다.
5. Quest에서 기존과 같은 WebRTC 주소를 연다. 기본 head camera signaling 포트는 `60001`이다.
6. 아래 인수검사만 수행한 뒤 실제 영상 소스로 전환한다.

## 첫 연결 인수검사

하드웨어 없이는 정확히 알 수 없으므로 현재 임의값을 넣지 않은 항목이다.

- 장치가 보고하는 실제 intrinsics와 distortion coefficients
- 조립 공차가 반영된 실제 `camera -> torso` 외부 파라미터
- 자동 노출과 연구원 내부 조명의 저조도 성능
- 카메라 노출부터 Quest 표시까지의 end-to-end 지연
- 30 fps 유지 여부와 frame drop 비율
- 팔 또는 장착 도구가 카메라를 가리는 구간

장착 브래킷이 공식 위치와 같다면 장소가 바뀔 때 카메라 외부 파라미터를 다시 보정하지 않는다. 장소별 보정 대상은 로봇과 점검 설비 사이의 상대 좌표다.

## 현재 시뮬레이션의 한계

MuJoCo 영상은 이상적인 pinhole 카메라다. 실제 D435i의 렌즈 왜곡, rolling shutter, 노출 변화, USB/네트워크 지연과 영상 압축 손실은 포함하지 않는다. 이 값들은 실제 장비의 측정 결과를 설정값으로 넣어야 하며, 측정 전 임의값으로 맞추지 않는다.

## 근거

- Unitree `xr_teleoperate`: G1 내장 D435i와 ego/WebRTC 영상 경로
- Unitree `unitree_sim_isaaclab`: G1 전방 카메라 축과 공유메모리 영상 규약
- Unitree `teleimager`: `isaacsim`/`realsense`, ZMQ/WebRTC 공통 영상 서버
- Intel RealSense D435i 공식 사양: RGB 화각
