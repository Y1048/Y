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
from .command_adapter import InternalCommand, parse_command_packet
from .config import (
    CollisionConfig,
    IKConfig,
    MotionConfig,
    NetworkConfig,
    RuntimeConfig,
    TeleopConfig,
    WorkspaceConfig,
    load_teleop_config,
)
from .live_receiver import ReceiveBatch, receive_available_commands
from .mapping import map_unity_ovr_wrist_to_head_yaw
from .mink_command_stream import MinkCommandStream, MinkCommandUpdate
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
from .protocol import PosePacketV1, PosePacketV2, StatePacketV1, StatePacketV2
from .runtime_state import RuntimeTransition, TeleopRuntimeStateMachine
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
    "CollisionConfig",
    "create_head_camera_source",
    "G1_D435I_CAMERA_NAME",
    "G1_D435I_ISAACLAB_ROS_QUAT_WXYZ",
    "G1_D435I_MUJOCO_QUAT_WXYZ",
    "G1_D435I_PARENT_LINK",
    "G1_D435I_PITCH_RAD",
    "G1_D435I_POSITION_M",
    "G1_D435I_VERTICAL_FOV_DEG",
    "IKConfig",
    "InternalCommand",
    "MotionConfig",
    "MinkCommandStream",
    "MinkCommandUpdate",
    "MuJoCoHeadCameraSource",
    "NetworkConfig",
    "NeutralCalibrationAccumulator",
    "PosePacketV1",
    "PosePacketV2",
    "RealSenseD435iSource",
    "ReceiveBatch",
    "RuntimeConfig",
    "RuntimeTransition",
    "SequenceWatchdog",
    "SessionSequenceWatchdog",
    "StatePacketV1",
    "StatePacketV2",
    "TeleopConfig",
    "TeleopRuntimeStateMachine",
    "UnitreeSimImageWriter",
    "WorkspaceConfig",
    "WorkspaceExitDebounce",
    "WorkspaceFaultLatch",
    "WorkspaceScaleEstimator",
    "add_g1_d435i_camera",
    "estimate_rigid_registration",
    "load_teleop_config",
    "map_unity_ovr_wrist_to_head_yaw",
    "load_camera_profile",
    "parse_command_packet",
    "receive_available_commands",
    "save_bgr_bmp",
]
