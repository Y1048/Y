# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **341개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

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
| [MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py](../MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py) | 81 | 목록 확인 | mujoco_to_unity_delta, main | `52b084b2b71a` |
| [MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py](../MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py) | 77 | 목록 확인 | drain_gate7_simulation_feedback, apply_gate7_simulation_feedback | `a3b14b20de41` |
| [MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py](../MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py) | 27 | 목록 확인 | ResolveCollisionProfile | `690f7acc0dbd` |
| [MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py) | 37 | 목록 확인 | mark_live_mink_packet, wrap_state_packet_factory | `b852ec80fc67` |
| [MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py](../MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py) | 10 | 목록 확인 | orientation_diagnostics | `a3b8dbe9cd27` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 입출력 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `0284be10a075` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 121 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `b33313c5d019` |
| [MuJoCo_G1_Controller/scripts/g1_right_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_right_arm_common.py) | 425 | 목록 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `a682abf803e0` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `7d6cb78dbfb2` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 267 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `bbc287889781` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py) | 913 | 목록 확인 | parse_args, _update_reachability_limit, _find_body, _prepare_mink_xml, LoadMinkModel (+25) | `bc391176d773` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py) | 20 | 목록 확인 | main | `aebdd2dc962a` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py) | 895 | 입출력 확인 | parse_args, main | `05e4e716a8e6` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py) | 19 | 목록 확인 | main | `d1983100a9de` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py) | 58 | 목록 확인 | LoadEngine, MarkSimulation, main | `dc8d6837c9cd` |
| [MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py) | 101 | 목록 확인 | MinkCommandProvenanceTests | `7819cd59119e` |
| [MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py](../MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py) | 99 | 목록 확인 | require, require_pattern, forbid, main | `30cc0d077b66` |
| [START_MUJOCO_ONLY.bat](../START_MUJOCO_ONLY.bat) | 55 | 목록 확인 | - | `bbbad8c0c2ce` |
| [START_VR_HAND_TO_MUJOCO.bat](../START_VR_HAND_TO_MUJOCO.bat) | 309 | 입출력 확인 | - | `0808c265b92a` |
| [START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat](../START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat) | 33 | 목록 확인 | - | `7bfda72adff1` |
| [START_VR_STANDARD_MINK.bat](../START_VR_STANDARD_MINK.bat) | 5 | 목록 확인 | - | `1d903fba29c2` |
| [Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs](../Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs) | 430 | 목록 확인 | - | `d3aa9d45c92a` |
| [Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs](../Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs) | 134 | 목록 확인 | - | `3a842c8567a3` |
| [Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs](../Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs) | 591 | 목록 확인 | - | `0cc491e3db1b` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 607 | 목록 확인 | - | `091cb87249c3` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 67 | 목록 확인 | - | `0132defcf35b` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 900 | 입출력 확인 | - | `5f73a74bee4b` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 523 | 입출력 확인 | - | `b976a72f1a16` |
| [Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs) | 98 | 목록 확인 | - | `40a96eb5264c` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 646 | 목록 확인 | - | `295e2c47e0d2` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 265 | 목록 확인 | - | `7373a9492fc6` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs](../Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs) | 280 | 목록 확인 | - | `05cd0f96c8c8` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 375 | 목록 확인 | - | `db28be0dcd81` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 777 | 입출력 확인 | - | `f5aff63a7db3` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 963 | 입출력 확인 | - | `b9e213ae0888` |
| [Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs](../Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs) | 50 | 목록 확인 | - | `3124aab0e080` |
| [VIEW_IK_COMPARISON.bat](../VIEW_IK_COMPARISON.bat) | 19 | 목록 확인 | - | `862667f3fe95` |
| [VIEW_TRAJECTORY_AB.bat](../VIEW_TRAJECTORY_AB.bat) | 14 | 목록 확인 | - | `01a1ebf28067` |
| [backend/g1_teleop/__init__.py](../backend/g1_teleop/__init__.py) | 101 | 목록 확인 | - | `86664979265c` |
| [backend/g1_teleop/calibration.py](../backend/g1_teleop/calibration.py) | 363 | 목록 확인 | _pose_matrix, _scale_vector, _pose_to_dict, _pose_from_dict, ArmCalibration (+8) | `a2aefc7d8a10` |
| [backend/g1_teleop/camera.py](../backend/g1_teleop/camera.py) | 314 | 목록 확인 | CameraIntrinsics, CameraFrame, HeadCameraSource, MuJoCoHeadCameraSource, RealSenseD435iSource (+1) | `b3ce4be392b7` |
| [backend/g1_teleop/camera_factory.py](../backend/g1_teleop/camera_factory.py) | 103 | 목록 확인 | load_camera_profile, validate_camera_profile, validate_teleimager_profile, create_head_camera_source | `097bd1a6a72d` |
| [backend/g1_teleop/command_adapter.py](../backend/g1_teleop/command_adapter.py) | 182 | 입출력 확인 | InternalCommand, _decode_object, _legacy_integer, _legacy_source_time_ns, _legacy_vector (+4) | `eb251eba6545` |
| [backend/g1_teleop/config.py](../backend/g1_teleop/config.py) | 240 | 목록 확인 | NetworkConfig, RuntimeConfig, MotionConfig, IKConfig, CollisionConfig (+11) | `4cf11c8fcace` |
| [backend/g1_teleop/g1_camera_mount.py](../backend/g1_teleop/g1_camera_mount.py) | 60 | 목록 확인 | _find_body, add_g1_d435i_camera | `eac56096d9a5` |
| [backend/g1_teleop/gate7_simulation_feedback.py](../backend/g1_teleop/gate7_simulation_feedback.py) | 153 | 목록 확인 | Gate7SimulationFeedbackError, Gate7SimulationFeedback, _finite_vector, build_packet, parse_packet (+1) | `89aa873e72b0` |
| [backend/g1_teleop/inspection_contact.py](../backend/g1_teleop/inspection_contact.py) | 161 | 목록 확인 | InspectionContactState, InspectionContactTransition, InspectionContactStateMachine, install_inspection_contact_monitor | `8241c3028ba3` |
| [backend/g1_teleop/inspection_demo.py](../backend/g1_teleop/inspection_demo.py) | 159 | 목록 확인 | InspectionDemoState, InspectionDemoSnapshot, InspectionDemoTracker, append_inspection_result | `92a6711f4497` |
| [backend/g1_teleop/live_receiver.py](../backend/g1_teleop/live_receiver.py) | 136 | 입출력 확인 | DatagramSocket, ReceiveBatch, receive_available_commands | `1d02a4ee903a` |
| [backend/g1_teleop/mapping.py](../backend/g1_teleop/mapping.py) | 36 | 목록 확인 | map_unity_ovr_wrist_to_head_yaw | `5166bfed6876` |
| [backend/g1_teleop/mink_command_stream.py](../backend/g1_teleop/mink_command_stream.py) | 203 | 입출력 확인 | MinkCommandUpdate, MinkCommandStream | `d0dea7baca9f` |
| [backend/g1_teleop/motion_reference.py](../backend/g1_teleop/motion_reference.py) | 64 | 목록 확인 | step_position, step_rotation | `cef1334bbb00` |
| [backend/g1_teleop/protocol.py](../backend/g1_teleop/protocol.py) | 370 | 목록 확인 | ProtocolError, _boolean, _finite_vector, _integer, _nonempty_string (+7) | `9ade9295e9eb` |
| [backend/g1_teleop/runtime_state.py](../backend/g1_teleop/runtime_state.py) | 91 | 목록 확인 | RuntimeTransition, TeleopRuntimeStateMachine | `43b826597eb4` |
| [backend/g1_teleop/source_provenance.py](../backend/g1_teleop/source_provenance.py) | 135 | 목록 확인 | SourceAcceptance, _SessionClock, CommandSourceGuard | `4e152f262150` |
| [backend/g1_teleop/transforms.py](../backend/g1_teleop/transforms.py) | 243 | 목록 확인 | validate_rotation_matrix, validate_pose_matrix, normalize_quaternion, quaternion_to_matrix, matrix_to_quaternion (+9) | `c9b42fbaf146` |
| [backend/g1_teleop/unitree_image_transport.py](../backend/g1_teleop/unitree_image_transport.py) | 111 | 목록 확인 | shared_memory_name, UnitreeImageHeader, UnitreeSimImageWriter | `047f9078051c` |
| [backend/g1_teleop/watchdog.py](../backend/g1_teleop/watchdog.py) | 227 | 목록 확인 | PacketAcceptance, SequenceWatchdog, SessionSequenceWatchdog, WorkspaceFaultLatch, WorkspaceExitDebounce | `e72fcea42d14` |
| [backend/tests/test_batch_failure_guidance.py](../backend/tests/test_batch_failure_guidance.py) | 70 | 목록 확인 | BatchFailureGuidanceTest | `05e261289c21` |
| [backend/tests/test_capture_output_isolation.py](../backend/tests/test_capture_output_isolation.py) | 67 | 목록 확인 | test_same_second_names_are_unique, test_existing_outputs_never_overwritten | `26ddd4192a13` |
| [backend/tests/test_code_index.py](../backend/tests/test_code_index.py) | 42 | 목록 확인 | CodeIndexTests | `bfd86a963b9d` |
| [backend/tests/test_dds_firewall_rollback.py](../backend/tests/test_dds_firewall_rollback.py) | 128 | 목록 확인 | test_transaction, test_adapter_selection, run_mock | `dfd424d7ff67` |
| [backend/tests/test_diagnostic_exit_contract.py](../backend/tests/test_diagnostic_exit_contract.py) | 340 | 목록 확인 | test_camera_read_deadline_csharp_without_network, test_camera_cli_rejects_nonfinite_without_transport, test_network_final_state_is_verified, test_adapter_selection_is_unambiguous, test_network_capture_checks_native_failures (+4) | `e59e6f7055bd` |
| [backend/tests/test_ethernet_dns_transaction.py](../backend/tests/test_ethernet_dns_transaction.py) | 77 | 목록 확인 | test_dns_mode_recovery, test_snapshot_precedes_ip_changes | `6e24eb4209e8` |
| [backend/tests/test_ethernet_transaction.py](../backend/tests/test_ethernet_transaction.py) | 105 | 목록 확인 | test_ethernet_transaction | `9842519e4878` |
| [backend/tests/test_feasible_target_return.py](../backend/tests/test_feasible_target_return.py) | 79 | 목록 확인 | ReturnTests | `9613b3617f22` |
| [backend/tests/test_foundation.py](../backend/tests/test_foundation.py) | 380 | 목록 확인 | RigidPoseValidationTest, FoundationTest | `a2be064681ae` |
| [backend/tests/test_gate7_mujoco_feedback_receiver.py](../backend/tests/test_gate7_mujoco_feedback_receiver.py) | 120 | 목록 확인 | _payload, Gate7MujocoFeedbackReceiverTest | `80e7ce430b16` |
| [backend/tests/test_gate7_simulation_feedback.py](../backend/tests/test_gate7_simulation_feedback.py) | 89 | 목록 확인 | Gate7SimulationFeedbackTest | `fc81a75e405d` |
| [backend/tests/test_ik_visual_comparison.py](../backend/tests/test_ik_visual_comparison.py) | 112 | 목록 확인 | test_composite_goals_are_closed_multiaxis_pose_paths, test_invalid_standard_velocity_holds_pose_without_hiding_failure, test_playback_speed_preserves_fixed_steps_and_pause, test_comparison_keys_do_not_use_mujoco_shortcuts, test_comparison_reset_and_independent_joint_states | `8310646fbe68` |
| [backend/tests/test_inspection_contact.py](../backend/tests/test_inspection_contact.py) | 67 | 목록 확인 | InspectionContactStateMachineTest | `8029e94d123e` |
| [backend/tests/test_inspection_demo.py](../backend/tests/test_inspection_demo.py) | 74 | 목록 확인 | InspectionDemoTrackerTest | `bcbbbeecca0b` |
| [backend/tests/test_live_receiver.py](../backend/tests/test_live_receiver.py) | 243 | 목록 확인 | FakeSocket, legacy_packet, legacy_disengage_packet, legacy_tracking_disengage_packet, legacy_workspace_exit_packet (+2) | `b1f1f90f6d43` |
| [backend/tests/test_lowstate_firewall_scope.py](../backend/tests/test_lowstate_firewall_scope.py) | 112 | 목록 확인 | test_scope_without_admin_or_network | `8b0d1836d46e` |
| [backend/tests/test_mink_candidate_benchmark.py](../backend/tests/test_mink_candidate_benchmark.py) | 383 | 목록 확인 | BenchmarkTests, test_real_render_process_lifecycle | `f756206deec9` |
| [backend/tests/test_mink_collision_diagnostics.py](../backend/tests/test_mink_collision_diagnostics.py) | 205 | 목록 확인 | MinkCollisionDiagnosticsTest | `23ac337983c7` |
| [backend/tests/test_mink_collision_feasibility.py](../backend/tests/test_mink_collision_feasibility.py) | 129 | 목록 확인 | CollisionFeasibilityTests | `56c40659ba98` |
| [backend/tests/test_mink_command_stream.py](../backend/tests/test_mink_command_stream.py) | 272 | 목록 확인 | FakeSocket, packet, MinkCommandStreamTest | `1fc5b8f38131` |
| [backend/tests/test_mink_distance_invariance.py](../backend/tests/test_mink_distance_invariance.py) | 120 | 목록 확인 | DistanceInvarianceTests | `3dc5048606a4` |
| [backend/tests/test_mink_feasible_target.py](../backend/tests/test_mink_feasible_target.py) | 459 | 목록 확인 | FeasibleTargetTest | `4b022bbbf9c7` |
| [backend/tests/test_mink_reachability_limit.py](../backend/tests/test_mink_reachability_limit.py) | 33 | 목록 확인 | MinkReachabilityLimitTest | `d3feecf0bd93` |
| [backend/tests/test_mink_runtime_refactor_compatibility.py](../backend/tests/test_mink_runtime_refactor_compatibility.py) | 71 | 목록 확인 | MinkRuntimeRefactorCompatibilityTest | `b5030515059f` |
| [backend/tests/test_mink_stateful_trajectory.py](../backend/tests/test_mink_stateful_trajectory.py) | 82 | 목록 확인 | MinkStatefulTrajectoryTest | `c013b386564d` |
| [backend/tests/test_mink_step_acceptance_comparison.py](../backend/tests/test_mink_step_acceptance_comparison.py) | 503 | 목록 확인 | MinkStepAcceptanceComparisonTests | `1c0f38e0cdf5` |
| [backend/tests/test_mink_task_cost_contract.py](../backend/tests/test_mink_task_cost_contract.py) | 47 | 목록 확인 | ExampleTask, MinkTaskCostContractTest | `62ece4cc7488` |
| [backend/tests/test_mink_tracking_lag.py](../backend/tests/test_mink_tracking_lag.py) | 60 | 목록 확인 | TrackingLagTests | `934ed801dfdc` |
| [backend/tests/test_mink_virtual_center_trajectory.py](../backend/tests/test_mink_virtual_center_trajectory.py) | 212 | 목록 확인 | rotation_error_degrees, MinkVirtualCenterTrajectoryTest | `b237161d44d1` |
| [backend/tests/test_motion_reference.py](../backend/tests/test_motion_reference.py) | 52 | 목록 확인 | MotionReferenceTest | `1003f5d2d186` |
| [backend/tests/test_mujoco312_simulation_entry.py](../backend/tests/test_mujoco312_simulation_entry.py) | 97 | 목록 확인 | test_simulation_packet_cannot_enter_hardware, test_isolated_import_validation, test_hardware_profile_rejected_before_import, test_missing_engine_does_not_fall_back, test_preloaded_engine_rejected (+3) | `31e90c3662e5` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `87ba04dd2d7d` |
| [backend/tests/test_mujoco_inspection_scene_visibility.py](../backend/tests/test_mujoco_inspection_scene_visibility.py) | 75 | 목록 확인 | MujocoInspectionSceneVisibilityTest | `5d8672ed9a10` |
| [backend/tests/test_offline_model_isolation.py](../backend/tests/test_offline_model_isolation.py) | 594 | 목록 확인 | test_render_replay_xml_lifetime, test_render_replay_loads_isolated_model, test_live_entry_model_block_isolated, test_jog_provenance_uses_validator_model, shared_bytes (+18) | `883b5eecafb5` |
| [backend/tests/test_protocol_v2.py](../backend/tests/test_protocol_v2.py) | 196 | 목록 확인 | tracked, pose_v2, ProtocolV1IntegerTest, ProtocolV2Test | `4853abfbd76f` |
| [backend/tests/test_recorded_ik_hierarchy.py](../backend/tests/test_recorded_ik_hierarchy.py) | 174 | 목록 확인 | test_goal_rebase_preserves_delta_and_neutral, test_fixed_basis_and_clutch_preserve_rotation_step, test_operator_quaternion_sign_does_not_change_target, test_qp_summary_includes_small_rotation_errors, test_short_stationary_comparison (+8) | `c4fd8d4dd8f6` |
| [backend/tests/test_recorded_pose_speed_comparison.py](../backend/tests/test_recorded_pose_speed_comparison.py) | 61 | 목록 확인 | MakePacket, RecordedPoseSpeedComparisonTest | `f667723f00c9` |
| [backend/tests/test_recorded_reach_bound.py](../backend/tests/test_recorded_reach_bound.py) | 140 | 목록 확인 | RecordedReachBoundTest | `545d9f3fb9bc` |
| [backend/tests/test_rotation_trace_analysis.py](../backend/tests/test_rotation_trace_analysis.py) | 83 | 목록 확인 | MakeRow, test_sign_and_duplicate_packet_are_not_events, test_semantic_change_is_distinguished_from_source, test_new_session_does_not_compare_packet_rotation, test_packet_jump_and_cli_output (+2) | `01223e7fd256` |
| [backend/tests/test_runtime_architecture.py](../backend/tests/test_runtime_architecture.py) | 62 | 목록 확인 | command, RuntimeArchitectureTest | `e39e40892b1e` |
| [backend/tests/test_source_provenance.py](../backend/tests/test_source_provenance.py) | 123 | 목록 확인 | command, CommandSourceGuardTests | `a49810e1a73c` |
| [backend/tests/test_standard_mink_live.py](../backend/tests/test_standard_mink_live.py) | 171 | 목록 확인 | test_standard_qp_shared_limits_and_goal, test_launcher_selection_and_locked_profile, test_live_parser_preserves_default_and_selects_vanilla, test_local_launcher_default_without_starting_runtime, test_continuous_standard_motion | `ea61cbb0e11f` |
| [backend/tests/test_startup_ready_pose_editor.py](../backend/tests/test_startup_ready_pose_editor.py) | 75 | 목록 확인 | StartupReadyPoseEditorTest | `9ef3c18fabae` |
| [backend/tests/test_synthetic_ik_cases.py](../backend/tests/test_synthetic_ik_cases.py) | 194 | 목록 확인 | test_path_observer_preserves_decision_and_records_joint_rejection, test_single_qp_cost_changes_only_proximal_damping_and_restores, test_single_qp_cost_rejects_nonfinite_or_negative, test_out_of_range_start_is_rejected_before_output, test_wrist_axes_are_distinct_and_positions_stay_fixed (+9) | `456828d7ecfe` |
| [backend/tests/test_teleop_config.py](../backend/tests/test_teleop_config.py) | 154 | 목록 확인 | TeleopConfigTest | `54349f1dcbca` |
| [backend/tests/test_trajectory_ab.py](../backend/tests/test_trajectory_ab.py) | 57 | 목록 확인 | test_forward_then_wrist_keeps_requested_position_fixed, test_candidate_bounds_and_stop_without_changing_baseline, test_candidate_rejects_nonfinite | `bf7d34f8b1f0` |
| [backend/tests/test_unity_display_mode_launcher.py](../backend/tests/test_unity_display_mode_launcher.py) | 43 | 목록 확인 | UnityDisplayModeLauncherTests | `d14e1956fd6e` |
| [backend/tests/test_unity_workspace_policy.py](../backend/tests/test_unity_workspace_policy.py) | 252 | 목록 확인 | UnityWorkspacePolicyTest | `6c1c6feaeb62` |
| [backend/tests/test_virtual_center_kinematics_regression.py](../backend/tests/test_virtual_center_kinematics_regression.py) | 96 | 목록 확인 | VirtualCenterKinematicsRegressionTest | `3b6fd2ba628c` |
| [backend/tests/test_virtual_center_orientation_policy.py](../backend/tests/test_virtual_center_orientation_policy.py) | 136 | 목록 확인 | VirtualCenterOrientationPolicyTest | `81a125906c62` |
| [backend/tests/test_wrist_target_mapping_audit.py](../backend/tests/test_wrist_target_mapping_audit.py) | 50 | 목록 확인 | MappingAuditTests | `4c7b69cdb5a9` |
| [backend/tools/analyze_rotation_trace.py](../backend/tools/analyze_rotation_trace.py) | 95 | 목록 확인 | GetQuaternion, GetAngle, AnalyzeRows, main | `bee05da32cd2` |
| [backend/tools/audit_wrist_target_mapping.py](../backend/tools/audit_wrist_target_mapping.py) | 180 | 목록 확인 | OperatorToRobotDelta, GetNecessaryScale, ReadUnitySegments, GetVectors, AuditSender (+2) | `7a637d7a6e1f` |
| [backend/tools/benchmark_mink_candidate.py](../backend/tools/benchmark_mink_candidate.py) | 274 | 목록 확인 | CachedClearance, BoundedClearance, CachedCollisionLimit, BuildCandidate, SummarizeTiming (+3) | `d11bf9af2ed7` |
| [backend/tools/benchmark_mink_rendered_replay.py](../backend/tools/benchmark_mink_rendered_replay.py) | 316 | 목록 확인 | WaitForRelease, GetNextRelease, LoadReplay, ReplayRenderer, RunRenderedReplay (+3) | `3c3b8b1a6e77` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 121 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `bae8666a7a4d` |
| [backend/tools/compare_mink_step_acceptance.py](../backend/tools/compare_mink_step_acceptance.py) | 774 | 목록 확인 | GetLimitMetadata, WristPositionTask, FullOrientationErrorTask, IncrementCollisionLimit, ResolvedCollisionLimit (+12) | `297847c0c720` |
| [backend/tools/compare_mink_trajectory.py](../backend/tools/compare_mink_trajectory.py) | 130 | 목록 확인 | ForwardWristGoal, ThroughTrajectory, TrajectoryComparison | `1b7ae7b09310` |
| [backend/tools/compare_recorded_ik_hierarchy.py](../backend/tools/compare_recorded_ik_hierarchy.py) | 289 | 목록 확인 | UseOfflineProximalCost, GetNormalizedGoal, RunDiagnosedPlan, SummarizeQP, SummarizeTargetEvents (+3) | `ebad66c86e77` |
| [backend/tools/compare_recorded_pose_speeds.py](../backend/tools/compare_recorded_pose_speeds.py) | 116 | 목록 확인 | GetActiveSegments, GetRecordedTargets, GetTargetIndex, main | `20e5bb9f6880` |
| [backend/tools/compare_synthetic_ik.py](../backend/tools/compare_synthetic_ik.py) | 298 | 목록 확인 | ObservePathChecks, UseSingleQPCost, UseMeritAblation, ProgressBand, TargetErrorBand (+3) | `c1074d7940d7` |
| [backend/tools/diagnose_mink_collision_feasibility.py](../backend/tools/diagnose_mink_collision_feasibility.py) | 282 | 목록 확인 | EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, main | `4971628c3917` |
| [backend/tools/diagnose_mink_distance_invariance.py](../backend/tools/diagnose_mink_distance_invariance.py) | 214 | 목록 확인 | GetSupportGap, GetWorldVertices, GetEnclosingVertices, GetSeparationCertificate, InspectTrace (+3) | `85ed5aa1eb7b` |
| [backend/tools/diagnose_mink_tracking_lag.py](../backend/tools/diagnose_mink_tracking_lag.py) | 189 | 목록 확인 | GetSchedule, GetSustainedSettleTime, GetReachSummary, Step, GetSample (+4) | `cb0331fae08e` |
| [backend/tools/diagnose_recorded_reach.py](../backend/tools/diagnose_recorded_reach.py) | 123 | 목록 확인 | GetReachUpperBound, SaveInputFailure, main, RunDiagnosis | `6176af6d366d` |
| [backend/tools/inspect_feasible_target_return.py](../backend/tools/inspect_feasible_target_return.py) | 194 | 목록 확인 | InterpolateGoal, SummarizePreview, GetVerdict, Run, main (+1) | `75f6671e6d8f` |
| [backend/tools/offline_render_worker.py](../backend/tools/offline_render_worker.py) | 193 | 목록 확인 | LatestStateSlot, RunRenderWorker, ProcessRenderer | `02d2d4eca5b8` |
| [backend/tools/reconcile_review_ledger.py](../backend/tools/reconcile_review_ledger.py) | 176 | 목록 확인 | _read_csv, _semantic_map, _static_check, build_rows, _csv_text (+1) | `91ee37c20ba9` |
| [backend/tools/verify_camera_simulation.py](../backend/tools/verify_camera_simulation.py) | 271 | 목록 확인 | parse_args, quaternion_rotation_matrix, official_optical_axes, verify_transport, main | `fb906d515a54` |
| [backend/tools/verify_feasible_target.py](../backend/tools/verify_feasible_target.py) | 137 | 목록 확인 | BuildPlanner, RunSequence, main | `c8949581faef` |
| [backend/tools/verify_unity_state_packets.ps1](../backend/tools/verify_unity_state_packets.ps1) | 149 | 목록 확인 | - | `b447591f7026` |
| [backend/tools/verify_virtual_center_kinematics.py](../backend/tools/verify_virtual_center_kinematics.py) | 269 | 목록 확인 | LegacyOrientationTask, ExactOrientationTask, CheckJacobian, GetStepCount, RunCase (+1) | `2a90bb815370` |
| [backend/tools/view_ik_comparison.py](../backend/tools/view_ik_comparison.py) | 358 | 목록 확인 | NextPlaybackSpeed, GetCompositeGoal, HandleComparisonKey, RecordedPlayback, Comparison (+2) | `da895fd24a9f` |
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
| [experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat) | 30 | 목록 확인 | - | `1988bf538801` |
| [experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat) | 37 | 목록 확인 | - | `99106c99747b` |
| [experiments/startup_recovery_posture_sweep/run_sweep.py](../experiments/startup_recovery_posture_sweep/run_sweep.py) | 653 | 목록 확인 | SweepCase, ParseOffsets, ParseArguments, LoadPose, BuildProvenance (+12) | `98cf3f8363a5` |
| [experiments/startup_recovery_posture_sweep/single_pose_runner.py](../experiments/startup_recovery_posture_sweep/single_pose_runner.py) | 62 | 목록 확인 | ParseArguments, UseIsolatedModel, Main | `a297bc767c17` |
| [experiments/startup_recovery_posture_sweep/test_sweep.py](../experiments/startup_recovery_posture_sweep/test_sweep.py) | 191 | 목록 확인 | StartupRecoveryPostureSweepTests | `39510cd9add0` |
| [experiments/twist2_right_arm_manual/TEST_OFFLINE.bat](../experiments/twist2_right_arm_manual/TEST_OFFLINE.bat) | 18 | 목록 확인 | - | `53a20610cefb` |
| [experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat](../experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat) | 34 | 목록 확인 | - | `a4e2c141ef04` |
| [experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py) | 219 | 목록 확인 | PhysicalSample, _FiniteValue, LoadPhysicalCsv, BuildSummary, ParseArguments (+1) | `2d72f4abd74e` |
| [experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py) | 81 | 목록 확인 | ReplayPhysicalCsvMuJoCoTests | `0de94441a4a5` |
| [experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp](../experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp) | 1205 | 목록 확인 | - | `e61d8a3cf830` |
| [experiments/twist2_right_arm_manual/verify_offline.py](../experiments/twist2_right_arm_manual/verify_offline.py) | 213 | 목록 확인 | CheckCondition, GetFunction, GetDeclaration, GetLinuxPath, RunLocal (+4) | `f23e6091c4ee` |
| [hardware/g1_arm_bridge/arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/arm_sdk_hold_contract.py) | 364 | 목록 확인 | ArmSdkHoldConfig, HoldValidation, ArmSdkCommandFrame, _finite_vector, _uint8 (+6) | `7096d037e98e` |
| [hardware/g1_arm_bridge/arm_sdk_release_contract.py](../hardware/g1_arm_bridge/arm_sdk_release_contract.py) | 138 | 목록 확인 | ReleaseEvidence, _validate_release_arguments, execute_release_sequence | `64072ef0df8b` |
| [hardware/g1_arm_bridge/arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/arm_sdk_teleop_contract.py) | 873 | 목록 확인 | Gate7ContractError, RegularArmPose, Gate7Config, MinkArmSample, TrajectorySample (+11) | `1e99e86a004f` |
| [hardware/g1_arm_bridge/check_startup_readiness.py](../hardware/g1_arm_bridge/check_startup_readiness.py) | 601 | 목록 확인 | PrecheckConfig, TimedPacket, Blocker, _positive_float, load_config (+12) | `58acd357a834` |
| [hardware/g1_arm_bridge/check_startup_readiness_entry.py](../hardware/g1_arm_bridge/check_startup_readiness_entry.py) | 176 | 목록 확인 | _pop_option, _option_path, validate_forward_token, _finite_vector, _validated_raw_odom (+3) | `77da5a14e8db` |
| [hardware/g1_arm_bridge/diagnose_initial_pose_collision.py](../hardware/g1_arm_bridge/diagnose_initial_pose_collision.py) | 304 | 목록 확인 | _joint_pose, _has_exact_geom_contact, _probe_zero_mesh_distance, _robust_geom_distance, _nearby_pairs (+1) | `311f7734032c` |
| [hardware/g1_arm_bridge/edit_startup_ready_pose.py](../hardware/g1_arm_bridge/edit_startup_ready_pose.py) | 462 | 목록 확인 | PoseAssessment, EditorState, ParseArguments, LoadPose, SafeLimitsDegrees (+11) | `3fe368c521b9` |
| [hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py) | 29 | 목록 확인 | ExperimentalStatefulGate7TeleopController | `a93f2c85b9b1` |
| [hardware/g1_arm_bridge/g1_base_state.py](../hardware/g1_arm_bridge/g1_base_state.py) | 212 | 목록 확인 | InvalidBaseStateError, NormalizedBaseState, _FiniteVector, NormalizeQuaternionWXYZ, MultiplyQuaternionWXYZ (+4) | `11c6f8e1e985` |
| [hardware/g1_arm_bridge/g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/g1_camera_replay_tcp.py) | 321 | 목록 확인 | LoadFont, BuildReplayJpeg, ParseArguments, ValidateArguments, WriteResult (+1) | `70aec2811f81` |
| [hardware/g1_arm_bridge/g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/g1_camera_tcp_bridge.py) | 211 | 목록 확인 | BuildFramePacket, ParseArguments, CreateVideoClient, ConnectUnity, ValidateArguments (+1) | `f541d4174678` |
| [hardware/g1_arm_bridge/g1_joint_contract.py](../hardware/g1_arm_bridge/g1_joint_contract.py) | 39 | 목록 확인 | - | `bb33790cb1af` |
| [hardware/g1_arm_bridge/g1_right_arm_jog.py](../hardware/g1_arm_bridge/g1_right_arm_jog.py) | 1284 | 목록 확인 | RuntimeConfig, KeyboardReader, _number, load_config, validate_config (+18) | `e323255f4810` |
| [hardware/g1_arm_bridge/g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/g1_right_arm_jog_entry.py) | 234 | 목록 확인 | _argument_path, _config_path, apply_release_result_guard, install_jog_safety_guards, main | `fac8801820e7` |
| [hardware/g1_arm_bridge/g1_unity_state_bridge.py](../hardware/g1_arm_bridge/g1_unity_state_bridge.py) | 224 | 목록 확인 | _FiniteVector, _QuaternionAngleDegrees, _RequireFullBody, BuildUnityHardwareStatePacket, EncodeUnityHardwareStatePacket (+1) | `4d820db4d806` |
| [hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py) | 803 | 목록 확인 | LowStatePacketError, BaseStateTelemetry, LowStateTelemetry, PacketOrderTracker, _finite_joint_vector (+16) | `1081cdcd9e21` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold.py) | 870 | 목록 확인 | RuntimeConfig, LowStateSnapshot, LowStateBuffer, _finite_number, load_runtime_config (+12) | `c364ba2eefd4` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py) | 72 | 목록 확인 | install_supported_gate6_guards, main | `2a8dcda852e6` |
| [hardware/g1_arm_bridge/gate7_acquisition_guard.py](../hardware/g1_arm_bridge/gate7_acquisition_guard.py) | 126 | 목록 확인 | ActiveAcquisitionGuard, validate_full_body_snapshot_matches_precheck, validate_acquisition_hold_target | `d7dcaf61ae8a` |
| [hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py](../hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py) | 268 | 목록 확인 | SleepUntilStep, SelectReplayWindow, _replace_dual, CheckReplayModelIdentity, BuildExperimentalLimitedFrames (+2) | `c435dbe3019a` |
| [hardware/g1_arm_bridge/gate7_capture_quality.py](../hardware/g1_arm_bridge/gate7_capture_quality.py) | 876 | 목록 확인 | _percentile, _round, _replace_dual, _decode_capture, _series_metrics (+9) | `a11c586372eb` |
| [hardware/g1_arm_bridge/gate7_capture_regression.py](../hardware/g1_arm_bridge/gate7_capture_regression.py) | 217 | 목록 확인 | _replace_dual, _file_sha256, BuildRegressionTrace, CompareTrace, _automatic_result_path (+2) | `6ea4853ec628` |
| [hardware/g1_arm_bridge/gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/gate7_fault_injection_matrix.py) | 317 | 목록 확인 | _replace_dual, _synthetic_active_value, _load_active_value, _payload, _new_controller (+5) | `46f4cef501a3` |
| [hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py) | 372 | 목록 확인 | _replace_dual, _packet, _automatic_result_path, _parse_args, main | `ea6fd0e7b5ae` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk.py) | 869 | 입출력 확인 | LiveHardwareConfig, _finite, LoadLiveHardwareConfig, ValidateLiveHardwareConfig, ValidateRuckigRuntime (+12) | `ea971a23d1ba` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py) | 268 | 목록 확인 | _argument_path, _pop_argument, install_supported_path_guards, main | `30914406d1e9` |
| [hardware/g1_arm_bridge/gate7_live_dry_run.py](../hardware/g1_arm_bridge/gate7_live_dry_run.py) | 743 | 목록 확인 | DryRunTick, _finite_all_joints, _replace_dual_arm, _automatic_path, _resolve_output_path (+6) | `c23e7372b0d1` |
| [hardware/g1_arm_bridge/gate7_live_safety_guard.py](../hardware/g1_arm_bridge/gate7_live_safety_guard.py) | 120 | 목록 확인 | ArmSegmentPoint, LinearDualArmSegment, require_active_collision_evidence, _finite_all_joints, build_final_command_segment (+1) | `c89e7f456590` |
| [hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py](../hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py) | 515 | 목록 확인 | _set_full_body_pose, CollisionPathValidator, _replace_dual_arm, _mink_packet, _target_right_arm (+3) | `ef06e7998652` |
| [hardware/g1_arm_bridge/gate7_mink_capture.py](../hardware/g1_arm_bridge/gate7_mink_capture.py) | 149 | 목록 확인 | _automatic_path, _write_line, _parse_args, main | `9afa91a55ee0` |
| [hardware/g1_arm_bridge/gate7_mink_replay.py](../hardware/g1_arm_bridge/gate7_mink_replay.py) | 152 | 목록 확인 | CapturedPacket, LoadCapture, NormalizePayload, CaptureSha256, validate_replay_destination (+2) | `60e2e3c2814f` |
| [hardware/g1_arm_bridge/gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/gate7_mink_wsl_relay.py) | 216 | 입출력 확인 | MinkOrderGuard, ValidateRelayEndpoint, ValidateAndForward, _automatic_result_path, _parse_args (+1) | `88ca395aaf34` |
| [hardware/g1_arm_bridge/gate7_relay_provenance_guard.py](../hardware/g1_arm_bridge/gate7_relay_provenance_guard.py) | 170 | 목록 확인 | validate_relay_token, _payload_object, require_relay_token, command_provenance, require_live_candidate_for_relay (+3) | `d05ece716376` |
| [hardware/g1_arm_bridge/generate_fake_mink_targets.py](../hardware/g1_arm_bridge/generate_fake_mink_targets.py) | 117 | 목록 확인 | parse_args, main | `eeb5c6e0e331` |
| [hardware/g1_arm_bridge/hardware_state.py](../hardware/g1_arm_bridge/hardware_state.py) | 91 | 목록 확인 | HardwarePhase, FaultCode, build_status, write_status | `81f126c94061` |
| [hardware/g1_arm_bridge/live_lowstate_mujoco.py](../hardware/g1_arm_bridge/live_lowstate_mujoco.py) | 652 | 목록 확인 | StreamState, BaseBodyPose, ParseArguments, ResolveMeasurementLogPath, BuildMirrorMeasurement (+14) | `58c291775bbc` |
| [hardware/g1_arm_bridge/lowstate_health_guard.py](../hardware/g1_arm_bridge/lowstate_health_guard.py) | 119 | 목록 확인 | _value, _temperature_max_c, validate_lowstate_health_message, install_lowstate_health_tracking, require_latest_lowstate_health | `c8715c8899a3` |
| [hardware/g1_arm_bridge/mink_target_dry_run.py](../hardware/g1_arm_bridge/mink_target_dry_run.py) | 127 | 목록 확인 | _fmt_deg, main | `372002c8b23c` |
| [hardware/g1_arm_bridge/plan_startup_transition.py](../hardware/g1_arm_bridge/plan_startup_transition.py) | 686 | 목록 확인 | _inside_pairs, _waypoints_for_order, _dense_segment, _evaluate_order, _joint_limits (+6) | `5f5cfd2b7f31` |
| [hardware/g1_arm_bridge/precheck_provenance_guard.py](../hardware/g1_arm_bridge/precheck_provenance_guard.py) | 39 | 목록 확인 | require_provenance_bound_precheck | `aa8fbdd33530` |
| [hardware/g1_arm_bridge/probe_joint_motion.py](../hardware/g1_arm_bridge/probe_joint_motion.py) | 177 | 목록 확인 | parse_args, current_positions, collect_positions, summarize, main | `6b43271de626` |
| [hardware/g1_arm_bridge/query_motion_mode.py](../hardware/g1_arm_bridge/query_motion_mode.py) | 110 | 목록 확인 | _write_json, parse_args, main | `d86bc3ea68ba` |
| [hardware/g1_arm_bridge/query_motion_mode_wsl.sh](../hardware/g1_arm_bridge/query_motion_mode_wsl.sh) | 24 | 목록 확인 | - | `19cdf2097714` |
| [hardware/g1_arm_bridge/read_only_lowstate.py](../hardware/g1_arm_bridge/read_only_lowstate.py) | 563 | 목록 확인 | JointSample, ReadOnlyG1LowState, ReadOnlyG1BaseState, _motor_value, _state_uint8 (+9) | `bfaef913f786` |
| [hardware/g1_arm_bridge/read_only_lowstate_entry.py](../hardware/g1_arm_bridge/read_only_lowstate_entry.py) | 154 | 목록 확인 | _pop_option, _finite_vector, install_raw_odom_binding, install_forward_token, main | `a38ce663d019` |
| [hardware/g1_arm_bridge/receive_initial_state.py](../hardware/g1_arm_bridge/receive_initial_state.py) | 199 | 목록 확인 | parse_args, _raw_object, _validate_provenance, _validate_full_body_consistency, main | `4285ba83ada2` |
| [hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py) | 354 | 목록 확인 | SavedLowState, _FiniteVector, _JointNames, _OptionalMode, LoadSnapshot (+5) | `a869fd552b3d` |
| [hardware/g1_arm_bridge/replay_startup_recovery.py](../hardware/g1_arm_bridge/replay_startup_recovery.py) | 186 | 목록 확인 | ParseArguments, LoadViewerSettings, LoadRecovery, InterpolatePose, ApplyRightArmPose (+1) | `a1e8b1cdf652` |
| [hardware/g1_arm_bridge/right_arm_jog_contract.py](../hardware/g1_arm_bridge/right_arm_jog_contract.py) | 194 | 목록 확인 | ArmJointJogLimits, ArmJointJogTick, validate_jog_limits, ArmJointJogController | `83f51c0a80df` |
| [hardware/g1_arm_bridge/right_arm_jog_safety_guard.py](../hardware/g1_arm_bridge/right_arm_jog_safety_guard.py) | 92 | 목록 확인 | file_sha256, build_jog_permit_provenance, validate_jog_permit_provenance, validate_jog_runtime_full_body, validate_jog_final_segment | `0be6e55cfd49` |
| [hardware/g1_arm_bridge/ruckig_gate7_controller.py](../hardware/g1_arm_bridge/ruckig_gate7_controller.py) | 121 | 목록 확인 | RuckigGate7TeleopController | `dcc46f5329c7` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 95 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `cb2102cd76c2` |
| [hardware/g1_arm_bridge/runtime_base_state_guard.py](../hardware/g1_arm_bridge/runtime_base_state_guard.py) | 316 | 목록 확인 | RuntimeBaseSnapshot, RuntimeBaseStateMonitor, _relative_yaw_rad, _finite_vector, _quaternion_angle_delta_rad (+5) | `9f1816007448` |
| [hardware/g1_arm_bridge/safety_gate.py](../hardware/g1_arm_bridge/safety_gate.py) | 149 | 목록 확인 | SafetyConfig, SafetyDecision, _vector, _within_joint_limits, evaluate_target | `20d483a19afa` |
| [hardware/g1_arm_bridge/simulate_startup_recovery.py](../hardware/g1_arm_bridge/simulate_startup_recovery.py) | 1181 | 목록 확인 | _load_startup_safe_ready_degrees, _right_qpos_ids, _minimum_clearance, _minimum_clearance_extended, _recovery_edge_is_valid (+10) | `95e0d81f039a` |
| [hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh](../hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh) | 26 | 목록 확인 | - | `fa0ef501c148` |
| [hardware/g1_arm_bridge/start_gate6_hold_wsl.sh](../hardware/g1_arm_bridge/start_gate6_hold_wsl.sh) | 24 | 목록 확인 | - | `02803d8b764f` |
| [hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh](../hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh) | 29 | 목록 확인 | - | `1040c430ca14` |
| [hardware/g1_arm_bridge/start_read_only_wsl.sh](../hardware/g1_arm_bridge/start_read_only_wsl.sh) | 22 | 목록 확인 | - | `09de003deb87` |
| [hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh](../hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh) | 24 | 목록 확인 | - | `bf6fc5424ee2` |
| [hardware/g1_arm_bridge/startup_state_binding_guard.py](../hardware/g1_arm_bridge/startup_state_binding_guard.py) | 143 | 목록 확인 | file_sha256, build_state_binding, base_state_to_dict, _require_finite_vector, require_state_binding | `386687ebca94` |
| [hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py) | 138 | 목록 확인 | _safe_all_q, ArmSdkHoldContractTests | `595ee6731836` |
| [hardware/g1_arm_bridge/test_arm_sdk_release_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_release_contract.py) | 192 | 목록 확인 | FakeClock, ReleaseContractTests | `38d715bdad76` |
| [hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py) | 438 | 목록 확인 | _replace_dual, _sample, ArmSdkTeleopContractTests | `91ef91bbeb57` |
| [hardware/g1_arm_bridge/test_check_startup_readiness.py](../hardware/g1_arm_bridge/test_check_startup_readiness.py) | 196 | 목록 확인 | _config, _timed_packet, _mode_query, StartupReadinessTests | `37e1032193bc` |
| [hardware/g1_arm_bridge/test_check_startup_readiness_entry.py](../hardware/g1_arm_bridge/test_check_startup_readiness_entry.py) | 111 | 목록 확인 | _raw_base_state, StartupPrecheckEntryTests | `6a1c5cdb14eb` |
| [hardware/g1_arm_bridge/test_collision_diagnostics.py](../hardware/g1_arm_bridge/test_collision_diagnostics.py) | 60 | 목록 확인 | _FakeG1, _FakeController, CollisionDiagnosticTests | `b2642345a203` |
| [hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py) | 43 | 목록 확인 | ExperimentalStatefulGate7ControllerTests | `cc444df0124f` |
| [hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py](../hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py) | 82 | 목록 확인 | main | `fa397980398b` |
| [hardware/g1_arm_bridge/test_g1_base_state.py](../hardware/g1_arm_bridge/test_g1_base_state.py) | 118 | 목록 확인 | YawQuaternionWXYZ, G1BaseStateTests | `11a58e53ca27` |
| [hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py) | 93 | 목록 확인 | G1CameraReplayTcpTest | `3ee3f9b6b459` |
| [hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py) | 44 | 목록 확인 | G1CameraTcpBridgeTest | `e1047b89e99b` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog.py) | 359 | 목록 확인 | G1RightArmJogTests | `35f1d18285ca` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py) | 50 | 목록 확인 | DirectJogReleaseIntegrationTests | `1b11145d8b85` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py) | 107 | 목록 확인 | RightArmJogReleaseGuardTests | `808ab9f76a81` |
| [hardware/g1_arm_bridge/test_g1_unity_state_bridge.py](../hardware/g1_arm_bridge/test_g1_unity_state_bridge.py) | 175 | 목록 확인 | LowStatePacket, G1UnityStateBridgeTests | `0c91cc2833b5` |
| [hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py) | 218 | 목록 확인 | _packet, _base_state, _unused_local_port, Gate5LowStateSafetyTests | `5ab06a9f3908` |
| [hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py) | 163 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, Gate6ArmSdkHoldTests | `eb7980a6479b` |
| [hardware/g1_arm_bridge/test_gate6_fault_release.py](../hardware/g1_arm_bridge/test_gate6_fault_release.py) | 154 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, _FakeCRC, _FakeBuffer, _FakePublisher (+2) | `697a9ab1c6a9` |
| [hardware/g1_arm_bridge/test_gate6_interrupt_release.py](../hardware/g1_arm_bridge/test_gate6_interrupt_release.py) | 130 | 목록 확인 | validate_interrupt_release_contract, Gate6InterruptReleaseTests, main | `fad40aefbdfa` |
| [hardware/g1_arm_bridge/test_gate7_acquisition_guard.py](../hardware/g1_arm_bridge/test_gate7_acquisition_guard.py) | 95 | 목록 확인 | sample, Gate7AcquisitionGuardTests | `646fe47e3b73` |
| [hardware/g1_arm_bridge/test_gate7_capture_quality.py](../hardware/g1_arm_bridge/test_gate7_capture_quality.py) | 155 | 목록 확인 | Gate7CaptureQualityTests | `a9cff3814d24` |
| [hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py) | 32 | 목록 확인 | Gate7FaultInjectionMatrixTests | `63b8b799b54f` |
| [hardware/g1_arm_bridge/test_gate7_first_live_profile.py](../hardware/g1_arm_bridge/test_gate7_first_live_profile.py) | 112 | 목록 확인 | Gate7FirstLiveProfileTests | `c563edb0cf19` |
| [hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py) | 66 | 목록 확인 | _free_udp_port, Gate7HardwareVirtualE2ETests | `f905f33e9bfa` |
| [hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py) | 208 | 목록 확인 | Gate7LiveArmSdkTests | `10032d407ebf` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run.py) | 361 | 목록 확인 | _replace_dual, _sample, Gate7LiveDryRunTests | `7a777136e907` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py) | 136 | 목록 확인 | _free_udp_port, Gate7LiveDryRunE2ETests | `0eeb63044d28` |
| [hardware/g1_arm_bridge/test_gate7_live_entrypoint.py](../hardware/g1_arm_bridge/test_gate7_live_entrypoint.py) | 108 | 목록 확인 | Gate7LiveEntrypointTests | `0fa603aec2a0` |
| [hardware/g1_arm_bridge/test_gate7_live_safety_guard.py](../hardware/g1_arm_bridge/test_gate7_live_safety_guard.py) | 89 | 목록 확인 | Gate7LiveSafetyGuardTests | `398bb4186f52` |
| [hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py](../hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py) | 119 | 목록 확인 | _free_udp_port, Gate7MinkCaptureReplayTests | `a67b307d7562` |
| [hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py) | 207 | 목록 확인 | _packet, Gate7MinkWslRelayTests | `a8b9772f4e80` |
| [hardware/g1_arm_bridge/test_gate7_release_finalization.py](../hardware/g1_arm_bridge/test_gate7_release_finalization.py) | 175 | 목록 확인 | Gate7ReleaseFinalizationTests | `2af3045bbab1` |
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
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py) | 262 | 목록 확인 | load_precheck, measured_pose, build_offset_trajectory, build_endpoint_trajectories, validate_offset_path (+5) | `deb2e297af64` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py) | 43 | 목록 확인 | _argument_path, main | `a0b6625d2eb7` |
| [hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py](../hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py) | 64 | 목록 확인 | main | `172f652bdf8b` |
| [hardware/g1_arm_bridge/verify_initial_pose_sync.py](../hardware/g1_arm_bridge/verify_initial_pose_sync.py) | 130 | 목록 확인 | _load_captured_pose, main | `f59a74c6c84d` |
| [tools/ALLOW_G1_DDS_WSL.bat](../tools/ALLOW_G1_DDS_WSL.bat) | 12 | 목록 확인 | - | `bc3b8d2daaee` |
| [tools/ALLOW_G1_DDS_WSL_ADMIN.ps1](../tools/ALLOW_G1_DDS_WSL_ADMIN.ps1) | 137 | 목록 확인 | - | `02a905d48817` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat) | 14 | 목록 확인 | - | `c837ff7d3891` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1) | 112 | 목록 확인 | - | `1fdde38692c4` |
| [tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat](../tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat) | 32 | 목록 확인 | - | `bd53ccf085f5` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 105 | 목록 확인 | - | `96a7e70577b4` |
| [tools/CHECK_G1_TELEOP_STARTUP.bat](../tools/CHECK_G1_TELEOP_STARTUP.bat) | 66 | 목록 확인 | - | `bbaa4c38b10e` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 11 | 목록 확인 | - | `308b1b54bec6` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `51b044fcd99b` |
| [tools/DETECT_G1_NETWORK.bat](../tools/DETECT_G1_NETWORK.bat) | 11 | 목록 확인 | - | `be9f63666f9c` |
| [tools/DETECT_G1_NETWORK_ADMIN.ps1](../tools/DETECT_G1_NETWORK_ADMIN.ps1) | 48 | 목록 확인 | - | `f62902448f5b` |
| [tools/EDIT_G1_STARTUP_READY_POSE.bat](../tools/EDIT_G1_STARTUP_READY_POSE.bat) | 33 | 목록 확인 | - | `64872de03943` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `43a32b2e3524` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 126 | 목록 확인 | - | `acf79f4cc8e0` |
| [tools/PREPARE_G1_GATE6_HOLD.bat](../tools/PREPARE_G1_GATE6_HOLD.bat) | 39 | 목록 확인 | - | `3153383c91bf` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 11 | 목록 확인 | - | `698638321bb5` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 23 | 목록 확인 | - | `682a37b9d06a` |
| [tools/SET_UNITY_DISPLAY_MODE.ps1](../tools/SET_UNITY_DISPLAY_MODE.ps1) | 25 | 입출력 확인 | - | `d9f1eb1f0fca` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 26 | 목록 확인 | - | `980967bbd243` |
| [tools/START_G1_GATE5_READ_ONLY.bat](../tools/START_G1_GATE5_READ_ONLY.bat) | 37 | 목록 확인 | - | `5315ab2202d3` |
| [tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat](../tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat) | 112 | 목록 확인 | - | `8ec7aff5f329` |
| [tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat](../tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat) | 25 | 목록 확인 | - | `d3c82d1693ca` |
| [tools/START_G1_GATE7_LIVE_DRY_RUN.bat](../tools/START_G1_GATE7_LIVE_DRY_RUN.bat) | 57 | 목록 확인 | - | `cd05305f462e` |
| [tools/START_G1_GATE7_LIVE_HARDWARE.bat](../tools/START_G1_GATE7_LIVE_HARDWARE.bat) | 224 | 목록 확인 | - | `8f98e4f51201` |
| [tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat](../tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat) | 92 | 목록 확인 | - | `264801696a18` |
| [tools/START_G1_GATE7_STANDARD_MINK.bat](../tools/START_G1_GATE7_STANDARD_MINK.bat) | 6 | 목록 확인 | - | `e0ceb7b2a4a8` |
| [tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat](../tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat) | 25 | 목록 확인 | - | `20b8d69ecc4c` |
| [tools/START_G1_GATE7_VR_RECORDING.bat](../tools/START_G1_GATE7_VR_RECORDING.bat) | 59 | 목록 확인 | - | `fc20a76e7cc9` |
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
| [tools/VIEW_G1_LIVE_MUJOCO.bat](../tools/VIEW_G1_LIVE_MUJOCO.bat) | 45 | 목록 확인 | - | `fc967d5600cf` |
| [tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat](../tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat) | 35 | 목록 확인 | - | `2169a22c9d3f` |
| [tools/VIEW_G1_STARTUP_RECOVERY.bat](../tools/VIEW_G1_STARTUP_RECOVERY.bat) | 28 | 목록 확인 | - | `401c61f102ba` |
