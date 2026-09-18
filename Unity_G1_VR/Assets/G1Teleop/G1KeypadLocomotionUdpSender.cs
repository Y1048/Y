using System;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using UnityEngine;
using Stopwatch = System.Diagnostics.Stopwatch;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

/// <summary>Sends joystick-like numeric-keypad velocity input to localhost only.</summary>
public sealed class G1KeypadLocomotionUdpSender : MonoBehaviour
{
    private const string Host = "127.0.0.1";
    private const int Port = 5016;
    private const float SendPeriodSeconds = 0.02f;
    private const float VelocityStep = 0.20f;
    private const float VelocityLimit = 0.80f;

    [Serializable]
    private sealed class VelocityPacket
    {
        public string schema = "g1.velocity.keypad.v1";
        public string command_provenance = "unity_keypad";
        public bool simulation_only;
        public string session;
        public long sequence;
        public double source_monotonic_s;
        public float[] velocity;
    }

    private UdpClient udp;
    private IPEndPoint endpoint;
    private string session;
    private long sequence;
    private float sendTimer;
    private Vector3 lastLoggedVelocity;
    private bool haveLoggedVelocity;
    private readonly object velocityLock = new object();
    private Vector3 latchedVelocity;
    private readonly bool[] previousKeyStates = new bool[7];
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
    private Timer windowsSendTimer;
#endif

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void Install()
    {
        if (G1BimanualSimulationSender.IsSimulationSceneLoaded()) return;
        if (FindObjectOfType<G1KeypadLocomotionUdpSender>() != null) return;
        GameObject sender = new GameObject("G1KeypadLocomotionUdpSender");
        DontDestroyOnLoad(sender);
        sender.AddComponent<G1KeypadLocomotionUdpSender>();
    }

    private void Awake()
    {
        if (G1BimanualSimulationSender.IsSimulationSceneLoaded()) { enabled = false; return; }
        udp = new UdpClient();
        endpoint = new IPEndPoint(IPAddress.Loopback, Port);
        session = Guid.NewGuid().ToString("N");
        Debug.Log("G1 KEYPAD latched locomotion: each 8/2/4/6/7/9 press changes one axis by 0.2, 5 alone stops; limits +/-0.8; localhost UDP 5016");
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
        windowsSendTimer = new Timer(_ => SendWindowsHeartbeat(), null, 0, 20);
#endif
    }

    private void Update()
    {
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
        // The Windows heartbeat is independent of XR/main-frame updates.
        return;
#else
        sendTimer += Time.unscaledDeltaTime;
        if (sendTimer < SendPeriodSeconds) return;
        sendTimer %= SendPeriodSeconds;
        Send(ReadLatchedVelocity());
#endif
    }

    private Vector3 ReadLatchedVelocity()
    {
        // Windows reports keypad navigation keys as Keypad* with Num Lock on,
        // and as navigation keys with Num Lock off. Accept both forms so the
        // operator does not silently send a zero command.
        bool[] current = { ForwardPressed(), BackwardPressed(), LeftPressed(),
            RightPressed(), TurnLeftPressed(), TurnRightPressed(), StopPressed() };
        lock (velocityLock)
        {
            ApplyRisingEdges(current);
            return latchedVelocity;
        }
    }

    private void ApplyRisingEdges(bool[] current)
    {
        if (current[6] && !previousKeyStates[6]) latchedVelocity = Vector3.zero;
        else
        {
            float x = latchedVelocity.x;
            float y = latchedVelocity.y;
            float z = latchedVelocity.z;
            if (current[0] && !previousKeyStates[0]) x += VelocityStep;
            if (current[1] && !previousKeyStates[1]) x -= VelocityStep;
            if (current[2] && !previousKeyStates[2]) y += VelocityStep;
            if (current[3] && !previousKeyStates[3]) y -= VelocityStep;
            if (current[4] && !previousKeyStates[4]) z += VelocityStep;
            if (current[5] && !previousKeyStates[5]) z -= VelocityStep;
            latchedVelocity = new Vector3(
                Mathf.Clamp(x, -VelocityLimit, VelocityLimit),
                Mathf.Clamp(y, -VelocityLimit, VelocityLimit),
                Mathf.Clamp(z, -VelocityLimit, VelocityLimit));
        }
        Array.Copy(current, previousKeyStates, current.Length);
    }

    private static bool AnyKey(KeyCode keypad, KeyCode navigation)
    {
        return Input.GetKey(keypad) || Input.GetKey(navigation);
    }

    private static bool ForwardPressed() => AnyKey(KeyCode.Keypad8, KeyCode.UpArrow)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad8Key.isPressed || Keyboard.current.upArrowKey.isPressed))
#endif
        || WindowsKeyDown(0x68) || WindowsKeyDown(0x26)
        ;
    private static bool BackwardPressed() => AnyKey(KeyCode.Keypad2, KeyCode.DownArrow)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad2Key.isPressed || Keyboard.current.downArrowKey.isPressed))
#endif
        || WindowsKeyDown(0x62) || WindowsKeyDown(0x28)
        ;
    private static bool LeftPressed() => AnyKey(KeyCode.Keypad4, KeyCode.LeftArrow)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad4Key.isPressed || Keyboard.current.leftArrowKey.isPressed))
#endif
        || WindowsKeyDown(0x64) || WindowsKeyDown(0x25)
        ;
    private static bool RightPressed() => AnyKey(KeyCode.Keypad6, KeyCode.RightArrow)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad6Key.isPressed || Keyboard.current.rightArrowKey.isPressed))
#endif
        || WindowsKeyDown(0x66) || WindowsKeyDown(0x27)
        ;
    private static bool TurnLeftPressed() => AnyKey(KeyCode.Keypad7, KeyCode.Home)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad7Key.isPressed || Keyboard.current.homeKey.isPressed))
#endif
        || WindowsKeyDown(0x67) || WindowsKeyDown(0x24)
        ;
    private static bool TurnRightPressed() => AnyKey(KeyCode.Keypad9, KeyCode.PageUp)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && (Keyboard.current.numpad9Key.isPressed || Keyboard.current.pageUpKey.isPressed))
#endif
        || WindowsKeyDown(0x69) || WindowsKeyDown(0x21)
        ;
    private static bool StopPressed() => AnyKey(KeyCode.Keypad5, KeyCode.Clear)
#if ENABLE_INPUT_SYSTEM
        || (Keyboard.current != null && Keyboard.current.numpad5Key.isPressed)
#endif
        || WindowsKeyDown(0x65) || WindowsKeyDown(0x0C)
        ;

#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int virtualKey);
#endif

    private static bool WindowsKeyDown(int virtualKey)
    {
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
        return (GetAsyncKeyState(virtualKey) & 0x8000) != 0;
#else
        return false;
#endif
    }

#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
    private Vector3 ReadWindowsVelocity()
    {
        bool[] current = {
            WindowsKeyDown(0x68) || WindowsKeyDown(0x26),
            WindowsKeyDown(0x62) || WindowsKeyDown(0x28),
            WindowsKeyDown(0x64) || WindowsKeyDown(0x25),
            WindowsKeyDown(0x66) || WindowsKeyDown(0x27),
            WindowsKeyDown(0x67) || WindowsKeyDown(0x24),
            WindowsKeyDown(0x69) || WindowsKeyDown(0x21),
            WindowsKeyDown(0x65) || WindowsKeyDown(0x0C)
        };
        lock (velocityLock)
        {
            ApplyRisingEdges(current);
            return latchedVelocity;
        }
    }

    private void SendWindowsHeartbeat()
    {
        try
        {
            Vector3 velocity = ReadWindowsVelocity();
            long packetSequence = Interlocked.Increment(ref sequence) - 1;
            double monotonicSeconds = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
            string json = string.Format(CultureInfo.InvariantCulture,
                "{{\"schema\":\"g1.velocity.keypad.v1\",\"command_provenance\":\"unity_keypad\",\"simulation_only\":false,\"session\":\"{0}\",\"sequence\":{1},\"source_monotonic_s\":{2:R},\"velocity\":[{3:R},{4:R},{5:R}]}}",
                session, packetSequence, monotonicSeconds,
                velocity.x, velocity.y, velocity.z);
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            udp?.Send(bytes, bytes.Length, endpoint);
        }
        catch (ObjectDisposedException) { }
        catch (SocketException) { }
    }
#endif

    private void Send(Vector3 velocity)
    {
        if (udp == null) return;
        if (!haveLoggedVelocity || velocity != lastLoggedVelocity)
        {
            Debug.Log($"G1 KEYPAD velocity=({velocity.x:F2}, {velocity.y:F2}, {velocity.z:F2})");
            lastLoggedVelocity = velocity;
            haveLoggedVelocity = true;
        }
        VelocityPacket packet = new VelocityPacket
        {
            simulation_only = false,
            session = session,
            sequence = sequence++,
            source_monotonic_s = Time.realtimeSinceStartupAsDouble,
            velocity = new[] { velocity.x, velocity.y, velocity.z }
        };
        byte[] bytes = Encoding.UTF8.GetBytes(JsonUtility.ToJson(packet));
        udp.Send(bytes, bytes.Length, endpoint);
    }

    private void OnDestroy()
    {
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
        windowsSendTimer?.Dispose();
        windowsSendTimer = null;
#endif
        try { Send(Vector3.zero); } catch (Exception) { }
        udp?.Close();
        udp = null;
    }
}
