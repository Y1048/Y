# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **303개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

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
| [MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py) | 37 | 목록 확인 | mark_live_mink_packet, wrap_state_packet_factory | `b852ec80fc67` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 239 | 입출력 확인 | FeasiblePlan, FeasibleTargetPlanner | `550fde8d5867` |
| [MuJoCo_G1_Controller/scripts/g1_right_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_right_arm_common.py) | 413 | 목록 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `14885a5cbd68` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py) | 812 | 목록 확인 | _update_reachability_limit, _find_body, _prepare_mink_xml, _joint_id, _apply_operational_joint_limits (+20) | `950fe331d1a5` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py) | 20 | 목록 확인 | main | `aebdd2dc962a` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py) | 1109 | 입출력 확인 | ResolveCollisionProfile, virtual_center_damping_costs, virtual_center_posture_costs, orientation_diagnostics, virtual_center_velocity_limits (+6) | `ea5896890bb1` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py) | 19 | 목록 확인 | main | `d1983100a9de` |
| [MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py) | 101 | 목록 확인 | MinkCommandProvenanceTests | `7819cd59119e` |
| [MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py](../MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py) | 99 | 목록 확인 | require, require_pattern, forbid, main | `30cc0d077b66` |
| [START_MUJOCO_ONLY.bat](../START_MUJOCO_ONLY.bat) | 55 | 목록 확인 | - | `bbbad8c0c2ce` |
| [START_VR_HAND_TO_MUJOCO.bat](../START_VR_HAND_TO_MUJOCO.bat) | 211 | 입출력 확인 | - | `6a3d98ec4bff` |
| [Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs](../Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs) | 430 | 목록 확인 | - | `d3aa9d45c92a` |
| [Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs](../Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs) | 134 | 목록 확인 | - | `3a842c8567a3` |
| [Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs](../Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs) | 591 | 목록 확인 | - | `0cc491e3db1b` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 607 | 목록 확인 | - | `091cb87249c3` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 48 | 목록 확인 | - | `259ee66f4b17` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 893 | 입출력 확인 | - | `f948b691f0e5` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 521 | 입출력 확인 | - | `f387b9a95a39` |
| [Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs) | 98 | 목록 확인 | - | `40a96eb5264c` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 628 | 목록 확인 | - | `99f5d8a4f0dd` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 265 | 목록 확인 | - | `7373a9492fc6` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs](../Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs) | 220 | 목록 확인 | - | `a836926776ec` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 375 | 목록 확인 | - | `db28be0dcd81` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 777 | 입출력 확인 | - | `f5aff63a7db3` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 963 | 입출력 확인 | - | `b9e213ae0888` |
| [Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs](../Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs) | 50 | 목록 확인 | - | `3124aab0e080` |
| [backend/g1_teleop/__init__.py](../backend/g1_teleop/__init__.py) | 101 | 목록 확인 | - | `86664979265c` |
| [backend/g1_teleop/calibration.py](../backend/g1_teleop/calibration.py) | 362 | 목록 확인 | _pose_matrix, _scale_vector, _pose_to_dict, _pose_from_dict, ArmCalibration (+8) | `cf6ccf3108db` |
| [backend/g1_teleop/camera.py](../backend/g1_teleop/camera.py) | 314 | 목록 확인 | CameraIntrinsics, CameraFrame, HeadCameraSource, MuJoCoHeadCameraSource, RealSenseD435iSource (+1) | `b3ce4be392b7` |
| [backend/g1_teleop/camera_factory.py](../backend/g1_teleop/camera_factory.py) | 66 | 목록 확인 | load_camera_profile, create_head_camera_source | `1c37692be7cd` |
| [backend/g1_teleop/command_adapter.py](../backend/g1_teleop/command_adapter.py) | 182 | 입출력 확인 | InternalCommand, _decode_object, _legacy_integer, _legacy_source_time_ns, _legacy_vector (+4) | `eb251eba6545` |
| [backend/g1_teleop/config.py](../backend/g1_teleop/config.py) | 240 | 목록 확인 | NetworkConfig, RuntimeConfig, MotionConfig, IKConfig, CollisionConfig (+11) | `b98eb47d78f3` |
| [backend/g1_teleop/g1_camera_mount.py](../backend/g1_teleop/g1_camera_mount.py) | 60 | 목록 확인 | _find_body, add_g1_d435i_camera | `eac56096d9a5` |
| [backend/g1_teleop/gate7_simulation_feedback.py](../backend/g1_teleop/gate7_simulation_feedback.py) | 153 | 목록 확인 | Gate7SimulationFeedbackError, Gate7SimulationFeedback, _finite_vector, build_packet, parse_packet (+1) | `89aa873e72b0` |
| [backend/g1_teleop/inspection_contact.py](../backend/g1_teleop/inspection_contact.py) | 161 | 목록 확인 | InspectionContactState, InspectionContactTransition, InspectionContactStateMachine, install_inspection_contact_monitor | `8241c3028ba3` |
| [backend/g1_teleop/inspection_demo.py](../backend/g1_teleop/inspection_demo.py) | 159 | 목록 확인 | InspectionDemoState, InspectionDemoSnapshot, InspectionDemoTracker, append_inspection_result | `92a6711f4497` |
| [backend/g1_teleop/live_receiver.py](../backend/g1_teleop/live_receiver.py) | 136 | 입출력 확인 | DatagramSocket, ReceiveBatch, receive_available_commands | `1d02a4ee903a` |
| [backend/g1_teleop/mapping.py](../backend/g1_teleop/mapping.py) | 36 | 목록 확인 | map_unity_ovr_wrist_to_head_yaw | `5166bfed6876` |
| [backend/g1_teleop/mink_command_stream.py](../backend/g1_teleop/mink_command_stream.py) | 203 | 입출력 확인 | MinkCommandUpdate, MinkCommandStream | `d0dea7baca9f` |
| [backend/g1_teleop/motion_reference.py](../backend/g1_teleop/motion_reference.py) | 64 | 목록 확인 | step_position, step_rotation | `cef1334bbb00` |
| [backend/g1_teleop/protocol.py](../backend/g1_teleop/protocol.py) | 379 | 목록 확인 | ProtocolError, _boolean, _finite_vector, _integer, _nonempty_string (+7) | `f9410e3f8465` |
| [backend/g1_teleop/runtime_state.py](../backend/g1_teleop/runtime_state.py) | 91 | 목록 확인 | RuntimeTransition, TeleopRuntimeStateMachine | `43b826597eb4` |
| [backend/g1_teleop/source_provenance.py](../backend/g1_teleop/source_provenance.py) | 135 | 목록 확인 | SourceAcceptance, _SessionClock, CommandSourceGuard | `4e152f262150` |
| [backend/g1_teleop/transforms.py](../backend/g1_teleop/transforms.py) | 217 | 목록 확인 | normalize_quaternion, quaternion_to_matrix, matrix_to_quaternion, make_pose, split_pose (+7) | `c97855b9c4e9` |
| [backend/g1_teleop/unitree_image_transport.py](../backend/g1_teleop/unitree_image_transport.py) | 111 | 목록 확인 | shared_memory_name, UnitreeImageHeader, UnitreeSimImageWriter | `047f9078051c` |
| [backend/g1_teleop/watchdog.py](../backend/g1_teleop/watchdog.py) | 224 | 목록 확인 | PacketAcceptance, SequenceWatchdog, SessionSequenceWatchdog, WorkspaceFaultLatch, WorkspaceExitDebounce | `d42ceeba4df5` |
| [backend/tests/test_batch_failure_guidance.py](../backend/tests/test_batch_failure_guidance.py) | 70 | 목록 확인 | BatchFailureGuidanceTest | `05e261289c21` |
| [backend/tests/test_code_index.py](../backend/tests/test_code_index.py) | 42 | 목록 확인 | CodeIndexTests | `bfd86a963b9d` |
| [backend/tests/test_feasible_target_return.py](../backend/tests/test_feasible_target_return.py) | 49 | 목록 확인 | ReturnTests | `69b1f9015ba4` |
| [backend/tests/test_foundation.py](../backend/tests/test_foundation.py) | 262 | 목록 확인 | FoundationTest | `2437777ece27` |
| [backend/tests/test_gate7_mujoco_feedback_receiver.py](../backend/tests/test_gate7_mujoco_feedback_receiver.py) | 118 | 목록 확인 | _payload, Gate7MujocoFeedbackReceiverTest | `5d7035c989ca` |
| [backend/tests/test_gate7_simulation_feedback.py](../backend/tests/test_gate7_simulation_feedback.py) | 89 | 목록 확인 | Gate7SimulationFeedbackTest | `fc81a75e405d` |
| [backend/tests/test_inspection_contact.py](../backend/tests/test_inspection_contact.py) | 67 | 목록 확인 | InspectionContactStateMachineTest | `8029e94d123e` |
| [backend/tests/test_inspection_demo.py](../backend/tests/test_inspection_demo.py) | 74 | 목록 확인 | InspectionDemoTrackerTest | `bcbbbeecca0b` |
| [backend/tests/test_live_receiver.py](../backend/tests/test_live_receiver.py) | 243 | 목록 확인 | FakeSocket, legacy_packet, legacy_disengage_packet, legacy_tracking_disengage_packet, legacy_workspace_exit_packet (+2) | `b1f1f90f6d43` |
| [backend/tests/test_mink_candidate_benchmark.py](../backend/tests/test_mink_candidate_benchmark.py) | 309 | 목록 확인 | BenchmarkTests | `266fcfe97edb` |
| [backend/tests/test_mink_collision_diagnostics.py](../backend/tests/test_mink_collision_diagnostics.py) | 203 | 목록 확인 | MinkCollisionDiagnosticsTest | `291354c1067e` |
| [backend/tests/test_mink_collision_feasibility.py](../backend/tests/test_mink_collision_feasibility.py) | 123 | 목록 확인 | CollisionFeasibilityTests | `734201ef55d0` |
| [backend/tests/test_mink_command_stream.py](../backend/tests/test_mink_command_stream.py) | 272 | 목록 확인 | FakeSocket, packet, MinkCommandStreamTest | `1fc5b8f38131` |
| [backend/tests/test_mink_distance_invariance.py](../backend/tests/test_mink_distance_invariance.py) | 120 | 목록 확인 | DistanceInvarianceTests | `3dc5048606a4` |
| [backend/tests/test_mink_feasible_target.py](../backend/tests/test_mink_feasible_target.py) | 293 | 목록 확인 | FeasibleTargetTest | `d559f122e580` |
| [backend/tests/test_mink_reachability_limit.py](../backend/tests/test_mink_reachability_limit.py) | 33 | 목록 확인 | MinkReachabilityLimitTest | `d3feecf0bd93` |
| [backend/tests/test_mink_step_acceptance_comparison.py](../backend/tests/test_mink_step_acceptance_comparison.py) | 458 | 목록 확인 | MinkStepAcceptanceComparisonTests | `ca56251a63ad` |
| [backend/tests/test_mink_task_cost_contract.py](../backend/tests/test_mink_task_cost_contract.py) | 47 | 목록 확인 | ExampleTask, MinkTaskCostContractTest | `62ece4cc7488` |
| [backend/tests/test_mink_tracking_lag.py](../backend/tests/test_mink_tracking_lag.py) | 48 | 목록 확인 | TrackingLagTests | `82469d1c0233` |
| [backend/tests/test_mink_virtual_center_trajectory.py](../backend/tests/test_mink_virtual_center_trajectory.py) | 209 | 목록 확인 | rotation_error_degrees, MinkVirtualCenterTrajectoryTest | `0cbc064b5821` |
| [backend/tests/test_motion_reference.py](../backend/tests/test_motion_reference.py) | 52 | 목록 확인 | MotionReferenceTest | `1003f5d2d186` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `87ba04dd2d7d` |
| [backend/tests/test_mujoco_inspection_scene_visibility.py](../backend/tests/test_mujoco_inspection_scene_visibility.py) | 52 | 목록 확인 | MujocoInspectionSceneVisibilityTest | `044e93e9fb93` |
| [backend/tests/test_protocol_v2.py](../backend/tests/test_protocol_v2.py) | 162 | 목록 확인 | tracked, pose_v2, ProtocolV2Test | `dd655e88ec5b` |
| [backend/tests/test_recorded_pose_speed_comparison.py](../backend/tests/test_recorded_pose_speed_comparison.py) | 61 | 목록 확인 | MakePacket, RecordedPoseSpeedComparisonTest | `f667723f00c9` |
| [backend/tests/test_recorded_reach_bound.py](../backend/tests/test_recorded_reach_bound.py) | 53 | 목록 확인 | RecordedReachBoundTest | `872765bf8ad0` |
| [backend/tests/test_runtime_architecture.py](../backend/tests/test_runtime_architecture.py) | 62 | 목록 확인 | command, RuntimeArchitectureTest | `e39e40892b1e` |
| [backend/tests/test_source_provenance.py](../backend/tests/test_source_provenance.py) | 123 | 목록 확인 | command, CommandSourceGuardTests | `a49810e1a73c` |
| [backend/tests/test_startup_ready_pose_editor.py](../backend/tests/test_startup_ready_pose_editor.py) | 75 | 목록 확인 | StartupReadyPoseEditorTest | `9ef3c18fabae` |
| [backend/tests/test_teleop_config.py](../backend/tests/test_teleop_config.py) | 129 | 목록 확인 | TeleopConfigTest | `5acaf5989f21` |
| [backend/tests/test_unity_display_mode_launcher.py](../backend/tests/test_unity_display_mode_launcher.py) | 43 | 목록 확인 | UnityDisplayModeLauncherTests | `d14e1956fd6e` |
| [backend/tests/test_unity_workspace_policy.py](../backend/tests/test_unity_workspace_policy.py) | 214 | 목록 확인 | UnityWorkspacePolicyTest | `6e01479820ca` |
| [backend/tests/test_virtual_center_kinematics_regression.py](../backend/tests/test_virtual_center_kinematics_regression.py) | 89 | 목록 확인 | VirtualCenterKinematicsRegressionTest | `42a59361c09c` |
| [backend/tests/test_virtual_center_orientation_policy.py](../backend/tests/test_virtual_center_orientation_policy.py) | 99 | 목록 확인 | VirtualCenterOrientationPolicyTest | `09c6c58158c2` |
| [backend/tests/test_wrist_target_mapping_audit.py](../backend/tests/test_wrist_target_mapping_audit.py) | 50 | 목록 확인 | MappingAuditTests | `4c7b69cdb5a9` |
| [backend/tools/audit_wrist_target_mapping.py](../backend/tools/audit_wrist_target_mapping.py) | 180 | 목록 확인 | OperatorToRobotDelta, GetNecessaryScale, ReadUnitySegments, GetVectors, AuditSender (+2) | `609e6e79e51c` |
| [backend/tools/benchmark_mink_candidate.py](../backend/tools/benchmark_mink_candidate.py) | 252 | 목록 확인 | CachedClearance, BoundedClearance, CachedCollisionLimit, BuildCandidate, SummarizeTiming (+2) | `9ec73185c420` |
| [backend/tools/benchmark_mink_rendered_replay.py](../backend/tools/benchmark_mink_rendered_replay.py) | 283 | 목록 확인 | WaitForRelease, GetNextRelease, LoadReplay, ReplayRenderer, RunRenderedReplay (+2) | `0ce3b7a47862` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 121 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `bae8666a7a4d` |
| [backend/tools/compare_mink_step_acceptance.py](../backend/tools/compare_mink_step_acceptance.py) | 767 | 목록 확인 | WristPositionTask, FullOrientationErrorTask, IncrementCollisionLimit, ResolvedCollisionLimit, GetLimitAvoidanceStep (+11) | `250c66da32c6` |
| [backend/tools/compare_recorded_pose_speeds.py](../backend/tools/compare_recorded_pose_speeds.py) | 115 | 목록 확인 | GetActiveSegments, GetRecordedTargets, GetTargetIndex, main | `369d5a51f6f7` |
| [backend/tools/diagnose_mink_collision_feasibility.py](../backend/tools/diagnose_mink_collision_feasibility.py) | 282 | 목록 확인 | EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, main | `6e10b78eb359` |
| [backend/tools/diagnose_mink_distance_invariance.py](../backend/tools/diagnose_mink_distance_invariance.py) | 213 | 목록 확인 | GetSupportGap, GetWorldVertices, GetEnclosingVertices, GetSeparationCertificate, InspectTrace (+3) | `6913cc195174` |
| [backend/tools/diagnose_mink_tracking_lag.py](../backend/tools/diagnose_mink_tracking_lag.py) | 188 | 목록 확인 | GetSchedule, GetSustainedSettleTime, GetReachSummary, Step, GetSample (+4) | `21ff27a5a2c9` |
| [backend/tools/diagnose_recorded_reach.py](../backend/tools/diagnose_recorded_reach.py) | 92 | 목록 확인 | GetReachUpperBound, main | `4b59d728798b` |
| [backend/tools/inspect_feasible_target_return.py](../backend/tools/inspect_feasible_target_return.py) | 171 | 목록 확인 | InterpolateGoal, SummarizePreview, GetVerdict, Run, main | `2427846d8593` |
| [backend/tools/offline_render_worker.py](../backend/tools/offline_render_worker.py) | 192 | 목록 확인 | LatestStateSlot, RunRenderWorker, ProcessRenderer | `60918476d5de` |
| [backend/tools/reconcile_review_ledger.py](../backend/tools/reconcile_review_ledger.py) | 176 | 목록 확인 | _read_csv, _semantic_map, _static_check, build_rows, _csv_text (+1) | `91ee37c20ba9` |
| [backend/tools/verify_camera_simulation.py](../backend/tools/verify_camera_simulation.py) | 239 | 목록 확인 | parse_args, quaternion_rotation_matrix, official_optical_axes, verify_transport, main | `323a114cf33b` |
| [backend/tools/verify_feasible_target.py](../backend/tools/verify_feasible_target.py) | 135 | 목록 확인 | BuildPlanner, RunSequence, main | `02ee868239f7` |
| [backend/tools/verify_unity_state_packets.ps1](../backend/tools/verify_unity_state_packets.ps1) | 139 | 목록 확인 | - | `1d368878fd61` |
| [backend/tools/verify_virtual_center_kinematics.py](../backend/tools/verify_virtual_center_kinematics.py) | 250 | 목록 확인 | LegacyOrientationTask, ExactOrientationTask, CheckJacobian, RunCase, main | `6d3b28dce4ac` |
| [config/camera_profile.json](../config/camera_profile.json) | 42 | 목록 확인 | - | `96583ab70069` |
| [config/g1_gate6_hold.json](../config/g1_gate6_hold.json) | 31 | 목록 확인 | - | `32ea9e5f0223` |
| [config/g1_gate6_interrupt_release_test.json](../config/g1_gate6_interrupt_release_test.json) | 31 | 목록 확인 | - | `02040744b4fc` |
| [config/g1_gate7_first_live_hardware_output.json](../config/g1_gate7_first_live_hardware_output.json) | 33 | 목록 확인 | - | `e34cc263326e` |
| [config/g1_gate7_first_live_mink_arm_sdk.json](../config/g1_gate7_first_live_mink_arm_sdk.json) | 20 | 목록 확인 | - | `44fa4ecaff39` |
| [config/g1_gate7_live_hardware_output.json](../config/g1_gate7_live_hardware_output.json) | 33 | 목록 확인 | - | `5e91cd5adcba` |
| [config/g1_gate7_mink_arm_sdk.json](../config/g1_gate7_mink_arm_sdk.json) | 20 | 목록 확인 | - | `4f1ab28f00ce` |
| [config/g1_gate7_visible_motion_hardware_output.json](../config/g1_gate7_visible_motion_hardware_output.json) | 33 | 목록 확인 | - | `111d6a4c44a8` |
| [config/g1_gate7_visible_motion_mink_arm_sdk.json](../config/g1_gate7_visible_motion_mink_arm_sdk.json) | 20 | 목록 확인 | - | `44fa4ecaff39` |
| [config/g1_regular_arm_pose.json](../config/g1_regular_arm_pose.json) | 61 | 목록 확인 | - | `fc0b80702dfb` |
| [config/g1_right_arm_jog.json](../config/g1_right_arm_jog.json) | 39 | 목록 확인 | - | `b974a756fbe4` |
| [config/g1_right_shoulder_pitch_full_authority_trial.json](../config/g1_right_shoulder_pitch_full_authority_trial.json) | 47 | 목록 확인 | - | `916cedef6059` |
| [config/g1_startup_precheck.json](../config/g1_startup_precheck.json) | 19 | 목록 확인 | - | `3fca74fe17f7` |
| [config/startup_recovery.json](../config/startup_recovery.json) | 15 | 목록 확인 | - | `75e9a6d9be3a` |
| [config/teleimager_real_d435i.yaml](../config/teleimager_real_d435i.yaml) | 36 | 목록 확인 | - | `c045d2399086` |
| [config/teleimager_simulation.yaml](../config/teleimager_simulation.yaml) | 36 | 목록 확인 | - | `8bbd691c574e` |
| [config/teleop.json](../config/teleop.json) | 83 | 목록 확인 | - | `e3498304c8b4` |
| [experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat](../experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat) | 30 | 목록 확인 | - | `c17f8f5e265c` |
| [experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat](../experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat) | 26 | 목록 확인 | - | `07f85ccfcd9f` |
| [experiments/startup_recovery_multistrategy/candidate_runner.py](../experiments/startup_recovery_multistrategy/candidate_runner.py) | 39 | 목록 확인 | parse_arguments, main | `20b2e8d8ebca` |
| [experiments/startup_recovery_multistrategy/run_experiment.py](../experiments/startup_recovery_multistrategy/run_experiment.py) | 248 | 목록 확인 | RecoveryCandidate, parse_arguments, load_initial_pose, candidate_score, select_candidate (+3) | `a3e6a8dec3ae` |
| [experiments/startup_recovery_multistrategy/test_experiment.py](../experiments/startup_recovery_multistrategy/test_experiment.py) | 87 | 목록 확인 | MultiStrategyRecoveryExperimentTest | `c97dd80049c2` |
| [experiments/startup_recovery_multistrategy/view_selected.py](../experiments/startup_recovery_multistrategy/view_selected.py) | 37 | 목록 확인 | main | `f277d289ab9e` |
| [experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat) | 30 | 목록 확인 | - | `4a5a4d2379e6` |
| [experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat) | 37 | 목록 확인 | - | `42a3046f8048` |
| [experiments/startup_recovery_posture_sweep/run_sweep.py](../experiments/startup_recovery_posture_sweep/run_sweep.py) | 565 | 목록 확인 | SweepCase, ParseOffsets, ParseArguments, LoadPose, GenerateCases (+9) | `813bf214c985` |
| [experiments/startup_recovery_posture_sweep/single_pose_runner.py](../experiments/startup_recovery_posture_sweep/single_pose_runner.py) | 48 | 목록 확인 | ParseArguments, Main | `537e1f51ce89` |
| [experiments/startup_recovery_posture_sweep/test_sweep.py](../experiments/startup_recovery_posture_sweep/test_sweep.py) | 74 | 목록 확인 | StartupRecoveryPostureSweepTests | `b17abad23a99` |
| [experiments/twist2_right_arm_manual/TEST_OFFLINE.bat](../experiments/twist2_right_arm_manual/TEST_OFFLINE.bat) | 18 | 목록 확인 | - | `53a20610cefb` |
| [experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp](../experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp) | 1205 | 목록 확인 | - | `e61d8a3cf830` |
| [experiments/twist2_right_arm_manual/verify_offline.py](../experiments/twist2_right_arm_manual/verify_offline.py) | 207 | 목록 확인 | CheckCondition, GetFunction, GetDeclaration, GetLinuxPath, RunLocal (+3) | `9947537a59a5` |
| [hardware/g1_arm_bridge/arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/arm_sdk_hold_contract.py) | 364 | 목록 확인 | ArmSdkHoldConfig, HoldValidation, ArmSdkCommandFrame, _finite_vector, _uint8 (+6) | `7096d037e98e` |
| [hardware/g1_arm_bridge/arm_sdk_release_contract.py](../hardware/g1_arm_bridge/arm_sdk_release_contract.py) | 138 | 목록 확인 | ReleaseEvidence, _validate_release_arguments, execute_release_sequence | `64072ef0df8b` |
| [hardware/g1_arm_bridge/arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/arm_sdk_teleop_contract.py) | 855 | 목록 확인 | Gate7ContractError, RegularArmPose, Gate7Config, MinkArmSample, TrajectorySample (+11) | `3e74d573204d` |
| [hardware/g1_arm_bridge/check_startup_readiness.py](../hardware/g1_arm_bridge/check_startup_readiness.py) | 599 | 목록 확인 | PrecheckConfig, TimedPacket, Blocker, _positive_float, load_config (+12) | `fe7560fdbed9` |
| [hardware/g1_arm_bridge/check_startup_readiness_entry.py](../hardware/g1_arm_bridge/check_startup_readiness_entry.py) | 176 | 목록 확인 | _pop_option, _option_path, validate_forward_token, _finite_vector, _validated_raw_odom (+3) | `77da5a14e8db` |
| [hardware/g1_arm_bridge/diagnose_initial_pose_collision.py](../hardware/g1_arm_bridge/diagnose_initial_pose_collision.py) | 302 | 목록 확인 | _joint_pose, _has_exact_geom_contact, _probe_zero_mesh_distance, _robust_geom_distance, _nearby_pairs (+1) | `bff1b66dfe80` |
| [hardware/g1_arm_bridge/edit_startup_ready_pose.py](../hardware/g1_arm_bridge/edit_startup_ready_pose.py) | 460 | 목록 확인 | PoseAssessment, EditorState, ParseArguments, LoadPose, SafeLimitsDegrees (+11) | `f81dc7c11775` |
| [hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py) | 29 | 목록 확인 | ExperimentalStatefulGate7TeleopController | `a93f2c85b9b1` |
| [hardware/g1_arm_bridge/g1_base_state.py](../hardware/g1_arm_bridge/g1_base_state.py) | 212 | 목록 확인 | InvalidBaseStateError, NormalizedBaseState, _FiniteVector, NormalizeQuaternionWXYZ, MultiplyQuaternionWXYZ (+4) | `11c6f8e1e985` |
| [hardware/g1_arm_bridge/g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/g1_camera_replay_tcp.py) | 317 | 목록 확인 | LoadFont, BuildReplayJpeg, ParseArguments, ValidateArguments, WriteResult (+1) | `651871f79df3` |
| [hardware/g1_arm_bridge/g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/g1_camera_tcp_bridge.py) | 206 | 목록 확인 | BuildFramePacket, ParseArguments, CreateVideoClient, ConnectUnity, ValidateArguments (+1) | `47a863f1b4fc` |
| [hardware/g1_arm_bridge/g1_joint_contract.py](../hardware/g1_arm_bridge/g1_joint_contract.py) | 39 | 목록 확인 | - | `bb33790cb1af` |
| [hardware/g1_arm_bridge/g1_right_arm_jog.py](../hardware/g1_arm_bridge/g1_right_arm_jog.py) | 1262 | 목록 확인 | RuntimeConfig, KeyboardReader, _number, load_config, validate_config (+17) | `4e0745b00cf8` |
| [hardware/g1_arm_bridge/g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/g1_right_arm_jog_entry.py) | 234 | 목록 확인 | _argument_path, _config_path, apply_release_result_guard, install_jog_safety_guards, main | `3a4377883963` |
| [hardware/g1_arm_bridge/g1_unity_state_bridge.py](../hardware/g1_arm_bridge/g1_unity_state_bridge.py) | 224 | 목록 확인 | _FiniteVector, _QuaternionAngleDegrees, _RequireFullBody, BuildUnityHardwareStatePacket, EncodeUnityHardwareStatePacket (+1) | `4d820db4d806` |
| [hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py) | 803 | 목록 확인 | LowStatePacketError, BaseStateTelemetry, LowStateTelemetry, PacketOrderTracker, _finite_joint_vector (+16) | `1081cdcd9e21` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold.py) | 870 | 목록 확인 | RuntimeConfig, LowStateSnapshot, LowStateBuffer, _finite_number, load_runtime_config (+12) | `c364ba2eefd4` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py) | 72 | 목록 확인 | install_supported_gate6_guards, main | `2a8dcda852e6` |
| [hardware/g1_arm_bridge/gate7_acquisition_guard.py](../hardware/g1_arm_bridge/gate7_acquisition_guard.py) | 126 | 목록 확인 | ActiveAcquisitionGuard, validate_full_body_snapshot_matches_precheck, validate_acquisition_hold_target | `d7dcaf61ae8a` |
| [hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py](../hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py) | 231 | 목록 확인 | SleepUntilStep, SelectReplayWindow, _replace_dual, BuildExperimentalLimitedFrames, _parse_args (+1) | `d072bbb57296` |
| [hardware/g1_arm_bridge/gate7_capture_quality.py](../hardware/g1_arm_bridge/gate7_capture_quality.py) | 851 | 목록 확인 | _percentile, _round, _replace_dual, _decode_capture, _series_metrics (+9) | `0b5ae4a1e96f` |
| [hardware/g1_arm_bridge/gate7_capture_regression.py](../hardware/g1_arm_bridge/gate7_capture_regression.py) | 217 | 목록 확인 | _replace_dual, _file_sha256, BuildRegressionTrace, CompareTrace, _automatic_result_path (+2) | `6ea4853ec628` |
| [hardware/g1_arm_bridge/gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/gate7_fault_injection_matrix.py) | 317 | 목록 확인 | _replace_dual, _synthetic_active_value, _load_active_value, _payload, _new_controller (+5) | `46f4cef501a3` |
| [hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py) | 358 | 목록 확인 | _replace_dual, _packet, _automatic_result_path, _parse_args, main | `8bcbae023597` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk.py) | 861 | 입출력 확인 | LiveHardwareConfig, _finite, LoadLiveHardwareConfig, ValidateLiveHardwareConfig, ValidateRuckigRuntime (+12) | `de7bbeec93bf` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py) | 268 | 목록 확인 | _argument_path, _pop_argument, install_supported_path_guards, main | `30914406d1e9` |
| [hardware/g1_arm_bridge/gate7_live_dry_run.py](../hardware/g1_arm_bridge/gate7_live_dry_run.py) | 743 | 목록 확인 | DryRunTick, _finite_all_joints, _replace_dual_arm, _automatic_path, _resolve_output_path (+6) | `c23e7372b0d1` |
| [hardware/g1_arm_bridge/gate7_live_safety_guard.py](../hardware/g1_arm_bridge/gate7_live_safety_guard.py) | 120 | 목록 확인 | ArmSegmentPoint, LinearDualArmSegment, require_active_collision_evidence, _finite_all_joints, build_final_command_segment (+1) | `c89e7f456590` |
| [hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py](../hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py) | 518 | 목록 확인 | _set_full_body_pose, CollisionPathValidator, _replace_dual_arm, _mink_packet, _target_right_arm (+3) | `11515a3d2625` |
| [hardware/g1_arm_bridge/gate7_mink_capture.py](../hardware/g1_arm_bridge/gate7_mink_capture.py) | 146 | 목록 확인 | _automatic_path, _write_line, _parse_args, main | `aa84643b4466` |
| [hardware/g1_arm_bridge/gate7_mink_replay.py](../hardware/g1_arm_bridge/gate7_mink_replay.py) | 152 | 목록 확인 | CapturedPacket, LoadCapture, NormalizePayload, CaptureSha256, validate_replay_destination (+2) | `60e2e3c2814f` |
| [hardware/g1_arm_bridge/gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/gate7_mink_wsl_relay.py) | 213 | 입출력 확인 | MinkOrderGuard, ValidateRelayEndpoint, ValidateAndForward, _automatic_result_path, _parse_args (+1) | `fe8ce859af13` |
| [hardware/g1_arm_bridge/gate7_relay_provenance_guard.py](../hardware/g1_arm_bridge/gate7_relay_provenance_guard.py) | 170 | 목록 확인 | validate_relay_token, _payload_object, require_relay_token, command_provenance, require_live_candidate_for_relay (+3) | `d05ece716376` |
| [hardware/g1_arm_bridge/generate_fake_mink_targets.py](../hardware/g1_arm_bridge/generate_fake_mink_targets.py) | 117 | 목록 확인 | parse_args, main | `eeb5c6e0e331` |
| [hardware/g1_arm_bridge/hardware_state.py](../hardware/g1_arm_bridge/hardware_state.py) | 91 | 목록 확인 | HardwarePhase, FaultCode, build_status, write_status | `81f126c94061` |
| [hardware/g1_arm_bridge/live_lowstate_mujoco.py](../hardware/g1_arm_bridge/live_lowstate_mujoco.py) | 651 | 목록 확인 | StreamState, BaseBodyPose, ParseArguments, ResolveMeasurementLogPath, BuildMirrorMeasurement (+14) | `8fdc36365c68` |
| [hardware/g1_arm_bridge/lowstate_health_guard.py](../hardware/g1_arm_bridge/lowstate_health_guard.py) | 119 | 목록 확인 | _value, _temperature_max_c, validate_lowstate_health_message, install_lowstate_health_tracking, require_latest_lowstate_health | `c8715c8899a3` |
| [hardware/g1_arm_bridge/mink_target_dry_run.py](../hardware/g1_arm_bridge/mink_target_dry_run.py) | 127 | 목록 확인 | _fmt_deg, main | `372002c8b23c` |
| [hardware/g1_arm_bridge/plan_startup_transition.py](../hardware/g1_arm_bridge/plan_startup_transition.py) | 684 | 목록 확인 | _inside_pairs, _waypoints_for_order, _dense_segment, _evaluate_order, _joint_limits (+6) | `743e1de0dc71` |
| [hardware/g1_arm_bridge/precheck_provenance_guard.py](../hardware/g1_arm_bridge/precheck_provenance_guard.py) | 39 | 목록 확인 | require_provenance_bound_precheck | `aa8fbdd33530` |
| [hardware/g1_arm_bridge/probe_joint_motion.py](../hardware/g1_arm_bridge/probe_joint_motion.py) | 177 | 목록 확인 | parse_args, current_positions, collect_positions, summarize, main | `6b43271de626` |
| [hardware/g1_arm_bridge/query_motion_mode.py](../hardware/g1_arm_bridge/query_motion_mode.py) | 110 | 목록 확인 | _write_json, parse_args, main | `d86bc3ea68ba` |
| [hardware/g1_arm_bridge/query_motion_mode_wsl.sh](../hardware/g1_arm_bridge/query_motion_mode_wsl.sh) | 24 | 목록 확인 | - | `19cdf2097714` |
| [hardware/g1_arm_bridge/read_only_lowstate.py](../hardware/g1_arm_bridge/read_only_lowstate.py) | 563 | 목록 확인 | JointSample, ReadOnlyG1LowState, ReadOnlyG1BaseState, _motor_value, _state_uint8 (+9) | `bfaef913f786` |
| [hardware/g1_arm_bridge/read_only_lowstate_entry.py](../hardware/g1_arm_bridge/read_only_lowstate_entry.py) | 154 | 목록 확인 | _pop_option, _finite_vector, install_raw_odom_binding, install_forward_token, main | `a38ce663d019` |
| [hardware/g1_arm_bridge/receive_initial_state.py](../hardware/g1_arm_bridge/receive_initial_state.py) | 199 | 목록 확인 | parse_args, _raw_object, _validate_provenance, _validate_full_body_consistency, main | `4285ba83ada2` |
| [hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py) | 354 | 목록 확인 | SavedLowState, _FiniteVector, _JointNames, _OptionalMode, LoadSnapshot (+5) | `a869fd552b3d` |
| [hardware/g1_arm_bridge/replay_startup_recovery.py](../hardware/g1_arm_bridge/replay_startup_recovery.py) | 184 | 목록 확인 | ParseArguments, LoadViewerSettings, LoadRecovery, InterpolatePose, ApplyRightArmPose (+1) | `b9d0962771a0` |
| [hardware/g1_arm_bridge/right_arm_jog_contract.py](../hardware/g1_arm_bridge/right_arm_jog_contract.py) | 194 | 목록 확인 | ArmJointJogLimits, ArmJointJogTick, validate_jog_limits, ArmJointJogController | `83f51c0a80df` |
| [hardware/g1_arm_bridge/right_arm_jog_safety_guard.py](../hardware/g1_arm_bridge/right_arm_jog_safety_guard.py) | 93 | 목록 확인 | file_sha256, build_jog_permit_provenance, validate_jog_permit_provenance, validate_jog_runtime_full_body, validate_jog_final_segment | `ff8778a8eb9e` |
| [hardware/g1_arm_bridge/ruckig_gate7_controller.py](../hardware/g1_arm_bridge/ruckig_gate7_controller.py) | 121 | 목록 확인 | RuckigGate7TeleopController | `dcc46f5329c7` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 95 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `cb2102cd76c2` |
| [hardware/g1_arm_bridge/runtime_base_state_guard.py](../hardware/g1_arm_bridge/runtime_base_state_guard.py) | 316 | 목록 확인 | RuntimeBaseSnapshot, RuntimeBaseStateMonitor, _relative_yaw_rad, _finite_vector, _quaternion_angle_delta_rad (+5) | `9f1816007448` |
| [hardware/g1_arm_bridge/safety_gate.py](../hardware/g1_arm_bridge/safety_gate.py) | 149 | 목록 확인 | SafetyConfig, SafetyDecision, _vector, _within_joint_limits, evaluate_target | `20d483a19afa` |
| [hardware/g1_arm_bridge/simulate_startup_recovery.py](../hardware/g1_arm_bridge/simulate_startup_recovery.py) | 1179 | 목록 확인 | _load_startup_safe_ready_degrees, _right_qpos_ids, _minimum_clearance, _minimum_clearance_extended, _recovery_edge_is_valid (+10) | `255ddab4dff2` |
| [hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh](../hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh) | 27 | 목록 확인 | - | `68617dd7529a` |
| [hardware/g1_arm_bridge/start_gate6_hold_wsl.sh](../hardware/g1_arm_bridge/start_gate6_hold_wsl.sh) | 24 | 목록 확인 | - | `02803d8b764f` |
| [hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh](../hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh) | 29 | 목록 확인 | - | `1040c430ca14` |
| [hardware/g1_arm_bridge/start_read_only_wsl.sh](../hardware/g1_arm_bridge/start_read_only_wsl.sh) | 22 | 목록 확인 | - | `969530765469` |
| [hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh](../hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh) | 24 | 목록 확인 | - | `bf6fc5424ee2` |
| [hardware/g1_arm_bridge/startup_state_binding_guard.py](../hardware/g1_arm_bridge/startup_state_binding_guard.py) | 143 | 목록 확인 | file_sha256, build_state_binding, base_state_to_dict, _require_finite_vector, require_state_binding | `386687ebca94` |
| [hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py) | 138 | 목록 확인 | _safe_all_q, ArmSdkHoldContractTests | `595ee6731836` |
| [hardware/g1_arm_bridge/test_arm_sdk_release_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_release_contract.py) | 138 | 목록 확인 | FakeClock, ReleaseContractTests | `54920f957d0c` |
| [hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py) | 387 | 목록 확인 | _replace_dual, _sample, ArmSdkTeleopContractTests | `34878fa95cdf` |
| [hardware/g1_arm_bridge/test_check_startup_readiness.py](../hardware/g1_arm_bridge/test_check_startup_readiness.py) | 196 | 목록 확인 | _config, _timed_packet, _mode_query, StartupReadinessTests | `37e1032193bc` |
| [hardware/g1_arm_bridge/test_check_startup_readiness_entry.py](../hardware/g1_arm_bridge/test_check_startup_readiness_entry.py) | 111 | 목록 확인 | _raw_base_state, StartupPrecheckEntryTests | `6a1c5cdb14eb` |
| [hardware/g1_arm_bridge/test_collision_diagnostics.py](../hardware/g1_arm_bridge/test_collision_diagnostics.py) | 60 | 목록 확인 | _FakeG1, _FakeController, CollisionDiagnosticTests | `b2642345a203` |
| [hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py) | 43 | 목록 확인 | ExperimentalStatefulGate7ControllerTests | `cc444df0124f` |
| [hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py](../hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py) | 82 | 목록 확인 | main | `fa397980398b` |
| [hardware/g1_arm_bridge/test_g1_base_state.py](../hardware/g1_arm_bridge/test_g1_base_state.py) | 118 | 목록 확인 | YawQuaternionWXYZ, G1BaseStateTests | `11a58e53ca27` |
| [hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py) | 75 | 목록 확인 | G1CameraReplayTcpTest | `9b8a5cc0dc54` |
| [hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py) | 44 | 목록 확인 | G1CameraTcpBridgeTest | `e1047b89e99b` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog.py) | 327 | 목록 확인 | G1RightArmJogTests | `ee9310bc7ab1` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py) | 50 | 목록 확인 | DirectJogReleaseIntegrationTests | `1b11145d8b85` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py) | 107 | 목록 확인 | RightArmJogReleaseGuardTests | `808ab9f76a81` |
| [hardware/g1_arm_bridge/test_g1_unity_state_bridge.py](../hardware/g1_arm_bridge/test_g1_unity_state_bridge.py) | 175 | 목록 확인 | LowStatePacket, G1UnityStateBridgeTests | `0c91cc2833b5` |
| [hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py) | 218 | 목록 확인 | _packet, _base_state, _unused_local_port, Gate5LowStateSafetyTests | `5ab06a9f3908` |
| [hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py) | 163 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, Gate6ArmSdkHoldTests | `eb7980a6479b` |
| [hardware/g1_arm_bridge/test_gate6_fault_release.py](../hardware/g1_arm_bridge/test_gate6_fault_release.py) | 154 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, _FakeCRC, _FakeBuffer, _FakePublisher (+2) | `697a9ab1c6a9` |
| [hardware/g1_arm_bridge/test_gate6_interrupt_release.py](../hardware/g1_arm_bridge/test_gate6_interrupt_release.py) | 130 | 목록 확인 | validate_interrupt_release_contract, Gate6InterruptReleaseTests, main | `fad40aefbdfa` |
| [hardware/g1_arm_bridge/test_gate7_acquisition_guard.py](../hardware/g1_arm_bridge/test_gate7_acquisition_guard.py) | 95 | 목록 확인 | sample, Gate7AcquisitionGuardTests | `646fe47e3b73` |
| [hardware/g1_arm_bridge/test_gate7_capture_quality.py](../hardware/g1_arm_bridge/test_gate7_capture_quality.py) | 106 | 목록 확인 | Gate7CaptureQualityTests | `065920308f3a` |
| [hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py) | 32 | 목록 확인 | Gate7FaultInjectionMatrixTests | `63b8b799b54f` |
| [hardware/g1_arm_bridge/test_gate7_first_live_profile.py](../hardware/g1_arm_bridge/test_gate7_first_live_profile.py) | 112 | 목록 확인 | Gate7FirstLiveProfileTests | `c563edb0cf19` |
| [hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py) | 66 | 목록 확인 | _free_udp_port, Gate7HardwareVirtualE2ETests | `f905f33e9bfa` |
| [hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py) | 208 | 목록 확인 | Gate7LiveArmSdkTests | `10032d407ebf` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run.py) | 361 | 목록 확인 | _replace_dual, _sample, Gate7LiveDryRunTests | `7a777136e907` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py) | 136 | 목록 확인 | _free_udp_port, Gate7LiveDryRunE2ETests | `0eeb63044d28` |
| [hardware/g1_arm_bridge/test_gate7_live_entrypoint.py](../hardware/g1_arm_bridge/test_gate7_live_entrypoint.py) | 54 | 목록 확인 | Gate7LiveEntrypointTests | `c8442f5aea8b` |
| [hardware/g1_arm_bridge/test_gate7_live_safety_guard.py](../hardware/g1_arm_bridge/test_gate7_live_safety_guard.py) | 89 | 목록 확인 | Gate7LiveSafetyGuardTests | `398bb4186f52` |
| [hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py](../hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py) | 119 | 목록 확인 | _free_udp_port, Gate7MinkCaptureReplayTests | `a67b307d7562` |
| [hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py) | 180 | 목록 확인 | _packet, Gate7MinkWslRelayTests | `9a94a1dd078e` |
| [hardware/g1_arm_bridge/test_gate7_release_finalization.py](../hardware/g1_arm_bridge/test_gate7_release_finalization.py) | 59 | 목록 확인 | Gate7ReleaseFinalizationTests | `727d3f4f3d7c` |
| [hardware/g1_arm_bridge/test_gate7_replay_provenance.py](../hardware/g1_arm_bridge/test_gate7_replay_provenance.py) | 72 | 목록 확인 | Gate7ReplayProvenanceTests | `a339d0a3a941` |
| [hardware/g1_arm_bridge/test_gate7_visible_motion_profile.py](../hardware/g1_arm_bridge/test_gate7_visible_motion_profile.py) | 38 | 목록 확인 | Gate7VisibleMotionProfileTests | `a21bafb9a9fd` |
| [hardware/g1_arm_bridge/test_hardware_state.py](../hardware/g1_arm_bridge/test_hardware_state.py) | 71 | 목록 확인 | HardwareStateTests | `ef04766efed9` |
| [hardware/g1_arm_bridge/test_live_lowstate_mujoco.py](../hardware/g1_arm_bridge/test_live_lowstate_mujoco.py) | 252 | 목록 확인 | Packet, LiveLowStateMuJoCoTests | `472543c7ee7d` |
| [hardware/g1_arm_bridge/test_lowstate_health_guard.py](../hardware/g1_arm_bridge/test_lowstate_health_guard.py) | 85 | 목록 확인 | _Motor, _Message, LowStateHealthGuardTests | `c6485263b8dc` |
| [hardware/g1_arm_bridge/test_lowstate_provenance_launchers.py](../hardware/g1_arm_bridge/test_lowstate_provenance_launchers.py) | 72 | 목록 확인 | LowStateProvenanceLauncherTests | `1ac62a0be824` |
| [hardware/g1_arm_bridge/test_mink_safety_pipeline.py](../hardware/g1_arm_bridge/test_mink_safety_pipeline.py) | 129 | 목록 확인 | _target_at, main | `8b18042096ca` |
| [hardware/g1_arm_bridge/test_physical_precheck_provenance_entries.py](../hardware/g1_arm_bridge/test_physical_precheck_provenance_entries.py) | 27 | 목록 확인 | PhysicalPrecheckProvenanceEntryTests | `95cee35eee8b` |
| [hardware/g1_arm_bridge/test_precheck_provenance_guard.py](../hardware/g1_arm_bridge/test_precheck_provenance_guard.py) | 87 | 목록 확인 | PrecheckProvenanceGuardTests | `4359340176d6` |
| [hardware/g1_arm_bridge/test_replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/test_replay_saved_lowstate_mujoco.py) | 93 | 목록 확인 | ReplaySavedLowStateMuJoCoTests | `8eed5e51ef73` |
| [hardware/g1_arm_bridge/test_right_arm_jog_contract.py](../hardware/g1_arm_bridge/test_right_arm_jog_contract.py) | 191 | 목록 확인 | measured_pose, RightArmJogContractTests | `49e66419d52f` |
| [hardware/g1_arm_bridge/test_right_arm_jog_safety_guard.py](../hardware/g1_arm_bridge/test_right_arm_jog_safety_guard.py) | 67 | 목록 확인 | RightArmJogSafetyGuardTests | `3d057af5e962` |
| [hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py) | 75 | 목록 확인 | RuckigJointMotionLimiterTests | `9c8b5a2b35e6` |
| [hardware/g1_arm_bridge/test_runtime_base_state_guard.py](../hardware/g1_arm_bridge/test_runtime_base_state_guard.py) | 212 | 목록 확인 | _Message, _yaw_quaternion_wxyz, _precheck, RuntimeBaseStateGuardTests | `9cd231d92daf` |
| [hardware/g1_arm_bridge/test_safety_gate.py](../hardware/g1_arm_bridge/test_safety_gate.py) | 124 | 목록 확인 | SafetyGateTests | `021ebefe3f9f` |
| [hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py) | 73 | 목록 확인 | ValidateRightArmJogCollisionPathTests | `fdf09a9611a9` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py) | 261 | 목록 확인 | load_precheck, measured_pose, build_offset_trajectory, build_endpoint_trajectories, validate_offset_path (+5) | `4e63d58751d4` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py) | 40 | 목록 확인 | _argument_path, main | `5571099212f5` |
| [hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py](../hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py) | 64 | 목록 확인 | main | `172f652bdf8b` |
| [hardware/g1_arm_bridge/verify_initial_pose_sync.py](../hardware/g1_arm_bridge/verify_initial_pose_sync.py) | 128 | 목록 확인 | _load_captured_pose, main | `5e10bddca4d2` |
| [tools/ALLOW_G1_DDS_WSL.bat](../tools/ALLOW_G1_DDS_WSL.bat) | 11 | 목록 확인 | - | `b175434b623d` |
| [tools/ALLOW_G1_DDS_WSL_ADMIN.ps1](../tools/ALLOW_G1_DDS_WSL_ADMIN.ps1) | 40 | 목록 확인 | - | `8c34d5960fe1` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat) | 13 | 목록 확인 | - | `fa0aa31c0cc6` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1) | 19 | 목록 확인 | - | `a7eceaf93887` |
| [tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat](../tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat) | 32 | 목록 확인 | - | `bd53ccf085f5` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 74 | 목록 확인 | - | `9bc1b7a2f666` |
| [tools/CHECK_G1_TELEOP_STARTUP.bat](../tools/CHECK_G1_TELEOP_STARTUP.bat) | 66 | 목록 확인 | - | `bbaa4c38b10e` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 11 | 목록 확인 | - | `308b1b54bec6` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `f0fc88d7eda9` |
| [tools/DETECT_G1_NETWORK.bat](../tools/DETECT_G1_NETWORK.bat) | 11 | 목록 확인 | - | `be9f63666f9c` |
| [tools/DETECT_G1_NETWORK_ADMIN.ps1](../tools/DETECT_G1_NETWORK_ADMIN.ps1) | 24 | 목록 확인 | - | `9256505bee6a` |
| [tools/EDIT_G1_STARTUP_READY_POSE.bat](../tools/EDIT_G1_STARTUP_READY_POSE.bat) | 33 | 목록 확인 | - | `64872de03943` |
| [tools/PREPARE_G1_GATE6_HOLD.bat](../tools/PREPARE_G1_GATE6_HOLD.bat) | 39 | 목록 확인 | - | `3153383c91bf` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 11 | 목록 확인 | - | `698638321bb5` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 14 | 목록 확인 | - | `8ce67bf732bd` |
| [tools/SET_UNITY_DISPLAY_MODE.ps1](../tools/SET_UNITY_DISPLAY_MODE.ps1) | 25 | 입출력 확인 | - | `d9f1eb1f0fca` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 26 | 목록 확인 | - | `980967bbd243` |
| [tools/START_G1_GATE5_READ_ONLY.bat](../tools/START_G1_GATE5_READ_ONLY.bat) | 37 | 목록 확인 | - | `5315ab2202d3` |
| [tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat](../tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat) | 112 | 목록 확인 | - | `8ec7aff5f329` |
| [tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat](../tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat) | 25 | 목록 확인 | - | `d3c82d1693ca` |
| [tools/START_G1_GATE7_LIVE_DRY_RUN.bat](../tools/START_G1_GATE7_LIVE_DRY_RUN.bat) | 57 | 목록 확인 | - | `cd1d84f9ea66` |
| [tools/START_G1_GATE7_LIVE_HARDWARE.bat](../tools/START_G1_GATE7_LIVE_HARDWARE.bat) | 207 | 목록 확인 | - | `a54b0e17b2e0` |
| [tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat](../tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat) | 92 | 목록 확인 | - | `264801696a18` |
| [tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat](../tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat) | 25 | 목록 확인 | - | `20b8d69ecc4c` |
| [tools/START_G1_GATE7_VR_RECORDING.bat](../tools/START_G1_GATE7_VR_RECORDING.bat) | 59 | 목록 확인 | - | `bbdf7d312c3d` |
| [tools/START_G1_READ_ONLY.bat](../tools/START_G1_READ_ONLY.bat) | 15 | 목록 확인 | - | `a7662ec59842` |
| [tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat](../tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat) | 128 | 목록 확인 | - | `cb2107ef0a12` |
| [tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat](../tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat) | 128 | 목록 확인 | - | `e059a027d941` |
| [tools/START_MINK_G1_HARDWARE_SYNC.bat](../tools/START_MINK_G1_HARDWARE_SYNC.bat) | 66 | 목록 확인 | - | `fa24c6c45e36` |
| [tools/TEST_CAMERA_REPLAY_TO_UNITY.bat](../tools/TEST_CAMERA_REPLAY_TO_UNITY.bat) | 101 | 목록 확인 | - | `9f30acf8eb02` |
| [tools/TEST_FAKE_MINK_SAFETY_E2E.bat](../tools/TEST_FAKE_MINK_SAFETY_E2E.bat) | 35 | 목록 확인 | - | `e47a6a5f6ae8` |
| [tools/TEST_G1_GATE5_READ_ONLY.bat](../tools/TEST_G1_GATE5_READ_ONLY.bat) | 32 | 목록 확인 | - | `9aee1e5307a0` |
| [tools/TEST_G1_GATE6_HOLD_OFFLINE.bat](../tools/TEST_G1_GATE6_HOLD_OFFLINE.bat) | 46 | 목록 확인 | - | `d39eb8191468` |
| [tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat](../tools/TEST_G1_GATE6_INTERRUPT_RELEASE_OFFLINE.bat) | 31 | 목록 확인 | - | `5ae70d51e35e` |
| [tools/TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat](../tools/TEST_G1_GATE7_CAPTURE_REPLAY_OFFLINE.bat) | 32 | 목록 확인 | - | `60542b0f6af5` |
| [tools/TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat](../tools/TEST_G1_GATE7_FAULT_MATRIX_OFFLINE.bat) | 35 | 목록 확인 | - | `2efd23cb12cc` |
| [tools/TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat](../tools/TEST_G1_GATE7_FIRST_LIVE_OFFLINE.bat) | 42 | 목록 확인 | - | `6701c0a011d7` |
| [tools/TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat](../tools/TEST_G1_GATE7_HARDWARE_FOUNDATION_OFFLINE.bat) | 43 | 목록 확인 | - | `773adf884173` |
| [tools/TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat](../tools/TEST_G1_GATE7_LATEST_CAPTURE_FAULT_MATRIX.bat) | 30 | 목록 확인 | - | `a1e0938bea2d` |
| [tools/TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat](../tools/TEST_G1_GATE7_LATEST_CAPTURE_REGRESSION.bat) | 34 | 목록 확인 | - | `373610450412` |
| [tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat](../tools/TEST_G1_GATE7_LIVE_DRY_RUN.bat) | 39 | 목록 확인 | - | `164a458217ae` |
| [tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat](../tools/TEST_G1_GATE7_MINK_ARM_SDK_OFFLINE.bat) | 46 | 목록 확인 | - | `ebfc6821ad0e` |
| [tools/TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat](../tools/TEST_G1_GATE7_RUCKIG_HARDWARE_PROFILE_OFFLINE.bat) | 45 | 목록 확인 | - | `04d7284db991` |
| [tools/TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat](../tools/TEST_G1_GATE7_VIRTUAL_HARDWARE_E2E.bat) | 51 | 목록 확인 | - | `b53545df3a37` |
| [tools/TEST_G1_HARDWARE_SAFETY_GATE.bat](../tools/TEST_G1_HARDWARE_SAFETY_GATE.bat) | 34 | 목록 확인 | - | `4c2c7eb49988` |
| [tools/TEST_G1_HARDWARE_STATE.bat](../tools/TEST_G1_HARDWARE_STATE.bat) | 33 | 목록 확인 | - | `774508dc5f65` |
| [tools/TEST_G1_MINK_FK_PARITY.bat](../tools/TEST_G1_MINK_FK_PARITY.bat) | 70 | 목록 확인 | - | `ed21e490ab91` |
| [tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat](../tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat) | 43 | 목록 확인 | - | `82d5a9f2f879` |
| [tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat](../tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat) | 40 | 목록 확인 | - | `b99057a32b5c` |
| [tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat](../tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat) | 31 | 목록 확인 | - | `c94d9691fe18` |
| [tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat](../tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat) | 27 | 목록 확인 | - | `21597a36c35d` |
| [tools/TEST_MINK_SAFETY_PIPELINE.bat](../tools/TEST_MINK_SAFETY_PIPELINE.bat) | 35 | 목록 확인 | - | `3592659bb64f` |
| [tools/TEST_MINK_WRIST_FRAME.bat](../tools/TEST_MINK_WRIST_FRAME.bat) | 34 | 목록 확인 | - | `414187888f10` |
| [tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat](../tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat) | 27 | 목록 확인 | - | `eae096375075` |
| [tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat) | 29 | 목록 확인 | - | `863b6b3bab9c` |
| [tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat) | 35 | 목록 확인 | - | `6a5931f23923` |
| [tools/VIEW_G1_LIVE_MUJOCO.bat](../tools/VIEW_G1_LIVE_MUJOCO.bat) | 44 | 목록 확인 | - | `443a31bda5ec` |
| [tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat](../tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat) | 35 | 목록 확인 | - | `2169a22c9d3f` |
| [tools/VIEW_G1_STARTUP_RECOVERY.bat](../tools/VIEW_G1_STARTUP_RECOVERY.bat) | 28 | 목록 확인 | - | `401c61f102ba` |
