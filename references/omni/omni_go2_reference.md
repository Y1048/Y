# Omni + Go2 + 360Camera + VR

360도 카메라로 Go2가 있는 환경을 사용자에게 WebRTC 방법을 사용해 VR로 실시간으로 보여주고 Virtuix Omni Treadmill을 사용하여 사용자의 걸음대로 Go2가 이동한다.

## Omni와 노트북, Unity 연결하기

OmniConnectSetup 실행해서 Omni Connect 설치

![image.png](image.png)

![image.png](image%201.png)

~~잘 되던 옴니가 업데이트로 인해 사용 불가능하게 되어서 다시 이전으로 돌리는 업데이트를 하고 있다는 메일을 받고 기다리는 중이다.~~

~~일단은 OpenXR에 맞춰 만들어진 Unity Project만 사용 가능하다. 업데이트 전에는 안 그랬음~~

이제 잘 된다

---

---

![image.png](image%202.png)

---

---

## WebRT

RTSP 방식은 지연이 너무 심해서 WebRTC로 시도해보았는데 매우 성공적이다. 

지연은 0.2초정도로 거의 없다.

[delaytest.mp4](delaytest.mp4)

![image.png](image%203.png)

RTSP 방식보다 초기 설정과 신호 교환 과정이 복잡해 구현 난이도가 높았다.

## Unity

기존에 RTSP 방식으로 영상 송출하던 프로젝트에서 RTSP 코드만 삭제하고 사용했다.

VideoSphere은 무조건 남겨둬야한다.

- Package Manager > WebRTC 패키지 설치하기

Add Package by name → com.unity.webrtc / 버전: 2.4.0-exp.11

![image.png](image%204.png)

- WebRTC 수신 코드 붙이기
- WhepVideoToSphere.cs
    
    ```csharp
    using System.Collections;
    using System.Text;
    using Unity.WebRTC;
    using UnityEngine;
    using UnityEngine.Networking;
    using UnityEngine.UI;
    
    [DisallowMultipleComponent]
    public class WhepReceiverSampleStyle : MonoBehaviour
    {
        [Header("WHEP Endpoint (MediaMTX)")]
        public string whepUrl = "https://192.168.68.53:8889/vr360/whep"; // Edge에서 보던 주소 그대로
    
        [Header("Targets")]
        public Renderer sphereRenderer;      // VideoSphere MeshRenderer (옵션: 없으면 RawImage만 사용)
        public bool spawnFullscreenRawImage = true;
    
        // RP별 머티리얼 텍스처 슬롯명
        public string builtinProp = "_MainTex";
        public string urpProp     = "_BaseMap";
        public string hdrpProp    = "_BaseColorMap";
    
        private RTCPeerConnection _pc;
        private RawImage _raw;       // 디버그용 전체화면 RawImage
        private Texture _lastTex;
    
        void Awake()
        {
            WebRTC.Initialize();                      // 샘플과 동일
            Application.runInBackground = true;
            QualitySettings.vSyncCount = 0;
        }
    
        IEnumerator Start()
        {
            if (spawnFullscreenRawImage) CreateFullscreenRawImage();
    
            // 1) PeerConnection (사설망이라 STUN 불필요)
            var conf = new RTCConfiguration { iceServers = new RTCIceServer[]{} };
            _pc = new RTCPeerConnection(ref conf);
    
            // 2) 원격 트랙 수신(샘플과 같은 패턴)
            _pc.OnTrack = e =>
            {
                if (e.Track is VideoStreamTrack v)
                {
                    v.OnVideoReceived += tex =>
                    {
                        _lastTex = tex;
                        if (_raw != null && _raw.texture != tex) _raw.texture = tex;
                        ApplyTextureToSphere(tex);
                    };
                }
            };
    
            // 3) 수신 전용 비디오 트랜시버
            _pc.AddTransceiver(TrackKind.Video, new RTCRtpTransceiverInit
            {
                direction = RTCRtpTransceiverDirection.RecvOnly
            });
    
            // 4) Offer 생성/로컬 설정
            var offerOp = _pc.CreateOffer();
            yield return offerOp;
            var offer = offerOp.Desc;
            yield return _pc.SetLocalDescription(ref offer);
    
            // 5) WHEP POST (샘플은 로컬-원격 2PC였지만, 여긴 서버와 교환)
            var req = new UnityWebRequest(whepUrl, "POST");
            req.uploadHandler   = new UploadHandlerRaw(Encoding.UTF8.GetBytes(offer.sdp));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/sdp");
    
            // 내부망/자가서명 인증서 허용(테스트 전용)
            req.certificateHandler = new TrustAllCerts();
            req.disposeCertificateHandlerOnDispose = true;
    
            Debug.Log("[WHEP] POST -> " + whepUrl);
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"[WHEP] HTTP Error: {req.responseCode} / {req.error}\n{req.downloadHandler.text}");
                yield break;
            }
    
            // 6) Answer 수신/원격 설정
            var answer = new RTCSessionDescription { type = RTCSdpType.Answer, sdp = req.downloadHandler.text };
            yield return _pc.SetRemoteDescription(ref answer);
    
            // 7) 샘플처럼 WebRTC.Update 루프
            StartCoroutine(WebRTC.Update());
            Debug.Log("[WHEP] Handshake complete. Waiting frames...");
        }
    
        void OnDestroy()
        {
            _pc?.Close();
            _pc?.Dispose();
            WebRTC.Dispose();
        }
    
        void ApplyTextureToSphere(Texture tex)
        {
            if (sphereRenderer == null || tex == null) return;
            var mat = sphereRenderer.material;
            if (mat.HasProperty(builtinProp)) mat.SetTexture(builtinProp, tex);
            if (mat.HasProperty(urpProp))     mat.SetTexture(urpProp,     tex);
            if (mat.HasProperty(hdrpProp))    mat.SetTexture(hdrpProp,    tex);
        }
    
        void CreateFullscreenRawImage()
        {
            var canvasGO = new GameObject("[WHEP] Canvas");
            var canvas   = canvasGO.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasGO.AddComponent<CanvasScaler>();
            canvasGO.AddComponent<GraphicRaycaster>();
    
            var rawGO = new GameObject("VideoRawImage");
            rawGO.transform.SetParent(canvasGO.transform, false);
            _raw = rawGO.AddComponent<RawImage>();
            var rt = _raw.rectTransform;
            rt.anchorMin = Vector2.zero; rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero; rt.offsetMax = Vector2.zero;
        }
    
        // ★ 자가서명 인증서 허용 (개발/테스트 전용)
        class TrustAllCerts : CertificateHandler
        {
            protected override bool ValidateCertificate(byte[] certificateData) => true;
        }
    }
    
    ```
    

![image.png](image%205.png)

- Package Manager > Omni Connect sdk 설치하기

sdk 내부에 있는 Omni와 연결해 주는 코드다.

![image.png](image%206.png)

- Omni에서 나온 데이터를 Go2로 보내기
- UdpSender.cs
    
    ```csharp
    using UnityEngine;
    using System.Net.Sockets;
    using System.Text;
    using System.Globalization;
    using UnityEngine.XR;                    // XR HMD 높이
    using Virtuix.OmniConnectSdk;
    
    [DisallowMultipleComponent]
    public class UdpSender : MonoBehaviour
    {
        [Header("Target (Go2/ROS2)")]
        public string targetIp = "192.168.68.53";
        public int targetPort = 5005;
        public int sendHz = 50;
    
        [Header("Active 판정 문턱(0~1)")]
        [Tooltip("움직임 크기(|mv|)가 이 값 이상일 때 active=true (0~1)")]
        public float moveThreshold = 0.10f;
    
        [Header("Yaw만으로도 active 허용")]
        [Tooltip("초당 yaw 회전속도(deg/s)가 이 값 이상이면 발이 정지여도 active=true")]
        public float yawActiveDps = 25f;     // 20~40 권장
        [Tooltip("yaw 속도 EMA(0~1, 0=느림/안정, 1=즉각)")]
        public float yawDpsAlpha = 0.25f;
        public bool allowYawOnlyActive = true;
    
        [Header("Optional")]
        public float heightMeters = 1.60f;   // XR에서 못 읽으면 이 값 전송
    
        UdpClient _client;
        float _nextSend;
        int _sendCount;
    
        // yaw 속도 계산용 상태
        float _prevYawDeg, _prevTime, _yawDpsEma;
        bool _hasPrevYaw;
    
        static float WrapDeg180(float d){
            while(d>180f) d-=360f;
            while(d<-180f) d+=360f;
            return d;
        }
    
        void Start()
        {
            _client = new UdpClient();
            Application.runInBackground = true;
            moveThreshold = Mathf.Clamp01(moveThreshold);
            yawDpsAlpha  = Mathf.Clamp01(yawDpsAlpha);
            Debug.Log($"[UdpSenderRaw] target={targetIp}:{targetPort} hz={sendHz} thr={moveThreshold:F2} yawActiveDps={yawActiveDps:F1}");
        }
    
        void OnDisable(){ try{ _client?.Close(); } catch {} }
        void OnApplicationQuit(){ try{ _client?.Close(); } catch {} }
    
        void Update()
        {
            if (Time.time < _nextSend) return;
            _nextSend = Time.time + 1f / Mathf.Max(1, sendHz);
    
            // 1) Omni 입력: x=좌우, y=전후 (-1..+1)
            Vector2 mv = OmniConnectManager.GetMovementVector();
            float mx = mv.x;   // 오른쪽 +, 왼쪽 -
            float my = mv.y;   // 앞 +, 뒤 -
    
            // 2) 움직임 기반 active
            float magSq = mx * mx + my * my;
            bool isActive = magSq >= (moveThreshold * moveThreshold);
    
            // 3) 하네스 yaw(절대 각도, deg) + yaw 속도(dps, EMA)
            float yawDeg = OmniConnectManager.GetArmYaw();
            float now = Time.time;
            if (_hasPrevYaw){
                float dyaw = WrapDeg180(yawDeg - _prevYawDeg);
                float dt = Mathf.Max(1e-4f, now - _prevTime);
                float yawDps = dyaw / dt; // deg/s
                _yawDpsEma = yawDpsAlpha * yawDps + (1f - yawDpsAlpha) * _yawDpsEma;
            } else {
                _yawDpsEma = 0f;
                _hasPrevYaw = true;
            }
            _prevYawDeg = yawDeg;
            _prevTime   = now;
    
            // 4) yaw만으로도 active 허용
            if (allowYawOnlyActive && Mathf.Abs(_yawDpsEma) >= yawActiveDps)
                isActive = true;
    
            // 5) HMD 높이(Y, m) - XR 우선, 실패 시 fallback
            float h = heightMeters;
            var head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (head.isValid && head.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 headPos))
                h = headPos.y;
            else if (Camera.main != null)
                h = Camera.main.transform.position.y;
    
            // 6) JSON 송신
            string json = string.Format(
                CultureInfo.InvariantCulture,
                "{{\"mx\":{0:F4},\"my\":{1:F4},\"yaw_deg\":{2:F2},\"h\":{3:F3},\"active\":{4}}}",
                mx, my, yawDeg, h, isActive ? "true" : "false"
            );
    
            byte[] data = Encoding.UTF8.GetBytes(json);
            _client.Send(data, data.Length, targetIp, targetPort);
    
            if ((++_sendCount % 50) == 0) {
                Debug.Log($"[UdpSender] mx={mx:F3} my={my:F3} | yaw={yawDeg:F1} dps={_yawDpsEma:F1} | h={h:F3} | active={isActive}");
            }
        }
    }
    
    ```
    

![image.png](image%207.png)

## Go2

💥💥💥💥💥 그냥 처음부터 ffmpeg8.0으로 설치하삼💥💥💥💥💥

WebRTC 구성은 대략적으로 다음과 같다.

1. MediaMTX 서버 준비 (WebRTC+HTTPS+ICE)
2. 올바른 인증서 생성 (SAN 포함)
3. FFmpeg 최신 빌드 (WHIP 지원)
4. FFmpeg로 곧장 WHIP 송출
5. 브라우저/Unity에서 WHEP로 재생

- MediaMTX 설치 (WebRTC + HTTPS + ICE)

원래 있었는데  최신 버전으로 설치함

![image.png](image%208.png)

- 올바른 인증서 생성 (SAN 포함)

![image.png](image%209.png)

- 폴더 관리

WebRTC 폴더 만들고 mediamtx를 옮겼다.

w:1920 YUV, 이건 뭔지 모르겠다.

![image.png](image%2010.png)

- mediamtx.yml 수정하기

![image.png](image%2011.png)

→ 로그 볼 수 있게 하는 부분

![image.png](image%2012.png)

→ WebRTC의 몸통이 되는 부분 / 포트는 **8889** 이다.

![image.png](image%2013.png)

- mediamtx 실행

![image.png](image%2014.png)

Go2에서 영상을 먼저 송출한 뒤에 Unity를 실행해야 한다. 

- 실행 명령어

ip주소는 Go2의 ip주소를 입력 해야 한다.

```bash
~/ffmpeg-whip/bin/ffmpeg -loglevel warning  -fflags nobuffer -flags low_delay  -f v4l2 -thread_queue_size 64 -input_format mjpeg -framerate 30 -video_size 2880x1440 -i /dev/video0  -f lavfi -i anullsrc=r=48000:cl=stereo  -vf "scale=1920:960:flags=fast_bilinear,format=yuv420p,swapuv"  -c:v libx264 -preset ultrafast -tune zerolatency  -profile:v baseline -level 4.0 -g 15 -keyint_min 15 -bf 0 -rc-lookahead 0  -pix_fmt yuv420p -b:v 4M -maxrate 4M -bufsize 1M  -x264-params "repeat-headers=1:scenecut=0:open-gop=0:cabac=0:ref=1:colorprim=bt709:transfer=bt709:colormatrix=bt709"  -c:a libopus -b:a 64k  -f whip "https://192.168.68.53:8889/vr360/whip"
```

- Unity로부터 데이터 값을 받아 Go2 움직이게 하기
- ~~moving_well.py~~
    
    ```python
    #!/usr/bin/env python3
    # moving_well.py
    # Unity(Omni) → UDP(JSON: mx,my,yaw_deg,h,active) → FSM → /wirelesscontroller
    # 좌표: Unity mx(오른+)·my(앞+) → ROS2 +X=앞, +Y=좌 (vx=+my, vy=-mx)
    # 동작:
    #  - active=False(정지): 회전/이동 축 0, 높이 키(↑/↓)만 퍼블리시(상대 추종)
    #  - active=True(이동): FSM으로 lx/ly/rx만 퍼블리시, 높이 키 멈춤
    #  - 하강 시작 문턱: h0의 1/3만큼 숙여졌을 때부터 ↓ 시작 (그 전엔 무시)
    #  - 기준 h0: 프로그램 시작 후 정지 상태에서 받은 첫 유니티 h로 자동 설정
    
    import json, math, socket, time
    import rclpy
    from rclpy.node import Node
    from unitree_go.msg import WirelessController
    
    def clamp(x, lo, hi): return lo if x < lo else hi if x > hi else x
    def wrap_deg180(d):
        while d > 180.0:  d -= 360.0
        while d < -180.0: d += 360.0
        return d
    
    class FSM:
        IDLE = 0
        ROTATE_ONLY = 1
        STRAFE_ONLY = 2
        CURVE_MOVE = 3
    
    # ===================== 상대 높이 팔로워(논블로킹) =====================
    class RelativeHeightFollower:
        """초기 HMD 높이(h0)를 기준으로만 하강/복귀(기준 초과 금지).
           하강 시작은 'h0의 일정 비율(기본 1/3)'만큼 숙여졌을 때부터."""
        def __init__(self, key_up:int, key_dn:int, loop_hz:float,
                     click_m=0.010, band_m=0.020, max_pps=3.0,
                     pulse_ms=120, release_frames=3, timeout_s=0.5,
                     max_down_m=0.12, auto_baseline=True, init_h0=None,
                     down_start_h_ratio=1/3):
            self.KEY_UP, self.KEY_DN = key_up, key_dn
            self.click_m = max(1e-6, float(click_m))     # 1클릭당 ΔH 추정[m]
            self.band_m  = float(band_m)                 # 목표 근처 데드밴드[m]
            self.max_pps = float(max_pps)                # 초당 최대 클릭
            self.pulse_s = pulse_ms / 1000.0             # 누름 지속시간[s]
            self.release_dt = release_frames / max(1.0, loop_hz)
            self.timeout_s = float(timeout_s)
            self.max_down_clicks = int(round(max_down_m / self.click_m))
            self.auto_baseline = bool(auto_baseline)
            self.down_start_h_ratio = float(down_start_h_ratio)  # h0의 비율
    
            # 상태
            self.h0 = float(init_h0) if (init_h0 is not None) else None  # 기준(HMD)
            self.cur_click = 0                                           # 기준 위치(0)
            self.desired_h = None
            self.last_rx_ts = 0.0
    
            # 토큰 버킷
            self.bucket = 0.0
            self.last_bucket_ts = time.time()
    
            # 펄스 상태기계
            self.phase = "idle"      # idle | press | release
            self.phase_until = 0.0
            self.phase_dir = 0       # +1=UP, -1=DOWN
    
        def feed_h(self, h: float, now: float, accept_for_baseline: bool):
            if h is None or h <= 0.5:
                return
            self.desired_h = float(h)
            self.last_rx_ts = now
            if self.h0 is None and (self.auto_baseline and accept_for_baseline):
                # 정지 상태에서 첫 유효값으로 기준 설정
                self.h0 = self.desired_h
                self.cur_click = 0
    
        def _refill_bucket(self, now):
            dt = now - self.last_bucket_ts
            if dt > 0:
                self.bucket = min(self.max_pps, self.bucket + dt * self.max_pps)
                self.last_bucket_ts = now
    
        def update(self, active: bool, now: float):
            # 입력/타임아웃/기준 체크
            if self.desired_h is None or (now - self.last_rx_ts) > self.timeout_s:
                return
            if self.h0 is None:
                return
            if active:
                return  # 이동 중엔 높이 조절 금지
    
            delta_h = self.desired_h - self.h0  # (음수면 숙임)
    
            # ★ 하강 시작 문턱: 아직 내린 적 없으면(h=기준상태) h0의 1/3 넘게 숙여졌을 때만 시작
            threshold_m = self.h0 * self.down_start_h_ratio
            if self.cur_click == 0 and delta_h > -threshold_m:
                return
    
            # 목표 클릭(음수만 허용 = 기준보다 낮아짐 / 양수는 0(기준)까지)
            tgt_click = int(round(delta_h / self.click_m))
            tgt_click = max(-self.max_down_clicks, min(0, tgt_click))
    
            # 진행 중 펄스 마무리
            if self.phase != "idle" and now >= self.phase_until:
                if self.phase == "press":
                    self.phase = "release"
                    self.phase_until = now + self.release_dt
                    self.cur_click += self.phase_dir
                elif self.phase == "release":
                    self.phase = "idle"
                    self.phase_dir = 0
    
            if self.phase != "idle":
                return
    
            # 데드밴드(현재 추정 높이 vs 목표 높이)
            cur_h_est = self.h0 + self.cur_click * self.click_m
            tgt_h     = self.h0 + tgt_click * self.click_m
            if abs(tgt_h - cur_h_est) < self.band_m:
                return
    
            # 레이트 리밋
            self._refill_bucket(now)
            if self.bucket < 1.0:
                return
            self.bucket -= 1.0
    
            # 방향 결정: tgt_click < cur_click → ↓, > → ↑
            self.phase_dir = -1 if tgt_click < self.cur_click else +1
            # 상한 보호: 위로는 0(기준)까지만
            if self.phase_dir > 0 and self.cur_click >= 0:
                self.phase_dir = 0
                return
    
            # 펄스 시작
            self.phase = "press"
            self.phase_until = now + self.pulse_s
    
        def get_keys(self) -> int:
            if self.phase == "press":
                return self.KEY_UP if self.phase_dir > 0 else self.KEY_DN
            return 0
    # ===========================================================================
    
    class OmniFsmNode(Node):
        def __init__(self):
            super().__init__('omni_fsm')
    
            # -------- ROS2 Parameters --------
            self.declare_parameter('udp_port', 5005)
            self.declare_parameter('local_ip', '0.0.0.0')
            self.declare_parameter('hz', 50)
    
            # 스케일/임계값
            self.declare_parameter('max_lin', 0.25)
            self.declare_parameter('max_ang', 1.00)
            self.declare_parameter('deadzone_lin', 0.03)
            self.declare_parameter('move_enter', 0.05)
            self.declare_parameter('rot_enter', 0.18)
            self.declare_parameter('rot_exit', 0.08)
    
            # 필터(EMA)
            self.declare_parameter('alpha_v', 0.30)
            self.declare_parameter('alpha_wz', 0.20)
    
            # 워치독
            self.declare_parameter('timeout_s', 0.30)
    
            # 테스트 모드
            self.declare_parameter('test_mode', 0)
    
            # (옛 파라미터: 선언만 유지, 실제 사용 안 함)
            self.declare_parameter('use_ry_axis', False)
            self.declare_parameter('h0', 1.60)
            self.declare_parameter('hrange', 0.30)
            self.declare_parameter('height_deadband', 0.20)
    
            # -------- 상대 높이 팔로워 파라미터 --------
            self.declare_parameter('height_key_up', 4096)     # KEY_BODY_UP
            self.declare_parameter('height_key_dn', 16384)    # KEY_BODY_DN
            self.declare_parameter('height_click_m', 0.010)   # 1클릭당 ΔH[m]
            self.declare_parameter('height_band_m', 0.020)    # 데드밴드[m]
            self.declare_parameter('height_max_pps', 3.0)     # 초당 최대 클릭
            self.declare_parameter('height_pulse_ms', 120)    # 누름 시간[ms]
            self.declare_parameter('height_release_frames', 3)
            self.declare_parameter('height_timeout_s', 0.5)
            self.declare_parameter('height_max_down_m', 0.12) # 기준 대비 최대로 내릴 거리
            self.declare_parameter('height_auto_baseline', True)
            self.declare_parameter('height_down_start_h_ratio', 0.3333333)  # ★ h0의 1/2
    
            # 로그
            self.declare_parameter('log_transitions', True)
    
            # ========= 축 매핑/극성 파라미터 =========
            self.declare_parameter('forward_to', 'ly')         # 'ly' or 'lx'
            self.declare_parameter('invert_forward', False)
            self.declare_parameter('invert_strafe',  False)
            self.declare_parameter('no_reverse', True)
            self.declare_parameter('no_strafe',  True)
    
            # -------- 내부 상태 --------
            self.state = FSM.IDLE
            self.last_state = FSM.IDLE
            self.last_rx_time = 0.0
            self.t_last = time.time()
    
            self.vx_ema = 0.0
            self.vy_ema = 0.0
            self.yaw_prev_deg = None
            self.yaw_rate_ema = 0.0
    
            # UDP
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_ip = self.get_parameter('local_ip').value
            udp_port = int(self.get_parameter('udp_port').value)
            self.sock.bind((local_ip, udp_port))
            self.sock.setblocking(False)
    
            # Pub
            self.pub = self.create_publisher(WirelessController, '/wirelesscontroller', 10)
    
            # 기준을 "유니티 첫 h"로 자동 설정 → init_h0=None
            hz = float(self.get_parameter('hz').value)
            self.height_ctrl = RelativeHeightFollower(
                key_up=int(self.get_parameter('height_key_up').value),
                key_dn=int(self.get_parameter('height_key_dn').value),
                loop_hz=hz,
                click_m=float(self.get_parameter('height_click_m').value),
                band_m=float(self.get_parameter('height_band_m').value),
                max_pps=float(self.get_parameter('height_max_pps').value),
                pulse_ms=int(self.get_parameter('height_pulse_ms').value),
                release_frames=int(self.get_parameter('height_release_frames').value),
                timeout_s=float(self.get_parameter('height_timeout_s').value),
                max_down_m=float(self.get_parameter('height_max_down_m').value),
                auto_baseline=bool(self.get_parameter('height_auto_baseline').value),
                init_h0=None,  # ← 첫 유니티 h로 기준 자동설정
                down_start_h_ratio=float(self.get_parameter('height_down_start_h_ratio').value)
            )
    
            # Timer
            self.timer = self.create_timer(1.0 / max(1.0, hz), self.loop)
            self.get_logger().info(f"[omni_fsm] UDP {local_ip}:{udp_port}, hz={hz}")
    
        def loop(self):
            # 파라미터
            max_lin      = float(self.get_parameter('max_lin').value)
            max_ang      = float(self.get_parameter('max_ang').value)
            deadzone_lin = float(self.get_parameter('deadzone_lin').value)
            move_enter   = float(self.get_parameter('move_enter').value)
            rot_enter    = float(self.get_parameter('rot_enter').value)
            rot_exit     = float(self.get_parameter('rot_exit').value)
            alpha_v      = float(self.get_parameter('alpha_v').value)
            alpha_wz     = float(self.get_parameter('alpha_wz').value)
            timeout_s    = float(self.get_parameter('timeout_s').value)
            test_mode    = int(self.get_parameter('test_mode').value)
            log_trans    = bool(self.get_parameter('log_transitions').value)
    
            # 축 매핑 관련
            forward_to      = str(self.get_parameter('forward_to').value)  # 'ly' or 'lx'
            invert_forward  = bool(self.get_parameter('invert_forward').value)
            invert_strafe   = bool(self.get_parameter('invert_strafe').value)
            no_reverse      = bool(self.get_parameter('no_reverse').value)
            no_strafe       = bool(self.get_parameter('no_strafe').value)
    
            now = time.time()
            dt  = max(1e-6, now - self.t_last)
            self.t_last = now
    
            # 입력
            mx = my = 0.0
            yaw_deg = 0.0
            height = None
            active = False
    
            try:
                data, _ = self.sock.recvfrom(4096)
                pkt = json.loads(data.decode('utf-8'))
                mx = float(pkt.get('mx', 0.0))
                my = float(pkt.get('my', 0.0))
                yaw_deg = float(pkt.get('yaw_deg', 0.0))
                h_val = pkt.get('h', None)
                height = float(h_val) if h_val is not None else None
                active = bool(pkt.get('active', False))  # 기본 False
                self.last_rx_time = now
            except BlockingIOError:
                pass
            except Exception as e:
                self.get_logger().warning(f"UDP parse error: {e}")
    
            # 높이 팔로워 입력/업데이트 (정지 시에만 기준 설정·조절)
            self.height_ctrl.feed_h(height, now=now, accept_for_baseline=(not active))
            self.height_ctrl.update(active=active, now=now)
            extra_keys = self.height_ctrl.get_keys()
    
            # 워치독: 신호 끊기면 완전 정지
            if (now - self.last_rx_time) > timeout_s:
                self.publish_axes(0.0, 0.0, 0.0, 0.0, keys=0)
                self.set_state(FSM.IDLE, log_trans)
                return
    
            # 정지(active=False): 축 0, 높이 키만 퍼블리시
            if not active:
                self.publish_axes(0.0, 0.0, 0.0, 0.0, keys=int(extra_keys))
                self.set_state(FSM.IDLE, log_trans)
                return
    
            # ====== active=True: FSM 동작, 높이 키는 멈춤 ======
            vx_raw =  my * max_lin    # +X 전진
            vy_raw = -mx * max_lin    # +Y 좌측
            self.vx_ema = alpha_v * vx_raw + (1.0 - alpha_v) * self.vx_ema
            self.vy_ema = alpha_v * vy_raw + (1.0 - alpha_v) * self.vy_ema
    
            lin = math.hypot(self.vx_ema, self.vy_ema)
            if lin < deadzone_lin:
                vx_f = 0.0; vy_f = 0.0; lin = 0.0
            else:
                vx_f = self.vx_ema; vy_f = self.vy_ema
    
            if self.yaw_prev_deg is None:
                self.yaw_prev_deg = yaw_deg
            dyaw_deg = wrap_deg180(yaw_deg - self.yaw_prev_deg)
            self.yaw_prev_deg = yaw_deg
            yaw_rate_raw = math.radians(dyaw_deg) / dt
            self.yaw_rate_ema = alpha_wz * yaw_rate_raw + (1.0 - alpha_wz) * self.yaw_rate_ema
            yaw_rate = self.yaw_rate_ema
    
            # FSM 전이
            new_state = self.state
            if self.state == FSM.IDLE:
                if abs(yaw_rate) >= rot_enter:
                    new_state = FSM.ROTATE_ONLY
                elif lin >= move_enter:
                    new_state = FSM.STRAFE_ONLY
            elif self.state == FSM.ROTATE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (abs(yaw_rate) <= rot_exit) and (lin >= move_enter):
                    new_state = FSM.STRAFE_ONLY
                elif (abs(yaw_rate) < rot_enter) and (lin < move_enter):
                    new_state = FSM.IDLE
            elif self.state == FSM.STRAFE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (abs(yaw_rate) >= rot_enter) and (lin < move_enter):
                    new_state = FSM.ROTATE_ONLY
            elif self.state == FSM.CURVE_MOVE:
                if (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (lin >= move_enter) and (abs(yaw_rate) <= rot_exit):
                    new_state = FSM.STRAFE_ONLY
                elif (lin < move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.ROTATE_ONLY
    
            self.set_state(new_state, log_trans)
    
            # 상태별 축 계산/퍼블리시
            fwd_norm    = clamp(vx_f / max_lin, -1.0, 1.0)
            strafe_norm = clamp(vy_f / max_lin, -1.0, 1.0)
            
            using_strafe = not bool(self.get_parameter('no_strafe').value)
            if not using_strafe:
            	speed_norm = clamp(math.hypot(vx_f, vy_f)/max_lin, 0.0, 1.0)
            	fwd_norm = speed_norm
            
            if bool(self.get_parameter('invert_forward').value):  fwd_norm    = -fwd_norm
            if bool(self.get_parameter('invert_strafe').value):   strafe_norm = -strafe_norm
            if test_mode != 1:
                if bool(self.get_parameter('no_strafe').value):  strafe_norm = 0.0
                if bool(self.get_parameter('no_reverse').value):
                	EPS_BACK = 0.04
                	fwd_norm = 0.0 if abs(fwd_norm) < EPS_BACK else abs(fwd_norm)
    
            forward_to = str(self.get_parameter('forward_to').value)
            lx = ly = rx = 0.0
            if self.state == FSM.ROTATE_ONLY:
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0); lx = ly = 0.0
            elif self.state in (FSM.STRAFE_ONLY, FSM.CURVE_MOVE):
                if forward_to == 'ly':
                    ly = fwd_norm; lx = strafe_norm
                else:
                    lx = fwd_norm; ly = strafe_norm
                if self.state == FSM.CURVE_MOVE:
                    rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
    
            if test_mode == 1:
                lx = ly = 0.0
            elif test_mode == 2:
                rx = 0.0
            elif test_mode == 4:
                lx = ly = rx = 0.0
    
            self.publish_axes(lx, ly, rx, 0.0, keys=0)
    
        # 공용
        def set_state(self, s, log_transitions):
            if s != self.state:
                if log_transitions:
                    self.get_logger().info(f"[FSM] {self.state_name(self.state)} -> {self.state_name(s)}")
                self.last_state = self.state
                self.state = s
    
        def state_name(self, s):
            return {
                FSM.IDLE: "Idle",
                FSM.ROTATE_ONLY: "RotateOnly",
                FSM.STRAFE_ONLY: "StrafeOnly",
                FSM.CURVE_MOVE: "CurveMove",
            }.get(s, f"{s}")
    
        def publish_axes(self, lx, ly, rx, ry, keys=0):
            msg = WirelessController()
            msg.lx = float(lx); msg.ly = float(ly); msg.rx = float(rx); msg.ry = float(ry)
            try:
                msg.keys = int(keys)
            except AttributeError:
                pass
            self.pub.publish(msg)
    
    def main():
        rclpy.init()
        node = OmniFsmNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        rclpy.shutdown()
    
    if __name__ == '__main__':
        main()
    ```
    
- ~~rotatego2.py~~
    
    ```bash
    #!/usr/bin/env python3
    # moving_go2.py (axis-mapping fix)
    # Unity(Omni) → UDP(JSON: mx,my,yaw_deg,h,active) → FSM → /wirelesscontroller
    # 좌표: Unity mx(오른+)·my(앞+) → ROS2 +X=앞, +Y=좌 (vx=+my, vy=-mx)
    
    import json, math, socket, time
    import rclpy
    from rclpy.node import Node
    from unitree_go.msg import WirelessController
    
    def clamp(x, lo, hi):
        return lo if x < lo else hi if x > hi else x
    
    def wrap_deg180(d):
        while d > 180.0:
            d -= 360.0
        while d < -180.0:
            d += 360.0
        return d
    
    class FSM:
        IDLE = 0
        ROTATE_ONLY = 1
        STRAFE_ONLY = 2
        CURVE_MOVE = 3
    
    class OmniFsmNode(Node):
        def __init__(self):
            super().__init__('omni_fsm')
    
            # -------- ROS2 Parameters --------
            self.declare_parameter('udp_port', 5005)
            self.declare_parameter('local_ip', '0.0.0.0')
            self.declare_parameter('hz', 50)
    
            # 스케일/임계값
            self.declare_parameter('max_lin', 0.25)
            self.declare_parameter('max_ang', 1.00)
            self.declare_parameter('deadzone_lin', 0.06)
            self.declare_parameter('move_enter', 0.08)
            self.declare_parameter('rot_enter', 0.12)
            self.declare_parameter('rot_exit', 0.08)
    
            # 필터(EMA)
            self.declare_parameter('alpha_v', 0.20)
            self.declare_parameter('alpha_wz', 0.20)
    
            # 워치독
            self.declare_parameter('timeout_s', 0.30)
    
            # 테스트 모드
            self.declare_parameter('test_mode', 0)
    
            # 높낮이
            self.declare_parameter('use_ry_axis', False)
            self.declare_parameter('h0', 1.60)
            self.declare_parameter('hrange', 0.30)
            self.declare_parameter('height_deadband', 0.20)
    
            # 로그
            self.declare_parameter('log_transitions', True)
    
            # ========= [신규] 축 매핑/극성 파라미터 =========
            # forward_to: 'ly' (권장, 대부분 전진축이 ly) 또는 'lx'
            self.declare_parameter('forward_to', 'ly')
            self.declare_parameter('invert_forward', False)  # 전진축 부호 반전
            self.declare_parameter('invert_strafe', False)   # 스트레이프축 부호 반전
    
            # “항상 전진만” 옵션 (전진/스트레이프 축 정의에 맞춰 적용)
            self.declare_parameter('no_reverse', True)
            self.declare_parameter('no_strafe', True)
            # ============================================
    
            # -------- 내부 상태 --------
            self.state = FSM.IDLE
            self.last_state = FSM.IDLE
            self.last_rx_time = 0.0
            self.t_last = time.time()
    
            self.vx_ema = 0.0
            self.vy_ema = 0.0
    
            self.yaw_prev_deg = None
            self.yaw_rate_ema = 0.0
    
            # UDP
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_ip = self.get_parameter('local_ip').value
            udp_port = int(self.get_parameter('udp_port').value)
            self.sock.bind((local_ip, udp_port))
            self.sock.setblocking(False)
    
            # Pub
            self.pub = self.create_publisher(WirelessController, '/wirelesscontroller', 10)
    
            # Timer
            hz = float(self.get_parameter('hz').value)
            self.timer = self.create_timer(1.0 / max(1.0, hz), self.loop)
            self.get_logger().info(f"[omni_fsm] UDP {local_ip}:{udp_port}, hz={hz}")
    
        def loop(self):
            # 파라미터
            max_lin = float(self.get_parameter('max_lin').value)
            max_ang = float(self.get_parameter('max_ang').value)
    
            deadzone_lin = float(self.get_parameter('deadzone_lin').value)
            move_enter = float(self.get_parameter('move_enter').value)
            rot_enter = float(self.get_parameter('rot_enter').value)
            rot_exit = float(self.get_parameter('rot_exit').value)
    
            alpha_v = float(self.get_parameter('alpha_v').value)
            alpha_wz = float(self.get_parameter('alpha_wz').value)
    
            timeout_s = float(self.get_parameter('timeout_s').value)
            test_mode = int(self.get_parameter('test_mode').value)
    
            use_ry_axis = bool(self.get_parameter('use_ry_axis').value)
            h0 = float(self.get_parameter('h0').value)
            hrange = float(self.get_parameter('hrange').value)
            height_db = float(self.get_parameter('height_deadband').value)
    
            log_trans = bool(self.get_parameter('log_transitions').value)
    
            # [신규] 축 매핑 관련
            forward_to = str(self.get_parameter('forward_to').value)  # 'ly' or 'lx'
            invert_forward = bool(self.get_parameter('invert_forward').value)
            invert_strafe = bool(self.get_parameter('invert_strafe').value)
            no_reverse = bool(self.get_parameter('no_reverse').value)
            no_strafe = bool(self.get_parameter('no_strafe').value)
    
            now = time.time()
            dt = max(1e-6, now - self.t_last)
            self.t_last = now
    
            # 입력
            mx = my = 0.0
            yaw_deg = 0.0
            height = None
            active = False
    
            try:
                data, _ = self.sock.recvfrom(4096)
                pkt = json.loads(data.decode('utf-8'))
    
                mx = float(pkt.get('mx', 0.0))
                my = float(pkt.get('my', 0.0))
                yaw_deg = float(pkt.get('yaw_deg', 0.0))
    
                height = pkt.get('h', None)
                if height is not None:
                    height = float(height)
    
                active = bool(pkt.get('active', True))
                self.last_rx_time = now
    
            except BlockingIOError:
                pass
            except Exception as e:
                self.get_logger().warn(f"UDP parse error: {e}")
    
            # 워치독
            if (now - self.last_rx_time > timeout_s) or (not active):
                self.publish_axes(0.0, 0.0, 0.0, 0.0, keys=0)
                self.set_state(FSM.IDLE, log_trans)
                return
    
            # 좌표변환 + 필터
            vx_raw = my * max_lin   # +X 전진
            vy_raw = -mx * max_lin  # +Y 좌측
    
            self.vx_ema = alpha_v * vx_raw + (1.0 - alpha_v) * self.vx_ema
            self.vy_ema = alpha_v * vy_raw + (1.0 - alpha_v) * self.vy_ema
    
            lin = math.hypot(self.vx_ema, self.vy_ema)
    
            if lin < deadzone_lin:
                vx_f = 0.0
                vy_f = 0.0
                lin = 0.0
            else:
                vx_f = self.vx_ema
                vy_f = self.vy_ema
    
            # yaw → 각속도(EMA)
            if self.yaw_prev_deg is None:
                self.yaw_prev_deg = yaw_deg
    
            dyaw_deg = wrap_deg180(yaw_deg - self.yaw_prev_deg)
            self.yaw_prev_deg = yaw_deg
    
            yaw_rate_raw = math.radians(dyaw_deg) / dt
            self.yaw_rate_ema = alpha_wz * yaw_rate_raw + (1.0 - alpha_wz) * self.yaw_rate_ema
            yaw_rate = self.yaw_rate_ema
    
            # FSM 전이
            new_state = self.state
    
            if self.state == FSM.IDLE:
                if abs(yaw_rate) >= rot_enter:
                    new_state = FSM.ROTATE_ONLY
                elif lin >= move_enter:
                    new_state = FSM.STRAFE_ONLY
    
            elif self.state == FSM.ROTATE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (abs(yaw_rate) <= rot_exit) and (lin >= move_enter):
                    new_state = FSM.STRAFE_ONLY
                elif (abs(yaw_rate) < rot_enter) and (lin < move_enter):
                    new_state = FSM.IDLE
    
            elif self.state == FSM.STRAFE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (abs(yaw_rate) >= rot_enter) and (lin < move_enter):
                    new_state = FSM.ROTATE_ONLY
    
            elif self.state == FSM.CURVE_MOVE:
                if (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (lin >= move_enter) and (abs(yaw_rate) <= rot_exit):
                    new_state = FSM.STRAFE_ONLY
                elif (lin < move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.ROTATE_ONLY
    
            self.set_state(new_state, log_trans)
    
            # ====== 상태별 ‘전진/스트레이프’ 값 먼저 계산 ======
            # (정규화: [-1..1])
            fwd_norm = clamp(vx_f / max_lin, -1.0, 1.0)      # 전/후
            strafe_norm = clamp(vy_f / max_lin, -1.0, 1.0)   # 좌/우
    
            # 극성 옵션
            if invert_forward:
                fwd_norm = -fwd_norm
            if invert_strafe:
                strafe_norm = -strafe_norm
    
            # “항상 전진만” 옵션 적용 (테스트 모드 회전 전용 제외)
            if test_mode != 1:
                if no_strafe:
                    strafe_norm = 0.0
                if no_reverse:
                    fwd_norm = max(0.0, fwd_norm)
    
            # ====== 여기서부터 실제 컨트롤러 축에 ‘매핑’ ======
            # forward_to == 'ly' (권장): 전진은 ly, 스트레이프는 lx
            # forward_to == 'lx' : 전진은 lx, 스트레이프는 ly
            lx = ly = rx = 0.0
    
            if self.state == FSM.ROTATE_ONLY:
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
                lx = ly = 0.0
    
            elif self.state == FSM.STRAFE_ONLY:
                if forward_to == 'ly':
                    ly = fwd_norm
                    lx = strafe_norm
                else:
                    lx = fwd_norm
                    ly = strafe_norm
                rx = 0.0
    
            elif self.state == FSM.CURVE_MOVE:
                if forward_to == 'ly':
                    ly = fwd_norm
                    lx = strafe_norm
                else:
                    lx = fwd_norm
                    ly = strafe_norm
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
    
            # 테스트 모드 가드
            if test_mode == 1:
                # 회전만 테스트
                lx = ly = 0.0
            elif test_mode == 2:
                # 회전 차단
                rx = 0.0
            elif test_mode == 4:
                # 완전 정지
                lx = ly = rx = 0.0
    
            # 높낮이/키
            ry = 0.0
            keys = 0
            KEY_UP = 1 << 0
            KEY_DOWN = 1 << 1
    
            if height is not None:
                h_norm = 0.0
                if hrange > 1e-6:
                    h_norm = clamp((float(height) - h0) / hrange, -1.0, 1.0)
    
                if use_ry_axis:
                    ry = h_norm
                else:
                    if h_norm > +height_db:
                        keys |= KEY_UP
                    elif h_norm < -height_db:
                        keys |= KEY_DOWN
    
            self.publish_axes(lx, ly, rx, ry, keys)
    
        # 공용
        def set_state(self, s, log_transitions):
            if s != self.state:
                if log_transitions:
                    self.get_logger().info(
                        f"[FSM] {self.state_name(self.state)} -> {self.state_name(s)}"
                    )
                self.last_state = self.state
                self.state = s
    
        def state_name(self, s):
            return {
                FSM.IDLE: "Idle",
                FSM.ROTATE_ONLY: "RotateOnly",
                FSM.STRAFE_ONLY: "StrafeOnly",
                FSM.CURVE_MOVE: "CurveMove",
            }.get(s, f"{s}")
    
        def publish_axes(self, lx, ly, rx, ry, keys=0):
            msg = WirelessController()
            msg.lx = float(lx)
            msg.ly = float(ly)
            msg.rx = float(rx)
            msg.ry = float(ry)
            try:
                msg.keys = int(keys)
            except AttributeError:
                # 일부 메시지 타입에는 keys 필드가 없을 수 있음
                pass
            self.pub.publish(msg)
    
    def main():
        rclpy.init()
        node = OmniFsmNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        rclpy.shutdown()
    
    if __name__ == '__main__':
        main()
    
    ```
    
- ~~회전 코드 좋았던거(사용 X) → 뭔가 이상함 이 코드 아니고 위에 코드인것같~~
    
    ```python
    #!/usr/bin/env python3
    # omni_fsm_node.py
    # Unity(Omni) → UDP(JSON: mx,my,yaw_deg,h,active) → FSM → /wirelesscontroller 퍼블리시
    # 좌표계: Unity mx(오른+)·my(앞+) → ROS2 +X=앞, +Y=좌 로 맞춤(vx = +my, vy = -mx)
    
    import json, math, socket, time
    import rclpy
    from rclpy.node import Node
    
    # 메시지 타입은 환경에 맞게 조정 필요
    # - 일반적으로 unitree_go.msg.WirelessController 에 'lx, ly, rx, ry, keys' 필드가 있음
    from unitree_go.msg import WirelessController
    
    def clamp(x, lo, hi): return lo if x < lo else hi if x > hi else x
    def wrap_deg180(d):    # [-180, +180]로 접기
        while d > 180.0:  d -= 360.0
        while d < -180.0: d += 360.0
        return d
    
    class FSM:
        IDLE = 0
        ROTATE_ONLY = 1
        STRAFE_ONLY = 2
        CURVE_MOVE = 3
    
    class OmniFsmNode(Node):
        def __init__(self):
            super().__init__('omni_fsm')
    
            # -------- ROS2 Parameters (실행 중 변경 가능) --------
            self.declare_parameter('udp_port', 5005)
            self.declare_parameter('local_ip', '0.0.0.0')
            self.declare_parameter('hz', 50)
    
            # 스케일/임계값
            self.declare_parameter('max_lin', 0.25)      # m/s -> [-1,1]
            self.declare_parameter('max_ang', 1.00)      # rad/s -> [-1,1]
            self.declare_parameter('deadzone_lin', 0.06) # m/s
            self.declare_parameter('move_enter', 0.08)   # m/s
            self.declare_parameter('rot_enter', 0.12)    # rad/s
            self.declare_parameter('rot_exit', 0.08)     # rad/s
    
            # 필터(EMA)
            self.declare_parameter('alpha_v', 0.20)      # vx,vy
            self.declare_parameter('alpha_wz', 0.20)     # yaw rate
    
            # 워치독
            self.declare_parameter('timeout_s', 0.30)
    
            # 테스트 모드: 0 FULL / 1 ROTATE_ONLY / 2 STRAFE_ONLY / 3 CURVE / 4 HEIGHT_ONLY
            self.declare_parameter('test_mode', 0)
    
            # 높낮이 오버레이(선택)
            self.declare_parameter('use_ry_axis', False) # True면 ry에 높이 정규화 입력
            self.declare_parameter('h0', 1.60)           # 중립 키(미터)
            self.declare_parameter('hrange', 0.30)       # 상하 범위(±hrange)
            self.declare_parameter('height_deadband', 0.20) # 키 탭 deadband
    
            # 로그
            self.declare_parameter('log_transitions', True)
    
            # -------- 내부 상태 --------
            self.state = FSM.IDLE
            self.last_state = FSM.IDLE
            self.last_rx_time = 0.0
            self.t_last = time.time()
    
            self.vx_ema = 0.0
            self.vy_ema = 0.0
            self.yaw_prev_deg = None
            self.yaw_rate_ema = 0.0
    
            # UDP 수신 소켓
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_ip = self.get_parameter('local_ip').value
            udp_port = int(self.get_parameter('udp_port').value)
            self.sock.bind((local_ip, udp_port))
            self.sock.setblocking(False)
    
            # 퍼블리셔
            self.pub = self.create_publisher(WirelessController, '/wirelesscontroller', 10)
    
            # 타이머(주기 실행)
            hz = float(self.get_parameter('hz').value)
            self.timer = self.create_timer(1.0 / max(1.0, hz), self.loop)
    
            self.get_logger().info(f"[omni_fsm] UDP {local_ip}:{udp_port}, hz={hz}")
    
        # ---------------- 메인 루프 ----------------
        def loop(self):
            # 파라미터 읽기(실행 중 변경 반영)
            max_lin      = float(self.get_parameter('max_lin').value)
            max_ang      = float(self.get_parameter('max_ang').value)
            deadzone_lin = float(self.get_parameter('deadzone_lin').value)
            move_enter   = float(self.get_parameter('move_enter').value)
            rot_enter    = float(self.get_parameter('rot_enter').value)
            rot_exit     = float(self.get_parameter('rot_exit').value)
            alpha_v      = float(self.get_parameter('alpha_v').value)
            alpha_wz     = float(self.get_parameter('alpha_wz').value)
            timeout_s    = float(self.get_parameter('timeout_s').value)
            test_mode    = int(self.get_parameter('test_mode').value)
            use_ry_axis  = bool(self.get_parameter('use_ry_axis').value)
            h0           = float(self.get_parameter('h0').value)
            hrange       = float(self.get_parameter('hrange').value)
            height_db    = float(self.get_parameter('height_deadband').value)
            log_trans    = bool(self.get_parameter('log_transitions').value)
    
            now = time.time()
            dt  = max(1e-6, now - self.t_last)
            self.t_last = now
    
            # 기본값
            has_pkt = False
            mx = my = 0.0
            yaw_deg = 0.0
            height = None
            active = False
    
            # UDP 수신(JSON 파싱)
            try:
                data, _ = self.sock.recvfrom(4096)
                pkt = json.loads(data.decode('utf-8'))
                mx = float(pkt.get('mx', 0.0))        # -1..+1 (오른+)
                my = float(pkt.get('my', 0.0))        # -1..+1 (앞+)
                yaw_deg = float(pkt.get('yaw_deg', 0.0))  # 절대 각도(도)
                height = pkt.get('h', None)
                if height is not None:
                    height = float(height)
                active = bool(pkt.get('active', True))
                has_pkt = True
                self.last_rx_time = now
            except BlockingIOError:
                pass
            except Exception as e:
                self.get_logger().warn(f"UDP parse error: {e}")
    
            # 워치독: 신호 없음 or 비활성 → 정지
            if (now - self.last_rx_time > timeout_s) or (not active):
                self.publish_axes(0.0, 0.0, 0.0, 0.0, keys=0)
                self.set_state(FSM.IDLE, log_trans)
                return
    
            # ---------- 입력 스케일링/필터 ----------
            # Unity→ROS 좌표 변환 & m/s 스케일
            vx_raw =  my * max_lin        # 앞(+) → +X
            vy_raw = -mx * max_lin        # 오른(+) → -Y (ROS 규약: +Y=좌)
    
            # EMA for vx,vy
            self.vx_ema = alpha_v * vx_raw + (1.0 - alpha_v) * self.vx_ema
            self.vy_ema = alpha_v * vy_raw + (1.0 - alpha_v) * self.vy_ema
    
            # 속도 크기
            lin = math.hypot(self.vx_ema, self.vy_ema)
            if lin < deadzone_lin:
                vx_f = 0.0
                vy_f = 0.0
                lin  = 0.0
            else:
                vx_f = self.vx_ema
                vy_f = self.vy_ema
    
            # yaw: 절대각(도) → 언랩 → 각속도(rad/s) → EMA
            yaw_rate = 0.0
            if self.yaw_prev_deg is None:
                self.yaw_prev_deg = yaw_deg
            dyaw_deg = wrap_deg180(yaw_deg - self.yaw_prev_deg)
            self.yaw_prev_deg = yaw_deg
            yaw_rate_raw = math.radians(dyaw_deg) / dt
            self.yaw_rate_ema = alpha_wz * yaw_rate_raw + (1.0 - alpha_wz) * self.yaw_rate_ema
            yaw_rate = self.yaw_rate_ema
    
            # ---------- FSM 전이 ----------
            # test_mode 가드 전에 상태 계산 (FULL 동작 기준)
            new_state = self.state
            if self.state == FSM.IDLE:
                if abs(yaw_rate) >= rot_enter:
                    new_state = FSM.ROTATE_ONLY
                elif lin >= move_enter:
                    new_state = FSM.STRAFE_ONLY
    
            elif self.state == FSM.ROTATE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (abs(yaw_rate) <= rot_exit) and (lin >= move_enter):
                    new_state = FSM.STRAFE_ONLY
                elif (abs(yaw_rate) < rot_enter) and (lin < move_enter):
                    new_state = FSM.IDLE
    
            elif self.state == FSM.STRAFE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (abs(yaw_rate) >= rot_enter) and (lin < move_enter):
                    new_state = FSM.ROTATE_ONLY
    
            elif self.state == FSM.CURVE_MOVE:
                if (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (lin >= move_enter) and (abs(yaw_rate) <= rot_exit):
                    new_state = FSM.STRAFE_ONLY
                elif (lin < move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.ROTATE_ONLY
    
            self.set_state(new_state, log_trans)
    
            # ---------- 상태별 출력 값(lx, ly, rx) ----------
            lx = ly = rx = 0.0
    
            if self.state == FSM.ROTATE_ONLY:
                # 제자리 회전
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
                lx = ly = 0.0
    
            elif self.state == FSM.STRAFE_ONLY:
                lx = clamp(vx_f / max_lin, -1.0, 1.0)
                ly = clamp(vy_f / max_lin, -1.0, 1.0)
                rx = 0.0
    
            elif self.state == FSM.CURVE_MOVE:
                lx = clamp(vx_f / max_lin, -1.0, 1.0)
                ly = clamp(vy_f / max_lin, -1.0, 1.0)
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
    
            # ---------- 테스트 모드 가드 ----------
            # 0 FULL / 1 ROTATE_ONLY / 2 STRAFE_ONLY / 3 CURVE / 4 HEIGHT_ONLY
            if test_mode == 1:
                # 회전만 테스트
                lx = 0.0; ly = 0.0
            elif test_mode == 2:
                # 평면 이동만 테스트
                rx = 0.0
            elif test_mode == 3:
                # 선회 테스트(그대로)
                pass
            elif test_mode == 4:
                # 높낮이만 테스트
                lx = ly = rx = 0.0
    
            # ---------- 높낮이 오버레이 ----------
            ry = 0.0
            keys = 0
            KEY_UP = 1 << 0   # 실제 키 비트맵은 펌웨어에 맞게 조정
            KEY_DOWN = 1 << 1
    
            if height is not None:
                h_norm = 0.0
                if hrange > 1e-6:
                    h_norm = clamp((float(height) - h0) / hrange, -1.0, 1.0)
    
                if use_ry_axis:
                    # ry 축으로 직접 전달(펌웨어에서 해석 가능할 때만)
                    ry = h_norm
                else:
                    # 키 탭 방식: deadband 밖에서만 탭
                    if h_norm > +height_db:
                        keys |= KEY_UP
                    elif h_norm < -height_db:
                        keys |= KEY_DOWN
    
            # ---------- 퍼블리시 ----------
            self.publish_axes(lx, ly, rx, ry, keys)
    
        # 상태 변경 시 로그
        def set_state(self, s, log_transitions):
            if s != self.state:
                if log_transitions:
                    self.get_logger().info(f"[FSM] {self.state_name(self.state)} -> {self.state_name(s)}")
                self.last_state = self.state
                self.state = s
    
        def state_name(self, s):
            return {
                FSM.IDLE: "Idle",
                FSM.ROTATE_ONLY: "RotateOnly",
                FSM.STRAFE_ONLY: "StrafeOnly",
                FSM.CURVE_MOVE: "CurveMove",
            }.get(s, f"{s}")
    
        def publish_axes(self, lx, ly, rx, ry, keys=0):
            msg = WirelessController()
            # 사용 중인 메시지 정의에 맞게 필드명을 확인하세요.
            # (일반적으로 아래와 같은 축/키 필드가 존재)
            msg.lx = float(lx)
            msg.ly = float(ly)
            msg.rx = float(rx)
            msg.ry = float(ry)
            try:
                msg.keys = int(keys)
            except AttributeError:
                # keys 필드가 없다면 생략
                pass
            self.pub.publish(msg)
    
    def main():
        rclpy.init()
        node = OmniFsmNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        rclpy.shutdown()
    
    if __name__ == '__main__':
        main()
    
    ```
    
- ~~test3 → 이게 제일 최신꺼 제일 좋음~~
    
    ```bash
    #!/usr/bin/env python3
    # omni_fsm_mixed.py
    # moving_well 구조 유지 + 회전 처리(및 FSM 회전 전이, 매핑)는 예전 moving_go2 스타일 적용
    #
    # Unity(Omni) → UDP(JSON: mx,my,yaw_deg,h,active) → FSM → /wirelesscontroller
    # 좌표: Unity mx(오른+)·my(앞+) → ROS2 +X=앞, +Y=좌 (vx=+my, vy=-mx)
    
    import json
    import math
    import socket
    import time
    import rclpy
    from rclpy.node import Node
    
    from unitree_go.msg import WirelessController
    
    def clamp(x, lo, hi):
        return lo if x < lo else hi if x > hi else x
    
    def wrap_deg180(d):
        while d > 180.0:
            d -= 360.0
        while d < -180.0:
            d += 360.0
        return d
    
    class FSM:
        IDLE = 0
        ROTATE_ONLY = 1
        STRAFE_ONLY = 2
        CURVE_MOVE = 3
    
    class OmniFsmNode(Node):
        def __init__(self):
            super().__init__('omni_fsm_mixed')
    
            # -------- ROS2 Parameters (moving_well + a few mapping params) --------
            self.declare_parameter('udp_port', 5005)
            self.declare_parameter('local_ip', '0.0.0.0')
            self.declare_parameter('hz', 50)
    
            # 스케일/임계값
            self.declare_parameter('max_lin', 0.25)
            self.declare_parameter('max_ang', 1.00)
            self.declare_parameter('deadzone_lin', 0.06)
            self.declare_parameter('move_enter', 0.08)
            self.declare_parameter('rot_enter', 0.12)
            self.declare_parameter('rot_exit', 0.08)
    
            # 필터(EMA)
            self.declare_parameter('alpha_v', 0.20)
            self.declare_parameter('alpha_wz', 0.20)
    
            # 워치독
            self.declare_parameter('timeout_s', 0.30)
    
            # 테스트 모드
            # 0 normal, 1 rotation-only test, 2 rotation-block, 4 full stop
            self.declare_parameter('test_mode', 0)
    
            # 높낮이
            self.declare_parameter('use_ry_axis', False)
            self.declare_parameter('h0', 1.60)
            self.declare_parameter('hrange', 0.30)
            self.declare_parameter('height_deadband', 0.20)
    
            # 로그
            self.declare_parameter('log_transitions', True)
    
            # ========= 축 매핑/극성 파라미터 =========
            # forward_to: 'ly' (권장) or 'lx'
            self.declare_parameter('forward_to', 'ly')
            self.declare_parameter('invert_forward', False)
            self.declare_parameter('invert_strafe', False)
    
            # always forward / no strafe (for testing)
            self.declare_parameter('no_reverse', True)
            self.declare_parameter('no_strafe', True)
            # ============================================
    
            # -------- 내부 상태 --------
            self.state = FSM.IDLE
            self.last_state = FSM.IDLE
            self.last_rx_time = 0.0
            self.t_last = time.time()
    
            self.vx_ema = 0.0
            self.vy_ema = 0.0
    
            # rotation-state from old moving_go2
            self.yaw_prev_deg = None
            self.yaw_rate_ema = 0.0
    
            # UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_ip = self.get_parameter('local_ip').value
            udp_port = int(self.get_parameter('udp_port').value)
            self.sock.bind((local_ip, udp_port))
            self.sock.setblocking(False)
    
            # Publisher
            self.pub = self.create_publisher(WirelessController, '/wirelesscontroller', 10)
    
            # Timer
            hz = float(self.get_parameter('hz').value)
            self.timer = self.create_timer(1.0 / max(1.0, hz), self.loop)
            self.get_logger().info(f"[omni_fsm_mixed] UDP {local_ip}:{udp_port}, hz={hz}")
    
        def loop(self):
            # --- parameters (read every loop to allow runtime tuning) ---
            max_lin = float(self.get_parameter('max_lin').value)
            max_ang = float(self.get_parameter('max_ang').value)
    
            deadzone_lin = float(self.get_parameter('deadzone_lin').value)
            move_enter = float(self.get_parameter('move_enter').value)
            rot_enter = float(self.get_parameter('rot_enter').value)
            rot_exit = float(self.get_parameter('rot_exit').value)
    
            alpha_v = float(self.get_parameter('alpha_v').value)
            alpha_wz = float(self.get_parameter('alpha_wz').value)
    
            timeout_s = float(self.get_parameter('timeout_s').value)
            test_mode = int(self.get_parameter('test_mode').value)
    
            use_ry_axis = bool(self.get_parameter('use_ry_axis').value)
            h0 = float(self.get_parameter('h0').value)
            hrange = float(self.get_parameter('hrange').value)
            height_db = float(self.get_parameter('height_deadband').value)
    
            log_trans = bool(self.get_parameter('log_transitions').value)
    
            forward_to = str(self.get_parameter('forward_to').value)
            invert_forward = bool(self.get_parameter('invert_forward').value)
            invert_strafe = bool(self.get_parameter('invert_strafe').value)
            no_reverse = bool(self.get_parameter('no_reverse').value)
            no_strafe = bool(self.get_parameter('no_strafe').value)
    
            # --- timing ---
            now = time.time()
            dt = max(1e-6, now - self.t_last)
            self.t_last = now
    
            # --- receive UDP ---
            mx = my = 0.0
            yaw_deg = 0.0
            height = None
            active = False
    
            try:
                data, _ = self.sock.recvfrom(4096)
                pkt = json.loads(data.decode('utf-8'))
    
                mx = float(pkt.get('mx', 0.0))
                my = float(pkt.get('my', 0.0))
                yaw_deg = float(pkt.get('yaw_deg', 0.0))
    
                height = pkt.get('h', None)
                if height is not None:
                    height = float(height)
    
                active = bool(pkt.get('active', True))
                self.last_rx_time = now
    
            except BlockingIOError:
                # no packet this tick
                pass
            except Exception as e:
                # JSON/parse/etc error
                self.get_logger().warn(f"UDP parse error: {e}")
    
            # --- watchdog: if timeout OR not active -> fully stop (moving_well behavior) ---
            if (now - self.last_rx_time > timeout_s) or (not active):
                self.publish_axes(0.0, 0.0, 0.0, 0.0, keys=0)
                self.set_state(FSM.IDLE, log_trans)
                return
    
            # --- linear (vx, vy) conversion + EMA filtering (moving_well style) ---
            vx_raw = my * max_lin   # Unity my => forward (+X)
            vy_raw = -mx * max_lin  # Unity mx => right(+), but we want +Y = left
    
            self.vx_ema = alpha_v * vx_raw + (1.0 - alpha_v) * self.vx_ema
            self.vy_ema = alpha_v * vy_raw + (1.0 - alpha_v) * self.vy_ema
    
            lin = math.hypot(self.vx_ema, self.vy_ema)
    
            if lin < deadzone_lin:
                vx_f = 0.0
                vy_f = 0.0
                lin = 0.0
            else:
                vx_f = self.vx_ema
                vy_f = self.vy_ema
    
            # --------------------------
            # Rotation handling (OLD moving_go2 style)
            # --------------------------
            if self.yaw_prev_deg is None:
                self.yaw_prev_deg = yaw_deg
    
            dyaw_deg = wrap_deg180(yaw_deg - self.yaw_prev_deg)
            self.yaw_prev_deg = yaw_deg
    
            yaw_rate_raw = math.radians(dyaw_deg) / dt
            self.yaw_rate_ema = alpha_wz * yaw_rate_raw + (1.0 - alpha_wz) * self.yaw_rate_ema
            yaw_rate = self.yaw_rate_ema
            # --------------------------
    
            # --- FSM transitions (OLD moving_go2 style) ---
            new_state = self.state
    
            if self.state == FSM.IDLE:
                if abs(yaw_rate) >= rot_enter:
                    new_state = FSM.ROTATE_ONLY
                elif lin >= move_enter:
                    new_state = FSM.STRAFE_ONLY
    
            elif self.state == FSM.ROTATE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (abs(yaw_rate) <= rot_exit) and (lin >= move_enter):
                    new_state = FSM.STRAFE_ONLY
                elif (abs(yaw_rate) < rot_enter) and (lin < move_enter):
                    new_state = FSM.IDLE
    
            elif self.state == FSM.STRAFE_ONLY:
                if (lin >= move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.CURVE_MOVE
                elif (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (abs(yaw_rate) >= rot_enter) and (lin < move_enter):
                    new_state = FSM.ROTATE_ONLY
    
            elif self.state == FSM.CURVE_MOVE:
                if (lin < move_enter) and (abs(yaw_rate) < rot_enter):
                    new_state = FSM.IDLE
                elif (lin >= move_enter) and (abs(yaw_rate) <= rot_exit):
                    new_state = FSM.STRAFE_ONLY
                elif (lin < move_enter) and (abs(yaw_rate) >= rot_enter):
                    new_state = FSM.ROTATE_ONLY
    
            self.set_state(new_state, log_trans)
    
            # ====== ‘전진/스트레이프’ 값 계산 (정규화: [-1..1]) ======
            fwd_norm = clamp(vx_f / max_lin, -1.0, 1.0)
            strafe_norm = clamp(vy_f / max_lin, -1.0, 1.0)
    
            # ---- moving_well 스타일 보행 벡터 후처리 ----
            # no_strafe이면, 전체 속도 크기(hypot)를 전진값으로 사용
            using_strafe = not no_strafe
            if not using_strafe:
                speed_norm = clamp(math.hypot(vx_f, vy_f) / max_lin, 0.0, 1.0)
                fwd_norm = speed_norm
    
            # 극성 옵션
            if invert_forward:
                fwd_norm = -fwd_norm
            if invert_strafe:
                strafe_norm = -strafe_norm
    
            # “항상 전진만 / 스트레이프 막기” 옵션
            if test_mode != 1:
                if no_strafe:
                    strafe_norm = 0.0
                if no_reverse:
                    EPS_BACK = 0.04
                    fwd_norm = 0.0 if abs(fwd_norm) < EPS_BACK else abs(fwd_norm)
            # ---- 보행 벡터 처리 끝 ----
    
            # ====== 상태별 컨트롤 축 매핑 (회전 매핑은 예전 스타일 유지) ======
            lx = ly = rx = 0.0
    
            if self.state == FSM.ROTATE_ONLY:
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
                lx = ly = 0.0
    
            elif self.state == FSM.STRAFE_ONLY:
                if forward_to == 'ly':
                    ly = fwd_norm
                    lx = strafe_norm
                else:
                    lx = fwd_norm
                    ly = strafe_norm
                rx = 0.0
    
            elif self.state == FSM.CURVE_MOVE:
                if forward_to == 'ly':
                    ly = fwd_norm
                    lx = strafe_norm
                else:
                    lx = fwd_norm
                    ly = strafe_norm
                rx = clamp(yaw_rate / max_ang, -1.0, 1.0)
    
            # --- test_mode guards ---
            if test_mode == 1:
                lx = ly = 0.0
            elif test_mode == 2:
                rx = 0.0
            elif test_mode == 4:
                lx = ly = rx = 0.0
    
            # --- height/keys handling (simple moving_well style) ---
            ry = 0.0
            keys = 0
            KEY_UP = 1 << 0
            KEY_DOWN = 1 << 1
    
            if height is not None:
                h_norm = 0.0
                if hrange > 1e-6:
                    h_norm = clamp((float(height) - h0) / hrange, -1.0, 1.0)
    
                if use_ry_axis:
                    ry = h_norm
                else:
                    if h_norm > +height_db:
                        keys |= KEY_UP
                    elif h_norm < -height_db:
                        keys |= KEY_DOWN
    
            # publish to /wirelesscontroller
            self.publish_axes(lx, ly, rx, ry, keys)
    
        # ---------- helper methods ----------
        def set_state(self, s, log_transitions):
            if s != self.state:
                if log_transitions:
                    self.get_logger().info(f"[FSM] {self.state_name(self.state)} -> {self.state_name(s)}")
                self.last_state = self.state
                self.state = s
    
        def state_name(self, s):
            return {
                FSM.IDLE: "Idle",
                FSM.ROTATE_ONLY: "RotateOnly",
                FSM.STRAFE_ONLY: "StrafeOnly",
                FSM.CURVE_MOVE: "CurveMove",
            }.get(s, f"{s}")
    
        def publish_axes(self, lx, ly, rx, ry, keys=0):
            msg = WirelessController()
            msg.lx = float(lx)
            msg.ly = float(ly)
            msg.rx = float(rx)
            msg.ry = float(ry)
            try:
                msg.keys = int(keys)
            except AttributeError:
                # some message types might not have 'keys'
                pass
            self.pub.publish(msg)
    
    def main():
        rclpy.init()
        node = OmniFsmNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            rclpy.shutdown()
    
    if __name__ == '__main__':
        main()
    
    ```
    

## 영상

[https://youtu.be/8AZqPZcWN-I](https://youtu.be/8AZqPZcWN-I)

[https://youtu.be/YsG6uqIZtqA](https://youtu.be/YsG6uqIZtqA)

![image.png](image%2015.png)