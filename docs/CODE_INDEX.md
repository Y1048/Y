# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **264개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

## 포함 범위

루트 실행 파일과 다음 폴더의 코드/설정 파일:

- `backend`
- `hardware`
- `experiments`
- `tools`
- `config`
- `MuJoCo_G1_Controller/scripts`
- `Unity_G1_VR/Assets/G1Teleop`
- `Unity_G1_VR/Assets/Editor`

원본 `references`, 로그·캡처, 로봇 mesh/XML, Unity 씬/prefab/meta,
외부 SDK·Packages·Library·빌드 산출물은 이 코드 색인에서 제외한다.
제외 항목을 미사용 또는 검토 완료로 판정한 것은 아니다.

## 갱신

```powershell
py -3.11 backend/tools/build_code_index.py
py -3.11 backend/tools/build_code_index.py --check
```

## 파일 목록

| 파일 | 줄 수 | 상태 | Python 최상위 선언(최대 5개) | SHA256 앞 12자리 |
| --- | ---: | --- | --- | --- |
| [MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py](../MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py) | 79 | 목록 확인 | mujoco_to_unity_delta, main | `48576cf30900` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 172 | 입출력 확인 | FeasiblePlan, FeasibleTargetPlanner | `de382bd302cf` |
| [MuJoCo_G1_Controller/scripts/g1_right_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_right_arm_common.py) | 413 | 목록 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `aa490bdc7b17` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py) | 812 | 목록 확인 | _update_reachability_limit, _find_body, _prepare_mink_xml, _joint_id, _apply_operational_joint_limits (+20) | `4dca1640414f` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py) | 1053 | 입출력 확인 | virtual_center_damping_costs, virtual_center_posture_costs, orientation_diagnostics, virtual_center_velocity_limits, orientation_limit_policy (+5) | `cb5a83596a17` |
| [MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py](../MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py) | 99 | 목록 확인 | require, require_pattern, forbid, main | `5f8fc9463b9b` |
| [START_MUJOCO_ONLY.bat](../START_MUJOCO_ONLY.bat) | 54 | 목록 확인 | - | `951590ee86d2` |
| [START_VR_HAND_TO_MUJOCO.bat](../START_VR_HAND_TO_MUJOCO.bat) | 198 | 입출력 확인 | - | `6c2f2b34b8f6` |
| [Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs](../Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs) | 430 | 목록 확인 | - | `8236aa4fa0c1` |
| [Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs](../Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs) | 134 | 목록 확인 | - | `3a842c8567a3` |
| [Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs](../Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs) | 591 | 목록 확인 | - | `3cffcb44a86a` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 607 | 목록 확인 | - | `089c93a5bf21` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 48 | 목록 확인 | - | `259ee66f4b17` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 893 | 입출력 확인 | - | `f3633d9735fb` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 521 | 입출력 확인 | - | `9c3a6df29385` |
| [Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs) | 98 | 목록 확인 | - | `b8c0c519b3e0` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 628 | 목록 확인 | - | `1f97d7b66ae0` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 265 | 목록 확인 | - | `36ecd4c8050c` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `078259d42d80` |
| [Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs](../Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs) | 220 | 목록 확인 | - | `044b001c5dea` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 375 | 목록 확인 | - | `126c5a8383b1` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 777 | 입출력 확인 | - | `7575a5ac8b2d` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 963 | 입출력 확인 | - | `4ebfbba0635e` |
| [Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs](../Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs) | 50 | 목록 확인 | - | `8cc5b243b908` |
| [backend/g1_teleop/__init__.py](../backend/g1_teleop/__init__.py) | 101 | 목록 확인 | - | `cdb74a9a69a1` |
| [backend/g1_teleop/calibration.py](../backend/g1_teleop/calibration.py) | 362 | 목록 확인 | _pose_matrix, _scale_vector, _pose_to_dict, _pose_from_dict, ArmCalibration (+8) | `cf6ccf3108db` |
| [backend/g1_teleop/camera.py](../backend/g1_teleop/camera.py) | 314 | 목록 확인 | CameraIntrinsics, CameraFrame, HeadCameraSource, MuJoCoHeadCameraSource, RealSenseD435iSource (+1) | `b3ce4be392b7` |
| [backend/g1_teleop/camera_factory.py](../backend/g1_teleop/camera_factory.py) | 66 | 목록 확인 | load_camera_profile, create_head_camera_source | `1c37692be7cd` |
| [backend/g1_teleop/command_adapter.py](../backend/g1_teleop/command_adapter.py) | 161 | 입출력 확인 | InternalCommand, _decode_object, _legacy_integer, _legacy_vector, _parse_legacy_value (+3) | `477b4f5deef9` |
| [backend/g1_teleop/config.py](../backend/g1_teleop/config.py) | 240 | 목록 확인 | NetworkConfig, RuntimeConfig, MotionConfig, IKConfig, CollisionConfig (+11) | `5489730fed32` |
| [backend/g1_teleop/g1_camera_mount.py](../backend/g1_teleop/g1_camera_mount.py) | 60 | 목록 확인 | _find_body, add_g1_d435i_camera | `eac56096d9a5` |
| [backend/g1_teleop/gate7_simulation_feedback.py](../backend/g1_teleop/gate7_simulation_feedback.py) | 153 | 목록 확인 | Gate7SimulationFeedbackError, Gate7SimulationFeedback, _finite_vector, build_packet, parse_packet (+1) | `e9e526fb904d` |
| [backend/g1_teleop/inspection_contact.py](../backend/g1_teleop/inspection_contact.py) | 161 | 목록 확인 | InspectionContactState, InspectionContactTransition, InspectionContactStateMachine, install_inspection_contact_monitor | `8241c3028ba3` |
| [backend/g1_teleop/inspection_demo.py](../backend/g1_teleop/inspection_demo.py) | 159 | 목록 확인 | InspectionDemoState, InspectionDemoSnapshot, InspectionDemoTracker, append_inspection_result | `0cb4a9878bd6` |
| [backend/g1_teleop/live_receiver.py](../backend/g1_teleop/live_receiver.py) | 96 | 입출력 확인 | DatagramSocket, ReceiveBatch, receive_available_commands | `3051c118ee19` |
| [backend/g1_teleop/mapping.py](../backend/g1_teleop/mapping.py) | 36 | 목록 확인 | map_unity_ovr_wrist_to_head_yaw | `2f6eca490bd6` |
| [backend/g1_teleop/mink_command_stream.py](../backend/g1_teleop/mink_command_stream.py) | 180 | 입출력 확인 | MinkCommandUpdate, MinkCommandStream | `5eace1ef2d71` |
| [backend/g1_teleop/motion_reference.py](../backend/g1_teleop/motion_reference.py) | 64 | 목록 확인 | step_position, step_rotation | `471e1aea5e53` |
| [backend/g1_teleop/protocol.py](../backend/g1_teleop/protocol.py) | 379 | 목록 확인 | ProtocolError, _boolean, _finite_vector, _integer, _nonempty_string (+7) | `09bfd7ff25c0` |
| [backend/g1_teleop/runtime_state.py](../backend/g1_teleop/runtime_state.py) | 91 | 목록 확인 | RuntimeTransition, TeleopRuntimeStateMachine | `527b855aa9b9` |
| [backend/g1_teleop/transforms.py](../backend/g1_teleop/transforms.py) | 217 | 목록 확인 | normalize_quaternion, quaternion_to_matrix, matrix_to_quaternion, make_pose, split_pose (+7) | `087439c556d2` |
| [backend/g1_teleop/unitree_image_transport.py](../backend/g1_teleop/unitree_image_transport.py) | 111 | 목록 확인 | shared_memory_name, UnitreeImageHeader, UnitreeSimImageWriter | `047f9078051c` |
| [backend/g1_teleop/watchdog.py](../backend/g1_teleop/watchdog.py) | 191 | 목록 확인 | PacketAcceptance, SequenceWatchdog, SessionSequenceWatchdog, WorkspaceFaultLatch, WorkspaceExitDebounce | `fd7ef43b6c5e` |
| [backend/tests/test_batch_failure_guidance.py](../backend/tests/test_batch_failure_guidance.py) | 70 | 목록 확인 | BatchFailureGuidanceTest | `76ff0afe30ab` |
| [backend/tests/test_code_index.py](../backend/tests/test_code_index.py) | 42 | 목록 확인 | CodeIndexTests | `902c76318cdc` |
| [backend/tests/test_feasible_target_return.py](../backend/tests/test_feasible_target_return.py) | 49 | 목록 확인 | ReturnTests | `28a8918fd7bf` |
| [backend/tests/test_foundation.py](../backend/tests/test_foundation.py) | 262 | 목록 확인 | FoundationTest | `2437777ece27` |
| [backend/tests/test_gate7_mujoco_feedback_receiver.py](../backend/tests/test_gate7_mujoco_feedback_receiver.py) | 118 | 목록 확인 | _payload, Gate7MujocoFeedbackReceiverTest | `84241b04a339` |
| [backend/tests/test_gate7_simulation_feedback.py](../backend/tests/test_gate7_simulation_feedback.py) | 89 | 목록 확인 | Gate7SimulationFeedbackTest | `65b7aab6fe88` |
| [backend/tests/test_inspection_contact.py](../backend/tests/test_inspection_contact.py) | 67 | 목록 확인 | InspectionContactStateMachineTest | `8029e94d123e` |
| [backend/tests/test_inspection_demo.py](../backend/tests/test_inspection_demo.py) | 74 | 목록 확인 | InspectionDemoTrackerTest | `3335a4b41f9a` |
| [backend/tests/test_live_receiver.py](../backend/tests/test_live_receiver.py) | 178 | 목록 확인 | FakeSocket, legacy_packet, legacy_disengage_packet, legacy_tracking_disengage_packet, v2_packet (+1) | `062f9f594342` |
| [backend/tests/test_mink_candidate_benchmark.py](../backend/tests/test_mink_candidate_benchmark.py) | 309 | 목록 확인 | BenchmarkTests | `e6f51d562fc4` |
| [backend/tests/test_mink_collision_diagnostics.py](../backend/tests/test_mink_collision_diagnostics.py) | 203 | 목록 확인 | MinkCollisionDiagnosticsTest | `690335f0c14e` |
| [backend/tests/test_mink_collision_feasibility.py](../backend/tests/test_mink_collision_feasibility.py) | 123 | 목록 확인 | CollisionFeasibilityTests | `da0443dc20cb` |
| [backend/tests/test_mink_command_stream.py](../backend/tests/test_mink_command_stream.py) | 182 | 목록 확인 | FakeSocket, packet, MinkCommandStreamTest | `6d9f75f27101` |
| [backend/tests/test_mink_distance_invariance.py](../backend/tests/test_mink_distance_invariance.py) | 120 | 목록 확인 | DistanceInvarianceTests | `aa0e4bfe3b1e` |
| [backend/tests/test_mink_feasible_target.py](../backend/tests/test_mink_feasible_target.py) | 185 | 목록 확인 | FeasibleTargetTest | `095db34fe49e` |
| [backend/tests/test_mink_reachability_limit.py](../backend/tests/test_mink_reachability_limit.py) | 33 | 목록 확인 | MinkReachabilityLimitTest | `5bebc4805cd0` |
| [backend/tests/test_mink_step_acceptance_comparison.py](../backend/tests/test_mink_step_acceptance_comparison.py) | 437 | 목록 확인 | MinkStepAcceptanceComparisonTests | `2437a35d94fd` |
| [backend/tests/test_mink_task_cost_contract.py](../backend/tests/test_mink_task_cost_contract.py) | 47 | 목록 확인 | ExampleTask, MinkTaskCostContractTest | `b58358ea29be` |
| [backend/tests/test_mink_tracking_lag.py](../backend/tests/test_mink_tracking_lag.py) | 48 | 목록 확인 | TrackingLagTests | `a74250226820` |
| [backend/tests/test_mink_virtual_center_trajectory.py](../backend/tests/test_mink_virtual_center_trajectory.py) | 209 | 목록 확인 | rotation_error_degrees, MinkVirtualCenterTrajectoryTest | `2388551a5c70` |
| [backend/tests/test_motion_reference.py](../backend/tests/test_motion_reference.py) | 52 | 목록 확인 | MotionReferenceTest | `0593d601be57` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `902c4dc708e7` |
| [backend/tests/test_mujoco_inspection_scene_visibility.py](../backend/tests/test_mujoco_inspection_scene_visibility.py) | 52 | 목록 확인 | MujocoInspectionSceneVisibilityTest | `554c51b7aac5` |
| [backend/tests/test_protocol_v2.py](../backend/tests/test_protocol_v2.py) | 162 | 목록 확인 | tracked, pose_v2, ProtocolV2Test | `dd655e88ec5b` |
| [backend/tests/test_recorded_pose_speed_comparison.py](../backend/tests/test_recorded_pose_speed_comparison.py) | 61 | 목록 확인 | MakePacket, RecordedPoseSpeedComparisonTest | `371a2f6a4cee` |
| [backend/tests/test_recorded_reach_bound.py](../backend/tests/test_recorded_reach_bound.py) | 53 | 목록 확인 | RecordedReachBoundTest | `5a686447a442` |
| [backend/tests/test_runtime_architecture.py](../backend/tests/test_runtime_architecture.py) | 62 | 목록 확인 | command, RuntimeArchitectureTest | `e39e40892b1e` |
| [backend/tests/test_startup_ready_pose_editor.py](../backend/tests/test_startup_ready_pose_editor.py) | 75 | 목록 확인 | StartupReadyPoseEditorTest | `96dfcaba64f6` |
| [backend/tests/test_teleop_config.py](../backend/tests/test_teleop_config.py) | 129 | 목록 확인 | TeleopConfigTest | `163d99c65c6e` |
| [backend/tests/test_unity_display_mode_launcher.py](../backend/tests/test_unity_display_mode_launcher.py) | 43 | 목록 확인 | UnityDisplayModeLauncherTests | `7df5387393ae` |
| [backend/tests/test_unity_workspace_policy.py](../backend/tests/test_unity_workspace_policy.py) | 214 | 목록 확인 | UnityWorkspacePolicyTest | `272d2557b50d` |
| [backend/tests/test_virtual_center_kinematics_regression.py](../backend/tests/test_virtual_center_kinematics_regression.py) | 89 | 목록 확인 | VirtualCenterKinematicsRegressionTest | `81055f5d6143` |
| [backend/tests/test_virtual_center_orientation_policy.py](../backend/tests/test_virtual_center_orientation_policy.py) | 98 | 목록 확인 | VirtualCenterOrientationPolicyTest | `b98b65d77eb7` |
| [backend/tests/test_wrist_target_mapping_audit.py](../backend/tests/test_wrist_target_mapping_audit.py) | 50 | 목록 확인 | MappingAuditTests | `8657d15ddf39` |
| [backend/tools/audit_wrist_target_mapping.py](../backend/tools/audit_wrist_target_mapping.py) | 180 | 목록 확인 | OperatorToRobotDelta, GetNecessaryScale, ReadUnitySegments, GetVectors, AuditSender (+2) | `cdffee38ed9e` |
| [backend/tools/benchmark_mink_candidate.py](../backend/tools/benchmark_mink_candidate.py) | 252 | 목록 확인 | CachedClearance, BoundedClearance, CachedCollisionLimit, BuildCandidate, SummarizeTiming (+2) | `0fbfa5616e9f` |
| [backend/tools/benchmark_mink_rendered_replay.py](../backend/tools/benchmark_mink_rendered_replay.py) | 283 | 목록 확인 | WaitForRelease, GetNextRelease, LoadReplay, ReplayRenderer, RunRenderedReplay (+2) | `1780ff6df849` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 121 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `4415f8462ff6` |
| [backend/tools/compare_mink_step_acceptance.py](../backend/tools/compare_mink_step_acceptance.py) | 688 | 목록 확인 | WristPositionTask, FullOrientationErrorTask, IncrementCollisionLimit, ResolvedCollisionLimit, GetLimitAvoidanceStep (+10) | `d7674883d9e4` |
| [backend/tools/compare_recorded_pose_speeds.py](../backend/tools/compare_recorded_pose_speeds.py) | 115 | 목록 확인 | GetActiveSegments, GetRecordedTargets, GetTargetIndex, main | `49db2732785e` |
| [backend/tools/diagnose_mink_collision_feasibility.py](../backend/tools/diagnose_mink_collision_feasibility.py) | 282 | 목록 확인 | EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, main | `5c31ab13526f` |
| [backend/tools/diagnose_mink_distance_invariance.py](../backend/tools/diagnose_mink_distance_invariance.py) | 213 | 목록 확인 | GetSupportGap, GetWorldVertices, GetEnclosingVertices, GetSeparationCertificate, InspectTrace (+3) | `621342f507d6` |
| [backend/tools/diagnose_mink_tracking_lag.py](../backend/tools/diagnose_mink_tracking_lag.py) | 188 | 목록 확인 | GetSchedule, GetSustainedSettleTime, GetReachSummary, Step, GetSample (+4) | `a7c4b204530f` |
| [backend/tools/diagnose_recorded_reach.py](../backend/tools/diagnose_recorded_reach.py) | 92 | 목록 확인 | GetReachUpperBound, main | `2ae2e82817d6` |
| [backend/tools/inspect_feasible_target_return.py](../backend/tools/inspect_feasible_target_return.py) | 171 | 목록 확인 | InterpolateGoal, SummarizePreview, GetVerdict, Run, main | `cea9d6791740` |
| [backend/tools/offline_render_worker.py](../backend/tools/offline_render_worker.py) | 192 | 목록 확인 | LatestStateSlot, RunRenderWorker, ProcessRenderer | `f4445d1fd317` |
| [backend/tools/verify_camera_simulation.py](../backend/tools/verify_camera_simulation.py) | 239 | 목록 확인 | parse_args, quaternion_rotation_matrix, official_optical_axes, verify_transport, main | `403676a805a0` |
| [backend/tools/verify_feasible_target.py](../backend/tools/verify_feasible_target.py) | 135 | 목록 확인 | BuildPlanner, RunSequence, main | `a873c4cb9109` |
| [backend/tools/verify_unity_state_packets.ps1](../backend/tools/verify_unity_state_packets.ps1) | 139 | 목록 확인 | - | `977520f9c441` |
| [backend/tools/verify_virtual_center_kinematics.py](../backend/tools/verify_virtual_center_kinematics.py) | 250 | 목록 확인 | LegacyOrientationTask, ExactOrientationTask, CheckJacobian, RunCase, main | `d33c52198ca6` |
| [config/camera_profile.json](../config/camera_profile.json) | 42 | 목록 확인 | - | `96583ab70069` |
| [config/g1_gate6_hold.json](../config/g1_gate6_hold.json) | 31 | 목록 확인 | - | `3d28c5a16761` |
| [config/g1_gate6_interrupt_release_test.json](../config/g1_gate6_interrupt_release_test.json) | 31 | 목록 확인 | - | `02040744b4fc` |
| [config/g1_gate7_first_live_hardware_output.json](../config/g1_gate7_first_live_hardware_output.json) | 33 | 목록 확인 | - | `e34cc263326e` |
| [config/g1_gate7_first_live_mink_arm_sdk.json](../config/g1_gate7_first_live_mink_arm_sdk.json) | 20 | 목록 확인 | - | `ecbc1ecbd4cd` |
| [config/g1_gate7_live_hardware_output.json](../config/g1_gate7_live_hardware_output.json) | 33 | 목록 확인 | - | `72bd044515c8` |
| [config/g1_gate7_mink_arm_sdk.json](../config/g1_gate7_mink_arm_sdk.json) | 20 | 목록 확인 | - | `b2d1ba4cf5cd` |
| [config/g1_gate7_visible_motion_hardware_output.json](../config/g1_gate7_visible_motion_hardware_output.json) | 33 | 목록 확인 | - | `111d6a4c44a8` |
| [config/g1_gate7_visible_motion_mink_arm_sdk.json](../config/g1_gate7_visible_motion_mink_arm_sdk.json) | 20 | 목록 확인 | - | `ecbc1ecbd4cd` |
| [config/g1_regular_arm_pose.json](../config/g1_regular_arm_pose.json) | 61 | 목록 확인 | - | `00f59b43d95c` |
| [config/g1_right_arm_jog.json](../config/g1_right_arm_jog.json) | 39 | 목록 확인 | - | `578f6accf65e` |
| [config/g1_right_shoulder_pitch_full_authority_trial.json](../config/g1_right_shoulder_pitch_full_authority_trial.json) | 47 | 목록 확인 | - | `16e052f5718c` |
| [config/g1_startup_precheck.json](../config/g1_startup_precheck.json) | 19 | 목록 확인 | - | `5cdcb0d28ba2` |
| [config/startup_recovery.json](../config/startup_recovery.json) | 15 | 목록 확인 | - | `75e9a6d9be3a` |
| [config/teleimager_real_d435i.yaml](../config/teleimager_real_d435i.yaml) | 36 | 목록 확인 | - | `c045d2399086` |
| [config/teleimager_simulation.yaml](../config/teleimager_simulation.yaml) | 36 | 목록 확인 | - | `8bbd691c574e` |
| [config/teleop.json](../config/teleop.json) | 83 | 목록 확인 | - | `9c12ace4a014` |
| [experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat](../experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat) | 30 | 목록 확인 | - | `227a60a2f894` |
| [experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat](../experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat) | 26 | 목록 확인 | - | `81852d4595c9` |
| [experiments/startup_recovery_multistrategy/candidate_runner.py](../experiments/startup_recovery_multistrategy/candidate_runner.py) | 39 | 목록 확인 | parse_arguments, main | `450de7f80c8c` |
| [experiments/startup_recovery_multistrategy/run_experiment.py](../experiments/startup_recovery_multistrategy/run_experiment.py) | 248 | 목록 확인 | RecoveryCandidate, parse_arguments, load_initial_pose, candidate_score, select_candidate (+3) | `634456bdde1b` |
| [experiments/startup_recovery_multistrategy/test_experiment.py](../experiments/startup_recovery_multistrategy/test_experiment.py) | 87 | 목록 확인 | MultiStrategyRecoveryExperimentTest | `1dcab540ed4d` |
| [experiments/startup_recovery_multistrategy/view_selected.py](../experiments/startup_recovery_multistrategy/view_selected.py) | 37 | 목록 확인 | main | `8fca1b7a793c` |
| [experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat) | 30 | 목록 확인 | - | `ba136718d32d` |
| [experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat) | 37 | 목록 확인 | - | `0a5a44dc8d4c` |
| [experiments/startup_recovery_posture_sweep/run_sweep.py](../experiments/startup_recovery_posture_sweep/run_sweep.py) | 565 | 목록 확인 | SweepCase, ParseOffsets, ParseArguments, LoadPose, GenerateCases (+9) | `c39f52ec8bf0` |
| [experiments/startup_recovery_posture_sweep/single_pose_runner.py](../experiments/startup_recovery_posture_sweep/single_pose_runner.py) | 48 | 목록 확인 | ParseArguments, Main | `90e4f9840c37` |
| [experiments/startup_recovery_posture_sweep/test_sweep.py](../experiments/startup_recovery_posture_sweep/test_sweep.py) | 74 | 목록 확인 | StartupRecoveryPostureSweepTests | `2256e3d4461f` |
| [experiments/twist2_right_arm_manual/TEST_OFFLINE.bat](../experiments/twist2_right_arm_manual/TEST_OFFLINE.bat) | 18 | 목록 확인 | - | `e9930c6cde26` |
| [experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp](../experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp) | 1205 | 목록 확인 | - | `51bc6ff5e688` |
| [experiments/twist2_right_arm_manual/verify_offline.py](../experiments/twist2_right_arm_manual/verify_offline.py) | 207 | 목록 확인 | CheckCondition, GetFunction, GetDeclaration, GetLinuxPath, RunLocal (+3) | `f518501b04c4` |
| [hardware/g1_arm_bridge/arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/arm_sdk_hold_contract.py) | 364 | 목록 확인 | ArmSdkHoldConfig, HoldValidation, ArmSdkCommandFrame, _finite_vector, _uint8 (+6) | `ce556422b287` |
| [hardware/g1_arm_bridge/arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/arm_sdk_teleop_contract.py) | 855 | 목록 확인 | Gate7ContractError, RegularArmPose, Gate7Config, MinkArmSample, TrajectorySample (+11) | `f499eb733f5c` |
| [hardware/g1_arm_bridge/check_startup_readiness.py](../hardware/g1_arm_bridge/check_startup_readiness.py) | 599 | 목록 확인 | PrecheckConfig, TimedPacket, Blocker, _positive_float, load_config (+12) | `d99fce83b65a` |
| [hardware/g1_arm_bridge/diagnose_initial_pose_collision.py](../hardware/g1_arm_bridge/diagnose_initial_pose_collision.py) | 302 | 목록 확인 | _joint_pose, _has_exact_geom_contact, _probe_zero_mesh_distance, _robust_geom_distance, _nearby_pairs (+1) | `8167b044ccb1` |
| [hardware/g1_arm_bridge/edit_startup_ready_pose.py](../hardware/g1_arm_bridge/edit_startup_ready_pose.py) | 460 | 목록 확인 | PoseAssessment, EditorState, ParseArguments, LoadPose, SafeLimitsDegrees (+11) | `debe2dd7e005` |
| [hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py) | 29 | 목록 확인 | ExperimentalStatefulGate7TeleopController | `0ac69202d60e` |
| [hardware/g1_arm_bridge/g1_base_state.py](../hardware/g1_arm_bridge/g1_base_state.py) | 212 | 목록 확인 | InvalidBaseStateError, NormalizedBaseState, _FiniteVector, NormalizeQuaternionWXYZ, MultiplyQuaternionWXYZ (+4) | `a66e7423c8b3` |
| [hardware/g1_arm_bridge/g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/g1_camera_replay_tcp.py) | 317 | 목록 확인 | LoadFont, BuildReplayJpeg, ParseArguments, ValidateArguments, WriteResult (+1) | `4e65d547e297` |
| [hardware/g1_arm_bridge/g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/g1_camera_tcp_bridge.py) | 206 | 목록 확인 | BuildFramePacket, ParseArguments, CreateVideoClient, ConnectUnity, ValidateArguments (+1) | `959d0c0ae747` |
| [hardware/g1_arm_bridge/g1_joint_contract.py](../hardware/g1_arm_bridge/g1_joint_contract.py) | 39 | 목록 확인 | - | `04109d0c0746` |
| [hardware/g1_arm_bridge/g1_right_arm_jog.py](../hardware/g1_arm_bridge/g1_right_arm_jog.py) | 1223 | 목록 확인 | RuntimeConfig, KeyboardReader, _number, load_config, validate_config (+17) | `96ea2a128b02` |
| [hardware/g1_arm_bridge/g1_unity_state_bridge.py](../hardware/g1_arm_bridge/g1_unity_state_bridge.py) | 224 | 목록 확인 | _FiniteVector, _QuaternionAngleDegrees, _RequireFullBody, BuildUnityHardwareStatePacket, EncodeUnityHardwareStatePacket (+1) | `a6ab43c8b22d` |
| [hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py) | 803 | 목록 확인 | LowStatePacketError, BaseStateTelemetry, LowStateTelemetry, PacketOrderTracker, _finite_joint_vector (+16) | `ce83984ed9bd` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold.py) | 755 | 목록 확인 | RuntimeConfig, LowStateSnapshot, LowStateBuffer, _finite_number, load_runtime_config (+11) | `c9ceddc83416` |
| [hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py](../hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py) | 231 | 목록 확인 | SleepUntilStep, SelectReplayWindow, _replace_dual, BuildExperimentalLimitedFrames, _parse_args (+1) | `6092caaa247c` |
| [hardware/g1_arm_bridge/gate7_capture_quality.py](../hardware/g1_arm_bridge/gate7_capture_quality.py) | 851 | 목록 확인 | _percentile, _round, _replace_dual, _decode_capture, _series_metrics (+9) | `26fd95b2feee` |
| [hardware/g1_arm_bridge/gate7_capture_regression.py](../hardware/g1_arm_bridge/gate7_capture_regression.py) | 217 | 목록 확인 | _replace_dual, _file_sha256, BuildRegressionTrace, CompareTrace, _automatic_result_path (+2) | `87e0e8715cb0` |
| [hardware/g1_arm_bridge/gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/gate7_fault_injection_matrix.py) | 317 | 목록 확인 | _replace_dual, _synthetic_active_value, _load_active_value, _payload, _new_controller (+5) | `c4b947c9e520` |
| [hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py) | 358 | 목록 확인 | _replace_dual, _packet, _automatic_result_path, _parse_args, main | `dbf4b692f306` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk.py) | 812 | 입출력 확인 | LiveHardwareConfig, _finite, LoadLiveHardwareConfig, ValidateLiveHardwareConfig, ValidateRuckigRuntime (+12) | `173c8f6a825d` |
| [hardware/g1_arm_bridge/gate7_live_dry_run.py](../hardware/g1_arm_bridge/gate7_live_dry_run.py) | 743 | 목록 확인 | DryRunTick, _finite_all_joints, _replace_dual_arm, _automatic_path, _resolve_output_path (+6) | `b835c55d9b65` |
| [hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py](../hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py) | 518 | 목록 확인 | _set_full_body_pose, CollisionPathValidator, _replace_dual_arm, _mink_packet, _target_right_arm (+3) | `9492c69b00f7` |
| [hardware/g1_arm_bridge/gate7_mink_capture.py](../hardware/g1_arm_bridge/gate7_mink_capture.py) | 146 | 목록 확인 | _automatic_path, _write_line, _parse_args, main | `2ca86c520fc4` |
| [hardware/g1_arm_bridge/gate7_mink_replay.py](../hardware/g1_arm_bridge/gate7_mink_replay.py) | 135 | 목록 확인 | CapturedPacket, LoadCapture, NormalizePayload, CaptureSha256, _parse_args (+1) | `933616e5f6ba` |
| [hardware/g1_arm_bridge/gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/gate7_mink_wsl_relay.py) | 198 | 입출력 확인 | MinkOrderGuard, ValidateRelayEndpoint, ValidateAndForward, _automatic_result_path, _parse_args (+1) | `23ecebd07a35` |
| [hardware/g1_arm_bridge/generate_fake_mink_targets.py](../hardware/g1_arm_bridge/generate_fake_mink_targets.py) | 117 | 목록 확인 | parse_args, main | `504d79f4433b` |
| [hardware/g1_arm_bridge/hardware_state.py](../hardware/g1_arm_bridge/hardware_state.py) | 91 | 목록 확인 | HardwarePhase, FaultCode, build_status, write_status | `543b95bceb5f` |
| [hardware/g1_arm_bridge/live_lowstate_mujoco.py](../hardware/g1_arm_bridge/live_lowstate_mujoco.py) | 651 | 목록 확인 | StreamState, BaseBodyPose, ParseArguments, ResolveMeasurementLogPath, BuildMirrorMeasurement (+14) | `497bce59bf2c` |
| [hardware/g1_arm_bridge/mink_target_dry_run.py](../hardware/g1_arm_bridge/mink_target_dry_run.py) | 127 | 목록 확인 | _fmt_deg, main | `372002c8b23c` |
| [hardware/g1_arm_bridge/plan_startup_transition.py](../hardware/g1_arm_bridge/plan_startup_transition.py) | 684 | 목록 확인 | _inside_pairs, _waypoints_for_order, _dense_segment, _evaluate_order, _joint_limits (+6) | `86f7c97cca94` |
| [hardware/g1_arm_bridge/probe_joint_motion.py](../hardware/g1_arm_bridge/probe_joint_motion.py) | 177 | 목록 확인 | parse_args, current_positions, collect_positions, summarize, main | `4a1078d960bc` |
| [hardware/g1_arm_bridge/query_motion_mode.py](../hardware/g1_arm_bridge/query_motion_mode.py) | 110 | 목록 확인 | _write_json, parse_args, main | `bb6273b07465` |
| [hardware/g1_arm_bridge/query_motion_mode_wsl.sh](../hardware/g1_arm_bridge/query_motion_mode_wsl.sh) | 24 | 목록 확인 | - | `43adffcedd77` |
| [hardware/g1_arm_bridge/read_only_lowstate.py](../hardware/g1_arm_bridge/read_only_lowstate.py) | 563 | 목록 확인 | JointSample, ReadOnlyG1LowState, ReadOnlyG1BaseState, _motor_value, _state_uint8 (+9) | `299865e024ec` |
| [hardware/g1_arm_bridge/receive_initial_state.py](../hardware/g1_arm_bridge/receive_initial_state.py) | 79 | 목록 확인 | parse_args, main | `d26b4d6f6f63` |
| [hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py) | 354 | 목록 확인 | SavedLowState, _FiniteVector, _JointNames, _OptionalMode, LoadSnapshot (+5) | `acb9e55657a1` |
| [hardware/g1_arm_bridge/replay_startup_recovery.py](../hardware/g1_arm_bridge/replay_startup_recovery.py) | 184 | 목록 확인 | ParseArguments, LoadViewerSettings, LoadRecovery, InterpolatePose, ApplyRightArmPose (+1) | `c552b8699bb2` |
| [hardware/g1_arm_bridge/right_arm_jog_contract.py](../hardware/g1_arm_bridge/right_arm_jog_contract.py) | 194 | 목록 확인 | ArmJointJogLimits, ArmJointJogTick, validate_jog_limits, ArmJointJogController | `ba221c863225` |
| [hardware/g1_arm_bridge/ruckig_gate7_controller.py](../hardware/g1_arm_bridge/ruckig_gate7_controller.py) | 121 | 목록 확인 | RuckigGate7TeleopController | `b29bf56a6ebd` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 95 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `349304ce41cc` |
| [hardware/g1_arm_bridge/safety_gate.py](../hardware/g1_arm_bridge/safety_gate.py) | 149 | 목록 확인 | SafetyConfig, SafetyDecision, _vector, _within_joint_limits, evaluate_target | `8f1f174502e4` |
| [hardware/g1_arm_bridge/simulate_startup_recovery.py](../hardware/g1_arm_bridge/simulate_startup_recovery.py) | 1179 | 목록 확인 | _load_startup_safe_ready_degrees, _right_qpos_ids, _minimum_clearance, _minimum_clearance_extended, _recovery_edge_is_valid (+10) | `1c0ff5fa66e4` |
| [hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh](../hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh) | 27 | 목록 확인 | - | `3d13d50a9dfd` |
| [hardware/g1_arm_bridge/start_gate6_hold_wsl.sh](../hardware/g1_arm_bridge/start_gate6_hold_wsl.sh) | 24 | 목록 확인 | - | `a3d17a4ba307` |
| [hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh](../hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh) | 29 | 목록 확인 | - | `09a89fd5ac22` |
| [hardware/g1_arm_bridge/start_read_only_wsl.sh](../hardware/g1_arm_bridge/start_read_only_wsl.sh) | 22 | 목록 확인 | - | `8bc905624f1d` |
| [hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh](../hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh) | 24 | 목록 확인 | - | `742e68f43486` |
| [hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py) | 138 | 목록 확인 | _safe_all_q, ArmSdkHoldContractTests | `e423fbd5db3a` |
| [hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py) | 387 | 목록 확인 | _replace_dual, _sample, ArmSdkTeleopContractTests | `442a265f90ba` |
| [hardware/g1_arm_bridge/test_check_startup_readiness.py](../hardware/g1_arm_bridge/test_check_startup_readiness.py) | 196 | 목록 확인 | _config, _timed_packet, _mode_query, StartupReadinessTests | `31e8187d1bef` |
| [hardware/g1_arm_bridge/test_collision_diagnostics.py](../hardware/g1_arm_bridge/test_collision_diagnostics.py) | 60 | 목록 확인 | _FakeG1, _FakeController, CollisionDiagnosticTests | `a50103ae95ef` |
| [hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py) | 43 | 목록 확인 | ExperimentalStatefulGate7ControllerTests | `3be67c772d1f` |
| [hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py](../hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py) | 82 | 목록 확인 | main | `fa397980398b` |
| [hardware/g1_arm_bridge/test_g1_base_state.py](../hardware/g1_arm_bridge/test_g1_base_state.py) | 118 | 목록 확인 | YawQuaternionWXYZ, G1BaseStateTests | `6ebbd1b19739` |
| [hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py) | 75 | 목록 확인 | G1CameraReplayTcpTest | `d6efdad6838c` |
| [hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py) | 44 | 목록 확인 | G1CameraTcpBridgeTest | `abb58cb2c277` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog.py) | 327 | 목록 확인 | G1RightArmJogTests | `889196530629` |
| [hardware/g1_arm_bridge/test_g1_unity_state_bridge.py](../hardware/g1_arm_bridge/test_g1_unity_state_bridge.py) | 175 | 목록 확인 | LowStatePacket, G1UnityStateBridgeTests | `17530e3b7439` |
| [hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py) | 218 | 목록 확인 | _packet, _base_state, _unused_local_port, Gate5LowStateSafetyTests | `ee42c7cef468` |
| [hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py) | 163 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, Gate6ArmSdkHoldTests | `cdbb4ae57639` |
| [hardware/g1_arm_bridge/test_gate6_interrupt_release.py](../hardware/g1_arm_bridge/test_gate6_interrupt_release.py) | 130 | 목록 확인 | validate_interrupt_release_contract, Gate6InterruptReleaseTests, main | `9c6539cb0d98` |
| [hardware/g1_arm_bridge/test_gate7_capture_quality.py](../hardware/g1_arm_bridge/test_gate7_capture_quality.py) | 106 | 목록 확인 | Gate7CaptureQualityTests | `edce062f10a6` |
| [hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py) | 32 | 목록 확인 | Gate7FaultInjectionMatrixTests | `228f2bc12bd0` |
| [hardware/g1_arm_bridge/test_gate7_first_live_profile.py](../hardware/g1_arm_bridge/test_gate7_first_live_profile.py) | 112 | 목록 확인 | Gate7FirstLiveProfileTests | `883cfe860c3d` |
| [hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py) | 66 | 목록 확인 | _free_udp_port, Gate7HardwareVirtualE2ETests | `9152aff0543e` |
| [hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py) | 208 | 목록 확인 | Gate7LiveArmSdkTests | `6b49eda8705e` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run.py) | 361 | 목록 확인 | _replace_dual, _sample, Gate7LiveDryRunTests | `acbdb37cb287` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py) | 136 | 목록 확인 | _free_udp_port, Gate7LiveDryRunE2ETests | `0e44617f036a` |
| [hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py](../hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py) | 119 | 목록 확인 | _free_udp_port, Gate7MinkCaptureReplayTests | `89793d19414a` |
| [hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py) | 94 | 목록 확인 | _packet, Gate7MinkWslRelayTests | `83233f7e2289` |
| [hardware/g1_arm_bridge/test_gate7_visible_motion_profile.py](../hardware/g1_arm_bridge/test_gate7_visible_motion_profile.py) | 38 | 목록 확인 | Gate7VisibleMotionProfileTests | `5b07559bb1c1` |
| [hardware/g1_arm_bridge/test_hardware_state.py](../hardware/g1_arm_bridge/test_hardware_state.py) | 71 | 목록 확인 | HardwareStateTests | `ef04766efed9` |
| [hardware/g1_arm_bridge/test_live_lowstate_mujoco.py](../hardware/g1_arm_bridge/test_live_lowstate_mujoco.py) | 252 | 목록 확인 | Packet, LiveLowStateMuJoCoTests | `9189a8d297af` |
| [hardware/g1_arm_bridge/test_mink_safety_pipeline.py](../hardware/g1_arm_bridge/test_mink_safety_pipeline.py) | 129 | 목록 확인 | _target_at, main | `8b18042096ca` |
| [hardware/g1_arm_bridge/test_replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/test_replay_saved_lowstate_mujoco.py) | 93 | 목록 확인 | ReplaySavedLowStateMuJoCoTests | `2223ed3bd2d9` |
| [hardware/g1_arm_bridge/test_right_arm_jog_contract.py](../hardware/g1_arm_bridge/test_right_arm_jog_contract.py) | 191 | 목록 확인 | measured_pose, RightArmJogContractTests | `58644c8671bb` |
| [hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py) | 75 | 목록 확인 | RuckigJointMotionLimiterTests | `f2ca76aa30a7` |
| [hardware/g1_arm_bridge/test_safety_gate.py](../hardware/g1_arm_bridge/test_safety_gate.py) | 124 | 목록 확인 | SafetyGateTests | `021ebefe3f9f` |
| [hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py) | 73 | 목록 확인 | ValidateRightArmJogCollisionPathTests | `8e54bd433313` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py) | 261 | 목록 확인 | load_precheck, measured_pose, build_offset_trajectory, build_endpoint_trajectories, validate_offset_path (+5) | `4842b47f9a9a` |
| [hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py](../hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py) | 64 | 목록 확인 | main | `8bae1461211a` |
| [hardware/g1_arm_bridge/verify_initial_pose_sync.py](../hardware/g1_arm_bridge/verify_initial_pose_sync.py) | 128 | 목록 확인 | _load_captured_pose, main | `89e6244d6a32` |
| [tools/ALLOW_G1_DDS_WSL.bat](../tools/ALLOW_G1_DDS_WSL.bat) | 11 | 목록 확인 | - | `f20f5d135012` |
| [tools/ALLOW_G1_DDS_WSL_ADMIN.ps1](../tools/ALLOW_G1_DDS_WSL_ADMIN.ps1) | 40 | 목록 확인 | - | `1a9bfb443e68` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat) | 13 | 목록 확인 | - | `47b29a0e9410` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1) | 19 | 목록 확인 | - | `89fb12a79a38` |
| [tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat](../tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat) | 32 | 목록 확인 | - | `40b5005082f4` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 74 | 목록 확인 | - | `27a4cedb8c08` |
| [tools/CHECK_G1_TELEOP_STARTUP.bat](../tools/CHECK_G1_TELEOP_STARTUP.bat) | 66 | 목록 확인 | - | `d49ce6c50475` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 11 | 목록 확인 | - | `527e5b996818` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `fa801691ba0e` |
| [tools/DETECT_G1_NETWORK.bat](../tools/DETECT_G1_NETWORK.bat) | 11 | 목록 확인 | - | `378e6e7e87fb` |
| [tools/DETECT_G1_NETWORK_ADMIN.ps1](../tools/DETECT_G1_NETWORK_ADMIN.ps1) | 24 | 목록 확인 | - | `ad01ff4e26e4` |
| [tools/EDIT_G1_STARTUP_READY_POSE.bat](../tools/EDIT_G1_STARTUP_READY_POSE.bat) | 33 | 목록 확인 | - | `a99abc2fc556` |
| [tools/PREPARE_G1_GATE6_HOLD.bat](../tools/PREPARE_G1_GATE6_HOLD.bat) | 39 | 목록 확인 | - | `bc83cef04c73` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 11 | 목록 확인 | - | `8b0dd5012230` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 14 | 목록 확인 | - | `dcf1bcda20fe` |
| [tools/SET_UNITY_DISPLAY_MODE.ps1](../tools/SET_UNITY_DISPLAY_MODE.ps1) | 25 | 입출력 확인 | - | `5d591cd1c961` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 26 | 목록 확인 | - | `a268bd7281a1` |
| [tools/START_G1_GATE5_READ_ONLY.bat](../tools/START_G1_GATE5_READ_ONLY.bat) | 37 | 목록 확인 | - | `9f303cf0b4fe` |
| [tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat](../tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat) | 107 | 목록 확인 | - | `3d41fa8ca83f` |
| [tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat](../tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat) | 25 | 목록 확인 | - | `e447eb1301f0` |
| [tools/START_G1_GATE7_LIVE_DRY_RUN.bat](../tools/START_G1_GATE7_LIVE_DRY_RUN.bat) | 57 | 목록 확인 | - | `cba384e2bba4` |
| [tools/START_G1_GATE7_LIVE_HARDWARE.bat](../tools/START_G1_GATE7_LIVE_HARDWARE.bat) | 197 | 목록 확인 | - | `583c33c6673d` |
| [tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat](../tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat) | 92 | 목록 확인 | - | `044c605099ba` |
| [tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat](../tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat) | 25 | 목록 확인 | - | `b2c031bb2932` |
| [tools/START_G1_GATE7_VR_RECORDING.bat](../tools/START_G1_GATE7_VR_RECORDING.bat) | 59 | 목록 확인 | - | `ebbfd3e3ae8b` |
| [tools/START_G1_READ_ONLY.bat](../tools/START_G1_READ_ONLY.bat) | 15 | 목록 확인 | - | `728f5c4f637d` |
| [tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat](../tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat) | 123 | 목록 확인 | - | `a91e401770ae` |
| [tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat](../tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat) | 123 | 목록 확인 | - | `7cac6cf9755b` |
| [tools/START_MINK_G1_HARDWARE_SYNC.bat](../tools/START_MINK_G1_HARDWARE_SYNC.bat) | 53 | 목록 확인 | - | `d09fe72815b8` |
| [tools/TEST_CAMERA_REPLAY_TO_UNITY.bat](../tools/TEST_CAMERA_REPLAY_TO_UNITY.bat) | 101 | 목록 확인 | - | `a0043e344891` |
| [tools/TEST_FAKE_MINK_SAFETY_E2E.bat](../tools/TEST_FAKE_MINK_SAFETY_E2E.bat) | 35 | 목록 확인 | - | `fbf38f6a6443` |
| [tools/TEST_G1_GATE5_READ_ONLY.bat](../tools/TEST_G1_GATE5_READ_ONLY.bat) | 32 | 목록 확인 | - | `535fd5b75668` |
| [tools/TEST_G1_GATE6_HOLD_OFFLINE.bat](../tools/TEST_G1_GATE6_HOLD_OFFLINE.bat) | 46 | 목록 확인 | - | `20cbbf1e5654` |
| [tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat](../tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat) | 31 | 목록 확인 | - | `12e63c1ab9c4` |
| [tools/TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat](../tools/TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat) | 32 | 목록 확인 | - | `f45e83fa8cfd` |
| [tools/TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat](../tools/TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat) | 35 | 목록 확인 | - | `0747d333e572` |
| [tools/TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat](../tools/TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat) | 42 | 목록 확인 | - | `0406dadf1d64` |
| [tools/TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat](../tools/TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat) | 43 | 목록 확인 | - | `61e627861351` |
| [tools/TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat](../tools/TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat) | 30 | 목록 확인 | - | `44ade23ede10` |
| [tools/TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat](../tools/TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat) | 34 | 목록 확인 | - | `be55a9c5fabd` |
| [tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat](../tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat) | 39 | 목록 확인 | - | `40ee2e5338ce` |
| [tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat](../tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat) | 46 | 목록 확인 | - | `5be78a9dbc8d` |
| [tools/TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat](../tools/TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat) | 45 | 목록 확인 | - | `ea4a663df406` |
| [tools/TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat](../tools/TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat) | 51 | 목록 확인 | - | `842db5201ad7` |
| [tools/TEST_G1_HARDWARE_SAFETY_GATE.bat](../tools/TEST_G1_HARDWARE_SAFETY_GATE.bat) | 34 | 목록 확인 | - | `6333bdb36241` |
| [tools/TEST_G1_HARDWARE_STATE.bat](../tools/TEST_G1_HARDWARE_STATE.bat) | 33 | 목록 확인 | - | `c4e4448a2a6c` |
| [tools/TEST_G1_MINK_FK_PARITY.bat](../tools/TEST_G1_MINK_FK_PARITY.bat) | 70 | 목록 확인 | - | `becee8bf9a62` |
| [tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat](../tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat) | 43 | 목록 확인 | - | `61a853e766d7` |
| [tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat](../tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat) | 40 | 목록 확인 | - | `ce845ebe6fdb` |
| [tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat](../tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat) | 31 | 목록 확인 | - | `336c6468e9e2` |
| [tools/TEST_MINK_SAFETY_PIPELINE.bat](../tools/TEST_MINK_SAFETY_PIPELINE.bat) | 35 | 목록 확인 | - | `e9e487794a68` |
| [tools/TEST_MINK_WRIST_FRAME.bat](../tools/TEST_MINK_WRIST_FRAME.bat) | 34 | 목록 확인 | - | `b94b9bb1725a` |
| [tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat](../tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat) | 27 | 목록 확인 | - | `6e6dadfbe931` |
| [tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat) | 29 | 목록 확인 | - | `aa5229c7f8d2` |
| [tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat) | 35 | 목록 확인 | - | `1570a684af40` |
| [tools/VIEW_G1_LIVE_MUJOCO.bat](../tools/VIEW_G1_LIVE_MUJOCO.bat) | 44 | 목록 확인 | - | `1c5e2e357c1a` |
| [tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat](../tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat) | 35 | 목록 확인 | - | `3cbe48ce3145` |
| [tools/VIEW_G1_STARTUP_RECOVERY.bat](../tools/VIEW_G1_STARTUP_RECOVERY.bat) | 28 | 목록 확인 | - | `14659a1eb0ee` |
