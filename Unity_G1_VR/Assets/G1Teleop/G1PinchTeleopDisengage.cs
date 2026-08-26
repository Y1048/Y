using UnityEngine;

/// <summary>
/// Uses a sustained right-hand index pinch as a one-way teleoperation disengage gesture.
/// Re-engagement is intentionally NOT toggled by pinch: after release, the normal
/// engagement-target alignment/hold flow is used again.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1PinchTeleopDisengage : MonoBehaviour
{
    public G1ExistingHandTargetBinder hand_binder;
    public OVRHand ovr_hand;
    public float pinch_hold_seconds = 0.50f;

    public bool IsPinchDisengageHolding { get; private set; }
    public float PinchDisengageProgress { get; private set; }

    private float pinch_duration;
    private bool wait_for_release;

    private void Awake()
    {
        pinch_hold_seconds = Mathf.Max(0.10f, pinch_hold_seconds);
    }

    private void Update()
    {
        ResolveReferences();

        if (hand_binder == null || ovr_hand == null)
        {
            ResetGestureProgress();
            return;
        }

        bool pinching = ovr_hand.GetFingerIsPinching(OVRHand.HandFinger.Index);

        if (wait_for_release)
        {
            // Keep the clutch open until the user fully releases the pinch. This
            // prevents the normal auto-engagement flow from immediately calibrating
            // again while the disengage gesture is still being held.
            if (hand_binder.IsCalibrated)
            {
                hand_binder.ResetCalibration();
            }

            IsPinchDisengageHolding = pinching;
            PinchDisengageProgress = pinching ? 1.0f : 0.0f;
            if (!pinching)
            {
                hand_binder.ResetCalibration();
                wait_for_release = false;
                ResetGestureProgress();
                Debug.Log("G1 pinch disengage released; normal engagement flow is available again.");
            }
            return;
        }

        if (!hand_binder.IsCalibrated || !hand_binder.IsTrackingValid)
        {
            ResetGestureProgress();
            return;
        }

        if (!pinching)
        {
            ResetGestureProgress();
            return;
        }

        IsPinchDisengageHolding = true;
        pinch_duration += Time.deltaTime;
        PinchDisengageProgress = Mathf.Clamp01(
            pinch_duration / Mathf.Max(0.10f, pinch_hold_seconds));

        if (pinch_duration < pinch_hold_seconds)
        {
            return;
        }

        hand_binder.ResetCalibration();
        wait_for_release = true;
        pinch_duration = 0.0f;
        PinchDisengageProgress = 1.0f;
        Debug.Log(
            "G1 teleoperation disengaged by sustained thumb-index pinch. "
            + "Release the pinch, then use the normal engagement target to reconnect.");
    }

    private void ResolveReferences()
    {
        if (hand_binder == null)
        {
            hand_binder = FindObjectOfType<G1ExistingHandTargetBinder>();
        }

        if (ovr_hand == null && hand_binder != null)
        {
            ovr_hand = hand_binder.ovr_hand;
        }
    }

    private void ResetGestureProgress()
    {
        pinch_duration = 0.0f;
        IsPinchDisengageHolding = false;
        PinchDisengageProgress = 0.0f;
    }
}
