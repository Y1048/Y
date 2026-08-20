"""G1 teleoperation backend building blocks."""

from .calibration import (
    ArmCalibration,
    CalibrationProfile,
    NeutralCalibrationAccumulator,
    WorkspaceScaleEstimator,
    estimate_rigid_registration,
)
from .camera import (
    CAMERA_FRAME_ID,
    CameraFrame,
    CameraIntrinsics,
    MuJoCoHeadCameraSource,
    RealSenseD435iSource,
    save_bgr_bmp,
)
from .camera_factory import create_head_camera_source, load_camera_profile
from .mapping import map_unity_ovr_wrist_to_head_yaw
from .g1_camera_mount import (
    G1_D435I_CAMERA_NAME,
    G1_D435I_ISAACLAB_ROS_QUAT_WXYZ,
    G1_D435I_MUJOCO_QUAT_WXYZ,
    G1_D435I_PARENT_LINK,
    G1_D435I_PITCH_RAD,
    G1_D435I_POSITION_M,
    G1_D435I_VERTICAL_FOV_DEG,
    add_g1_d435i_camera,
)
from .protocol import PosePacketV1, StatePacketV1
from .unitree_image_transport import UnitreeSimImageWriter
from .watchdog import (
    SequenceWatchdog,
    SessionSequenceWatchdog,
    WorkspaceExitDebounce,
    WorkspaceFaultLatch,
)

__all__ = [
    "ArmCalibration",
    "CAMERA_FRAME_ID",
    "CameraFrame",
    "CameraIntrinsics",
    "CalibrationProfile",
    "create_head_camera_source",
    "G1_D435I_CAMERA_NAME",
    "G1_D435I_ISAACLAB_ROS_QUAT_WXYZ",
    "G1_D435I_MUJOCO_QUAT_WXYZ",
    "G1_D435I_PARENT_LINK",
    "G1_D435I_PITCH_RAD",
    "G1_D435I_POSITION_M",
    "G1_D435I_VERTICAL_FOV_DEG",
    "MuJoCoHeadCameraSource",
    "NeutralCalibrationAccumulator",
    "PosePacketV1",
    "RealSenseD435iSource",
    "SequenceWatchdog",
    "SessionSequenceWatchdog",
    "StatePacketV1",
    "WorkspaceScaleEstimator",
    "WorkspaceExitDebounce",
    "WorkspaceFaultLatch",
    "add_g1_d435i_camera",
    "estimate_rigid_registration",
    "map_unity_ovr_wrist_to_head_yaw",
    "load_camera_profile",
    "save_bgr_bmp",
    "UnitreeSimImageWriter",
]
