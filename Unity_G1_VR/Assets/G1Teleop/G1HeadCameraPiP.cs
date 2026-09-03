using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// WSL의 읽기 전용 G1 카메라 브리지에서 JPEG를 받아 시야 고정 PiP에 표시한다.
/// 로봇 제어 패킷, IK 목표, 관절 명령은 만들지 않는다.
/// </summary>
public sealed class G1HeadCameraPiP : MonoBehaviour
{
    public const int DefaultTcpPort = 5011;
    public const int FrameHeaderSize = 24;
    public const int FrameVersion = 1;
    public const int MaximumJpegBytes = 4 * 1024 * 1024;
    public const string ObjectName = "G1_Head_Camera_PiP";

    public RawImage video_image;
    public Image status_indicator;
    public int tcp_port = DefaultTcpPort;
    public bool listen_on_start = true;
    [Min(0.25f)]
    public float stale_frame_timeout_seconds = 1.0f;

    public bool HasLiveFrame => received_frame
        && Time.realtimeSinceStartup - last_frame_time
            <= stale_frame_timeout_seconds;
    public bool IsBridgeConnected => bridge_connected;
    public string LastError
    {
        get
        {
            lock (state_lock)
            {
                return last_error;
            }
        }
    }

    private static readonly Color offline_color =
        new Color(0.55f, 0.58f, 0.62f, 1.0f);
    private static readonly Color waiting_color =
        new Color(1.0f, 0.72f, 0.12f, 1.0f);
    private static readonly Color live_color =
        new Color(0.16f, 0.85f, 0.40f, 1.0f);
    private static readonly Color failed_color =
        new Color(0.95f, 0.24f, 0.22f, 1.0f);

    private readonly object state_lock = new object();
    private TcpListener tcp_listener;
    private TcpClient active_client;
    private CancellationTokenSource receiver_cancellation;
    private Task receiver_task;
    private byte[] pending_jpeg;
    private Texture2D decoded_texture;
    private Texture2D placeholder_texture;
    private volatile bool bridge_connected;
    private bool receiver_started;
    private bool received_frame;
    private float last_frame_time;
    private string last_error = string.Empty;
    private string last_logged_error = string.Empty;

    public static G1HeadCameraPiP Create(
        Transform center_eye,
        int camera_tcp_port = DefaultTcpPort)
    {
        if (center_eye == null)
        {
            return null;
        }

        G1HeadCameraPiP existing_value = GetDirectChildComponent(center_eye);
        if (existing_value != null)
        {
            existing_value.tcp_port = camera_tcp_port;
            existing_value.gameObject.SetActive(true);
            return existing_value;
        }

        GameObject canvas_object = new GameObject(
            ObjectName,
            typeof(RectTransform),
            typeof(Canvas),
            typeof(CanvasScaler));
        canvas_object.SetActive(false);
        RectTransform canvas_transform =
            canvas_object.GetComponent<RectTransform>();
        canvas_transform.SetParent(center_eye, false);
        canvas_transform.localPosition = new Vector3(0.0f, 0.0f, 0.80f);
        canvas_transform.localRotation = Quaternion.identity;
        canvas_transform.localScale = Vector3.one * 0.00075f;
        canvas_transform.sizeDelta = new Vector2(320.0f, 240.0f);

        Canvas canvas_value = canvas_object.GetComponent<Canvas>();
        canvas_value.renderMode = RenderMode.WorldSpace;
        canvas_value.worldCamera = center_eye.GetComponent<Camera>();
        canvas_value.overrideSorting = true;
        canvas_value.sortingOrder = 100;

        CanvasScaler scaler_value = canvas_object.GetComponent<CanvasScaler>();
        scaler_value.dynamicPixelsPerUnit = 10.0f;

        Image frame_image = CreateImage(
            canvas_transform,
            "Camera_Frame",
            new Color(0.025f, 0.030f, 0.040f, 0.98f));
        Stretch(frame_image.rectTransform, Vector2.zero, Vector2.zero);

        RawImage camera_image = CreateRawImage(
            frame_image.rectTransform,
            "Camera_Video");
        Stretch(
            camera_image.rectTransform,
            new Vector2(7.0f, 7.0f),
            new Vector2(-7.0f, -7.0f));
        camera_image.raycastTarget = false;
        camera_image.color = Color.white;

        Image status_image = CreateImage(
            frame_image.rectTransform,
            "Camera_Status",
            offline_color);
        RectTransform status_transform = status_image.rectTransform;
        status_transform.anchorMin = new Vector2(0.0f, 1.0f);
        status_transform.anchorMax = new Vector2(0.0f, 1.0f);
        status_transform.pivot = new Vector2(0.0f, 1.0f);
        status_transform.anchoredPosition = new Vector2(14.0f, -14.0f);
        status_transform.sizeDelta = new Vector2(18.0f, 18.0f);
        status_image.raycastTarget = false;

        G1HeadCameraPiP pip_value =
            canvas_object.AddComponent<G1HeadCameraPiP>();
        pip_value.video_image = camera_image;
        pip_value.status_indicator = status_image;
        pip_value.tcp_port = camera_tcp_port;
        canvas_object.SetActive(true);
        return pip_value;
    }

    public static bool IsValidLoopbackPort(int value)
    {
        return value >= 1 && value <= 65535;
    }

    public static bool TryParseFrameHeader(
        byte[] header,
        out uint sequence,
        out ulong timestamp_ns,
        out int payload_size)
    {
        sequence = 0;
        timestamp_ns = 0;
        payload_size = 0;
        if (header == null || header.Length != FrameHeaderSize)
        {
            return false;
        }

        if (header[0] != (byte)'G'
            || header[1] != (byte)'1'
            || header[2] != (byte)'C'
            || header[3] != (byte)'M')
        {
            return false;
        }

        uint version = ReadUInt32BigEndian(header, 4);
        uint payload_size_unsigned = ReadUInt32BigEndian(header, 20);
        if (version != FrameVersion
            || payload_size_unsigned < 4
            || payload_size_unsigned > MaximumJpegBytes)
        {
            return false;
        }

        sequence = ReadUInt32BigEndian(header, 8);
        timestamp_ns = ReadUInt64BigEndian(header, 12);
        payload_size = (int)payload_size_unsigned;
        return true;
    }

    private void OnEnable()
    {
        InitializeDisplay();
        if (Application.isPlaying && listen_on_start)
        {
            StartReceiver();
        }
    }

    private void Update()
    {
        ConsumeNewestFrame();
        UpdateStatus();
        LogPendingError();
    }

    private void OnDisable()
    {
        StopReceiver();
        SetStatus(offline_color);
    }

    private void OnDestroy()
    {
        StopReceiver();
        if (decoded_texture != null)
        {
            Destroy(decoded_texture);
            decoded_texture = null;
        }
        if (placeholder_texture != null)
        {
            Destroy(placeholder_texture);
            placeholder_texture = null;
        }
    }

    private void StartReceiver()
    {
        if (receiver_started)
        {
            return;
        }
        if (!IsValidLoopbackPort(tcp_port))
        {
            SetBackgroundError("G1 camera TCP port is invalid.");
            return;
        }

        try
        {
            receiver_cancellation = new CancellationTokenSource();
            tcp_listener = new TcpListener(IPAddress.Loopback, tcp_port);
            tcp_listener.Start(1);
            receiver_started = true;
            receiver_task = Task.Run(
                () => RunReceiver(receiver_cancellation.Token));
            Debug.Log(
                $"G1 camera PiP listening on 127.0.0.1:{tcp_port}. "
                + "Run tools/START_G1_CAMERA_TO_UNITY.bat while G1 is connected.");
        }
        catch (Exception exception_value)
        {
            receiver_started = false;
            SetBackgroundError(
                "G1 camera TCP listener failed: "
                + exception_value.Message);
        }
    }

    private void RunReceiver(CancellationToken cancellation_token)
    {
        while (!cancellation_token.IsCancellationRequested)
        {
            TcpClient client_value = null;
            try
            {
                client_value = tcp_listener.AcceptTcpClient();
                client_value.NoDelay = true;
                lock (state_lock)
                {
                    active_client = client_value;
                    bridge_connected = true;
                    last_error = string.Empty;
                }

                ReceiveFrames(client_value, cancellation_token);
            }
            catch (SocketException exception_value)
            {
                if (!cancellation_token.IsCancellationRequested)
                {
                    SetBackgroundError(
                        "G1 camera TCP socket failed: "
                        + exception_value.Message);
                }
            }
            catch (Exception exception_value)
            {
                if (!cancellation_token.IsCancellationRequested)
                {
                    SetBackgroundError(
                        "G1 camera frame receiver failed: "
                        + exception_value.Message);
                }
            }
            finally
            {
                lock (state_lock)
                {
                    if (active_client == client_value)
                    {
                        active_client = null;
                    }
                    bridge_connected = false;
                }
                if (client_value != null)
                {
                    client_value.Close();
                }
            }
        }
    }

    private void ReceiveFrames(
        TcpClient client_value,
        CancellationToken cancellation_token)
    {
        NetworkStream stream_value = client_value.GetStream();
        byte[] header = new byte[FrameHeaderSize];
        while (!cancellation_token.IsCancellationRequested)
        {
            if (!ReadExactly(
                stream_value,
                header,
                header.Length,
                cancellation_token))
            {
                return;
            }

            if (!TryParseFrameHeader(
                header,
                out _,
                out _,
                out int payload_size))
            {
                throw new InvalidDataException(
                    "G1 camera frame header is invalid");
            }

            byte[] jpeg_payload = new byte[payload_size];
            if (!ReadExactly(
                stream_value,
                jpeg_payload,
                payload_size,
                cancellation_token))
            {
                return;
            }
            if (jpeg_payload[0] != 0xFF
                || jpeg_payload[1] != 0xD8
                || jpeg_payload[payload_size - 2] != 0xFF
                || jpeg_payload[payload_size - 1] != 0xD9)
            {
                throw new InvalidDataException(
                    "G1 camera payload is not a complete JPEG image");
            }

            lock (state_lock)
            {
                pending_jpeg = jpeg_payload;
                last_error = string.Empty;
            }
        }
    }

    private static bool ReadExactly(
        NetworkStream stream_value,
        byte[] destination,
        int length,
        CancellationToken cancellation_token)
    {
        int offset = 0;
        while (offset < length && !cancellation_token.IsCancellationRequested)
        {
            int read_count = stream_value.Read(
                destination,
                offset,
                length - offset);
            if (read_count <= 0)
            {
                return false;
            }
            offset += read_count;
        }
        return offset == length;
    }

    private void StopReceiver()
    {
        if (!receiver_started && receiver_cancellation == null)
        {
            return;
        }

        receiver_started = false;
        receiver_cancellation?.Cancel();
        lock (state_lock)
        {
            active_client?.Close();
            active_client = null;
            bridge_connected = false;
            pending_jpeg = null;
        }
        tcp_listener?.Stop();
        tcp_listener = null;

        if (receiver_task != null && !receiver_task.IsCompleted)
        {
            try
            {
                receiver_task.Wait(250);
            }
            catch (AggregateException)
            {
            }
        }
        receiver_task = null;
        receiver_cancellation?.Dispose();
        receiver_cancellation = null;
        received_frame = false;
    }

    private void ConsumeNewestFrame()
    {
        byte[] jpeg_payload;
        lock (state_lock)
        {
            jpeg_payload = pending_jpeg;
            pending_jpeg = null;
        }
        if (jpeg_payload == null)
        {
            return;
        }

        if (decoded_texture == null)
        {
            decoded_texture = new Texture2D(
                2,
                2,
                TextureFormat.RGB24,
                false);
            decoded_texture.name = "G1_Live_Head_Camera";
            decoded_texture.wrapMode = TextureWrapMode.Clamp;
            decoded_texture.filterMode = FilterMode.Bilinear;
        }

        if (!ImageConversion.LoadImage(
            decoded_texture,
            jpeg_payload,
            false))
        {
            SetBackgroundError("Unity could not decode the G1 camera JPEG.");
            return;
        }

        if (video_image != null)
        {
            video_image.texture = decoded_texture;
            video_image.color = Color.white;
        }
        received_frame = true;
        last_frame_time = Time.realtimeSinceStartup;
    }

    private void UpdateStatus()
    {
        if (HasLiveFrame)
        {
            SetStatus(live_color);
            return;
        }
        if (received_frame || !string.IsNullOrWhiteSpace(LastError))
        {
            SetStatus(failed_color);
            return;
        }
        SetStatus(receiver_started ? waiting_color : offline_color);
    }

    private void SetBackgroundError(string error_message)
    {
        lock (state_lock)
        {
            last_error = error_message;
        }
    }

    private void LogPendingError()
    {
        string error_message = LastError;
        if (!string.IsNullOrWhiteSpace(error_message)
            && !string.Equals(
                last_logged_error,
                error_message,
                StringComparison.Ordinal))
        {
            Debug.LogWarning(error_message);
            last_logged_error = error_message;
        }
    }

    private void InitializeDisplay()
    {
        if (placeholder_texture == null)
        {
            placeholder_texture = CreatePlaceholderTexture();
        }
        if (video_image != null)
        {
            video_image.texture = placeholder_texture;
            video_image.color = Color.white;
        }
        SetStatus(offline_color);
    }

    private void SetStatus(Color status_color)
    {
        if (status_indicator != null)
        {
            status_indicator.color = status_color;
        }
    }

    private static uint ReadUInt32BigEndian(byte[] value, int offset)
    {
        return ((uint)value[offset] << 24)
            | ((uint)value[offset + 1] << 16)
            | ((uint)value[offset + 2] << 8)
            | value[offset + 3];
    }

    private static ulong ReadUInt64BigEndian(byte[] value, int offset)
    {
        return ((ulong)value[offset] << 56)
            | ((ulong)value[offset + 1] << 48)
            | ((ulong)value[offset + 2] << 40)
            | ((ulong)value[offset + 3] << 32)
            | ((ulong)value[offset + 4] << 24)
            | ((ulong)value[offset + 5] << 16)
            | ((ulong)value[offset + 6] << 8)
            | value[offset + 7];
    }

    private static Texture2D CreatePlaceholderTexture()
    {
        Texture2D texture_value = new Texture2D(
            8,
            6,
            TextureFormat.RGBA32,
            false);
        texture_value.name = "G1_Head_Camera_Waiting";
        texture_value.wrapMode = TextureWrapMode.Clamp;
        texture_value.filterMode = FilterMode.Point;
        Color dark_color = new Color(0.09f, 0.11f, 0.14f, 1.0f);
        Color light_color = new Color(0.16f, 0.19f, 0.23f, 1.0f);
        for (int y_index = 0; y_index < texture_value.height; y_index++)
        {
            for (int x_index = 0; x_index < texture_value.width; x_index++)
            {
                texture_value.SetPixel(
                    x_index,
                    y_index,
                    (x_index + y_index) % 2 == 0
                        ? dark_color
                        : light_color);
            }
        }
        texture_value.Apply(false, true);
        return texture_value;
    }

    private static G1HeadCameraPiP GetDirectChildComponent(
        Transform center_eye)
    {
        for (int child_index = 0;
            child_index < center_eye.childCount;
            child_index++)
        {
            Transform child_value = center_eye.GetChild(child_index);
            if (child_value.name == ObjectName)
            {
                return child_value.GetComponent<G1HeadCameraPiP>();
            }
        }
        return null;
    }

    private static Image CreateImage(
        Transform parent_transform,
        string object_name,
        Color image_color)
    {
        GameObject image_object = new GameObject(
            object_name,
            typeof(RectTransform),
            typeof(CanvasRenderer),
            typeof(Image));
        image_object.transform.SetParent(parent_transform, false);
        Image image_value = image_object.GetComponent<Image>();
        image_value.color = image_color;
        image_value.raycastTarget = false;
        return image_value;
    }

    private static RawImage CreateRawImage(
        Transform parent_transform,
        string object_name)
    {
        GameObject image_object = new GameObject(
            object_name,
            typeof(RectTransform),
            typeof(CanvasRenderer),
            typeof(RawImage));
        image_object.transform.SetParent(parent_transform, false);
        return image_object.GetComponent<RawImage>();
    }

    private static void Stretch(
        RectTransform rect_transform,
        Vector2 offset_min,
        Vector2 offset_max)
    {
        rect_transform.anchorMin = Vector2.zero;
        rect_transform.anchorMax = Vector2.one;
        rect_transform.pivot = new Vector2(0.5f, 0.5f);
        rect_transform.offsetMin = offset_min;
        rect_transform.offsetMax = offset_max;
    }
}
