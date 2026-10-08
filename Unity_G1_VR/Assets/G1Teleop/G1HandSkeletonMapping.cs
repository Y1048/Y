// Bone IDs overlap between legacy OVR and OpenXR; never interpret them without skeleton type.
public static class G1HandSkeletonMapping
{
    public enum Joint { Wrist, IndexBase, MiddleBase, PinkyBase }

    public static OVRSkeleton.BoneId Bone(OVRSkeleton.SkeletonType type, Joint joint)
    {
        bool xr = type == OVRSkeleton.SkeletonType.XRHandLeft || type == OVRSkeleton.SkeletonType.XRHandRight;
        bool legacy = type == OVRSkeleton.SkeletonType.HandLeft || type == OVRSkeleton.SkeletonType.HandRight;
        if (!xr && !legacy) return OVRSkeleton.BoneId.Invalid;
        switch (joint)
        {
            case Joint.Wrist: return xr ? OVRSkeleton.BoneId.XRHand_Wrist : OVRSkeleton.BoneId.Hand_WristRoot;
            case Joint.IndexBase: return xr ? OVRSkeleton.BoneId.XRHand_IndexProximal : OVRSkeleton.BoneId.Hand_Index1;
            case Joint.MiddleBase: return xr ? OVRSkeleton.BoneId.XRHand_MiddleProximal : OVRSkeleton.BoneId.Hand_Middle1;
            case Joint.PinkyBase: return xr ? OVRSkeleton.BoneId.XRHand_LittleProximal : OVRSkeleton.BoneId.Hand_Pinky1;
            default: return OVRSkeleton.BoneId.Invalid;
        }
    }
}