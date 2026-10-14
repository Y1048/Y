using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

// Only an active local keyboard gateway enables this input. It never rotates XR tracking space.
public sealed class G1GameKeyboardInput : MonoBehaviour
{
    [Serializable] private sealed class Packet
    {
        public string schema = "g1.unity.keyboard.v1";
        public string token = "";
        public long request_sequence = -1;
        public bool focused;
        public int forward, left, turn_left;
    }
    private UdpClient socket;
    private Packet request;
    private double lastRequest = double.NegativeInfinity;
    private double nextSend;
    private bool armed;
    private string status = "";
    private readonly IPEndPoint destination = new IPEndPoint(IPAddress.Loopback, 55077);

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Install()
    {
        if (FindAnyObjectByType<G1GameKeyboardInput>() != null) return;
        var owner = new GameObject("G1 Game Keyboard Input");
        DontDestroyOnLoad(owner);
        owner.AddComponent<G1GameKeyboardInput>();
    }

    private void OnEnable()
    {
        try
        {
            socket = new UdpClient(AddressFamily.InterNetwork);
            socket.ExclusiveAddressUse = true;
            socket.Client.Bind(new IPEndPoint(IPAddress.Loopback, 55076));
            socket.Client.Blocking = false;
        }
        catch (SocketException error)
        {
            socket?.Close(); socket = null;
            Debug.LogWarning("[G1 KEYBOARD] Cannot bind local input port: " + error.Message);
        }
    }

    private static bool GameFocused()
    {
        if (!Application.isFocused) return false;
#if UNITY_EDITOR
        var window = UnityEditor.EditorWindow.focusedWindow;
        return window != null && window.GetType().Name == "GameView";
#else
        return true;
#endif
    }

    private static bool Held(char key)
    {
#if ENABLE_INPUT_SYSTEM
        var keyboard = Keyboard.current;
        if (keyboard == null) return false;
        switch (key)
        {
            case 'w': return keyboard.wKey.isPressed;
            case 's': return keyboard.sKey.isPressed;
            case 'a': return keyboard.aKey.isPressed;
            case 'd': return keyboard.dKey.isPressed;
            case 'q': return keyboard.qKey.isPressed;
            case 'e': return keyboard.eKey.isPressed;
        }
        return false;
#else
        return Input.GetKey(key.ToString());
#endif
    }

    private void Update()
    {
        if (socket == null) return;
        double now = Time.realtimeSinceStartupAsDouble;
        try
        {
            for (int count = 0; count < 64 && socket.Available > 0; count++)
            {
                IPEndPoint peer = null;
                byte[] raw = socket.Receive(ref peer);
                if (!peer.Equals(destination) || raw.Length > 2048) continue;
                Packet next;
                try { next = JsonUtility.FromJson<Packet>(Encoding.UTF8.GetString(raw)); }
                catch (ArgumentException) { continue; }
                if (next == null || next.schema != "g1.unity.keyboard.v1" ||
                    next.token == null || next.token.Length != 32 || next.request_sequence < 0) continue;
                if (request != null && next.token == request.token &&
                    next.request_sequence <= request.request_sequence) continue;
                if (request == null || next.token != request.token || now - lastRequest > 0.15) armed = false;
                request = next;
                lastRequest = now;
            }
            if (request == null || now - lastRequest > 0.15)
            { armed = false; status = ""; return; }
            bool focus = GameFocused();
            bool w = Held('w'), s = Held('s'), a = Held('a'), d = Held('d'), q = Held('q'), e = Held('e');
            if (!focus) armed = false;
            else if (!(w || s || a || d || q || e)) armed = true;
            bool enabledInput = focus && armed;
            request.focused = enabledInput;
            request.forward = enabledInput ? (w ? 1 : 0) - (s ? 1 : 0) : 0;
            request.left = enabledInput ? (a ? 1 : 0) - (d ? 1 : 0) : 0;
            request.turn_left = enabledInput ? (q ? 1 : 0) - (e ? 1 : 0) : 0;
            status = enabledInput ? "KEYBOARD | WASD / Q E | release: stop move, hold heading"
                : "KEYBOARD | click Game, release all movement keys to enable";
            if (now >= nextSend)
            {
                Send();
                nextSend = now + 1.0 / 60.0;
            }
        }
        catch (SocketException) { armed = false; }
    }

    private void Send()
    {
        byte[] raw = Encoding.UTF8.GetBytes(JsonUtility.ToJson(request));
        socket.Send(raw, raw.Length, destination);
    }
    private void OnGUI()
    {
        if (status.Length > 0) GUI.Box(new Rect(10, Screen.height - 42, 560, 32), status);
    }
    private void OnApplicationFocus(bool focused)
    {
        if (!focused) Zero();
    }
    private void Zero()
    {
        armed = false;
        if (socket == null || request == null) return;
        request.focused = false;
        request.forward = request.left = request.turn_left = 0;
        try { Send(); } catch (SocketException) { }
    }
    private void OnDisable()
    {
        Zero(); socket?.Close(); socket = null; request = null;
    }
}
