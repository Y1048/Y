# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **921개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

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
| [MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py](../MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py) | 81 | 목록 확인 | mujoco_to_unity_delta, main | `6421c8c003d6` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py) | 8 | 목록 확인 | - | `d2d8d9b6e9b4` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py) | 305 | 목록 확인 | ElbowClearanceTask, ShoulderComfortTask, ArmMotionPolicy | `739c1650ea89` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_return.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_return.py) | 288 | 목록 확인 | BimanualReturnMotion | `b2887be3bdc1` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py) | 130 | 목록 확인 | startup_stage, require_validated_engine, load_engine, runtime_metadata, main | `c92c5cdafe0f` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py) | 586 | 목록 확인 | _recorded_motion_limits, _current_motion_limits, _open_text, _percentiles, _current_source_hashes (+7) | `100d56344e2d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py) | 408 | 목록 확인 | BimanualSimulation, targets_from_json, main | `ca697a3f785e` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py) | 317 | 목록 확인 | make_packet, free_loopback_port, send_packet, valid_feedback, wait_feedback (+6) | `52640e4eee8d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py) | 447 | 목록 확인 | decode, PairedHandFilter, UnityCycle, main | `cd2dc3acf307` |
| [MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py](../MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py) | 77 | 목록 확인 | drain_gate7_simulation_feedback, apply_gate7_simulation_feedback | `a3b14b20de41` |
| [MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py](../MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py) | 83 | 목록 확인 | ReadSeedBytes, ReadSeed, ApplySeed | `dfaea6161c12` |
| [MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py](../MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py) | 27 | 목록 확인 | ResolveCollisionProfile | `690f7acc0dbd` |
| [MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py) | 45 | 목록 확인 | mark_simulation_cycle_packet, mark_live_mink_packet, wrap_state_packet_factory | `591c952b1ea1` |
| [MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py](../MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py) | 10 | 목록 확인 | orientation_diagnostics | `a3b8dbe9cd27` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 입출력 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `2bcce6eb3f89` |
| [MuJoCo_G1_Controller/scripts/g1_mink_live_cycle_bridge.py](../MuJoCo_G1_Controller/scripts/g1_mink_live_cycle_bridge.py) | 86 | 목록 확인 | live_tracking_active, LiveCycleBridge | `6a9395bd62f1` |
| [MuJoCo_G1_Controller/scripts/g1_mink_return_cycle.py](../MuJoCo_G1_Controller/scripts/g1_mink_return_cycle.py) | 83 | 목록 확인 | SimulationReturnCycle | `c8dcb0973e03` |
| [MuJoCo_G1_Controller/scripts/g1_mink_speed_profiles.py](../MuJoCo_G1_Controller/scripts/g1_mink_speed_profiles.py) | 26 | 목록 확인 | speed_profile, live_joint_bounds | `4d2f76563add` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 124 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `fbd4713dff2b` |
| [MuJoCo_G1_Controller/scripts/g1_right_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_right_arm_common.py) | 425 | 목록 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `8a96d733fdee` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `7d6cb78dbfb2` |
| [MuJoCo_G1_Controller/scripts/g1_tracking_diagnostic.py](../MuJoCo_G1_Controller/scripts/g1_tracking_diagnostic.py) | 47 | 목록 확인 | TrackingDiagnostic | `3bcee8b9cc2f` |
| [MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py](../MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py) | 502 | 목록 확인 | AccelerationBound, ElbowClearanceTask, ShoulderComfortTask, UpstreamMinkTracking | `fe0ab3273bb6` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 269 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `b5c7b2535548` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py) | 930 | 목록 확인 | parse_args, _update_reachability_limit, _find_body, _prepare_mink_xml, LoadMinkModel (+26) | `e69ec48950c6` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py) | 20 | 목록 확인 | main | `aebdd2dc962a` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py) | 1167 | 입출력 확인 | cycle_velocity_limits, parse_args, _write_right_arm_csv_row, main | `b08009b5d411` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py) | 41 | 목록 확인 | main | `c7a590174cf0` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py) | 80 | 목록 확인 | LoadEngine, MarkSimulation, main | `4d4c659b6f17` |
| [MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py) | 101 | 목록 확인 | MinkCommandProvenanceTests | `7d25329d76b6` |
| [MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py](../MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py) | 99 | 목록 확인 | require, require_pattern, forbid, main | `30cc0d077b66` |
| [START_MUJOCO_ONLY.bat](../START_MUJOCO_ONLY.bat) | 55 | 목록 확인 | - | `006b807a3319` |
| [START_VR_HAND_TO_MUJOCO.bat](../START_VR_HAND_TO_MUJOCO.bat) | 327 | 입출력 확인 | - | `b2256ac6ad6d` |
| [START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat](../START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat) | 33 | 목록 확인 | - | `7bfda72adff1` |
| [START_VR_STANDARD_MINK.bat](../START_VR_STANDARD_MINK.bat) | 5 | 목록 확인 | - | `1d903fba29c2` |
| [Unity_G1_VR/Assets/Editor/G1BimanualSimulationSetup.cs](../Unity_G1_VR/Assets/Editor/G1BimanualSimulationSetup.cs) | 59 | 목록 확인 | - | `6c8e0a68ed0a` |
| [Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs](../Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs) | 431 | 목록 확인 | - | `84c6850d4c57` |
| [Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs](../Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs) | 134 | 목록 확인 | - | `3a842c8567a3` |
| [Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs](../Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs) | 591 | 목록 확인 | - | `0cc491e3db1b` |
| [Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs](../Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs) | 92 | 목록 확인 | - | `fd1e225def8d` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 638 | 목록 확인 | - | `927bbdef3657` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 67 | 목록 확인 | - | `d5ced46ea9fc` |
| [Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs](../Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs) | 222 | 목록 확인 | - | `dc216d1edcfc` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs) | 40 | 목록 확인 | - | `b9e12ce1162f` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs) | 588 | 목록 확인 | - | `9a89db62fe7e` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 962 | 입출력 확인 | - | `f6ec8a550b1e` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 539 | 입출력 확인 | - | `bc934ede5e0e` |
| [Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs) | 98 | 목록 확인 | - | `40a96eb5264c` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 652 | 목록 확인 | - | `9fcbda59e81b` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 288 | 목록 확인 | - | `e6b5bc0732e9` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1KeypadLocomotionUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1KeypadLocomotionUdpSender.cs) | 251 | 목록 확인 | - | `db7096654b3d` |
| [Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs](../Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs) | 280 | 목록 확인 | - | `9e2777c84b13` |
| [Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs](../Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs) | 100 | 목록 확인 | - | `d560f0a9416c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 375 | 목록 확인 | - | `db28be0dcd81` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs) | 105 | 목록 확인 | - | `95ec4689277c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs) | 46 | 목록 확인 | - | `43571574c2ee` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 798 | 입출력 확인 | - | `9f4b122b5e9d` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 1050 | 입출력 확인 | - | `2e5fcdec8b71` |
| [Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs](../Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs) | 50 | 목록 확인 | - | `3124aab0e080` |
| [VIEW_IK_COMPARISON.bat](../VIEW_IK_COMPARISON.bat) | 19 | 목록 확인 | - | `862667f3fe95` |
| [VIEW_TRAJECTORY_AB.bat](../VIEW_TRAJECTORY_AB.bat) | 14 | 목록 확인 | - | `01a1ebf28067` |
| [backend/g1_teleop/__init__.py](../backend/g1_teleop/__init__.py) | 101 | 목록 확인 | - | `86664979265c` |
| [backend/g1_teleop/calibration.py](../backend/g1_teleop/calibration.py) | 363 | 목록 확인 | _pose_matrix, _scale_vector, _pose_to_dict, _pose_from_dict, ArmCalibration (+8) | `a2aefc7d8a10` |
| [backend/g1_teleop/camera.py](../backend/g1_teleop/camera.py) | 314 | 목록 확인 | CameraIntrinsics, CameraFrame, HeadCameraSource, MuJoCoHeadCameraSource, RealSenseD435iSource (+1) | `cea6222b9f0b` |
| [backend/g1_teleop/camera_factory.py](../backend/g1_teleop/camera_factory.py) | 103 | 목록 확인 | load_camera_profile, validate_camera_profile, validate_teleimager_profile, create_head_camera_source | `097bd1a6a72d` |
| [backend/g1_teleop/command_adapter.py](../backend/g1_teleop/command_adapter.py) | 182 | 입출력 확인 | InternalCommand, _decode_object, _legacy_integer, _legacy_source_time_ns, _legacy_vector (+4) | `eb251eba6545` |
| [backend/g1_teleop/config.py](../backend/g1_teleop/config.py) | 240 | 목록 확인 | NetworkConfig, RuntimeConfig, MotionConfig, IKConfig, CollisionConfig (+11) | `eaed1fd25c41` |
| [backend/g1_teleop/g1_camera_mount.py](../backend/g1_teleop/g1_camera_mount.py) | 60 | 목록 확인 | _find_body, add_g1_d435i_camera | `6ce8092bf39b` |
| [backend/g1_teleop/gate7_simulation_feedback.py](../backend/g1_teleop/gate7_simulation_feedback.py) | 153 | 목록 확인 | Gate7SimulationFeedbackError, Gate7SimulationFeedback, _finite_vector, build_packet, parse_packet (+1) | `89aa873e72b0` |
| [backend/g1_teleop/inspection_contact.py](../backend/g1_teleop/inspection_contact.py) | 161 | 목록 확인 | InspectionContactState, InspectionContactTransition, InspectionContactStateMachine, install_inspection_contact_monitor | `8241c3028ba3` |
| [backend/g1_teleop/inspection_demo.py](../backend/g1_teleop/inspection_demo.py) | 159 | 목록 확인 | InspectionDemoState, InspectionDemoSnapshot, InspectionDemoTracker, append_inspection_result | `92a6711f4497` |
| [backend/g1_teleop/live_receiver.py](../backend/g1_teleop/live_receiver.py) | 136 | 입출력 확인 | DatagramSocket, ReceiveBatch, receive_available_commands | `1d02a4ee903a` |
| [backend/g1_teleop/mapping.py](../backend/g1_teleop/mapping.py) | 36 | 목록 확인 | map_unity_ovr_wrist_to_head_yaw | `5166bfed6876` |
| [backend/g1_teleop/mink_command_stream.py](../backend/g1_teleop/mink_command_stream.py) | 268 | 입출력 확인 | MinkCommandUpdate, MinkCommandStream | `ad9ec3f250f8` |
| [backend/g1_teleop/motion_reference.py](../backend/g1_teleop/motion_reference.py) | 64 | 목록 확인 | step_position, step_rotation | `cef1334bbb00` |
| [backend/g1_teleop/protocol.py](../backend/g1_teleop/protocol.py) | 370 | 목록 확인 | ProtocolError, _boolean, _finite_vector, _integer, _nonempty_string (+7) | `a2822912dfb9` |
| [backend/g1_teleop/runtime_state.py](../backend/g1_teleop/runtime_state.py) | 91 | 목록 확인 | RuntimeTransition, TeleopRuntimeStateMachine | `43b826597eb4` |
| [backend/g1_teleop/source_provenance.py](../backend/g1_teleop/source_provenance.py) | 135 | 목록 확인 | SourceAcceptance, _SessionClock, CommandSourceGuard | `4e152f262150` |
| [backend/g1_teleop/transforms.py](../backend/g1_teleop/transforms.py) | 243 | 목록 확인 | validate_rotation_matrix, validate_pose_matrix, normalize_quaternion, quaternion_to_matrix, matrix_to_quaternion (+9) | `e7288927b5a2` |
| [backend/g1_teleop/unitree_image_transport.py](../backend/g1_teleop/unitree_image_transport.py) | 111 | 목록 확인 | shared_memory_name, UnitreeImageHeader, UnitreeSimImageWriter | `d2c08bb150f2` |
| [backend/g1_teleop/watchdog.py](../backend/g1_teleop/watchdog.py) | 227 | 목록 확인 | PacketAcceptance, SequenceWatchdog, SessionSequenceWatchdog, WorkspaceFaultLatch, WorkspaceExitDebounce | `1e5e91ff7c10` |
| [backend/tests/BimanualEngageGateTest.cs](../backend/tests/BimanualEngageGateTest.cs) | 32 | 목록 확인 | - | `2a05b9a1edc9` |
| [backend/tests/BimanualFeedbackGateTest.cs](../backend/tests/BimanualFeedbackGateTest.cs) | 35 | 목록 확인 | - | `3c00a1369e89` |
| [backend/tests/bimanual_replay_profiles.py](../backend/tests/bimanual_replay_profiles.py) | 29 | 목록 확인 | historical_recording_profile | `895ec554b84f` |
| [backend/tests/csharp/G1OmniHeadingStateTests.cs](../backend/tests/csharp/G1OmniHeadingStateTests.cs) | 34 | 목록 확인 | - | `36f1f4de84fd` |
| [backend/tests/fixtures/bimanual_return_near_hands_20260918.json](../backend/tests/fixtures/bimanual_return_near_hands_20260918.json) | 636 | 목록 확인 | - | `e6f50f455377` |
| [backend/tests/fixtures/bimanual_return_starts_20260918.json](../backend/tests/fixtures/bimanual_return_starts_20260918.json) | 127 | 목록 확인 | - | `a62fa392b291` |
| [backend/tests/fixtures/mink_elbow_boundary_20260909.json](../backend/tests/fixtures/mink_elbow_boundary_20260909.json) | 63 | 목록 확인 | - | `1b246fcb026b` |
| [backend/tests/fixtures/mink_front_elbow_20260917.json](../backend/tests/fixtures/mink_front_elbow_20260917.json) | 104 | 목록 확인 | - | `648f33cbe876` |
| [backend/tests/fixtures/mink_projected_wrist_rotation_20260917.json](../backend/tests/fixtures/mink_projected_wrist_rotation_20260917.json) | 104 | 목록 확인 | - | `11d50dfd2e5d` |
| [backend/tests/fixtures/mink_wrist_priority_20260909.json](../backend/tests/fixtures/mink_wrist_priority_20260909.json) | 126 | 목록 확인 | - | `7ffe144e4e97` |
| [backend/tests/test_arm_cycle_stream_integration.py](../backend/tests/test_arm_cycle_stream_integration.py) | 72 | 목록 확인 | IntegratedCycleTest | `b9da89ed967d` |
| [backend/tests/test_batch_failure_guidance.py](../backend/tests/test_batch_failure_guidance.py) | 70 | 목록 확인 | BatchFailureGuidanceTest | `05e261289c21` |
| [backend/tests/test_bimanual_boundaries.py](../backend/tests/test_bimanual_boundaries.py) | 210 | 목록 확인 | OutputContinuityTests, ProtocolBoundaryTests | `7ec74c8d6626` |
| [backend/tests/test_bimanual_marker_feedback.py](../backend/tests/test_bimanual_marker_feedback.py) | 132 | 목록 확인 | MarkerFeedbackTests | `47ad0def0fec` |
| [backend/tests/test_bimanual_motion_quality.py](../backend/tests/test_bimanual_motion_quality.py) | 289 | 목록 확인 | quality_case, replay_recorded_motion, MotionQualityTests, PoseFilterTests | `ae5294506d54` |
| [backend/tests/test_bimanual_near_hands_sweep.py](../backend/tests/test_bimanual_near_hands_sweep.py) | 269 | 목록 확인 | TriggerDecisionReached, fixture_q14, full_q, find_threshold_fraction, find_safe_lower_fraction (+4) | `a2b3093612ff` |
| [backend/tests/test_bimanual_quest_reengage.py](../backend/tests/test_bimanual_quest_reengage.py) | 149 | 목록 확인 | rows, QuestReengageReplayTests | `b9c810f2463c` |
| [backend/tests/test_bimanual_recorded_session.py](../backend/tests/test_bimanual_recorded_session.py) | 178 | 목록 확인 | load_fixture, RecordedStagedSessionTests | `b5171d78b2f4` |
| [backend/tests/test_bimanual_return.py](../backend/tests/test_bimanual_return.py) | 480 | 목록 확인 | assert_output, recorded_return, StagedReturnTests | `ebfff5ccb53d` |
| [backend/tests/test_bimanual_runtime.py](../backend/tests/test_bimanual_runtime.py) | 156 | 목록 확인 | fake_engine, RuntimeTests | `03d2c03047af` |
| [backend/tests/test_bimanual_session_report.py](../backend/tests/test_bimanual_session_report.py) | 413 | 목록 확인 | SessionReportTests | `e29f4d7925d9` |
| [backend/tests/test_bimanual_sim.py](../backend/tests/test_bimanual_sim.py) | 245 | 목록 확인 | BimanualTests | `f5a0afee7364` |
| [backend/tests/test_bimanual_unity_sim.py](../backend/tests/test_bimanual_unity_sim.py) | 271 | 목록 확인 | packet, CycleTests | `85eb715512ee` |
| [backend/tests/test_capture_output_isolation.py](../backend/tests/test_capture_output_isolation.py) | 67 | 목록 확인 | test_same_second_names_are_unique, test_existing_outputs_never_overwritten | `26ddd4192a13` |
| [backend/tests/test_code_index.py](../backend/tests/test_code_index.py) | 42 | 목록 확인 | CodeIndexTests | `bfd86a963b9d` |
| [backend/tests/test_dds_firewall_rollback.py](../backend/tests/test_dds_firewall_rollback.py) | 128 | 목록 확인 | test_transaction, test_adapter_selection, run_mock | `dfd424d7ff67` |
| [backend/tests/test_diagnostic_exit_contract.py](../backend/tests/test_diagnostic_exit_contract.py) | 351 | 목록 확인 | test_camera_read_deadline_csharp_without_network, test_camera_play_stop_never_waits_on_receiver_task, test_camera_cli_rejects_nonfinite_without_transport, test_network_final_state_is_verified, test_adapter_selection_is_unambiguous (+5) | `242bee7959d4` |
| [backend/tests/test_ethernet_dns_transaction.py](../backend/tests/test_ethernet_dns_transaction.py) | 77 | 목록 확인 | test_dns_mode_recovery, test_snapshot_precedes_ip_changes | `6e24eb4209e8` |
| [backend/tests/test_ethernet_transaction.py](../backend/tests/test_ethernet_transaction.py) | 105 | 목록 확인 | test_ethernet_transaction | `9842519e4878` |
| [backend/tests/test_feasible_target_return.py](../backend/tests/test_feasible_target_return.py) | 79 | 목록 확인 | ReturnTests | `03d486001e63` |
| [backend/tests/test_foundation.py](../backend/tests/test_foundation.py) | 380 | 목록 확인 | RigidPoseValidationTest, FoundationTest | `a2be064681ae` |
| [backend/tests/test_g1_body_translation_math.py](../backend/tests/test_g1_body_translation_math.py) | 31 | 목록 확인 | BodyTranslationTests | `79376e3dcf64` |
| [backend/tests/test_g1_camera_ssh.py](../backend/tests/test_g1_camera_ssh.py) | 52 | 목록 확인 | CameraTests | `13f331072539` |
| [backend/tests/test_g1_input_console.py](../backend/tests/test_g1_input_console.py) | 86 | 목록 확인 | arm_row, ConsoleTests | `a22fbc914ecd` |
| [backend/tests/test_g1_lowstate_view.py](../backend/tests/test_g1_lowstate_view.py) | 28 | 목록 확인 | LowStateTests | `51a289d5a2b5` |
| [backend/tests/test_g1_observation_audit.py](../backend/tests/test_g1_observation_audit.py) | 330 | 목록 확인 | packet, source_packet, AuditTests | `0b30b9d937f1` |
| [backend/tests/test_g1_observation_pipeline.py](../backend/tests/test_g1_observation_pipeline.py) | 375 | 목록 확인 | ObservationPipelineTests, ObservationLauncherTests | `b2e7743c2c98` |
| [backend/tests/test_g1_observation_tap.py](../backend/tests/test_g1_observation_tap.py) | 223 | 목록 확인 | ObservationTapTests, ProducerPreservationTests | `a180aeff8fc0` |
| [backend/tests/test_g1_omni_transport_recovery.py](../backend/tests/test_g1_omni_transport_recovery.py) | 152 | 목록 확인 | LocalOmniServer, OmniTransportRecoveryTests | `06fd59c737b7` |
| [backend/tests/test_g1_portable_environment.py](../backend/tests/test_g1_portable_environment.py) | 174 | 목록 확인 | PortableTests | `80d97f0ff9cf` |
| [backend/tests/test_g1_process_lifetime.py](../backend/tests/test_g1_process_lifetime.py) | 62 | 목록 확인 | LifetimeTests | `ebcce528a3f2` |
| [backend/tests/test_g1_quiet_observation.py](../backend/tests/test_g1_quiet_observation.py) | 52 | 목록 확인 | QuietTests | `cc779d373adf` |
| [backend/tests/test_g1_ssh_login.py](../backend/tests/test_g1_ssh_login.py) | 56 | 목록 확인 | LoginTests | `1fca27bf0d14` |
| [backend/tests/test_g1_teleop_dependencies.py](../backend/tests/test_g1_teleop_dependencies.py) | 60 | 목록 확인 | DependencyTests | `285271629dd5` |
| [backend/tests/test_g1_vr_teleop_launch.py](../backend/tests/test_g1_vr_teleop_launch.py) | 331 | 목록 확인 | worker_row, WorkerRecognitionTests, UnityLaunchTests, RedirectorTests, OrchestrationTests (+2) | `3368a64c8f34` |
| [backend/tests/test_gate7_mujoco_feedback_receiver.py](../backend/tests/test_gate7_mujoco_feedback_receiver.py) | 120 | 목록 확인 | _payload, Gate7MujocoFeedbackReceiverTest | `f8f6c79ec65e` |
| [backend/tests/test_gate7_simulation_feedback.py](../backend/tests/test_gate7_simulation_feedback.py) | 89 | 목록 확인 | Gate7SimulationFeedbackTest | `fc81a75e405d` |
| [backend/tests/test_ik_visual_comparison.py](../backend/tests/test_ik_visual_comparison.py) | 112 | 목록 확인 | test_composite_goals_are_closed_multiaxis_pose_paths, test_invalid_standard_velocity_holds_pose_without_hiding_failure, test_playback_speed_preserves_fixed_steps_and_pause, test_comparison_keys_do_not_use_mujoco_shortcuts, test_comparison_reset_and_independent_joint_states | `8310646fbe68` |
| [backend/tests/test_inspection_contact.py](../backend/tests/test_inspection_contact.py) | 67 | 목록 확인 | InspectionContactStateMachineTest | `8029e94d123e` |
| [backend/tests/test_inspection_demo.py](../backend/tests/test_inspection_demo.py) | 74 | 목록 확인 | InspectionDemoTrackerTest | `bcbbbeecca0b` |
| [backend/tests/test_live_receiver.py](../backend/tests/test_live_receiver.py) | 243 | 목록 확인 | FakeSocket, legacy_packet, legacy_disengage_packet, legacy_tracking_disengage_packet, legacy_workspace_exit_packet (+2) | `b1f1f90f6d43` |
| [backend/tests/test_lowstate_firewall_scope.py](../backend/tests/test_lowstate_firewall_scope.py) | 112 | 목록 확인 | test_scope_without_admin_or_network | `8b0d1836d46e` |
| [backend/tests/test_lowstate_mink_seed.py](../backend/tests/test_lowstate_mink_seed.py) | 57 | 목록 확인 | Seed, Load, test_all_29_joint_mapping_and_base_unchanged, test_rejected_seed, test_reject_model_limits_atomically | `933efa17d51f` |
| [backend/tests/test_lowstate_seed_writer.py](../backend/tests/test_lowstate_seed_writer.py) | 55 | 목록 확인 | Bytes, test_write_replace_expiry_cleanup, test_failure_removes_previous_seed_and_temp, test_never_adopts_existing_seed | `8c6233036a09` |
| [backend/tests/test_mink_candidate_benchmark.py](../backend/tests/test_mink_candidate_benchmark.py) | 383 | 목록 확인 | BenchmarkTests, test_real_render_process_lifecycle | `6bd80a5df64e` |
| [backend/tests/test_mink_collision_diagnostics.py](../backend/tests/test_mink_collision_diagnostics.py) | 205 | 목록 확인 | MinkCollisionDiagnosticsTest | `b908688b165a` |
| [backend/tests/test_mink_collision_feasibility.py](../backend/tests/test_mink_collision_feasibility.py) | 129 | 목록 확인 | CollisionFeasibilityTests | `725ff0bd0180` |
| [backend/tests/test_mink_command_stream.py](../backend/tests/test_mink_command_stream.py) | 272 | 목록 확인 | FakeSocket, packet, MinkCommandStreamTest | `1fc5b8f38131` |
| [backend/tests/test_mink_distance_invariance.py](../backend/tests/test_mink_distance_invariance.py) | 120 | 목록 확인 | DistanceInvarianceTests | `3dc5048606a4` |
| [backend/tests/test_mink_feasible_target.py](../backend/tests/test_mink_feasible_target.py) | 459 | 목록 확인 | FeasibleTargetTest | `b2bf9dc8d176` |
| [backend/tests/test_mink_model_return.py](../backend/tests/test_mink_model_return.py) | 96 | 목록 확인 | ModelReturnTest | `f663b28c30c7` |
| [backend/tests/test_mink_reachability_limit.py](../backend/tests/test_mink_reachability_limit.py) | 33 | 목록 확인 | MinkReachabilityLimitTest | `d3feecf0bd93` |
| [backend/tests/test_mink_return_handshake.py](../backend/tests/test_mink_return_handshake.py) | 124 | 목록 확인 | ReturnHandshakeTests | `6bfe92dc2227` |
| [backend/tests/test_mink_runtime_refactor_compatibility.py](../backend/tests/test_mink_runtime_refactor_compatibility.py) | 71 | 목록 확인 | MinkRuntimeRefactorCompatibilityTest | `d5ab8c5e505c` |
| [backend/tests/test_mink_stateful_trajectory.py](../backend/tests/test_mink_stateful_trajectory.py) | 82 | 목록 확인 | MinkStatefulTrajectoryTest | `c013b386564d` |
| [backend/tests/test_mink_step_acceptance_comparison.py](../backend/tests/test_mink_step_acceptance_comparison.py) | 503 | 목록 확인 | MinkStepAcceptanceComparisonTests | `3ea17b32ceee` |
| [backend/tests/test_mink_task_cost_contract.py](../backend/tests/test_mink_task_cost_contract.py) | 47 | 목록 확인 | ExampleTask, MinkTaskCostContractTest | `62ece4cc7488` |
| [backend/tests/test_mink_tracking_lag.py](../backend/tests/test_mink_tracking_lag.py) | 60 | 목록 확인 | TrackingLagTests | `e90e39b10f10` |
| [backend/tests/test_mink_virtual_center_trajectory.py](../backend/tests/test_mink_virtual_center_trajectory.py) | 212 | 목록 확인 | rotation_error_degrees, MinkVirtualCenterTrajectoryTest | `133a9529edd2` |
| [backend/tests/test_motion_reference.py](../backend/tests/test_motion_reference.py) | 52 | 목록 확인 | MotionReferenceTest | `1003f5d2d186` |
| [backend/tests/test_mujoco312_simulation_entry.py](../backend/tests/test_mujoco312_simulation_entry.py) | 135 | 목록 확인 | test_simulation_packet_cannot_enter_hardware, test_seed_environment_forwarding_without_shell_interpolation, test_right_arm_csv_forwarding, test_partial_seed_environment_rejected_before_engine, test_isolated_import_validation (+6) | `95547f60fb6a` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `87ba04dd2d7d` |
| [backend/tests/test_mujoco_inspection_scene_visibility.py](../backend/tests/test_mujoco_inspection_scene_visibility.py) | 75 | 목록 확인 | MujocoInspectionSceneVisibilityTest | `c412678a928e` |
| [backend/tests/test_offline_model_isolation.py](../backend/tests/test_offline_model_isolation.py) | 594 | 목록 확인 | test_render_replay_xml_lifetime, test_render_replay_loads_isolated_model, test_live_entry_model_block_isolated, test_jog_provenance_uses_validator_model, shared_bytes (+18) | `883b5eecafb5` |
| [backend/tests/test_offline_owner.py](../backend/tests/test_offline_owner.py) | 70 | 목록 확인 | load_fixture, test_owner_fault_latches, test_autonomous_timeout_without_stdin, test_existing_relay_packet_reaches_native_adapter | `c7f00122f464` |
| [backend/tests/test_protocol_v2.py](../backend/tests/test_protocol_v2.py) | 196 | 목록 확인 | tracked, pose_v2, ProtocolV1IntegerTest, ProtocolV2Test | `0697b9d01028` |
| [backend/tests/test_recorded_ik_hierarchy.py](../backend/tests/test_recorded_ik_hierarchy.py) | 174 | 목록 확인 | test_goal_rebase_preserves_delta_and_neutral, test_fixed_basis_and_clutch_preserve_rotation_step, test_operator_quaternion_sign_does_not_change_target, test_qp_summary_includes_small_rotation_errors, test_short_stationary_comparison (+8) | `c4fd8d4dd8f6` |
| [backend/tests/test_recorded_pose_speed_comparison.py](../backend/tests/test_recorded_pose_speed_comparison.py) | 61 | 목록 확인 | MakePacket, RecordedPoseSpeedComparisonTest | `f667723f00c9` |
| [backend/tests/test_recorded_reach_bound.py](../backend/tests/test_recorded_reach_bound.py) | 140 | 목록 확인 | RecordedReachBoundTest | `b466a232d4f7` |
| [backend/tests/test_rotation_trace_analysis.py](../backend/tests/test_rotation_trace_analysis.py) | 83 | 목록 확인 | MakeRow, test_sign_and_duplicate_packet_are_not_events, test_semantic_change_is_distinguished_from_source, test_new_session_does_not_compare_packet_rotation, test_packet_jump_and_cli_output (+2) | `01223e7fd256` |
| [backend/tests/test_runtime_architecture.py](../backend/tests/test_runtime_architecture.py) | 62 | 목록 확인 | command, RuntimeArchitectureTest | `e39e40892b1e` |
| [backend/tests/test_seed_file_sharing.py](../backend/tests/test_seed_file_sharing.py) | 35 | 목록 확인 | test_open_snapshot_allows_delete_sharing, test_missing_and_oversized_file | `aef900384cfd` |
| [backend/tests/test_seed_observer_failure.py](../backend/tests/test_seed_observer_failure.py) | 24 | 목록 확인 | test_permission_error_is_reported_and_fails | `e9132f6f40f0` |
| [backend/tests/test_seed_velocity_review.py](../backend/tests/test_seed_velocity_review.py) | 30 | 목록 확인 | test_trigger_context_clipping_and_no_event, test_spikes_runs_and_gap_are_distinct, test_bad_data_rejected | `dd7f70675ac3` |
| [backend/tests/test_seed_window_comparison.py](../backend/tests/test_seed_window_comparison.py) | 22 | 목록 확인 | test_spike_and_drift_are_separate, test_invalid_windows_rejected | `88b09cd1d57a` |
| [backend/tests/test_simulation_handoff_boundary.py](../backend/tests/test_simulation_handoff_boundary.py) | 81 | 목록 확인 | SimulationHandoffBoundaryTests | `a6a7c76d844e` |
| [backend/tests/test_source_provenance.py](../backend/tests/test_source_provenance.py) | 123 | 목록 확인 | command, CommandSourceGuardTests | `a49810e1a73c` |
| [backend/tests/test_standard_mink_live.py](../backend/tests/test_standard_mink_live.py) | 204 | 목록 확인 | test_standard_qp_shared_limits_and_goal, test_launcher_selection_and_locked_profile, test_live_parser_preserves_default_and_selects_vanilla, test_embedded_csv_preserves_exact_transmitted_json, test_local_launcher_default_without_starting_runtime (+1) | `06a86589c1d3` |
| [backend/tests/test_startup_ready_pose_editor.py](../backend/tests/test_startup_ready_pose_editor.py) | 75 | 목록 확인 | StartupReadyPoseEditorTest | `9ef3c18fabae` |
| [backend/tests/test_synthetic_ik_cases.py](../backend/tests/test_synthetic_ik_cases.py) | 194 | 목록 확인 | test_path_observer_preserves_decision_and_records_joint_rejection, test_single_qp_cost_changes_only_proximal_damping_and_restores, test_single_qp_cost_rejects_nonfinite_or_negative, test_out_of_range_start_is_rejected_before_output, test_wrist_axes_are_distinct_and_positions_stay_fixed (+9) | `456828d7ecfe` |
| [backend/tests/test_teleop_config.py](../backend/tests/test_teleop_config.py) | 154 | 목록 확인 | TeleopConfigTest | `c058e4abb9d3` |
| [backend/tests/test_trajectory_ab.py](../backend/tests/test_trajectory_ab.py) | 66 | 목록 확인 | test_live_tracking_reaches_acceleration_limit_within_one_control_tick, test_forward_then_wrist_keeps_requested_position_fixed, test_candidate_bounds_and_stop_without_changing_baseline, test_candidate_rejects_nonfinite | `da3051704046` |
| [backend/tests/test_unity_display_mode_launcher.py](../backend/tests/test_unity_display_mode_launcher.py) | 53 | 목록 확인 | UnityDisplayModeLauncherTests, ReadOnlyPreviewLauncherTests | `a1fbe7110ce4` |
| [backend/tests/test_unity_workspace_policy.py](../backend/tests/test_unity_workspace_policy.py) | 263 | 목록 확인 | UnityWorkspacePolicyTest | `f03a3bb36aaa` |
| [backend/tests/test_upstream_mink_tracking.py](../backend/tests/test_upstream_mink_tracking.py) | 416 | 목록 확인 | UpstreamTrackingTests | `85206343c759` |
| [backend/tests/test_virtual_center_kinematics_regression.py](../backend/tests/test_virtual_center_kinematics_regression.py) | 96 | 목록 확인 | VirtualCenterKinematicsRegressionTest | `0d2f1905a8bd` |
| [backend/tests/test_virtual_center_orientation_policy.py](../backend/tests/test_virtual_center_orientation_policy.py) | 135 | 목록 확인 | VirtualCenterOrientationPolicyTest | `4ab5378be0b9` |
| [backend/tests/test_windows_tool_paths.py](../backend/tests/test_windows_tool_paths.py) | 299 | 목록 확인 | PathContractTests, UnityEditorDiscoveryTests, OtherToolPathTests | `502ebdff5051` |
| [backend/tests/test_wrist_target_mapping_audit.py](../backend/tests/test_wrist_target_mapping_audit.py) | 50 | 목록 확인 | MappingAuditTests | `4c7b69cdb5a9` |
| [backend/tools/analyze_rotation_trace.py](../backend/tools/analyze_rotation_trace.py) | 95 | 목록 확인 | GetQuaternion, GetAngle, AnalyzeRows, main | `bee05da32cd2` |
| [backend/tools/audit_bimanual_known_targets.py](../backend/tools/audit_bimanual_known_targets.py) | 105 | 목록 확인 | main | `ed1330663c95` |
| [backend/tools/audit_bimanual_reachability.py](../backend/tools/audit_bimanual_reachability.py) | 137 | 목록 확인 | main | `771d58492bc1` |
| [backend/tools/audit_bimanual_settling.py](../backend/tools/audit_bimanual_settling.py) | 68 | 목록 확인 | main | `5baca4a68283` |
| [backend/tools/audit_wrist_target_mapping.py](../backend/tools/audit_wrist_target_mapping.py) | 180 | 목록 확인 | OperatorToRobotDelta, GetNecessaryScale, ReadUnitySegments, GetVectors, AuditSender (+2) | `39083704d2a8` |
| [backend/tools/benchmark_mink_candidate.py](../backend/tools/benchmark_mink_candidate.py) | 274 | 목록 확인 | CachedClearance, BoundedClearance, CachedCollisionLimit, BuildCandidate, SummarizeTiming (+3) | `5540f0438298` |
| [backend/tools/benchmark_mink_rendered_replay.py](../backend/tools/benchmark_mink_rendered_replay.py) | 316 | 목록 확인 | WaitForRelease, GetNextRelease, LoadReplay, ReplayRenderer, RunRenderedReplay (+3) | `f2e6683fdb45` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 121 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `bae8666a7a4d` |
| [backend/tools/compare_bimanual_single_arm.py](../backend/tools/compare_bimanual_single_arm.py) | 101 | 목록 확인 | main | `cf68ff3ca425` |
| [backend/tools/compare_mink_step_acceptance.py](../backend/tools/compare_mink_step_acceptance.py) | 774 | 목록 확인 | GetLimitMetadata, WristPositionTask, FullOrientationErrorTask, IncrementCollisionLimit, ResolvedCollisionLimit (+12) | `83efa367ecb5` |
| [backend/tools/compare_mink_trajectory.py](../backend/tools/compare_mink_trajectory.py) | 130 | 목록 확인 | ForwardWristGoal, ThroughTrajectory, TrajectoryComparison | `1b7ae7b09310` |
| [backend/tools/compare_recorded_ik_hierarchy.py](../backend/tools/compare_recorded_ik_hierarchy.py) | 289 | 목록 확인 | UseOfflineProximalCost, GetNormalizedGoal, RunDiagnosedPlan, SummarizeQP, SummarizeTargetEvents (+3) | `ebad66c86e77` |
| [backend/tools/compare_recorded_pose_speeds.py](../backend/tools/compare_recorded_pose_speeds.py) | 116 | 목록 확인 | GetActiveSegments, GetRecordedTargets, GetTargetIndex, main | `75d0ea5f77cd` |
| [backend/tools/compare_synthetic_ik.py](../backend/tools/compare_synthetic_ik.py) | 298 | 목록 확인 | ObservePathChecks, UseSingleQPCost, UseMeritAblation, ProgressBand, TargetErrorBand (+3) | `c1074d7940d7` |
| [backend/tools/diagnose_mink_collision_feasibility.py](../backend/tools/diagnose_mink_collision_feasibility.py) | 282 | 목록 확인 | EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, main | `9ed12aa42c01` |
| [backend/tools/diagnose_mink_distance_invariance.py](../backend/tools/diagnose_mink_distance_invariance.py) | 214 | 목록 확인 | GetSupportGap, GetWorldVertices, GetEnclosingVertices, GetSeparationCertificate, InspectTrace (+3) | `63026667f84d` |
| [backend/tools/diagnose_mink_tracking_lag.py](../backend/tools/diagnose_mink_tracking_lag.py) | 189 | 목록 확인 | GetSchedule, GetSustainedSettleTime, GetReachSummary, Step, GetSample (+4) | `130f0cf82a20` |
| [backend/tools/diagnose_recorded_reach.py](../backend/tools/diagnose_recorded_reach.py) | 123 | 목록 확인 | GetReachUpperBound, SaveInputFailure, main, RunDiagnosis | `95e5275d4c10` |
| [backend/tools/inspect_feasible_target_return.py](../backend/tools/inspect_feasible_target_return.py) | 194 | 목록 확인 | InterpolateGoal, SummarizePreview, GetVerdict, Run, main (+1) | `2d71ce4cfe49` |
| [backend/tools/offline_render_worker.py](../backend/tools/offline_render_worker.py) | 193 | 목록 확인 | LatestStateSlot, RunRenderWorker, ProcessRenderer | `d4a879a5cec9` |
| [backend/tools/reconcile_review_ledger.py](../backend/tools/reconcile_review_ledger.py) | 176 | 목록 확인 | _read_csv, _semantic_map, _static_check, build_rows, _csv_text (+1) | `91ee37c20ba9` |
| [backend/tools/verify_camera_simulation.py](../backend/tools/verify_camera_simulation.py) | 271 | 목록 확인 | parse_args, quaternion_rotation_matrix, official_optical_axes, verify_transport, main | `4807200b3f0d` |
| [backend/tools/verify_feasible_target.py](../backend/tools/verify_feasible_target.py) | 137 | 목록 확인 | BuildPlanner, RunSequence, main | `8be541bf0813` |
| [backend/tools/verify_unity_state_packets.ps1](../backend/tools/verify_unity_state_packets.ps1) | 149 | 목록 확인 | - | `53ca71f00528` |
| [backend/tools/verify_virtual_center_kinematics.py](../backend/tools/verify_virtual_center_kinematics.py) | 269 | 목록 확인 | LegacyOrientationTask, ExactOrientationTask, CheckJacobian, GetStepCount, RunCase (+1) | `e8abbbace58f` |
| [backend/tools/view_ik_comparison.py](../backend/tools/view_ik_comparison.py) | 358 | 목록 확인 | NextPlaybackSpeed, GetCompositeGoal, HandleComparisonKey, RecordedPlayback, Comparison (+2) | `da895fd24a9f` |
| [config/camera_profile.json](../config/camera_profile.json) | 42 | 목록 확인 | - | `00b755866d6e` |
| [config/g1_gate6_hold.json](../config/g1_gate6_hold.json) | 31 | 목록 확인 | - | `327fd93ebf88` |
| [config/g1_gate6_interrupt_release_test.json](../config/g1_gate6_interrupt_release_test.json) | 31 | 목록 확인 | - | `02040744b4fc` |
| [config/g1_gate7_first_live_hardware_output.json](../config/g1_gate7_first_live_hardware_output.json) | 33 | 목록 확인 | - | `e34cc263326e` |
| [config/g1_gate7_first_live_mink_arm_sdk.json](../config/g1_gate7_first_live_mink_arm_sdk.json) | 20 | 목록 확인 | - | `25f5a11e7c82` |
| [config/g1_gate7_live_hardware_output.json](../config/g1_gate7_live_hardware_output.json) | 33 | 목록 확인 | - | `5e91cd5adcba` |
| [config/g1_gate7_mink_arm_sdk.json](../config/g1_gate7_mink_arm_sdk.json) | 20 | 목록 확인 | - | `4f1ab28f00ce` |
| [config/g1_gate7_visible_motion_hardware_output.json](../config/g1_gate7_visible_motion_hardware_output.json) | 33 | 목록 확인 | - | `111d6a4c44a8` |
| [config/g1_gate7_visible_motion_mink_arm_sdk.json](../config/g1_gate7_visible_motion_mink_arm_sdk.json) | 20 | 목록 확인 | - | `44fa4ecaff39` |
| [config/g1_regular_arm_pose.json](../config/g1_regular_arm_pose.json) | 61 | 목록 확인 | - | `fc0b80702dfb` |
| [config/g1_right_arm_jog.json](../config/g1_right_arm_jog.json) | 39 | 목록 확인 | - | `b974a756fbe4` |
| [config/g1_right_shoulder_pitch_full_authority_trial.json](../config/g1_right_shoulder_pitch_full_authority_trial.json) | 47 | 목록 확인 | - | `916cedef6059` |
| [config/g1_startup_precheck.json](../config/g1_startup_precheck.json) | 19 | 목록 확인 | - | `3fca74fe17f7` |
| [config/g1_waist_hold_trial_draft.json](../config/g1_waist_hold_trial_draft.json) | 45 | 목록 확인 | - | `ddf4d06f89ec` |
| [config/startup_recovery.json](../config/startup_recovery.json) | 15 | 목록 확인 | - | `75e9a6d9be3a` |
| [config/teleimager_real_d435i.yaml](../config/teleimager_real_d435i.yaml) | 36 | 목록 확인 | - | `2646f08cfc76` |
| [config/teleimager_simulation.yaml](../config/teleimager_simulation.yaml) | 36 | 목록 확인 | - | `65127fae537d` |
| [config/teleop.json](../config/teleop.json) | 83 | 목록 확인 | - | `e3498304c8b4` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/manifest.json](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/manifest.json) | 32 | 목록 확인 | - | `bd8ef487e822` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_contract.hpp) | 190 | 목록 확인 | - | `8b5909c48f66` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `4657b484b9fd` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_udp_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_udp_target.hpp) | 53 | 목록 확인 | - | `4fab496e3ec6` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_relay_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_relay_contract.hpp) | 22 | 목록 확인 | - | `b3166d425d43` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_snapshot_freshness.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `b47a074855be` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_state_tick.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_state_tick.hpp) | 8 | 목록 확인 | - | `3c81f7a6a02d` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_cycle_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `c3f32f5a9b26` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_policy_adapter.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `951ea95f53f2` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/offline_twist2_constants.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `f07fcb5eb557` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_gain_options.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_gain_options.hpp) | 59 | 목록 확인 | - | `0ac7fb7e4d5f` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_joint_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `1198d63d09a0` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_reference.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `b8d7170be290` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `93cfa189edda` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_ready_settle.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `b73055656378` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_small_signal_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `6b1df6d7dff0` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/periodic_csv.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/periodic_csv.hpp) | 64 | 목록 확인 | - | `10755012a8eb` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/raw_input_watch_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `df293e7ee746` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_common.hpp) | 376 | 목록 확인 | - | `4b6a6842ab8f` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.cpp) | 1284 | 목록 확인 | - | `be7620e3761d` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.remote_current.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.remote_current.cpp) | 1590 | 목록 확인 | - | `c2d7e8d892a3` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/upper_target_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/upper_target_offline.hpp) | 140 | 목록 확인 | - | `8e90632b7613` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/validate_input.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/validate_input.hpp) | 178 | 목록 확인 | - | `a081a44c7ef7` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/vendor/json.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/vendor/json.hpp) | 25526 | 목록 확인 | - | `aaf127c04cb3` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/verified_regular_handoff.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/verified_regular_handoff.hpp) | 31 | 목록 확인 | - | `b7a323525786` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/writer_frame.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/writer_frame.hpp) | 37 | 목록 확인 | - | `edbed2c763cb` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/g1_velocity_policy.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/g1_velocity_policy.hpp) | 302 | 목록 확인 | - | `84bf4f778806` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/run_continuous_gait.sh](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/run_continuous_gait.sh) | 11 | 목록 확인 | - | `e4bfdaddc03b` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_common.hpp) | 384 | 목록 확인 | - | `9ece28a8450c` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_static_stand.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_static_stand.cpp) | 1687 | 목록 확인 | - | `6e7b7d5dc55d` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_mink_keypad_right_arm.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_mink_keypad_right_arm.cpp) | 1823 | 목록 확인 | - | `653013e15651` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_policy.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_policy.hpp) | 315 | 목록 확인 | - | `d3150f9dac6a` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/leg_policy_switch.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/leg_policy_switch.hpp) | 101 | 목록 확인 | - | `9ca3de01558d` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_contract.hpp) | 198 | 목록 확인 | - | `699c042471f3` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `9d9c3a5feb8e` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_udp_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_udp_target.hpp) | 53 | 목록 확인 | - | `4fab496e3ec6` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_relay_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_relay_contract.hpp) | 22 | 목록 확인 | - | `b3166d425d43` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_snapshot_freshness.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `b47a074855be` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_state_tick.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_state_tick.hpp) | 8 | 목록 확인 | - | `3c81f7a6a02d` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_velocity_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_velocity_udp.hpp) | 155 | 목록 확인 | - | `c3136edb10b2` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_cycle_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `c3f32f5a9b26` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_policy_adapter.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `951ea95f53f2` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/offline_twist2_constants.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `f07fcb5eb557` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_gain_options.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_gain_options.hpp) | 60 | 목록 확인 | - | `e62b17c52375` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_joint_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `1198d63d09a0` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_reference.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `b8d7170be290` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `93cfa189edda` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_ready_settle.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `b73055656378` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_small_signal_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `6b1df6d7dff0` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/periodic_csv.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/periodic_csv.hpp) | 64 | 목록 확인 | - | `10755012a8eb` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/raw_input_watch_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `df293e7ee746` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_static_stand_handoff_probe.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_static_stand_handoff_probe.sh) | 6 | 목록 확인 | - | `25912e7b7a12` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_axis_trial.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_axis_trial.sh) | 16 | 목록 확인 | - | `9adca7344b06` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_mink_keypad.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_mink_keypad.sh) | 21 | 목록 확인 | - | `a90cb043e5bf` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_initial_ready_continuous_gait.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_initial_ready_continuous_gait.cpp) | 55 | 목록 확인 | - | `4773d88d02cf` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_leg_policy_switch.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_leg_policy_switch.cpp) | 49 | 목록 확인 | - | `bb99b5c45da3` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_velocity_keypad_contract.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_velocity_keypad_contract.cpp) | 44 | 목록 확인 | - | `6a9c9414d28d` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/twist2_common.hpp) | 384 | 목록 확인 | - | `9ece28a8450c` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/upper_target_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/upper_target_offline.hpp) | 140 | 목록 확인 | - | `8e90632b7613` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/validate_input.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/validate_input.hpp) | 178 | 목록 확인 | - | `a081a44c7ef7` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/velocity_keypad_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/velocity_keypad_contract.hpp) | 78 | 목록 확인 | - | `3028e13fb5df` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/vendor/json.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/vendor/json.hpp) | 25526 | 목록 확인 | - | `aaf127c04cb3` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/verified_regular_handoff.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/verified_regular_handoff.hpp) | 31 | 목록 확인 | - | `b7a323525786` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/writer_frame.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/writer_frame.hpp) | 37 | 목록 확인 | - | `edbed2c763cb` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_arm_ready_decouple_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_arm_ready_decouple_20260915.sh) | 30 | 목록 확인 | - | `7643463d8642` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_build_continuous_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_build_continuous_20260915.sh) | 40 | 목록 확인 | - | `641e6c7e502e` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_continuous_gait_arm_ready_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_continuous_gait_arm_ready_20260915.sh) | 32 | 목록 확인 | - | `0e5d1e6c7dbb` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_dual_policy_idle_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_dual_policy_idle_20260915.sh) | 19 | 목록 확인 | - | `88744eb4d9e1` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_keypad_latched_08_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_keypad_latched_08_20260915.sh) | 28 | 목록 확인 | - | `040010a2ae09` |
| [experiments/independent_locomotion/data/mink_command_trajectories_v1.json](../experiments/independent_locomotion/data/mink_command_trajectories_v1.json) | 89 | 목록 확인 | - | `e61962fd0805` |
| [experiments/independent_locomotion/evaluate_upper_body_conditioned.py](../experiments/independent_locomotion/evaluate_upper_body_conditioned.py) | 160 | 목록 확인 | _state_snapshot, _unchanged, evaluate_seed, main | `be609421278a` |
| [experiments/independent_locomotion/evaluation_protocol_v1.json](../experiments/independent_locomotion/evaluation_protocol_v1.json) | 33 | 목록 확인 | - | `60e18c68d5df` |
| [experiments/independent_locomotion/matched_training_stage1.json](../experiments/independent_locomotion/matched_training_stage1.json) | 15 | 목록 확인 | - | `86a53e138eee` |
| [experiments/independent_locomotion/mink_trajectory_dataset.py](../experiments/independent_locomotion/mink_trajectory_dataset.py) | 111 | 목록 확인 | sha256, read_active_episode, build_bank, load_split | `3300c0c991a9` |
| [experiments/independent_locomotion/prepare_mink_trajectory_split.py](../experiments/independent_locomotion/prepare_mink_trajectory_split.py) | 32 | 목록 확인 | - | `ca089d64fc75` |
| [experiments/independent_locomotion/run_matched_training_continuation.sh](../experiments/independent_locomotion/run_matched_training_continuation.sh) | 46 | 목록 확인 | - | `26c8b4334339` |
| [experiments/independent_locomotion/run_matched_training_stage1.sh](../experiments/independent_locomotion/run_matched_training_stage1.sh) | 26 | 목록 확인 | - | `7d5ce9160214` |
| [experiments/independent_locomotion/run_recorded_curriculum.sh](../experiments/independent_locomotion/run_recorded_curriculum.sh) | 53 | 목록 확인 | - | `b0bb629795f5` |
| [experiments/independent_locomotion/select_matched_resume.py](../experiments/independent_locomotion/select_matched_resume.py) | 71 | 목록 확인 | checkpoint_from_result, select_checkpoint, main | `c0981db59943` |
| [experiments/independent_locomotion/smoke_mjlab.py](../experiments/independent_locomotion/smoke_mjlab.py) | 63 | 목록 확인 | check_finite, main | `bf1af65b1cbc` |
| [experiments/independent_locomotion/smoke_upper_body_conditioned.py](../experiments/independent_locomotion/smoke_upper_body_conditioned.py) | 82 | 목록 확인 | main | `56be65cb291c` |
| [experiments/independent_locomotion/summarize_matched_training.py](../experiments/independent_locomotion/summarize_matched_training.py) | 70 | 목록 확인 | summarize, main | `89bb86182432` |
| [experiments/independent_locomotion/test_mink_trajectory_dataset.py](../experiments/independent_locomotion/test_mink_trajectory_dataset.py) | 46 | 목록 확인 | SplitValidationTest | `8a1d291c6a57` |
| [experiments/independent_locomotion/test_recorded_curriculum.py](../experiments/independent_locomotion/test_recorded_curriculum.py) | 21 | 목록 확인 | RecordedCurriculumTest | `3a3fa59da4fb` |
| [experiments/independent_locomotion/test_select_matched_resume.py](../experiments/independent_locomotion/test_select_matched_resume.py) | 67 | 목록 확인 | ResumeSelectionTest | `387662bba52d` |
| [experiments/independent_locomotion/train_upper_body_conditioned.py](../experiments/independent_locomotion/train_upper_body_conditioned.py) | 151 | 목록 확인 | main | `cc7a677ee9c2` |
| [experiments/independent_locomotion/upper_body_conditioned_env.py](../experiments/independent_locomotion/upper_body_conditioned_env.py) | 229 | 목록 확인 | _upper_state, apply_smooth_upper_target, apply_fixed_upper_target, recorded_scale_at_step, apply_recorded_upper_target (+2) | `11d30118cf5d` |
| [experiments/independent_locomotion/verify_mjlab.sh](../experiments/independent_locomotion/verify_mjlab.sh) | 26 | 목록 확인 | - | `393f509c6d40` |
| [experiments/independent_locomotion/verify_upper_body_conditioned.sh](../experiments/independent_locomotion/verify_upper_body_conditioned.sh) | 27 | 목록 확인 | - | `fb4c583664c4` |
| [experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat](../experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat) | 30 | 목록 확인 | - | `c17f8f5e265c` |
| [experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat](../experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat) | 26 | 목록 확인 | - | `07f85ccfcd9f` |
| [experiments/startup_recovery_multistrategy/candidate_runner.py](../experiments/startup_recovery_multistrategy/candidate_runner.py) | 39 | 목록 확인 | parse_arguments, main | `20b2e8d8ebca` |
| [experiments/startup_recovery_multistrategy/run_experiment.py](../experiments/startup_recovery_multistrategy/run_experiment.py) | 248 | 목록 확인 | RecoveryCandidate, parse_arguments, load_initial_pose, candidate_score, select_candidate (+3) | `a3e6a8dec3ae` |
| [experiments/startup_recovery_multistrategy/test_experiment.py](../experiments/startup_recovery_multistrategy/test_experiment.py) | 87 | 목록 확인 | MultiStrategyRecoveryExperimentTest | `c97dd80049c2` |
| [experiments/startup_recovery_multistrategy/view_selected.py](../experiments/startup_recovery_multistrategy/view_selected.py) | 37 | 목록 확인 | main | `f277d289ab9e` |
| [experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat) | 30 | 목록 확인 | - | `f77e2ed0bc89` |
| [experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat) | 37 | 목록 확인 | - | `918bc558676d` |
| [experiments/startup_recovery_posture_sweep/run_sweep.py](../experiments/startup_recovery_posture_sweep/run_sweep.py) | 653 | 목록 확인 | SweepCase, ParseOffsets, ParseArguments, LoadPose, BuildProvenance (+12) | `3c1a78a88949` |
| [experiments/startup_recovery_posture_sweep/single_pose_runner.py](../experiments/startup_recovery_posture_sweep/single_pose_runner.py) | 62 | 목록 확인 | ParseArguments, UseIsolatedModel, Main | `577f95fc2bb5` |
| [experiments/startup_recovery_posture_sweep/test_sweep.py](../experiments/startup_recovery_posture_sweep/test_sweep.py) | 191 | 목록 확인 | StartupRecoveryPostureSweepTests | `fb553c72b128` |
| [experiments/twist2_right_arm_manual/TEST_OFFLINE.bat](../experiments/twist2_right_arm_manual/TEST_OFFLINE.bat) | 18 | 목록 확인 | - | `53a20610cefb` |
| [experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1](../experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1) | 31 | 목록 확인 | - | `52b6c499e266` |
| [experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat](../experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat) | 34 | 목록 확인 | - | `f1af8630a586` |
| [experiments/twist2_right_arm_manual/analyze_cycle_packets.py](../experiments/twist2_right_arm_manual/analyze_cycle_packets.py) | 45 | 목록 확인 | - | `734eea788ea6` |
| [experiments/twist2_right_arm_manual/analyze_pd_abort.py](../experiments/twist2_right_arm_manual/analyze_pd_abort.py) | 35 | 목록 확인 | sha, analyze | `ee2d26b227c8` |
| [experiments/twist2_right_arm_manual/analyze_pd_reach_com.py](../experiments/twist2_right_arm_manual/analyze_pd_reach_com.py) | 55 | 목록 확인 | coefficients, analyze, main | `1e263721fcbc` |
| [experiments/twist2_right_arm_manual/analyze_pd_sweep.py](../experiments/twist2_right_arm_manual/analyze_pd_sweep.py) | 56 | 목록 확인 | rms, analyze, main | `30aa288fdd6e` |
| [experiments/twist2_right_arm_manual/analyze_vr_pd_replay.py](../experiments/twist2_right_arm_manual/analyze_vr_pd_replay.py) | 105 | 목록 확인 | _rms, _percentile, _best_lag, analyze, main | `3582adf15072` |
| [experiments/twist2_right_arm_manual/anchored_alignment_study.py](../experiments/twist2_right_arm_manual/anchored_alignment_study.py) | 81 | 목록 확인 | AnchoredAlignmentStudy | `273d6233cf84` |
| [experiments/twist2_right_arm_manual/anchored_upper_study.hpp](../experiments/twist2_right_arm_manual/anchored_upper_study.hpp) | 122 | 목록 확인 | - | `2905849d8a3b` |
| [experiments/twist2_right_arm_manual/arm_cycle_offline.hpp](../experiments/twist2_right_arm_manual/arm_cycle_offline.hpp) | 101 | 목록 확인 | - | `258d981d7543` |
| [experiments/twist2_right_arm_manual/arm_cycle_stdio_offline.cpp](../experiments/twist2_right_arm_manual/arm_cycle_stdio_offline.cpp) | 26 | 목록 확인 | - | `3fe0eba3dc09` |
| [experiments/twist2_right_arm_manual/audit_fresh_seed_mink.py](../experiments/twist2_right_arm_manual/audit_fresh_seed_mink.py) | 67 | 목록 확인 | Main | `41b7427040c6` |
| [experiments/twist2_right_arm_manual/audit_identification_run.py](../experiments/twist2_right_arm_manual/audit_identification_run.py) | 66 | 목록 확인 | sha, audit | `d46d71c98a0c` |
| [experiments/twist2_right_arm_manual/audit_mink_precision.py](../experiments/twist2_right_arm_manual/audit_mink_precision.py) | 299 | 목록 확인 | pose, residual, witness, run_case, main | `9cc036ed1f88` |
| [experiments/twist2_right_arm_manual/audit_mink_resampler_geometry.py](../experiments/twist2_right_arm_manual/audit_mink_resampler_geometry.py) | 42 | 목록 확인 | - | `5b17af4d8b50` |
| [experiments/twist2_right_arm_manual/audit_mink_torch_combined_geometry.py](../experiments/twist2_right_arm_manual/audit_mink_torch_combined_geometry.py) | 52 | 목록 확인 | - | `cac9b16816b7` |
| [experiments/twist2_right_arm_manual/audit_native_relay.cpp](../experiments/twist2_right_arm_manual/audit_native_relay.cpp) | 16 | 목록 확인 | - | `3ed80f9c2c25` |
| [experiments/twist2_right_arm_manual/audit_saved_alignment.cpp](../experiments/twist2_right_arm_manual/audit_saved_alignment.cpp) | 38 | 목록 확인 | - | `b0ee0a8c0038` |
| [experiments/twist2_right_arm_manual/capture_hg_readonly.py](../experiments/twist2_right_arm_manual/capture_hg_readonly.py) | 79 | 목록 확인 | SelectInterface, Pack, Main | `eb0de95e3845` |
| [experiments/twist2_right_arm_manual/check_pc_receive_under_load.py](../experiments/twist2_right_arm_manual/check_pc_receive_under_load.py) | 69 | 목록 확인 | Worker, Main | `d6eb51e0810f` |
| [experiments/twist2_right_arm_manual/compare_feedback_recorded_offline.py](../experiments/twist2_right_arm_manual/compare_feedback_recorded_offline.py) | 86 | 목록 확인 | Gyro, Run | `8281d35e3ca0` |
| [experiments/twist2_right_arm_manual/compare_ik_targets.py](../experiments/twist2_right_arm_manual/compare_ik_targets.py) | 73 | 목록 확인 | load, compare | `02b12cda6c2b` |
| [experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py](../experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py) | 156 | 목록 확인 | read_episode, run, main | `b31397fc1af6` |
| [experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py](../experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py) | 84 | 목록 확인 | run, main | `00978dbe3baa` |
| [experiments/twist2_right_arm_manual/compare_native_writer_csv.py](../experiments/twist2_right_arm_manual/compare_native_writer_csv.py) | 49 | 목록 확인 | Compare | `5e50ab8db801` |
| [experiments/twist2_right_arm_manual/compare_seed_windows_offline.py](../experiments/twist2_right_arm_manual/compare_seed_windows_offline.py) | 49 | 목록 확인 | Metrics, Main | `ee3abda2ef7f` |
| [experiments/twist2_right_arm_manual/data/pitch_wrist_episode_20260910.provenance.json](../experiments/twist2_right_arm_manual/data/pitch_wrist_episode_20260910.provenance.json) | 12 | 목록 확인 | - | `44acc4b965f8` |
| [experiments/twist2_right_arm_manual/diagnose_mink_wrist_tradeoff.py](../experiments/twist2_right_arm_manual/diagnose_mink_wrist_tradeoff.py) | 50 | 목록 확인 | - | `502eaadd6365` |
| [experiments/twist2_right_arm_manual/diagnose_mujoco_stance_offline.py](../experiments/twist2_right_arm_manual/diagnose_mujoco_stance_offline.py) | 53 | 목록 확인 | contact_snapshot, run, main | `66f1e55226da` |
| [experiments/twist2_right_arm_manual/guarded_composition_offline.hpp](../experiments/twist2_right_arm_manual/guarded_composition_offline.hpp) | 145 | 목록 확인 | - | `20c6c482bd15` |
| [experiments/twist2_right_arm_manual/inspect_g1_native_readonly.sh](../experiments/twist2_right_arm_manual/inspect_g1_native_readonly.sh) | 26 | 목록 확인 | - | `01ef2f146a92` |
| [experiments/twist2_right_arm_manual/inspect_wsl_sdk_readonly.py](../experiments/twist2_right_arm_manual/inspect_wsl_sdk_readonly.py) | 58 | 목록 확인 | Inspect, Main | `4d0a87bd13f9` |
| [experiments/twist2_right_arm_manual/joint_limit_guard.py](../experiments/twist2_right_arm_manual/joint_limit_guard.py) | 194 | 목록 확인 | vector, LimitViolation, JointLimitEnvelope, JointLimitMonitor | `79fedc75b0d3` |
| [experiments/twist2_right_arm_manual/lowstate_seed_writer.py](../experiments/twist2_right_arm_manual/lowstate_seed_writer.py) | 42 | 목록 확인 | SeedWriter | `4798e41d35a5` |
| [experiments/twist2_right_arm_manual/measured_composition_offline.hpp](../experiments/twist2_right_arm_manual/measured_composition_offline.hpp) | 143 | 목록 확인 | - | `1cf1b7143683` |
| [experiments/twist2_right_arm_manual/mink_cycle_candidate_offline.hpp](../experiments/twist2_right_arm_manual/mink_cycle_candidate_offline.hpp) | 124 | 목록 확인 | - | `6ab7cc442778` |
| [experiments/twist2_right_arm_manual/mink_cycle_candidate_stdio_offline.cpp](../experiments/twist2_right_arm_manual/mink_cycle_candidate_stdio_offline.cpp) | 21 | 목록 확인 | - | `b37820d582e7` |
| [experiments/twist2_right_arm_manual/mink_cycle_owner_offline.hpp](../experiments/twist2_right_arm_manual/mink_cycle_owner_offline.hpp) | 147 | 목록 확인 | - | `c6b57412224a` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_contract.hpp](../experiments/twist2_right_arm_manual/mink_live_cycle_contract.hpp) | 190 | 목록 확인 | - | `bca168cf72bb` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_stdio_test.cpp](../experiments/twist2_right_arm_manual/mink_live_cycle_stdio_test.cpp) | 15 | 목록 확인 | - | `a34c81cfeab3` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_target.hpp](../experiments/twist2_right_arm_manual/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `f9556d12cdd7` |
| [experiments/twist2_right_arm_manual/mink_resampler_batch_offline.cpp](../experiments/twist2_right_arm_manual/mink_resampler_batch_offline.cpp) | 21 | 목록 확인 | - | `3df65167f30b` |
| [experiments/twist2_right_arm_manual/mink_resampler_offline.hpp](../experiments/twist2_right_arm_manual/mink_resampler_offline.hpp) | 81 | 목록 확인 | - | `c9f3f786eed4` |
| [experiments/twist2_right_arm_manual/mink_torch_owner_stdio_offline.cpp](../experiments/twist2_right_arm_manual/mink_torch_owner_stdio_offline.cpp) | 78 | 목록 확인 | - | `cb9de05e1b28` |
| [experiments/twist2_right_arm_manual/mink_udp_target.hpp](../experiments/twist2_right_arm_manual/mink_udp_target.hpp) | 53 | 목록 확인 | - | `de32b2bb7c9f` |
| [experiments/twist2_right_arm_manual/mujoco_feedback_offline.py](../experiments/twist2_right_arm_manual/mujoco_feedback_offline.py) | 58 | 목록 확인 | Dynamics, main | `fe5f557e621a` |
| [experiments/twist2_right_arm_manual/mujoco_pd_accuracy_stability.py](../experiments/twist2_right_arm_manual/mujoco_pd_accuracy_stability.py) | 326 | 목록 확인 | read, save, pair, collect_arrays, stability (+8) | `beeaa1ba453d` |
| [experiments/twist2_right_arm_manual/mujoco_pd_contract.py](../experiments/twist2_right_arm_manual/mujoco_pd_contract.py) | 144 | 목록 확인 | Contract, load_contract, Point, RoundTrip, candidate_gains (+1) | `c16f65cc16ab` |
| [experiments/twist2_right_arm_manual/mujoco_pd_coupled_matrix.py](../experiments/twist2_right_arm_manual/mujoco_pd_coupled_matrix.py) | 150 | 목록 확인 | source_records, missing_jobs, summarize, verify_extra, audit (+1) | `08f89c0f4b3c` |
| [experiments/twist2_right_arm_manual/mujoco_pd_coupled_stress.py](../experiments/twist2_right_arm_manual/mujoco_pd_coupled_stress.py) | 295 | 목록 확인 | Coupled, new_conditions, read, save, pair (+8) | `a85ccaf5cce5` |
| [experiments/twist2_right_arm_manual/mujoco_pd_expand.py](../experiments/twist2_right_arm_manual/mujoco_pd_expand.py) | 207 | 목록 확인 | block_network, init_worker, save_json, key, nominal_rank (+7) | `7baa8d173a02` |
| [experiments/twist2_right_arm_manual/mujoco_pd_expand_audit.py](../experiments/twist2_right_arm_manual/mujoco_pd_expand_audit.py) | 171 | 목록 확인 | require, sha, read, safe_path, metric_values (+3) | `261c2105590e` |
| [experiments/twist2_right_arm_manual/mujoco_pd_final.py](../experiments/twist2_right_arm_manual/mujoco_pd_final.py) | 320 | 목록 확인 | conditions, normalize, require, read, write_new (+8) | `5a678ffcda6a` |
| [experiments/twist2_right_arm_manual/mujoco_pd_fixture.py](../experiments/twist2_right_arm_manual/mujoco_pd_fixture.py) | 36 | 목록 확인 | preserve_root_parent_filter | `7f9eec1c2be8` |
| [experiments/twist2_right_arm_manual/mujoco_pd_independent_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_independent_study.py) | 227 | 목록 확인 | motions, jobs, run_case, summarize, check_guard (+6) | `69722cd68780` |
| [experiments/twist2_right_arm_manual/mujoco_pd_independent_timing.py](../experiments/twist2_right_arm_manual/mujoco_pd_independent_timing.py) | 216 | 목록 확인 | Motion, Timeline, simulate, evaluate | `9769340a87b3` |
| [experiments/twist2_right_arm_manual/mujoco_pd_limit_replay.py](../experiments/twist2_right_arm_manual/mujoco_pd_limit_replay.py) | 124 | 목록 확인 | load_plan, run_case, verify_guard_result, summarize, main | `695fbd0b21f4` |
| [experiments/twist2_right_arm_manual/mujoco_pd_minerror.py](../experiments/twist2_right_arm_manual/mujoco_pd_minerror.py) | 311 | 목록 확인 | validation_plan, grid, save, read, pair (+9) | `b6087560c605` |
| [experiments/twist2_right_arm_manual/mujoco_pd_motor_stress.py](../experiments/twist2_right_arm_manual/mujoco_pd_motor_stress.py) | 136 | 목록 확인 | TorquePath, simulate, summarize, main | `7203e5989f72` |
| [experiments/twist2_right_arm_manual/mujoco_pd_multiaxis.py](../experiments/twist2_right_arm_manual/mujoco_pd_multiaxis.py) | 152 | 목록 확인 | Motion, simulate, evaluate | `3a90257b1864` |
| [experiments/twist2_right_arm_manual/mujoco_pd_multiaxis_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_multiaxis_study.py) | 204 | 목록 확인 | norm, read, save, require, conditions (+7) | `9d662f064380` |
| [experiments/twist2_right_arm_manual/mujoco_pd_multiaxis_yaw.py](../experiments/twist2_right_arm_manual/mujoco_pd_multiaxis_yaw.py) | 176 | 목록 확인 | vectors, screen_conditions, validation_conditions, jobs, ranking (+5) | `0a31c62633be` |
| [experiments/twist2_right_arm_manual/mujoco_pd_operating_core.py](../experiments/twist2_right_arm_manual/mujoco_pd_operating_core.py) | 198 | 목록 확인 | Profile, Path, profile_contract, simulate, evaluate | `240522131ae6` |
| [experiments/twist2_right_arm_manual/mujoco_pd_operating_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_operating_study.py) | 212 | 목록 확인 | profiles, make_plan, read, save, run_case (+5) | `0cc084897cb0` |
| [experiments/twist2_right_arm_manual/mujoco_pd_perjoint.py](../experiments/twist2_right_arm_manual/mujoco_pd_perjoint.py) | 132 | 목록 확인 | Gains, scoped_gains, simulate, write_case, gain_key (+2) | `ddb99defd265` |
| [experiments/twist2_right_arm_manual/mujoco_pd_perjoint_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_perjoint_study.py) | 222 | 목록 확인 | read, save, normalize, change, search_conditions (+8) | `e9c7960968c0` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_core.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_core.py) | 171 | 목록 확인 | writer_target, simulate, evaluate | `70c1c601dd50` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_pitch_wrist.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_pitch_wrist.py) | 336 | 목록 확인 | specification, validate, spec_of, identity, research_scope (+11) | `080a6c3d0b30` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_ramp_core.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_ramp_core.py) | 130 | 목록 확인 | causal_reference, evaluate, simulate | `266be9c344ef` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_ramp_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_ramp_study.py) | 262 | 목록 확인 | save, read, norm, require, jobs (+9) | `0f7e799de7d4` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_roll_yaw.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_roll_yaw.py) | 271 | 목록 확인 | norm, save, read, require, identity (+16) | `a2788a96c23c` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recorded_study.py](../experiments/twist2_right_arm_manual/mujoco_pd_recorded_study.py) | 251 | 목록 확인 | save, read, norm, require, jobs (+9) | `186a37327359` |
| [experiments/twist2_right_arm_manual/mujoco_pd_recording.py](../experiments/twist2_right_arm_manual/mujoco_pd_recording.py) | 174 | 목록 확인 | strict_json, finite, Capture, extract | `785a865c5404` |
| [experiments/twist2_right_arm_manual/mujoco_pd_robust_refine.py](../experiments/twist2_right_arm_manual/mujoco_pd_robust_refine.py) | 324 | 목록 확인 | Scenario, pair_of, gain_pairs, rank_pairs, choose_finalists (+6) | `cc808d299f5e` |
| [experiments/twist2_right_arm_manual/mujoco_pd_sweep.py](../experiments/twist2_right_arm_manual/mujoco_pd_sweep.py) | 378 | 목록 확인 | sha256, source_hashes, write_json, load_model, summarize (+2) | `347f25a3fe9e` |
| [experiments/twist2_right_arm_manual/mujoco_pd_validate_results.py](../experiments/twist2_right_arm_manual/mujoco_pd_validate_results.py) | 160 | 목록 확인 | digest, require, validate, compare, main | `f6eed419198c` |
| [experiments/twist2_right_arm_manual/mujoco_pd_yaw_regression.py](../experiments/twist2_right_arm_manual/mujoco_pd_yaw_regression.py) | 225 | 목록 확인 | conditions, accepted, receipt, plan, dependencies (+4) | `9499ca6d092e` |
| [experiments/twist2_right_arm_manual/native_command_limits.hpp](../experiments/twist2_right_arm_manual/native_command_limits.hpp) | 17 | 목록 확인 | - | `9386a23a5c70` |
| [experiments/twist2_right_arm_manual/native_composition_offline.hpp](../experiments/twist2_right_arm_manual/native_composition_offline.hpp) | 39 | 목록 확인 | - | `008bc9b05bd9` |
| [experiments/twist2_right_arm_manual/native_relative_reference.hpp](../experiments/twist2_right_arm_manual/native_relative_reference.hpp) | 17 | 목록 확인 | - | `e7dbe4abcb20` |
| [experiments/twist2_right_arm_manual/native_relay_contract.hpp](../experiments/twist2_right_arm_manual/native_relay_contract.hpp) | 22 | 목록 확인 | - | `d3fe4a0fdf3c` |
| [experiments/twist2_right_arm_manual/native_snapshot_freshness.hpp](../experiments/twist2_right_arm_manual/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `7b9026980e86` |
| [experiments/twist2_right_arm_manual/native_state_audit.hpp](../experiments/twist2_right_arm_manual/native_state_audit.hpp) | 43 | 목록 확인 | - | `89dd0017fc29` |
| [experiments/twist2_right_arm_manual/native_state_tick.hpp](../experiments/twist2_right_arm_manual/native_state_tick.hpp) | 8 | 목록 확인 | - | `ff86033bf355` |
| [experiments/twist2_right_arm_manual/native_stop_audit.hpp](../experiments/twist2_right_arm_manual/native_stop_audit.hpp) | 34 | 목록 확인 | - | `3bdb344a9806` |
| [experiments/twist2_right_arm_manual/native_vr_cycle_udp.hpp](../experiments/twist2_right_arm_manual/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `2424fa527778` |
| [experiments/twist2_right_arm_manual/native_vr_invocation.hpp](../experiments/twist2_right_arm_manual/native_vr_invocation.hpp) | 10 | 목록 확인 | - | `f318dd20c768` |
| [experiments/twist2_right_arm_manual/native_vr_policy_adapter.hpp](../experiments/twist2_right_arm_manual/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `0c1ad7b3890c` |
| [experiments/twist2_right_arm_manual/native_vr_udp.hpp](../experiments/twist2_right_arm_manual/native_vr_udp.hpp) | 53 | 목록 확인 | - | `d5e6515d60e3` |
| [experiments/twist2_right_arm_manual/observe_seed_file_offline.py](../experiments/twist2_right_arm_manual/observe_seed_file_offline.py) | 32 | 목록 확인 | Main | `87efe04c6270` |
| [experiments/twist2_right_arm_manual/offline_blend.hpp](../experiments/twist2_right_arm_manual/offline_blend.hpp) | 39 | 목록 확인 | - | `d8fa6f767643` |
| [experiments/twist2_right_arm_manual/offline_dispatch.hpp](../experiments/twist2_right_arm_manual/offline_dispatch.hpp) | 63 | 목록 확인 | - | `e0c3835ea227` |
| [experiments/twist2_right_arm_manual/offline_hg_native_decoder.hpp](../experiments/twist2_right_arm_manual/offline_hg_native_decoder.hpp) | 62 | 목록 확인 | - | `2199a994afc4` |
| [experiments/twist2_right_arm_manual/offline_lag_fixture.hpp](../experiments/twist2_right_arm_manual/offline_lag_fixture.hpp) | 11 | 목록 확인 | - | `3874fc95bb42` |
| [experiments/twist2_right_arm_manual/offline_observation_history.hpp](../experiments/twist2_right_arm_manual/offline_observation_history.hpp) | 69 | 목록 확인 | - | `bbc93ab1c5ff` |
| [experiments/twist2_right_arm_manual/offline_owner.hpp](../experiments/twist2_right_arm_manual/offline_owner.hpp) | 185 | 목록 확인 | - | `52a200f196e8` |
| [experiments/twist2_right_arm_manual/offline_policy_adapter.py](../experiments/twist2_right_arm_manual/offline_policy_adapter.py) | 39 | 목록 확인 | ReadVerifiedPolicy, AdaptOutput | `9d57a80b407d` |
| [experiments/twist2_right_arm_manual/offline_state_continuity.hpp](../experiments/twist2_right_arm_manual/offline_state_continuity.hpp) | 35 | 목록 확인 | - | `14dd397a15bd` |
| [experiments/twist2_right_arm_manual/offline_twist2_constants.hpp](../experiments/twist2_right_arm_manual/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `517a651ecfc9` |
| [experiments/twist2_right_arm_manual/offline_word_crc.hpp](../experiments/twist2_right_arm_manual/offline_word_crc.hpp) | 21 | 목록 확인 | - | `d2cc2f9f6cf4` |
| [experiments/twist2_right_arm_manual/offline_writer_study.hpp](../experiments/twist2_right_arm_manual/offline_writer_study.hpp) | 93 | 목록 확인 | - | `b8ecfcf152c8` |
| [experiments/twist2_right_arm_manual/owner_policy_stdio.cpp](../experiments/twist2_right_arm_manual/owner_policy_stdio.cpp) | 151 | 목록 확인 | - | `dd5b882c6228` |
| [experiments/twist2_right_arm_manual/pc_native_receive_probe.cpp](../experiments/twist2_right_arm_manual/pc_native_receive_probe.cpp) | 73 | 목록 확인 | - | `ea5eee7a25d6` |
| [experiments/twist2_right_arm_manual/pd_gain_comparison.py](../experiments/twist2_right_arm_manual/pd_gain_comparison.py) | 115 | 목록 확인 | sha, candidates, evaluate, main | `de9e5d625607` |
| [experiments/twist2_right_arm_manual/pd_gain_options.hpp](../experiments/twist2_right_arm_manual/pd_gain_options.hpp) | 59 | 목록 확인 | - | `a992fe6591f1` |
| [experiments/twist2_right_arm_manual/pd_joint_trial.hpp](../experiments/twist2_right_arm_manual/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `e760154bb5a4` |
| [experiments/twist2_right_arm_manual/pd_reach_reference.hpp](../experiments/twist2_right_arm_manual/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `ca0f771ddfd2` |
| [experiments/twist2_right_arm_manual/pd_reach_timing.py](../experiments/twist2_right_arm_manual/pd_reach_timing.py) | 74 | 목록 확인 | check_acceleration, make_timing, choose_timing | `6c19e039aad6` |
| [experiments/twist2_right_arm_manual/pd_reach_trial.hpp](../experiments/twist2_right_arm_manual/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `a58197aaec1e` |
| [experiments/twist2_right_arm_manual/pd_ready_settle.hpp](../experiments/twist2_right_arm_manual/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `a33e931e51aa` |
| [experiments/twist2_right_arm_manual/pd_small_signal_trial.hpp](../experiments/twist2_right_arm_manual/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `a7b8562ab1ac` |
| [experiments/twist2_right_arm_manual/pd_trial_offline.py](../experiments/twist2_right_arm_manual/pd_trial_offline.py) | 138 | 목록 확인 | duration, segment, generate, review, main | `f915a56269b4` |
| [experiments/twist2_right_arm_manual/periodic_csv.hpp](../experiments/twist2_right_arm_manual/periodic_csv.hpp) | 67 | 목록 확인 | - | `4cd81484c2f5` |
| [experiments/twist2_right_arm_manual/plan_pd_followup_from_vr.py](../experiments/twist2_right_arm_manual/plan_pd_followup_from_vr.py) | 45 | 목록 확인 | build, main | `c3c351581f0a` |
| [experiments/twist2_right_arm_manual/plan_pd_reach_offline.py](../experiments/twist2_right_arm_manual/plan_pd_reach_offline.py) | 147 | 목록 확인 | plan | `b82de126115d` |
| [experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py](../experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py) | 37 | 목록 확인 | - | `68e32a5acbd1` |
| [experiments/twist2_right_arm_manual/policy_worker_client_offline.py](../experiments/twist2_right_arm_manual/policy_worker_client_offline.py) | 108 | 목록 확인 | PolicyWorkerError, PolicyWorkerClient | `2d52128fce6c` |
| [experiments/twist2_right_arm_manual/prepare_hg_class_fixture.py](../experiments/twist2_right_arm_manual/prepare_hg_class_fixture.py) | 22 | 목록 확인 | Prepare | `396eef0a653d` |
| [experiments/twist2_right_arm_manual/prepare_observation_reference.py](../experiments/twist2_right_arm_manual/prepare_observation_reference.py) | 33 | 목록 확인 | PrepareObservation | `0afd8a06c0d5` |
| [experiments/twist2_right_arm_manual/probe_mujoco_pd_contacts.py](../experiments/twist2_right_arm_manual/probe_mujoco_pd_contacts.py) | 67 | 목록 확인 | main | `0d34e7c6ab10` |
| [experiments/twist2_right_arm_manual/probe_seed_file_sharing.py](../experiments/twist2_right_arm_manual/probe_seed_file_sharing.py) | 53 | 목록 확인 | Main | `0f90bbd0b9c9` |
| [experiments/twist2_right_arm_manual/probe_udp_receive_only.py](../experiments/twist2_right_arm_manual/probe_udp_receive_only.py) | 29 | 목록 확인 | main | `cce2813246fb` |
| [experiments/twist2_right_arm_manual/prototype_mink_task_priority.py](../experiments/twist2_right_arm_manual/prototype_mink_task_priority.py) | 64 | 목록 확인 | TaskPriorityPrototype | `d7fbeec1bba0` |
| [experiments/twist2_right_arm_manual/queued_input_offline.hpp](../experiments/twist2_right_arm_manual/queued_input_offline.hpp) | 111 | 목록 확인 | - | `41787f9e8b3e` |
| [experiments/twist2_right_arm_manual/raw_input_watch_offline.hpp](../experiments/twist2_right_arm_manual/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `7f614be48562` |
| [experiments/twist2_right_arm_manual/real_response_frame.hpp](../experiments/twist2_right_arm_manual/real_response_frame.hpp) | 79 | 목록 확인 | - | `b47e4def6d9c` |
| [experiments/twist2_right_arm_manual/real_response_identification.py](../experiments/twist2_right_arm_manual/real_response_identification.py) | 63 | 목록 확인 | _matrix, estimate, main | `3e9cac7651d2` |
| [experiments/twist2_right_arm_manual/real_response_log.py](../experiments/twist2_right_arm_manual/real_response_log.py) | 167 | 목록 확인 | _strict_loads, _finite_number, validate_record, Trace, parse_trace (+1) | `33d98438c179` |
| [experiments/twist2_right_arm_manual/receive_only.cpp](../experiments/twist2_right_arm_manual/receive_only.cpp) | 109 | 목록 확인 | - | `2a4aaf38e165` |
| [experiments/twist2_right_arm_manual/receive_target_shadow.cpp](../experiments/twist2_right_arm_manual/receive_target_shadow.cpp) | 258 | 목록 확인 | - | `4f0f6334fc69` |
| [experiments/twist2_right_arm_manual/receive_vr_shadow.py](../experiments/twist2_right_arm_manual/receive_vr_shadow.py) | 124 | 목록 확인 | Run, main | `6f795b505a5e` |
| [experiments/twist2_right_arm_manual/regular_handoff_safety.hpp](../experiments/twist2_right_arm_manual/regular_handoff_safety.hpp) | 93 | 목록 확인 | - | `9b1408f2edb1` |
| [experiments/twist2_right_arm_manual/replay_cpp_input_tick.py](../experiments/twist2_right_arm_manual/replay_cpp_input_tick.py) | 147 | 목록 확인 | LoadEncoder, BuildTicks, Replay, main | `c5aff9ef2f87` |
| [experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py](../experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py) | 117 | 목록 확인 | Replay | `95a01bcd17a5` |
| [experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py](../experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py) | 104 | 목록 확인 | F32, Run | `704f4a877d22` |
| [experiments/twist2_right_arm_manual/replay_live_cycle_protocol.py](../experiments/twist2_right_arm_manual/replay_live_cycle_protocol.py) | 43 | 목록 확인 | run | `ac7355fb702e` |
| [experiments/twist2_right_arm_manual/replay_mink_boundary.py](../experiments/twist2_right_arm_manual/replay_mink_boundary.py) | 74 | 목록 확인 | main | `84364828f2fa` |
| [experiments/twist2_right_arm_manual/replay_mink_cycle_candidate_offline.py](../experiments/twist2_right_arm_manual/replay_mink_cycle_candidate_offline.py) | 89 | 목록 확인 | main | `7f75364a6a60` |
| [experiments/twist2_right_arm_manual/replay_mink_torch_owner.py](../experiments/twist2_right_arm_manual/replay_mink_torch_owner.py) | 85 | 목록 확인 | exchange | `f960cbc60d18` |
| [experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py) | 219 | 목록 확인 | PhysicalSample, _FiniteValue, LoadPhysicalCsv, BuildSummary, ParseArguments (+1) | `9d611fbdf982` |
| [experiments/twist2_right_arm_manual/replay_upstream_mink.py](../experiments/twist2_right_arm_manual/replay_upstream_mink.py) | 72 | 목록 확인 | build, main | `45bc54d5b671` |
| [experiments/twist2_right_arm_manual/replay_writer_policy_trace.py](../experiments/twist2_right_arm_manual/replay_writer_policy_trace.py) | 168 | 목록 확인 | Run | `42d7782e529f` |
| [experiments/twist2_right_arm_manual/review_hg_capture_offline.py](../experiments/twist2_right_arm_manual/review_hg_capture_offline.py) | 56 | 목록 확인 | Crc, Review | `a7ec92697fa5` |
| [experiments/twist2_right_arm_manual/review_loaded_settle.py](../experiments/twist2_right_arm_manual/review_loaded_settle.py) | 68 | 목록 확인 | Windows, Review | `5f0b9b3b3f38` |
| [experiments/twist2_right_arm_manual/review_pd_terms.py](../experiments/twist2_right_arm_manual/review_pd_terms.py) | 53 | 목록 확인 | terms, review | `d215208a9875` |
| [experiments/twist2_right_arm_manual/review_ready_components.py](../experiments/twist2_right_arm_manual/review_ready_components.py) | 63 | 목록 확인 | Review | `c65232bcecb1` |
| [experiments/twist2_right_arm_manual/review_seed_velocity.py](../experiments/twist2_right_arm_manual/review_seed_velocity.py) | 58 | 목록 확인 | TriggerWindow, JointStats, Main | `b340b8eccc1a` |
| [experiments/twist2_right_arm_manual/run_event_clock_offline.py](../experiments/twist2_right_arm_manual/run_event_clock_offline.py) | 211 | 목록 확인 | Run | `951f33ea5089` |
| [experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py](../experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py) | 133 | 목록 확인 | Main | `c5f3fa50d3ec` |
| [experiments/twist2_right_arm_manual/run_owner_cpu_offline.py](../experiments/twist2_right_arm_manual/run_owner_cpu_offline.py) | 90 | 목록 확인 | Owner, Main | `da7b688db639` |
| [experiments/twist2_right_arm_manual/run_pc_twist2.sh](../experiments/twist2_right_arm_manual/run_pc_twist2.sh) | 44 | 목록 확인 | - | `e3a47b8fa3cf` |
| [experiments/twist2_right_arm_manual/run_policy_cpu_offline.py](../experiments/twist2_right_arm_manual/run_policy_cpu_offline.py) | 51 | 목록 확인 | Smoke | `73b08a08428e` |
| [experiments/twist2_right_arm_manual/run_policy_history_offline.py](../experiments/twist2_right_arm_manual/run_policy_history_offline.py) | 105 | 목록 확인 | F32, Run | `c9f4658a0539` |
| [experiments/twist2_right_arm_manual/split_ready_study.py](../experiments/twist2_right_arm_manual/split_ready_study.py) | 82 | 목록 확인 | Limits, SplitReadyStudy | `eb9b96c23156` |
| [experiments/twist2_right_arm_manual/split_settle_window.hpp](../experiments/twist2_right_arm_manual/split_settle_window.hpp) | 50 | 목록 확인 | - | `2bea831c9f79` |
| [experiments/twist2_right_arm_manual/split_vr_adapter_study.hpp](../experiments/twist2_right_arm_manual/split_vr_adapter_study.hpp) | 97 | 목록 확인 | - | `24efeced795c` |
| [experiments/twist2_right_arm_manual/study_vr_packet_spacing.cpp](../experiments/twist2_right_arm_manual/study_vr_packet_spacing.cpp) | 39 | 목록 확인 | - | `c247c10e9ca7` |
| [experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py](../experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py) | 64 | 목록 확인 | JointNames, Main | `61344130c2d4` |
| [experiments/twist2_right_arm_manual/sysid_async_model.py](../experiments/twist2_right_arm_manual/sysid_async_model.py) | 138 | 목록 확인 | freeze, episodes, basis, _plan, fit (+1) | `1691252d537c` |
| [experiments/twist2_right_arm_manual/sysid_capture.py](../experiments/twist2_right_arm_manual/sysid_capture.py) | 181 | 목록 확인 | canonical, digest, decode, finite_tree, vector (+3) | `ca7a79cba197` |
| [experiments/twist2_right_arm_manual/sysid_excitation_crosscheck.py](../experiments/twist2_right_arm_manual/sysid_excitation_crosscheck.py) | 96 | 목록 확인 | _number, compare, main | `09101542d744` |
| [experiments/twist2_right_arm_manual/sysid_excitation_observer_bridge.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_observer_bridge.hpp) | 95 | 목록 확인 | - | `43a4008629a1` |
| [experiments/twist2_right_arm_manual/sysid_excitation_plan.py](../experiments/twist2_right_arm_manual/sysid_excitation_plan.py) | 161 | 목록 확인 | _finite_vector, _validate, _duration, _episode, build (+1) | `6eebe26261ac` |
| [experiments/twist2_right_arm_manual/sysid_excitation_plan_adapter.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_plan_adapter.hpp) | 258 | 목록 확인 | - | `68e2143c7bf4` |
| [experiments/twist2_right_arm_manual/sysid_excitation_plan_check.cpp](../experiments/twist2_right_arm_manual/sysid_excitation_plan_check.cpp) | 30 | 목록 확인 | - | `5fe284519411` |
| [experiments/twist2_right_arm_manual/sysid_excitation_plan_dump.cpp](../experiments/twist2_right_arm_manual/sysid_excitation_plan_dump.cpp) | 72 | 목록 확인 | - | `b3f12308d8bf` |
| [experiments/twist2_right_arm_manual/sysid_excitation_preview.py](../experiments/twist2_right_arm_manual/sysid_excitation_preview.py) | 99 | 목록 확인 | _smooth, _speed, _acceleration, expand, write (+1) | `2dc3ebb578a5` |
| [experiments/twist2_right_arm_manual/sysid_excitation_readiness.py](../experiments/twist2_right_arm_manual/sysid_excitation_readiness.py) | 118 | 목록 확인 | _load_plan, inspect, main | `e7ca43c23131` |
| [experiments/twist2_right_arm_manual/sysid_excitation_reference.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_reference.hpp) | 56 | 목록 확인 | - | `953c5c697fa8` |
| [experiments/twist2_right_arm_manual/sysid_excitation_request.py](../experiments/twist2_right_arm_manual/sysid_excitation_request.py) | 113 | 목록 확인 | _arrays, _spec, create, main | `3505ba3f6d67` |
| [experiments/twist2_right_arm_manual/sysid_excitation_runtime.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_runtime.hpp) | 150 | 목록 확인 | - | `0ef2e1ade46f` |
| [experiments/twist2_right_arm_manual/sysid_excitation_sequence.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_sequence.hpp) | 195 | 목록 확인 | - | `5266b24d0fb7` |
| [experiments/twist2_right_arm_manual/sysid_excitation_writer_hook.hpp](../experiments/twist2_right_arm_manual/sysid_excitation_writer_hook.hpp) | 119 | 목록 확인 | - | `a2c747cd4161` |
| [experiments/twist2_right_arm_manual/sysid_inspect_legacy.py](../experiments/twist2_right_arm_manual/sysid_inspect_legacy.py) | 37 | 목록 확인 | inspect | `00cb7f9a0b7c` |
| [experiments/twist2_right_arm_manual/sysid_model.py](../experiments/twist2_right_arm_manual/sysid_model.py) | 164 | 목록 확인 | create_plan, load_set, load_plan, fit, validate_model (+1) | `8373b660bd3b` |
| [experiments/twist2_right_arm_manual/sysid_native_observer.hpp](../experiments/twist2_right_arm_manual/sysid_native_observer.hpp) | 196 | 목록 확인 | - | `68f46ea523dc` |
| [experiments/twist2_right_arm_manual/sysid_quiet_stats.py](../experiments/twist2_right_arm_manual/sysid_quiet_stats.py) | 29 | 목록 확인 | summarize | `441d1aaa616a` |
| [experiments/twist2_right_arm_manual/sysid_readonly_dds.cpp](../experiments/twist2_right_arm_manual/sysid_readonly_dds.cpp) | 134 | 목록 확인 | - | `6e6f20360e8a` |
| [experiments/twist2_right_arm_manual/sysid_readonly_parse.py](../experiments/twist2_right_arm_manual/sysid_readonly_parse.py) | 77 | 목록 확인 | _decode, _vector, read, inspect | `59b208042ec0` |
| [experiments/twist2_right_arm_manual/test_analyze_pd_sweep.py](../experiments/twist2_right_arm_manual/test_analyze_pd_sweep.py) | 38 | 목록 확인 | SweepAnalysisTest | `7a9b2998409f` |
| [experiments/twist2_right_arm_manual/test_analyze_vr_pd_replay.py](../experiments/twist2_right_arm_manual/test_analyze_vr_pd_replay.py) | 33 | 목록 확인 | ReplayAnalysisTest | `0dfc8cc552d4` |
| [experiments/twist2_right_arm_manual/test_anchored_alignment_study.py](../experiments/twist2_right_arm_manual/test_anchored_alignment_study.py) | 95 | 목록 확인 | send, test_recorded_loaded_pose_first_packet_does_not_jump, test_rate_no_overshoot_other_joints_and_fixed_anchor, test_stop_latches, test_missing_packet_freezes_then_timeout_latches (+3) | `dccccb0eb370` |
| [experiments/twist2_right_arm_manual/test_arm_cycle_offline.cpp](../experiments/twist2_right_arm_manual/test_arm_cycle_offline.cpp) | 66 | 목록 확인 | - | `424ec349d35a` |
| [experiments/twist2_right_arm_manual/test_capture_hg_pack.py](../experiments/twist2_right_arm_manual/test_capture_hg_pack.py) | 36 | 목록 확인 | PackingTests | `f833218f26d4` |
| [experiments/twist2_right_arm_manual/test_compare_ik_targets.py](../experiments/twist2_right_arm_manual/test_compare_ik_targets.py) | 52 | 목록 확인 | fixture, ComparisonTests | `af5be8645916` |
| [experiments/twist2_right_arm_manual/test_compare_native_writer_csv.py](../experiments/twist2_right_arm_manual/test_compare_native_writer_csv.py) | 30 | 목록 확인 | test_old_csv_is_not_reconstructed, test_uses_paired_writer_state_and_skips_rejected_duplicate_attempts | `71c20bb2f1d0` |
| [experiments/twist2_right_arm_manual/test_controller_handoff_offline.py](../experiments/twist2_right_arm_manual/test_controller_handoff_offline.py) | 200 | 목록 확인 | ControllerHandoffOfflineTest | `f016a08bc6bd` |
| [experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py](../experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py) | 26 | 목록 확인 | GuardedTests | `398200c86836` |
| [experiments/twist2_right_arm_manual/test_cpp_input_contract.py](../experiments/twist2_right_arm_manual/test_cpp_input_contract.py) | 174 | 목록 확인 | Idle, PythonDisposition, InputContractTests | `6fdd1d6d3ba6` |
| [experiments/twist2_right_arm_manual/test_cpp_input_tick.py](../experiments/twist2_right_arm_manual/test_cpp_input_tick.py) | 125 | 목록 확인 | Received, Tick, InputTickTests, ReplayTests | `c7fb65b0658f` |
| [experiments/twist2_right_arm_manual/test_cpp_measured_composition.py](../experiments/twist2_right_arm_manual/test_cpp_measured_composition.py) | 127 | 목록 확인 | Event, CompositionTests | `edc735a99d5b` |
| [experiments/twist2_right_arm_manual/test_cpp_queued_input.py](../experiments/twist2_right_arm_manual/test_cpp_queued_input.py) | 171 | 목록 확인 | Push, Tick, QueuedInputTests | `b95d7cda8d18` |
| [experiments/twist2_right_arm_manual/test_cpp_receive_only.py](../experiments/twist2_right_arm_manual/test_cpp_receive_only.py) | 41 | 목록 확인 | ReceiveOnlyTest | `3dc8f605eefc` |
| [experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py](../experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py) | 258 | 목록 확인 | ReadRows, ReceiveTargetShadowTests | `4de051188003` |
| [experiments/twist2_right_arm_manual/test_cpp_upper_target.py](../experiments/twist2_right_arm_manual/test_cpp_upper_target.py) | 140 | 목록 확인 | Packet, Event, UpperTargetTests | `2efde9e3b52e` |
| [experiments/twist2_right_arm_manual/test_cpp_validator.py](../experiments/twist2_right_arm_manual/test_cpp_validator.py) | 98 | 목록 확인 | EncodePacket, ValidatorTests | `3c8b80e908c5` |
| [experiments/twist2_right_arm_manual/test_event_clock_loop.cpp](../experiments/twist2_right_arm_manual/test_event_clock_loop.cpp) | 103 | 목록 확인 | - | `7c1192e73c66` |
| [experiments/twist2_right_arm_manual/test_feedback_gyro.py](../experiments/twist2_right_arm_manual/test_feedback_gyro.py) | 16 | 목록 확인 | test_recorded_gyro_order_sign_and_scale, test_missing_is_explicit_and_partial_is_rejected, test_nonfinite_is_rejected | `f12555826e1f` |
| [experiments/twist2_right_arm_manual/test_guarded_composition.cpp](../experiments/twist2_right_arm_manual/test_guarded_composition.cpp) | 78 | 목록 확인 | - | `f5de9f3d4f3c` |
| [experiments/twist2_right_arm_manual/test_guarded_replay.cpp](../experiments/twist2_right_arm_manual/test_guarded_replay.cpp) | 49 | 목록 확인 | - | `ce09a32a746e` |
| [experiments/twist2_right_arm_manual/test_hg_native_decoder.cpp](../experiments/twist2_right_arm_manual/test_hg_native_decoder.cpp) | 72 | 목록 확인 | - | `34cbc7837272` |
| [experiments/twist2_right_arm_manual/test_identification_audit.py](../experiments/twist2_right_arm_manual/test_identification_audit.py) | 43 | 목록 확인 | AuditTest | `679320353e3f` |
| [experiments/twist2_right_arm_manual/test_input_validator.cpp](../experiments/twist2_right_arm_manual/test_input_validator.cpp) | 17 | 목록 확인 | - | `555992172d74` |
| [experiments/twist2_right_arm_manual/test_joint_limit_guard.py](../experiments/twist2_right_arm_manual/test_joint_limit_guard.py) | 134 | 목록 확인 | envelope, EnvelopeTest, DynamicsLimitTest | `016910115a71` |
| [experiments/twist2_right_arm_manual/test_live_cycle_cadence.py](../experiments/twist2_right_arm_manual/test_live_cycle_cadence.py) | 27 | 목록 확인 | run | `39f89052b48d` |
| [experiments/twist2_right_arm_manual/test_measured_composition.cpp](../experiments/twist2_right_arm_manual/test_measured_composition.cpp) | 37 | 목록 확인 | - | `d2ca09e4abc4` |
| [experiments/twist2_right_arm_manual/test_mink_cycle_candidate_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_cycle_candidate_offline.cpp) | 97 | 목록 확인 | - | `dfb67fc904a4` |
| [experiments/twist2_right_arm_manual/test_mink_cycle_owner_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_cycle_owner_offline.cpp) | 55 | 목록 확인 | - | `8b39de7fb365` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_bridge.py](../experiments/twist2_right_arm_manual/test_mink_live_cycle_bridge.py) | 127 | 목록 확인 | Socket, BridgeTests | `5278aa673d4f` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_contract.cpp](../experiments/twist2_right_arm_manual/test_mink_live_cycle_contract.cpp) | 164 | 목록 확인 | - | `993dd721b9a0` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_target.cpp](../experiments/twist2_right_arm_manual/test_mink_live_cycle_target.cpp) | 23 | 목록 확인 | - | `d8a253c5f4b9` |
| [experiments/twist2_right_arm_manual/test_mink_policy_hold_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_policy_hold_offline.cpp) | 67 | 목록 확인 | - | `01d762d0068e` |
| [experiments/twist2_right_arm_manual/test_mink_resampled_owner_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_resampled_owner_offline.cpp) | 80 | 목록 확인 | - | `a64b500695a7` |
| [experiments/twist2_right_arm_manual/test_mink_resampler_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_resampler_offline.cpp) | 67 | 목록 확인 | - | `cb513da3dffb` |
| [experiments/twist2_right_arm_manual/test_mink_speed_comparison.py](../experiments/twist2_right_arm_manual/test_mink_speed_comparison.py) | 51 | 목록 확인 | Profiles | `8b03ef8d9ed1` |
| [experiments/twist2_right_arm_manual/test_mink_udp_target.cpp](../experiments/twist2_right_arm_manual/test_mink_udp_target.cpp) | 46 | 목록 확인 | - | `833a1777ef26` |
| [experiments/twist2_right_arm_manual/test_mujoco_feedback_offline.py](../experiments/twist2_right_arm_manual/test_mujoco_feedback_offline.py) | 27 | 목록 확인 | FeedbackTests | `7b8ba99622bd` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_accuracy_stability.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_accuracy_stability.py) | 154 | 목록 확인 | fixture, MetricAndPlanTest, RealSmokeAndAuditTest | `4cf8292bbc86` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_artifacts.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_artifacts.py) | 98 | 목록 확인 | ArtifactTest | `11b717e47d72` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_coupled_matrix.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_coupled_matrix.py) | 72 | 목록 확인 | MatrixPlanTest, MatrixAuditTest | `d79456e4ae64` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_coupled_stress.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_coupled_stress.py) | 149 | 목록 확인 | PlanAndMutationTest, DynamicsAuditTest, SerialPool | `b22d56e5948a` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_expand.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_expand.py) | 75 | 목록 확인 | ExpandedTest | `8a3ce00dd7c1` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_expand_audit.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_expand_audit.py) | 57 | 목록 확인 | ExpandedAuditTest | `5f1e2df77ad0` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_final.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_final.py) | 176 | 목록 확인 | source_fixture, FinalPolicyTest, FinalDynamicsTest | `e05d6c00a32b` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_fixture.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_fixture.py) | 117 | 목록 확인 | FixtureXmlTest, FixtureDynamicsTest | `b1f58ef43f74` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_independent.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_independent.py) | 173 | 목록 확인 | PlanTest, DynamicsTest, ArtifactTest, AggregateRegressionTest | `288831bb3e9b` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_limit_replay.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_limit_replay.py) | 45 | 목록 확인 | LimitEvidenceTest | `6379208a9ea0` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_minerror.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_minerror.py) | 134 | 목록 확인 | record, proof_fixture, ProofTest, RealSmokeTest | `684c5e112be3` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_motor_stress.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_motor_stress.py) | 60 | 목록 확인 | MotorStressTest | `9ea3bba3a2b3` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_multiaxis.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_multiaxis.py) | 168 | 목록 확인 | PlanTest, DynamicsTest, changed, ArtifactTest | `bb21fc323792` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_multiaxis_yaw.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_multiaxis_yaw.py) | 78 | 목록 확인 | fake, PlanAndSelectionTest, ActualRecordTest | `409e9111c213` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_operating.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_operating.py) | 202 | 목록 확인 | PlanTest, DynamicsTest, ArtifactTest | `fb8fda863897` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_perjoint.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_perjoint.py) | 128 | 목록 확인 | GainsAndPlanTest, RealDynamicsTest | `f784d5b78de4` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_recorded.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_recorded.py) | 211 | 목록 확인 | fixture_rows, dump, capture, ParserTest, WriterPlanTest (+2) | `2a259d2db602` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_pitch_wrist.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_pitch_wrist.py) | 198 | 목록 확인 | mock_result, PlanTest, ScopeTest, DynamicsTest, BundleTest | `eaa9ef327da8` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_ramp.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_ramp.py) | 91 | 목록 확인 | FilterTest, DynamicsTest, BundleTest | `3f9c28ce2d08` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_roll_yaw.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_recorded_roll_yaw.py) | 148 | 목록 확인 | PlanTest, DynamicsTest, BundleTest | `38b1553d46ed` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_robust_refine.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_robust_refine.py) | 169 | 목록 확인 | synthetic, PlanTest, DynamicsAndEvidenceTest | `955d80b6aa9e` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_sweep.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_sweep.py) | 263 | 목록 확인 | fixture, MathTest, SummaryTest, DynamicsTest, PreservationTest | `39e3a8064081` |
| [experiments/twist2_right_arm_manual/test_mujoco_pd_yaw_regression.py](../experiments/twist2_right_arm_manual/test_mujoco_pd_yaw_regression.py) | 183 | 목록 확인 | source_summary, mock_record, PlanTest, ActualTraceTest, BundleAuditTest | `0bace62c5534` |
| [experiments/twist2_right_arm_manual/test_native_composition.cpp](../experiments/twist2_right_arm_manual/test_native_composition.cpp) | 70 | 목록 확인 | - | `a85740216873` |
| [experiments/twist2_right_arm_manual/test_native_cycle_build_contract.py](../experiments/twist2_right_arm_manual/test_native_cycle_build_contract.py) | 48 | 목록 확인 | NativeCycleBuildContractTest | `020f1d34459b` |
| [experiments/twist2_right_arm_manual/test_native_snapshot_freshness.cpp](../experiments/twist2_right_arm_manual/test_native_snapshot_freshness.cpp) | 16 | 목록 확인 | - | `004f9a0fab1e` |
| [experiments/twist2_right_arm_manual/test_native_state_audit.cpp](../experiments/twist2_right_arm_manual/test_native_state_audit.cpp) | 56 | 목록 확인 | - | `8260c795a7d5` |
| [experiments/twist2_right_arm_manual/test_native_vr_invocation.cpp](../experiments/twist2_right_arm_manual/test_native_vr_invocation.cpp) | 16 | 목록 확인 | - | `e72de6ee53a0` |
| [experiments/twist2_right_arm_manual/test_native_vr_policy_adapter.cpp](../experiments/twist2_right_arm_manual/test_native_vr_policy_adapter.cpp) | 78 | 목록 확인 | - | `3e5a59a0890d` |
| [experiments/twist2_right_arm_manual/test_no_overlap_runtime.py](../experiments/twist2_right_arm_manual/test_no_overlap_runtime.py) | 30 | 목록 확인 | NoOverlapRuntimeTest | `d6361b410538` |
| [experiments/twist2_right_arm_manual/test_observation_history.cpp](../experiments/twist2_right_arm_manual/test_observation_history.cpp) | 38 | 목록 확인 | - | `888a46f91043` |
| [experiments/twist2_right_arm_manual/test_offline_dispatch.cpp](../experiments/twist2_right_arm_manual/test_offline_dispatch.cpp) | 53 | 목록 확인 | - | `c8982edae847` |
| [experiments/twist2_right_arm_manual/test_offline_input_adapters.py](../experiments/twist2_right_arm_manual/test_offline_input_adapters.py) | 62 | 목록 확인 | ReferenceCrc, AdapterTests | `97fe4fcdb890` |
| [experiments/twist2_right_arm_manual/test_offline_owner.cpp](../experiments/twist2_right_arm_manual/test_offline_owner.cpp) | 79 | 목록 확인 | - | `02225b407b19` |
| [experiments/twist2_right_arm_manual/test_offline_word_crc.cpp](../experiments/twist2_right_arm_manual/test_offline_word_crc.cpp) | 18 | 목록 확인 | - | `72ba79f22ff2` |
| [experiments/twist2_right_arm_manual/test_offline_writer_study.cpp](../experiments/twist2_right_arm_manual/test_offline_writer_study.cpp) | 87 | 목록 확인 | - | `a75f1d7bcabc` |
| [experiments/twist2_right_arm_manual/test_owner_startup.cpp](../experiments/twist2_right_arm_manual/test_owner_startup.cpp) | 129 | 목록 확인 | - | `0d597f4c308e` |
| [experiments/twist2_right_arm_manual/test_owner_torque_fade.cpp](../experiments/twist2_right_arm_manual/test_owner_torque_fade.cpp) | 51 | 목록 확인 | - | `4b27fa589854` |
| [experiments/twist2_right_arm_manual/test_pd_gain_comparison.py](../experiments/twist2_right_arm_manual/test_pd_gain_comparison.py) | 61 | 목록 확인 | GainTests | `f8375eb6954b` |
| [experiments/twist2_right_arm_manual/test_pd_gain_options.cpp](../experiments/twist2_right_arm_manual/test_pd_gain_options.cpp) | 49 | 목록 확인 | - | `81bb7c7b7e08` |
| [experiments/twist2_right_arm_manual/test_pd_joint_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_joint_trial.cpp) | 22 | 목록 확인 | - | `a1484bdb339d` |
| [experiments/twist2_right_arm_manual/test_pd_reach_timing.py](../experiments/twist2_right_arm_manual/test_pd_reach_timing.py) | 42 | 목록 확인 | TimingTests | `1070c113aabb` |
| [experiments/twist2_right_arm_manual/test_pd_reach_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_reach_trial.cpp) | 31 | 목록 확인 | - | `1152ee753e4c` |
| [experiments/twist2_right_arm_manual/test_pd_ready_settle.cpp](../experiments/twist2_right_arm_manual/test_pd_ready_settle.cpp) | 46 | 목록 확인 | - | `5df3d6d965e1` |
| [experiments/twist2_right_arm_manual/test_pd_small_signal_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_small_signal_trial.cpp) | 56 | 목록 확인 | - | `7a2f5da19a6b` |
| [experiments/twist2_right_arm_manual/test_pd_trial_offline.py](../experiments/twist2_right_arm_manual/test_pd_trial_offline.py) | 88 | 목록 확인 | TrialTests | `271d9b456d9b` |
| [experiments/twist2_right_arm_manual/test_periodic_csv.cpp](../experiments/twist2_right_arm_manual/test_periodic_csv.cpp) | 39 | 목록 확인 | - | `4f448db57b4c` |
| [experiments/twist2_right_arm_manual/test_periodic_csv_failure.cpp](../experiments/twist2_right_arm_manual/test_periodic_csv_failure.cpp) | 27 | 목록 확인 | - | `09a655c5610a` |
| [experiments/twist2_right_arm_manual/test_persistent_pd_runtime.py](../experiments/twist2_right_arm_manual/test_persistent_pd_runtime.py) | 85 | 목록 확인 | PersistentPdRuntimeTest | `d61de3fe8266` |
| [experiments/twist2_right_arm_manual/test_policy_history_loop.cpp](../experiments/twist2_right_arm_manual/test_policy_history_loop.cpp) | 84 | 목록 확인 | - | `ad73869e6297` |
| [experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py](../experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py) | 56 | 목록 확인 | Command, WorkerClientTests | `73272ea0f8a9` |
| [experiments/twist2_right_arm_manual/test_policy_worker_offline.py](../experiments/twist2_right_arm_manual/test_policy_worker_offline.py) | 39 | 목록 확인 | WorkerTests | `0efb09d564c4` |
| [experiments/twist2_right_arm_manual/test_preinfer_blend.cpp](../experiments/twist2_right_arm_manual/test_preinfer_blend.cpp) | 56 | 목록 확인 | - | `bdc48284055f` |
| [experiments/twist2_right_arm_manual/test_queued_input.cpp](../experiments/twist2_right_arm_manual/test_queued_input.cpp) | 68 | 목록 확인 | - | `97c60d4eb5fc` |
| [experiments/twist2_right_arm_manual/test_raw_event_clock.py](../experiments/twist2_right_arm_manual/test_raw_event_clock.py) | 103 | 목록 확인 | Raw, RawEventTests | `14acb4cdb87a` |
| [experiments/twist2_right_arm_manual/test_real_response_frame.cpp](../experiments/twist2_right_arm_manual/test_real_response_frame.cpp) | 27 | 목록 확인 | - | `21867c44099a` |
| [experiments/twist2_right_arm_manual/test_real_response_identification.py](../experiments/twist2_right_arm_manual/test_real_response_identification.py) | 57 | 목록 확인 | record, RealResponseTest | `994218d7bdad` |
| [experiments/twist2_right_arm_manual/test_real_state_continuity.cpp](../experiments/twist2_right_arm_manual/test_real_state_continuity.cpp) | 37 | 목록 확인 | - | `218e66e3d5f5` |
| [experiments/twist2_right_arm_manual/test_receive_vr_shadow.py](../experiments/twist2_right_arm_manual/test_receive_vr_shadow.py) | 71 | 목록 확인 | ReceiverTests | `943c34cea59e` |
| [experiments/twist2_right_arm_manual/test_regular_handoff_safety.cpp](../experiments/twist2_right_arm_manual/test_regular_handoff_safety.cpp) | 149 | 목록 확인 | - | `e677ff55f33b` |
| [experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py) | 81 | 목록 확인 | ReplayPhysicalCsvMuJoCoTests | `37e735e9b405` |
| [experiments/twist2_right_arm_manual/test_review_loaded_settle.py](../experiments/twist2_right_arm_manual/test_review_loaded_settle.py) | 38 | 목록 확인 | rows, test_stationary_offset_does_not_imply_motion_or_ready, test_slow_drift_visible_even_when_reported_velocity_zero, test_invalid_sample_breaks_window, test_midwindow_excursion_not_hidden_by_matching_endpoints | `ed794a9b2fe8` |
| [experiments/twist2_right_arm_manual/test_review_ready_components.py](../experiments/twist2_right_arm_manual/test_review_ready_components.py) | 37 | 목록 확인 | row, test_load_error_is_separate_but_arm_error_still_blocks, test_uses_previous_target_not_current_target, test_gap_and_invalid_state_break_sampled_run | `05f6ca8b850d` |
| [experiments/twist2_right_arm_manual/test_split_ready_study.py](../experiments/twist2_right_arm_manual/test_split_ready_study.py) | 55 | 목록 확인 | gate, feed, settle, test_static_load_offset_and_alignment_are_separate, test_slow_drift_blocks_even_when_velocity_reports_zero (+3) | `0b8d7c23b7c9` |
| [experiments/twist2_right_arm_manual/test_split_vr_adapter_study.cpp](../experiments/twist2_right_arm_manual/test_split_vr_adapter_study.cpp) | 217 | 목록 확인 | - | `55e5c11b3f38` |
| [experiments/twist2_right_arm_manual/test_state_watchdog.cpp](../experiments/twist2_right_arm_manual/test_state_watchdog.cpp) | 20 | 목록 확인 | - | `84e130b62be1` |
| [experiments/twist2_right_arm_manual/test_sysid_async.py](../experiments/twist2_right_arm_manual/test_sysid_async.py) | 95 | 목록 확인 | fixture, AsyncTests | `6f8af3dfba62` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_crosscheck.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_crosscheck.py) | 80 | 목록 확인 | CrosscheckTests | `3ecd279d8b87` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_observer_bridge.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_observer_bridge.cpp) | 135 | 목록 확인 | - | `23008bc262c5` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_observer_bridge.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_observer_bridge.py) | 50 | 목록 확인 | ObserverBridgeSourceTests | `144d9fd0a7de` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_plan.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_plan.py) | 83 | 목록 확인 | request, ExcitationPlanTests | `09b91919eb00` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_plan_adapter.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_plan_adapter.cpp) | 128 | 목록 확인 | - | `2694e3fd4056` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_plan_adapter.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_plan_adapter.py) | 33 | 목록 확인 | PlanAdapterSourceTests | `27779bcb0226` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_preview.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_preview.py) | 45 | 목록 확인 | PreviewTests | `9280e5e1f2e2` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_readiness.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_readiness.py) | 76 | 목록 확인 | ReadinessTests | `13f245a64248` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_reference.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_reference.cpp) | 60 | 목록 확인 | - | `4b53925f1887` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_reference.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_reference.py) | 37 | 목록 확인 | ReferenceTests | `efbc8cffa8a9` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_request.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_request.py) | 81 | 목록 확인 | spec, RequestDraftTests | `769722fcb4cb` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_runtime.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_runtime.cpp) | 109 | 목록 확인 | - | `ec176ffd6573` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_runtime.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_runtime.py) | 30 | 목록 확인 | RuntimeSourceTests | `224ab02447ff` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_sequence.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_sequence.cpp) | 105 | 목록 확인 | - | `90c57ef569c1` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_sequence.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_sequence.py) | 25 | 목록 확인 | SequenceSourceTests | `6cf0aadc8fae` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_writer_hook.cpp](../experiments/twist2_right_arm_manual/test_sysid_excitation_writer_hook.cpp) | 107 | 목록 확인 | - | `034e6f5e87b2` |
| [experiments/twist2_right_arm_manual/test_sysid_excitation_writer_hook.py](../experiments/twist2_right_arm_manual/test_sysid_excitation_writer_hook.py) | 30 | 목록 확인 | WriterHookSourceTests | `9df776dbd26b` |
| [experiments/twist2_right_arm_manual/test_sysid_inspect_legacy.py](../experiments/twist2_right_arm_manual/test_sysid_inspect_legacy.py) | 34 | 목록 확인 | LegacyReadinessTests | `b929f61a2249` |
| [experiments/twist2_right_arm_manual/test_sysid_native.py](../experiments/twist2_right_arm_manual/test_sysid_native.py) | 69 | 목록 확인 | NativeTests | `384d3d167272` |
| [experiments/twist2_right_arm_manual/test_sysid_pipeline.py](../experiments/twist2_right_arm_manual/test_sysid_pipeline.py) | 235 | 목록 확인 | records, save, PipelineTests | `7629effd09ab` |
| [experiments/twist2_right_arm_manual/test_sysid_quiet_stats.py](../experiments/twist2_right_arm_manual/test_sysid_quiet_stats.py) | 15 | 목록 확인 | QuietStatsTests | `48f1b791bbbb` |
| [experiments/twist2_right_arm_manual/test_sysid_readonly.py](../experiments/twist2_right_arm_manual/test_sysid_readonly.py) | 54 | 목록 확인 | row, save, ReadonlyTests | `60b5035e3c02` |
| [experiments/twist2_right_arm_manual/test_upper_target_offline.cpp](../experiments/twist2_right_arm_manual/test_upper_target_offline.cpp) | 50 | 목록 확인 | - | `efe2ca0b237a` |
| [experiments/twist2_right_arm_manual/test_verified_regular_handoff.cpp](../experiments/twist2_right_arm_manual/test_verified_regular_handoff.cpp) | 64 | 목록 확인 | - | `4f74fe2ce105` |
| [experiments/twist2_right_arm_manual/test_vr_input_offline.py](../experiments/twist2_right_arm_manual/test_vr_input_offline.py) | 90 | 목록 확인 | MakePacket, VRInputTests | `15ea91f56c60` |
| [experiments/twist2_right_arm_manual/test_vr_rate_limits.cpp](../experiments/twist2_right_arm_manual/test_vr_rate_limits.cpp) | 31 | 목록 확인 | - | `464afb07b0d2` |
| [experiments/twist2_right_arm_manual/test_writer_frame.cpp](../experiments/twist2_right_arm_manual/test_writer_frame.cpp) | 21 | 목록 확인 | - | `f08138e06758` |
| [experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp](../experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp) | 35 | 목록 확인 | - | `6ad664610103` |
| [experiments/twist2_right_arm_manual/test_wsl_sdk_inventory.py](../experiments/twist2_right_arm_manual/test_wsl_sdk_inventory.py) | 22 | 목록 확인 | InventoryTests | `7fea86ef51d0` |
| [experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp](../experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp) | 1778 | 목록 확인 | - | `bc37a8ad0949` |
| [experiments/twist2_right_arm_manual/twist2_mink_udp_trial.cpp](../experiments/twist2_right_arm_manual/twist2_mink_udp_trial.cpp) | 1264 | 목록 확인 | - | `e417f8886bb9` |
| [experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp](../experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp) | 1205 | 목록 확인 | - | `e61d8a3cf830` |
| [experiments/twist2_right_arm_manual/twist2_vr_native_draft.cpp](../experiments/twist2_right_arm_manual/twist2_vr_native_draft.cpp) | 1214 | 목록 확인 | - | `ea59d742a612` |
| [experiments/twist2_right_arm_manual/upper_target_offline.hpp](../experiments/twist2_right_arm_manual/upper_target_offline.hpp) | 138 | 목록 확인 | - | `0bc6acba2a7a` |
| [experiments/twist2_right_arm_manual/validate_input.hpp](../experiments/twist2_right_arm_manual/validate_input.hpp) | 178 | 목록 확인 | - | `a28785a3f42b` |
| [experiments/twist2_right_arm_manual/vendor/json.hpp](../experiments/twist2_right_arm_manual/vendor/json.hpp) | 25526 | 목록 확인 | - | `5f09d1eebe9b` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/IMUState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/IMUState_.hpp) | 503 | 목록 확인 | - | `0b078db5401a` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/LowState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/LowState_.hpp) | 762 | 목록 확인 | - | `e01be2966710` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/MotorState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/MotorState_.hpp) | 691 | 목록 확인 | - | `9a461ce785c1` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/manifest.json](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/manifest.json) | 23 | 목록 확인 | - | `bf334ebe28c7` |
| [experiments/twist2_right_arm_manual/verified_regular_handoff.hpp](../experiments/twist2_right_arm_manual/verified_regular_handoff.hpp) | 64 | 목록 확인 | - | `c072a624d0f9` |
| [experiments/twist2_right_arm_manual/verify_offline.py](../experiments/twist2_right_arm_manual/verify_offline.py) | 213 | 목록 확인 | CheckCondition, GetFunction, GetDeclaration, GetLinuxPath, RunLocal (+4) | `2cf29eb56f5e` |
| [experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py](../experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py) | 89 | 목록 확인 | main | `f233967c614c` |
| [experiments/twist2_right_arm_manual/vr_input_offline.py](../experiments/twist2_right_arm_manual/vr_input_offline.py) | 103 | 목록 확인 | VRInputStudy | `34351c3bc023` |
| [experiments/twist2_right_arm_manual/writer_frame.hpp](../experiments/twist2_right_arm_manual/writer_frame.hpp) | 37 | 목록 확인 | - | `16f2ec354c74` |
| [experiments/twist2_right_arm_manual/writer_reference_study.hpp](../experiments/twist2_right_arm_manual/writer_reference_study.hpp) | 31 | 목록 확인 | - | `5aa5d4d05127` |
| [hardware/g1_arm_bridge/arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/arm_sdk_hold_contract.py) | 368 | 목록 확인 | ArmSdkHoldConfig, HoldValidation, ArmSdkCommandFrame, _finite_vector, _uint8 (+6) | `bd2cec76ffe4` |
| [hardware/g1_arm_bridge/arm_sdk_release_contract.py](../hardware/g1_arm_bridge/arm_sdk_release_contract.py) | 138 | 목록 확인 | ReleaseEvidence, _validate_release_arguments, execute_release_sequence | `64072ef0df8b` |
| [hardware/g1_arm_bridge/arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/arm_sdk_teleop_contract.py) | 873 | 목록 확인 | Gate7ContractError, RegularArmPose, Gate7Config, MinkArmSample, TrajectorySample (+11) | `976035a786e0` |
| [hardware/g1_arm_bridge/check_startup_readiness.py](../hardware/g1_arm_bridge/check_startup_readiness.py) | 601 | 목록 확인 | PrecheckConfig, TimedPacket, Blocker, _positive_float, load_config (+12) | `9844ec3852a4` |
| [hardware/g1_arm_bridge/check_startup_readiness_entry.py](../hardware/g1_arm_bridge/check_startup_readiness_entry.py) | 176 | 목록 확인 | _pop_option, _option_path, validate_forward_token, _finite_vector, _validated_raw_odom (+3) | `77da5a14e8db` |
| [hardware/g1_arm_bridge/diagnose_initial_pose_collision.py](../hardware/g1_arm_bridge/diagnose_initial_pose_collision.py) | 304 | 목록 확인 | _joint_pose, _has_exact_geom_contact, _probe_zero_mesh_distance, _robust_geom_distance, _nearby_pairs (+1) | `070b323157b8` |
| [hardware/g1_arm_bridge/edit_startup_ready_pose.py](../hardware/g1_arm_bridge/edit_startup_ready_pose.py) | 462 | 목록 확인 | PoseAssessment, EditorState, ParseArguments, LoadPose, SafeLimitsDegrees (+11) | `6ed7eda24240` |
| [hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py) | 29 | 목록 확인 | ExperimentalStatefulGate7TeleopController | `a93f2c85b9b1` |
| [hardware/g1_arm_bridge/g1_base_state.py](../hardware/g1_arm_bridge/g1_base_state.py) | 212 | 목록 확인 | InvalidBaseStateError, NormalizedBaseState, _FiniteVector, NormalizeQuaternionWXYZ, MultiplyQuaternionWXYZ (+4) | `11c6f8e1e985` |
| [hardware/g1_arm_bridge/g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/g1_camera_replay_tcp.py) | 321 | 목록 확인 | LoadFont, BuildReplayJpeg, ParseArguments, ValidateArguments, WriteResult (+1) | `095c99c94437` |
| [hardware/g1_arm_bridge/g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/g1_camera_tcp_bridge.py) | 211 | 목록 확인 | BuildFramePacket, ParseArguments, CreateVideoClient, ConnectUnity, ValidateArguments (+1) | `8335e934b232` |
| [hardware/g1_arm_bridge/g1_joint_contract.py](../hardware/g1_arm_bridge/g1_joint_contract.py) | 39 | 목록 확인 | - | `bb33790cb1af` |
| [hardware/g1_arm_bridge/g1_mink_right_arm_csv_logger.py](../hardware/g1_arm_bridge/g1_mink_right_arm_csv_logger.py) | 178 | 목록 확인 | _finite_number, parse_mink_state, row_for, main | `033582b978e6` |
| [hardware/g1_arm_bridge/g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/g1_omni_velocity_gateway.py) | 648 | 목록 확인 | clamp, deadzone, wrapped_delta_degrees, omni_to_body_velocity, OmniVelocityConfig (+10) | `aaa87a6c459c` |
| [hardware/g1_arm_bridge/g1_right_arm_jog.py](../hardware/g1_arm_bridge/g1_right_arm_jog.py) | 1284 | 목록 확인 | RuntimeConfig, KeyboardReader, _number, load_config, validate_config (+18) | `659e435400a0` |
| [hardware/g1_arm_bridge/g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/g1_right_arm_jog_entry.py) | 234 | 목록 확인 | _argument_path, _config_path, apply_release_result_guard, install_jog_safety_guards, main | `0c6c544823d2` |
| [hardware/g1_arm_bridge/g1_unity_state_bridge.py](../hardware/g1_arm_bridge/g1_unity_state_bridge.py) | 224 | 목록 확인 | _FiniteVector, _QuaternionAngleDegrees, _RequireFullBody, BuildUnityHardwareStatePacket, EncodeUnityHardwareStatePacket (+1) | `4d820db4d806` |
| [hardware/g1_arm_bridge/g1_velocity_axis_trial_sender.py](../hardware/g1_arm_bridge/g1_velocity_axis_trial_sender.py) | 110 | 목록 확인 | velocity_for, discover, main | `e0334baea2f6` |
| [hardware/g1_arm_bridge/g1_velocity_discovery.py](../hardware/g1_arm_bridge/g1_velocity_discovery.py) | 43 | 목록 확인 | parse_discovery, make_listener | `7a033e7bcb2d` |
| [hardware/g1_arm_bridge/g1_velocity_keypad_relay.py](../hardware/g1_arm_bridge/g1_velocity_keypad_relay.py) | 160 | 목록 확인 | StalePacket, strict_load, validate, validate_order, main | `83ba746a9c6e` |
| [hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py) | 803 | 목록 확인 | LowStatePacketError, BaseStateTelemetry, LowStateTelemetry, PacketOrderTracker, _finite_joint_vector (+16) | `1081cdcd9e21` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold.py) | 886 | 목록 확인 | RuntimeConfig, LowStateSnapshot, LowStateBuffer, _finite_number, load_runtime_config (+12) | `66a4f51c16ad` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py) | 72 | 목록 확인 | install_supported_gate6_guards, main | `2a8dcda852e6` |
| [hardware/g1_arm_bridge/gate6_weight_hold_trial.py](../hardware/g1_arm_bridge/gate6_weight_hold_trial.py) | 156 | 목록 확인 | BuildTrialConfig, LocalToWSL, RunChecked, RunTrial, main | `9ef07e9a36cb` |
| [hardware/g1_arm_bridge/gate7_acquisition_guard.py](../hardware/g1_arm_bridge/gate7_acquisition_guard.py) | 126 | 목록 확인 | ActiveAcquisitionGuard, validate_full_body_snapshot_matches_precheck, validate_acquisition_hold_target | `d7dcaf61ae8a` |
| [hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py](../hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py) | 268 | 목록 확인 | SleepUntilStep, SelectReplayWindow, _replace_dual, CheckReplayModelIdentity, BuildExperimentalLimitedFrames (+2) | `380b49b6dd64` |
| [hardware/g1_arm_bridge/gate7_capture_quality.py](../hardware/g1_arm_bridge/gate7_capture_quality.py) | 876 | 목록 확인 | _percentile, _round, _replace_dual, _decode_capture, _series_metrics (+9) | `46a8fe64f450` |
| [hardware/g1_arm_bridge/gate7_capture_regression.py](../hardware/g1_arm_bridge/gate7_capture_regression.py) | 217 | 목록 확인 | _replace_dual, _file_sha256, BuildRegressionTrace, CompareTrace, _automatic_result_path (+2) | `6ea4853ec628` |
| [hardware/g1_arm_bridge/gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/gate7_fault_injection_matrix.py) | 317 | 목록 확인 | _replace_dual, _synthetic_active_value, _load_active_value, _payload, _new_controller (+5) | `46f4cef501a3` |
| [hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py) | 372 | 목록 확인 | _replace_dual, _packet, _automatic_result_path, _parse_args, main | `c2701d99fd02` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk.py) | 963 | 입출력 확인 | LiveHardwareConfig, _finite, LoadLiveHardwareConfig, ValidateLiveHardwareConfig, ValidateRuckigRuntime (+13) | `c9d3bf5991b2` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py) | 270 | 목록 확인 | _argument_path, _pop_argument, install_supported_path_guards, main | `0cf4e54e623f` |
| [hardware/g1_arm_bridge/gate7_live_dry_run.py](../hardware/g1_arm_bridge/gate7_live_dry_run.py) | 743 | 목록 확인 | DryRunTick, _finite_all_joints, _replace_dual_arm, _automatic_path, _resolve_output_path (+6) | `c23e7372b0d1` |
| [hardware/g1_arm_bridge/gate7_live_safety_guard.py](../hardware/g1_arm_bridge/gate7_live_safety_guard.py) | 120 | 목록 확인 | ArmSegmentPoint, LinearDualArmSegment, require_active_collision_evidence, _finite_all_joints, build_final_command_segment (+1) | `c89e7f456590` |
| [hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py](../hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py) | 515 | 목록 확인 | _set_full_body_pose, CollisionPathValidator, _replace_dual_arm, _mink_packet, _target_right_arm (+3) | `b21990b0f29e` |
| [hardware/g1_arm_bridge/gate7_mink_capture.py](../hardware/g1_arm_bridge/gate7_mink_capture.py) | 149 | 목록 확인 | _automatic_path, _write_line, _parse_args, main | `9c532d36bf27` |
| [hardware/g1_arm_bridge/gate7_mink_cycle_relay.py](../hardware/g1_arm_bridge/gate7_mink_cycle_relay.py) | 102 | 목록 확인 | strict_load, validate, open_feedback_socket, main | `d782f6de8de3` |
| [hardware/g1_arm_bridge/gate7_mink_replay.py](../hardware/g1_arm_bridge/gate7_mink_replay.py) | 152 | 목록 확인 | CapturedPacket, LoadCapture, NormalizePayload, CaptureSha256, validate_replay_destination (+2) | `60e2e3c2814f` |
| [hardware/g1_arm_bridge/gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/gate7_mink_wsl_relay.py) | 244 | 입출력 확인 | MinkOrderGuard, ValidateRelayEndpoint, ValidateAndForward, _automatic_result_path, _parse_args (+1) | `b91ebb69cc57` |
| [hardware/g1_arm_bridge/gate7_relay_provenance_guard.py](../hardware/g1_arm_bridge/gate7_relay_provenance_guard.py) | 174 | 목록 확인 | validate_relay_token, _payload_object, require_relay_token, command_provenance, require_live_candidate_for_relay (+3) | `86d376e695a7` |
| [hardware/g1_arm_bridge/generate_fake_mink_targets.py](../hardware/g1_arm_bridge/generate_fake_mink_targets.py) | 117 | 목록 확인 | parse_args, main | `eeb5c6e0e331` |
| [hardware/g1_arm_bridge/hardware_state.py](../hardware/g1_arm_bridge/hardware_state.py) | 91 | 목록 확인 | HardwarePhase, FaultCode, build_status, write_status | `81f126c94061` |
| [hardware/g1_arm_bridge/live_lowstate_mujoco.py](../hardware/g1_arm_bridge/live_lowstate_mujoco.py) | 652 | 목록 확인 | StreamState, BaseBodyPose, ParseArguments, ResolveMeasurementLogPath, BuildMirrorMeasurement (+14) | `23012f64927c` |
| [hardware/g1_arm_bridge/lowstate_health_guard.py](../hardware/g1_arm_bridge/lowstate_health_guard.py) | 119 | 목록 확인 | _value, _temperature_max_c, validate_lowstate_health_message, install_lowstate_health_tracking, require_latest_lowstate_health | `c8715c8899a3` |
| [hardware/g1_arm_bridge/mink_target_dry_run.py](../hardware/g1_arm_bridge/mink_target_dry_run.py) | 127 | 목록 확인 | _fmt_deg, main | `372002c8b23c` |
| [hardware/g1_arm_bridge/plan_startup_transition.py](../hardware/g1_arm_bridge/plan_startup_transition.py) | 686 | 목록 확인 | _inside_pairs, _waypoints_for_order, _dense_segment, _evaluate_order, _joint_limits (+6) | `6c7c54666278` |
| [hardware/g1_arm_bridge/precheck_provenance_guard.py](../hardware/g1_arm_bridge/precheck_provenance_guard.py) | 39 | 목록 확인 | require_provenance_bound_precheck | `aa8fbdd33530` |
| [hardware/g1_arm_bridge/probe_joint_motion.py](../hardware/g1_arm_bridge/probe_joint_motion.py) | 177 | 목록 확인 | parse_args, current_positions, collect_positions, summarize, main | `6b43271de626` |
| [hardware/g1_arm_bridge/query_motion_mode.py](../hardware/g1_arm_bridge/query_motion_mode.py) | 110 | 목록 확인 | _write_json, parse_args, main | `d86bc3ea68ba` |
| [hardware/g1_arm_bridge/query_motion_mode_wsl.sh](../hardware/g1_arm_bridge/query_motion_mode_wsl.sh) | 24 | 목록 확인 | - | `19cdf2097714` |
| [hardware/g1_arm_bridge/read_only_lowstate.py](../hardware/g1_arm_bridge/read_only_lowstate.py) | 563 | 목록 확인 | JointSample, ReadOnlyG1LowState, ReadOnlyG1BaseState, _motor_value, _state_uint8 (+9) | `bfaef913f786` |
| [hardware/g1_arm_bridge/read_only_lowstate_entry.py](../hardware/g1_arm_bridge/read_only_lowstate_entry.py) | 154 | 목록 확인 | _pop_option, _finite_vector, install_raw_odom_binding, install_forward_token, main | `a38ce663d019` |
| [hardware/g1_arm_bridge/receive_initial_state.py](../hardware/g1_arm_bridge/receive_initial_state.py) | 199 | 목록 확인 | parse_args, _raw_object, _validate_provenance, _validate_full_body_consistency, main | `4285ba83ada2` |
| [hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py) | 354 | 목록 확인 | SavedLowState, _FiniteVector, _JointNames, _OptionalMode, LoadSnapshot (+5) | `a869fd552b3d` |
| [hardware/g1_arm_bridge/replay_startup_recovery.py](../hardware/g1_arm_bridge/replay_startup_recovery.py) | 186 | 목록 확인 | ParseArguments, LoadViewerSettings, LoadRecovery, InterpolatePose, ApplyRightArmPose (+1) | `8ff4b6c36a37` |
| [hardware/g1_arm_bridge/right_arm_jog_contract.py](../hardware/g1_arm_bridge/right_arm_jog_contract.py) | 194 | 목록 확인 | ArmJointJogLimits, ArmJointJogTick, validate_jog_limits, ArmJointJogController | `83f51c0a80df` |
| [hardware/g1_arm_bridge/right_arm_jog_safety_guard.py](../hardware/g1_arm_bridge/right_arm_jog_safety_guard.py) | 92 | 목록 확인 | file_sha256, build_jog_permit_provenance, validate_jog_permit_provenance, validate_jog_runtime_full_body, validate_jog_final_segment | `13ff40df3d50` |
| [hardware/g1_arm_bridge/ruckig_gate7_controller.py](../hardware/g1_arm_bridge/ruckig_gate7_controller.py) | 121 | 목록 확인 | RuckigGate7TeleopController | `dcc46f5329c7` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 98 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `cacd8b9519ca` |
| [hardware/g1_arm_bridge/run_omni_fake_g1_integration.py](../hardware/g1_arm_bridge/run_omni_fake_g1_integration.py) | 173 | 목록 확인 | discovery_loop, validate_command, main | `6836821ff846` |
| [hardware/g1_arm_bridge/runtime_base_state_guard.py](../hardware/g1_arm_bridge/runtime_base_state_guard.py) | 316 | 목록 확인 | RuntimeBaseSnapshot, RuntimeBaseStateMonitor, _relative_yaw_rad, _finite_vector, _quaternion_angle_delta_rad (+5) | `9f1816007448` |
| [hardware/g1_arm_bridge/safety_gate.py](../hardware/g1_arm_bridge/safety_gate.py) | 149 | 목록 확인 | SafetyConfig, SafetyDecision, _vector, _within_joint_limits, evaluate_target | `20d483a19afa` |
| [hardware/g1_arm_bridge/simulate_startup_recovery.py](../hardware/g1_arm_bridge/simulate_startup_recovery.py) | 1181 | 목록 확인 | _load_startup_safe_ready_degrees, _right_qpos_ids, _minimum_clearance, _minimum_clearance_extended, _recovery_edge_is_valid (+10) | `15689008c367` |
| [hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh](../hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh) | 69 | 목록 확인 | - | `7cd8933586e9` |
| [hardware/g1_arm_bridge/start_gate6_hold_wsl.sh](../hardware/g1_arm_bridge/start_gate6_hold_wsl.sh) | 24 | 목록 확인 | - | `02803d8b764f` |
| [hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh](../hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh) | 29 | 목록 확인 | - | `1040c430ca14` |
| [hardware/g1_arm_bridge/start_read_only_wsl.sh](../hardware/g1_arm_bridge/start_read_only_wsl.sh) | 22 | 목록 확인 | - | `969530765469` |
| [hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh](../hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh) | 24 | 목록 확인 | - | `bf6fc5424ee2` |
| [hardware/g1_arm_bridge/startup_state_binding_guard.py](../hardware/g1_arm_bridge/startup_state_binding_guard.py) | 143 | 목록 확인 | file_sha256, build_state_binding, base_state_to_dict, _require_finite_vector, require_state_binding | `386687ebca94` |
| [hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py) | 159 | 목록 확인 | _safe_all_q, ArmSdkHoldContractTests | `06948c01073c` |
| [hardware/g1_arm_bridge/test_arm_sdk_release_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_release_contract.py) | 192 | 목록 확인 | FakeClock, ReleaseContractTests | `8183056bf1db` |
| [hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py) | 438 | 목록 확인 | _replace_dual, _sample, ArmSdkTeleopContractTests | `fc78f3a8e790` |
| [hardware/g1_arm_bridge/test_check_startup_readiness.py](../hardware/g1_arm_bridge/test_check_startup_readiness.py) | 196 | 목록 확인 | _config, _timed_packet, _mode_query, StartupReadinessTests | `37e1032193bc` |
| [hardware/g1_arm_bridge/test_check_startup_readiness_entry.py](../hardware/g1_arm_bridge/test_check_startup_readiness_entry.py) | 111 | 목록 확인 | _raw_base_state, StartupPrecheckEntryTests | `6a1c5cdb14eb` |
| [hardware/g1_arm_bridge/test_collision_diagnostics.py](../hardware/g1_arm_bridge/test_collision_diagnostics.py) | 60 | 목록 확인 | _FakeG1, _FakeController, CollisionDiagnosticTests | `b2642345a203` |
| [hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py) | 43 | 목록 확인 | ExperimentalStatefulGate7ControllerTests | `cc444df0124f` |
| [hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py](../hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py) | 82 | 목록 확인 | main | `fa397980398b` |
| [hardware/g1_arm_bridge/test_g1_base_state.py](../hardware/g1_arm_bridge/test_g1_base_state.py) | 118 | 목록 확인 | YawQuaternionWXYZ, G1BaseStateTests | `11a58e53ca27` |
| [hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py) | 93 | 목록 확인 | G1CameraReplayTcpTest | `ed4673ed6ed1` |
| [hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py) | 44 | 목록 확인 | G1CameraTcpBridgeTest | `e1047b89e99b` |
| [hardware/g1_arm_bridge/test_g1_mink_right_arm_csv_logger.py](../hardware/g1_arm_bridge/test_g1_mink_right_arm_csv_logger.py) | 95 | 목록 확인 | packet, MinkCsvLoggerTests | `05f850f605f8` |
| [hardware/g1_arm_bridge/test_g1_omni_body_mapping.py](../hardware/g1_arm_bridge/test_g1_omni_body_mapping.py) | 84 | 목록 확인 | raw_body_vector, OmniBodyMappingTests | `bec8041b85d9` |
| [hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py](../hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py) | 459 | 목록 확인 | CaptureTap, SyntheticTimeout, BurstyConnection, ScriptedConnection, ClockedOmniObservationTests | `1ec08add17a5` |
| [hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py](../hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py) | 123 | 목록 확인 | omni_handler, serve, discovery_sender, main | `1bb556e60fcc` |
| [hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py) | 137 | 목록 확인 | OmniVelocityGatewayTests | `fb49ddeff1cd` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog.py) | 359 | 목록 확인 | G1RightArmJogTests | `e0eb1c493d3e` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py) | 50 | 목록 확인 | DirectJogReleaseIntegrationTests | `1b11145d8b85` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py) | 107 | 목록 확인 | RightArmJogReleaseGuardTests | `808ab9f76a81` |
| [hardware/g1_arm_bridge/test_g1_unity_state_bridge.py](../hardware/g1_arm_bridge/test_g1_unity_state_bridge.py) | 175 | 목록 확인 | LowStatePacket, G1UnityStateBridgeTests | `0c91cc2833b5` |
| [hardware/g1_arm_bridge/test_g1_velocity_axis_trial_sender.py](../hardware/g1_arm_bridge/test_g1_velocity_axis_trial_sender.py) | 14 | 목록 확인 | AxisTrialSenderTests | `22b474e034eb` |
| [hardware/g1_arm_bridge/test_g1_velocity_discovery.py](../hardware/g1_arm_bridge/test_g1_velocity_discovery.py) | 45 | 목록 확인 | DiscoveryContractTests | `4e0225dae03d` |
| [hardware/g1_arm_bridge/test_g1_velocity_keypad_relay.py](../hardware/g1_arm_bridge/test_g1_velocity_keypad_relay.py) | 75 | 목록 확인 | packet, RelayContractTests | `9352de00ff68` |
| [hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py) | 218 | 목록 확인 | _packet, _base_state, _unused_local_port, Gate5LowStateSafetyTests | `5ab06a9f3908` |
| [hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py) | 215 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, Gate6ArmSdkHoldTests | `7858891576b4` |
| [hardware/g1_arm_bridge/test_gate6_fault_release.py](../hardware/g1_arm_bridge/test_gate6_fault_release.py) | 154 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, _FakeCRC, _FakeBuffer, _FakePublisher (+2) | `697a9ab1c6a9` |
| [hardware/g1_arm_bridge/test_gate6_interrupt_release.py](../hardware/g1_arm_bridge/test_gate6_interrupt_release.py) | 130 | 목록 확인 | validate_interrupt_release_contract, Gate6InterruptReleaseTests, main | `fad40aefbdfa` |
| [hardware/g1_arm_bridge/test_gate6_weight_hold_trial.py](../hardware/g1_arm_bridge/test_gate6_weight_hold_trial.py) | 89 | 목록 확인 | WeightHoldTrialTests | `0a9fc85e193d` |
| [hardware/g1_arm_bridge/test_gate7_acquisition_guard.py](../hardware/g1_arm_bridge/test_gate7_acquisition_guard.py) | 95 | 목록 확인 | sample, Gate7AcquisitionGuardTests | `646fe47e3b73` |
| [hardware/g1_arm_bridge/test_gate7_capture_quality.py](../hardware/g1_arm_bridge/test_gate7_capture_quality.py) | 155 | 목록 확인 | Gate7CaptureQualityTests | `9a9517d80512` |
| [hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py) | 32 | 목록 확인 | Gate7FaultInjectionMatrixTests | `63b8b799b54f` |
| [hardware/g1_arm_bridge/test_gate7_first_live_profile.py](../hardware/g1_arm_bridge/test_gate7_first_live_profile.py) | 130 | 목록 확인 | Gate7FirstLiveProfileTests | `cf45df86d680` |
| [hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py) | 66 | 목록 확인 | _free_udp_port, Gate7HardwareVirtualE2ETests | `f905f33e9bfa` |
| [hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py) | 277 | 목록 확인 | Gate7LiveArmSdkTests | `28a1604626c1` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run.py) | 361 | 목록 확인 | _replace_dual, _sample, Gate7LiveDryRunTests | `7a777136e907` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py) | 136 | 목록 확인 | _free_udp_port, Gate7LiveDryRunE2ETests | `0eeb63044d28` |
| [hardware/g1_arm_bridge/test_gate7_live_entrypoint.py](../hardware/g1_arm_bridge/test_gate7_live_entrypoint.py) | 136 | 목록 확인 | Gate7LiveEntrypointTests | `c32b8752879f` |
| [hardware/g1_arm_bridge/test_gate7_live_safety_guard.py](../hardware/g1_arm_bridge/test_gate7_live_safety_guard.py) | 89 | 목록 확인 | Gate7LiveSafetyGuardTests | `398bb4186f52` |
| [hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py](../hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py) | 119 | 목록 확인 | _free_udp_port, Gate7MinkCaptureReplayTests | `a67b307d7562` |
| [hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py) | 258 | 목록 확인 | _packet, Gate7MinkWslRelayTests | `48e5b8ceda15` |
| [hardware/g1_arm_bridge/test_gate7_release_finalization.py](../hardware/g1_arm_bridge/test_gate7_release_finalization.py) | 192 | 목록 확인 | Gate7ReleaseFinalizationTests | `417fc5c11f86` |
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
| [hardware/g1_arm_bridge/test_run_omni_fake_g1_integration.py](../hardware/g1_arm_bridge/test_run_omni_fake_g1_integration.py) | 98 | 목록 확인 | omni_handler, serve, main | `461f4f319606` |
| [hardware/g1_arm_bridge/test_runtime_base_state_guard.py](../hardware/g1_arm_bridge/test_runtime_base_state_guard.py) | 212 | 목록 확인 | _Message, _yaw_quaternion_wxyz, _precheck, RuntimeBaseStateGuardTests | `9cd231d92daf` |
| [hardware/g1_arm_bridge/test_safety_gate.py](../hardware/g1_arm_bridge/test_safety_gate.py) | 124 | 목록 확인 | SafetyGateTests | `021ebefe3f9f` |
| [hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py) | 73 | 목록 확인 | ValidateRightArmJogCollisionPathTests | `fdf09a9611a9` |
| [hardware/g1_arm_bridge/test_waist_baseline_read_only.py](../hardware/g1_arm_bridge/test_waist_baseline_read_only.py) | 62 | 목록 확인 | State, test_fresh_recording_and_summary, test_loss_never_completes, test_summary_rejects_empty_and_bad_vectors | `918211cdc28c` |
| [hardware/g1_arm_bridge/test_waist_guard_offline.py](../hardware/g1_arm_bridge/test_waist_guard_offline.py) | 197 | 목록 확인 | WaistGuardTests | `5b0105c97c4a` |
| [hardware/g1_arm_bridge/test_waist_hold_offline.py](../hardware/g1_arm_bridge/test_waist_hold_offline.py) | 124 | 목록 확인 | WaistHoldStudyTests, test_each_axis_pd_direction_without_cross_axis_terms | `5eb9a63f86fc` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py) | 262 | 목록 확인 | load_precheck, measured_pose, build_offset_trajectory, build_endpoint_trajectories, validate_offset_path (+5) | `970f03459275` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py) | 43 | 목록 확인 | _argument_path, main | `b802ce6610b3` |
| [hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py](../hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py) | 64 | 목록 확인 | main | `172f652bdf8b` |
| [hardware/g1_arm_bridge/verify_initial_pose_sync.py](../hardware/g1_arm_bridge/verify_initial_pose_sync.py) | 130 | 목록 확인 | _load_captured_pose, main | `3de52d6177d1` |
| [hardware/g1_arm_bridge/waist_baseline_read_only.py](../hardware/g1_arm_bridge/waist_baseline_read_only.py) | 134 | 목록 확인 | Summarize, Capture, Run, main | `3b8a5324c857` |
| [hardware/g1_arm_bridge/waist_guard_offline.py](../hardware/g1_arm_bridge/waist_guard_offline.py) | 127 | 목록 확인 | WaistGuardStudy, AnalyzeCapture, main | `9a0fe6ef28e5` |
| [hardware/g1_arm_bridge/waist_hold_offline.py](../hardware/g1_arm_bridge/waist_hold_offline.py) | 102 | 목록 확인 | BuildStudyFrame, AnalyzeEvents, main | `dc8a3ed7697f` |
| [tools/ALLOW_G1_DDS_WSL.bat](../tools/ALLOW_G1_DDS_WSL.bat) | 12 | 목록 확인 | - | `e8e22cac61ce` |
| [tools/ALLOW_G1_DDS_WSL_ADMIN.ps1](../tools/ALLOW_G1_DDS_WSL_ADMIN.ps1) | 137 | 목록 확인 | - | `02a905d48817` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat) | 14 | 목록 확인 | - | `2855826cbe50` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1) | 112 | 목록 확인 | - | `908bf446bd5b` |
| [tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat](../tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat) | 32 | 목록 확인 | - | `bd53ccf085f5` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 108 | 목록 확인 | - | `a999bb9fc290` |
| [tools/CHECK_G1_TELEOP_STARTUP.bat](../tools/CHECK_G1_TELEOP_STARTUP.bat) | 66 | 목록 확인 | - | `bbaa4c38b10e` |
| [tools/CHECK_MJLAB_MATCHED_TRAINING.bat](../tools/CHECK_MJLAB_MATCHED_TRAINING.bat) | 25 | 목록 확인 | - | `4145b19da360` |
| [tools/CHECK_MJLAB_SETUP.bat](../tools/CHECK_MJLAB_SETUP.bat) | 10 | 목록 확인 | - | `6bf65972626f` |
| [tools/CHECK_MJLAB_SETUP.ps1](../tools/CHECK_MJLAB_SETUP.ps1) | 54 | 목록 확인 | - | `a7b43848415a` |
| [tools/CHECK_OMNI_GATEWAY_OFFLINE.bat](../tools/CHECK_OMNI_GATEWAY_OFFLINE.bat) | 15 | 목록 확인 | - | `1f22df6cf7e8` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 11 | 목록 확인 | - | `308b1b54bec6` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `53977cc931a4` |
| [tools/CONVERT_OMNI_CSV_BODY_VELOCITY.py](../tools/CONVERT_OMNI_CSV_BODY_VELOCITY.py) | 93 | 목록 확인 | _number, convert, main | `e8f154cc3771` |
| [tools/DETECT_G1_NETWORK.bat](../tools/DETECT_G1_NETWORK.bat) | 11 | 목록 확인 | - | `be9f63666f9c` |
| [tools/DETECT_G1_NETWORK_ADMIN.ps1](../tools/DETECT_G1_NETWORK_ADMIN.ps1) | 48 | 목록 확인 | - | `4ae700ad65c9` |
| [tools/EDIT_G1_STARTUP_READY_POSE.bat](../tools/EDIT_G1_STARTUP_READY_POSE.bat) | 33 | 목록 확인 | - | `64872de03943` |
| [tools/G1_CAMERA_LAUNCH.py](../tools/G1_CAMERA_LAUNCH.py) | 31 | 목록 확인 | main | `f6d11f6ffebb` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `43a32b2e3524` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 126 | 목록 확인 | - | `acf79f4cc8e0` |
| [tools/G1_INPUT_OBSERVATION_LAUNCH.py](../tools/G1_INPUT_OBSERVATION_LAUNCH.py) | 131 | 목록 확인 | worker_command, engine_environment, preflight, main | `780d2da11eca` |
| [tools/G1_INPUT_RECEIVE_AUDIT.py](../tools/G1_INPUT_RECEIVE_AUDIT.py) | 597 | 목록 확인 | _stdout_line, LatestOutput, _aged_payload, display_view, AsyncLog (+15) | `acd30b233117` |
| [tools/G1_VR_TELEOP_LAUNCH.py](../tools/G1_VR_TELEOP_LAUNCH.py) | 318 | 목록 확인 | windows_arguments, process_arguments, collapse_venv_redirectors, option, option_casefold (+10) | `3ad1fb4ca67e` |
| [tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat](../tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat) | 29 | 목록 확인 | - | `fde6c1d57d72` |
| [tools/PREPARE_G1_GATE6_HOLD.bat](../tools/PREPARE_G1_GATE6_HOLD.bat) | 39 | 목록 확인 | - | `3153383c91bf` |
| [tools/PRINT_G1_INPUTS_50HZ.bat](../tools/PRINT_G1_INPUTS_50HZ.bat) | 7 | 목록 확인 | - | `3d7b076d08e6` |
| [tools/PRINT_G1_INPUTS_50HZ.py](../tools/PRINT_G1_INPUTS_50HZ.py) | 228 | 목록 확인 | finite, arm_value, omni_value, LogTail, newest (+1) | `3eec882fce0d` |
| [tools/RECORD_G1_WAIST_BASELINE_READ_ONLY.bat](../tools/RECORD_G1_WAIST_BASELINE_READ_ONLY.bat) | 11 | 목록 확인 | - | `f921f5b124f9` |
| [tools/RECORD_MINK_RIGHT_ARM_CSV.bat](../tools/RECORD_MINK_RIGHT_ARM_CSV.bat) | 12 | 목록 확인 | - | `9c4de42752b0` |
| [tools/RECORD_OMNI_TIMESERIES_CSV.bat](../tools/RECORD_OMNI_TIMESERIES_CSV.bat) | 34 | 목록 확인 | - | `b9b4b1c0e91f` |
| [tools/REPORT_LATEST_BIMANUAL_SESSION.bat](../tools/REPORT_LATEST_BIMANUAL_SESSION.bat) | 14 | 목록 확인 | - | `9f2dcc428c8d` |
| [tools/RESOLVE_UNITY_EDITOR.bat](../tools/RESOLVE_UNITY_EDITOR.bat) | 39 | 목록 확인 | - | `d70d9fa8069a` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 11 | 목록 확인 | - | `698638321bb5` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 23 | 목록 확인 | - | `5e59d64f9745` |
| [tools/RUN_BIMANUAL_NEAR_HANDS_SWEEP.bat](../tools/RUN_BIMANUAL_NEAR_HANDS_SWEEP.bat) | 10 | 목록 확인 | - | `51d2406afc62` |
| [tools/RUN_BIMANUAL_UDP_CYCLE.bat](../tools/RUN_BIMANUAL_UDP_CYCLE.bat) | 11 | 목록 확인 | - | `3579acfe09d8` |
| [tools/RUN_MUJOCO_PD_FINAL.bat](../tools/RUN_MUJOCO_PD_FINAL.bat) | 16 | 목록 확인 | - | `b13b5ff4d843` |
| [tools/RUN_MUJOCO_PD_SWEEP.bat](../tools/RUN_MUJOCO_PD_SWEEP.bat) | 13 | 목록 확인 | - | `96f245582275` |
| [tools/RUN_PC_TWIST2.ps1](../tools/RUN_PC_TWIST2.ps1) | 21 | 목록 확인 | - | `1bc2957fae09` |
| [tools/SEND_G1_INPUT_AUDIT.bat](../tools/SEND_G1_INPUT_AUDIT.bat) | 7 | 목록 확인 | - | `9bb5687f5d55` |
| [tools/SETUP_G1_VR_TELEOP.bat](../tools/SETUP_G1_VR_TELEOP.bat) | 8 | 목록 확인 | - | `6de98da7a96a` |
| [tools/SETUP_G1_VR_TELEOP.py](../tools/SETUP_G1_VR_TELEOP.py) | 54 | 목록 확인 | main | `9187c1d018d6` |
| [tools/SET_UNITY_DISPLAY_MODE.ps1](../tools/SET_UNITY_DISPLAY_MODE.ps1) | 25 | 입출력 확인 | - | `d9f1eb1f0fca` |
| [tools/START_BIMANUAL_SIM.bat](../tools/START_BIMANUAL_SIM.bat) | 8 | 목록 확인 | - | `71e88b6d7d0e` |
| [tools/START_BIMANUAL_UNITY_SIM.bat](../tools/START_BIMANUAL_UNITY_SIM.bat) | 8 | 목록 확인 | - | `e9d4bf84af68` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 13 | 목록 확인 | - | `61dc0d12f4d1` |
| [tools/START_G1_GATE5_READ_ONLY.bat](../tools/START_G1_GATE5_READ_ONLY.bat) | 37 | 목록 확인 | - | `5315ab2202d3` |
| [tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat](../tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat) | 112 | 목록 확인 | - | `8ec7aff5f329` |
| [tools/START_G1_GATE6_WEIGHT_HOLD.bat](../tools/START_G1_GATE6_WEIGHT_HOLD.bat) | 12 | 목록 확인 | - | `b8dbcd9271f0` |
| [tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat](../tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat) | 25 | 목록 확인 | - | `6729696ed64b` |
| [tools/START_G1_GATE7_LIVE_DRY_RUN.bat](../tools/START_G1_GATE7_LIVE_DRY_RUN.bat) | 57 | 목록 확인 | - | `6876359ad681` |
| [tools/START_G1_GATE7_LIVE_HARDWARE.bat](../tools/START_G1_GATE7_LIVE_HARDWARE.bat) | 235 | 목록 확인 | - | `1c9a01f164c1` |
| [tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat](../tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat) | 92 | 목록 확인 | - | `264801696a18` |
| [tools/START_G1_GATE7_STANDARD_MINK.bat](../tools/START_G1_GATE7_STANDARD_MINK.bat) | 11 | 목록 확인 | - | `fbdb745798a1` |
| [tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat](../tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat) | 25 | 목록 확인 | - | `20b8d69ecc4c` |
| [tools/START_G1_GATE7_VR_RECORDING.bat](../tools/START_G1_GATE7_VR_RECORDING.bat) | 59 | 목록 확인 | - | `08e220d36e68` |
| [tools/START_G1_INPUT_OBSERVATION.bat](../tools/START_G1_INPUT_OBSERVATION.bat) | 13 | 목록 확인 | - | `2a1d356e7f4e` |
| [tools/START_G1_READ_ONLY.bat](../tools/START_G1_READ_ONLY.bat) | 15 | 목록 확인 | - | `a7662ec59842` |
| [tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat](../tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat) | 128 | 목록 확인 | - | `cb2107ef0a12` |
| [tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat](../tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat) | 128 | 목록 확인 | - | `e059a027d941` |
| [tools/START_G1_STATIC_STAND_HANDOFF_PROBE.bat](../tools/START_G1_STATIC_STAND_HANDOFF_PROBE.bat) | 27 | 목록 확인 | - | `e0fb9dd526b4` |
| [tools/START_G1_VELOCITY_MINK_KEYPAD.bat](../tools/START_G1_VELOCITY_MINK_KEYPAD.bat) | 10 | 목록 확인 | - | `b0de90824b7a` |
| [tools/START_G1_VELOCITY_MINK_KEYPAD.ps1](../tools/START_G1_VELOCITY_MINK_KEYPAD.ps1) | 70 | 목록 확인 | - | `d99f06c565c8` |
| [tools/START_G1_VR_PREVIEW_READ_ONLY.bat](../tools/START_G1_VR_PREVIEW_READ_ONLY.bat) | 43 | 목록 확인 | - | `6cc01c4110cb` |
| [tools/START_G1_VR_TELEOP.bat](../tools/START_G1_VR_TELEOP.bat) | 21 | 목록 확인 | - | `fa80b93ee095` |
| [tools/START_MINK_ARM_CYCLE_SIMULATION.bat](../tools/START_MINK_ARM_CYCLE_SIMULATION.bat) | 28 | 목록 확인 | - | `a8f59879ece0` |
| [tools/START_MINK_G1_HARDWARE_SYNC.bat](../tools/START_MINK_G1_HARDWARE_SYNC.bat) | 66 | 목록 확인 | - | `fa24c6c45e36` |
| [tools/START_MINK_SPEED_COMPARISON.bat](../tools/START_MINK_SPEED_COMPARISON.bat) | 15 | 목록 확인 | - | `9013c5814e8d` |
| [tools/START_MJLAB_MATCHED_CONTINUATION.bat](../tools/START_MJLAB_MATCHED_CONTINUATION.bat) | 21 | 목록 확인 | - | `c4f939d0ba5d` |
| [tools/START_MJLAB_RECORDED_CURRICULUM.bat](../tools/START_MJLAB_RECORDED_CURRICULUM.bat) | 23 | 목록 확인 | - | `8ba4dd09876e` |
| [tools/START_OMNI_FAKE_G1_INTEGRATION.bat](../tools/START_OMNI_FAKE_G1_INTEGRATION.bat) | 27 | 목록 확인 | - | `dcbcdabb3e99` |
| [tools/START_OMNI_GATEWAY_READONLY.bat](../tools/START_OMNI_GATEWAY_READONLY.bat) | 11 | 목록 확인 | - | `5f4abe1e16ea` |
| [tools/START_TWIST2_MINK_CYCLE_CANDIDATE.bat](../tools/START_TWIST2_MINK_CYCLE_CANDIDATE.bat) | 11 | 목록 확인 | - | `ea3f39c82b6e` |
| [tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1](../tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1) | 70 | 목록 확인 | - | `cfc3deae56f9` |
| [tools/START_TWIST2_MINK_UDP.bat](../tools/START_TWIST2_MINK_UDP.bat) | 11 | 목록 확인 | - | `80f69ec02672` |
| [tools/START_TWIST2_MINK_UDP.ps1](../tools/START_TWIST2_MINK_UDP.ps1) | 56 | 목록 확인 | - | `7e18f6a990a5` |
| [tools/START_TWIST2_PD_SWEEP_TO_VR.bat](../tools/START_TWIST2_PD_SWEEP_TO_VR.bat) | 6 | 목록 확인 | - | `05c42d5226e0` |
| [tools/START_TWIST2_VR_INPUT_SHADOW.bat](../tools/START_TWIST2_VR_INPUT_SHADOW.bat) | 30 | 목록 확인 | - | `5c635fd8bee2` |
| [tools/TEST_CAMERA_REPLAY_TO_UNITY.bat](../tools/TEST_CAMERA_REPLAY_TO_UNITY.bat) | 104 | 목록 확인 | - | `06550a973e85` |
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
| [tools/TEST_G1_MINK_FK_PARITY.bat](../tools/TEST_G1_MINK_FK_PARITY.bat) | 73 | 목록 확인 | - | `0f02d258eda6` |
| [tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat](../tools/TEST_G1_RIGHT_ARM_JOG_OFFLINE.bat) | 43 | 목록 확인 | - | `82d5a9f2f879` |
| [tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat](../tools/TEST_G1_SHOULDER_PITCH_FULL_AUTHORITY_OFFLINE.bat) | 40 | 목록 확인 | - | `b99057a32b5c` |
| [tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat](../tools/TEST_G1_STARTUP_RECOVERY_OFFLINE.bat) | 31 | 목록 확인 | - | `c94d9691fe18` |
| [tools/TEST_G1_WAIST_HOLD_OFFLINE.bat](../tools/TEST_G1_WAIST_HOLD_OFFLINE.bat) | 16 | 목록 확인 | - | `f3525c2d1433` |
| [tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat](../tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat) | 27 | 목록 확인 | - | `fb79771d5d08` |
| [tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat](../tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat) | 47 | 목록 확인 | - | `0d6db212eebb` |
| [tools/TEST_MINK_SAFETY_PIPELINE.bat](../tools/TEST_MINK_SAFETY_PIPELINE.bat) | 35 | 목록 확인 | - | `3592659bb64f` |
| [tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat](../tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat) | 32 | 목록 확인 | - | `cc44ceb0ae2a` |
| [tools/TEST_MINK_WRIST_FRAME.bat](../tools/TEST_MINK_WRIST_FRAME.bat) | 34 | 목록 확인 | - | `414187888f10` |
| [tools/VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1](../tools/VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1) | 60 | 목록 확인 | - | `9e287563ddd1` |
| [tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat](../tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat) | 27 | 목록 확인 | - | `eae096375075` |
| [tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat](../tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat) | 24 | 목록 확인 | - | `ef2a1e631f62` |
| [tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat) | 29 | 목록 확인 | - | `863b6b3bab9c` |
| [tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat) | 35 | 목록 확인 | - | `6a5931f23923` |
| [tools/VIEW_G1_LIVE_MUJOCO.bat](../tools/VIEW_G1_LIVE_MUJOCO.bat) | 45 | 목록 확인 | - | `260f114b0f46` |
| [tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat](../tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat) | 35 | 목록 확인 | - | `2169a22c9d3f` |
| [tools/VIEW_G1_STARTUP_RECOVERY.bat](../tools/VIEW_G1_STARTUP_RECOVERY.bat) | 28 | 목록 확인 | - | `401c61f102ba` |
| [tools/audit_ik_licenses.py](../tools/audit_ik_licenses.py) | 82 | 목록 확인 | collect, main | `4b2b83dbe7bc` |
| [tools/bimanual_preflight.py](../tools/bimanual_preflight.py) | 205 | 목록 확인 | sha256, require, check_runtime_scene, check_source_installer, check_tool_contracts (+5) | `2af48db04afa` |
| [tools/evaluate_g1_velocity_direction_mujoco.py](../tools/evaluate_g1_velocity_direction_mujoco.py) | 173 | 목록 확인 | sha256, gravity_orientation, yaw_from_quaternion, wrapped, step_policy (+2) | `9c1a358f0c47` |
| [tools/g1_camera_ssh.py](../tools/g1_camera_ssh.py) | 115 | 목록 확인 | read_exact, read_packet, check_environment, run | `46724a85e7aa` |
| [tools/g1_lowstate_view.py](../tools/g1_lowstate_view.py) | 103 | 목록 확인 | validate, run | `4a4e83208060` |
| [tools/g1_observation_tap.py](../tools/g1_observation_tap.py) | 85 | 목록 확인 | next_deadline, ObservationTap | `1970f5344e6e` |
| [tools/g1_portable_environment.py](../tools/g1_portable_environment.py) | 145 | 목록 확인 | select_robot_host, prepare_camera_sources, configure_mirrored_network, wsl_prefix, wsl_path (+3) | `5096bd23341a` |
| [tools/g1_process_lifetime.py](../tools/g1_process_lifetime.py) | 57 | 목록 확인 | bind_session_lifetime | `73562a1df329` |
| [tools/g1_quiet_observation.py](../tools/g1_quiet_observation.py) | 91 | 목록 확인 | receive, run_workers | `96069601f1e4` |
| [tools/g1_source_archive_check.py](../tools/g1_source_archive_check.py) | 35 | 목록 확인 | verify | `35d6c8764945` |
| [tools/g1_ssh_login.py](../tools/g1_ssh_login.py) | 86 | 목록 확인 | key_path, identity_options, registration_command, probe, ensure_login (+1) | `c19bc5adaefe` |
| [tools/g1_teleop_dependencies.py](../tools/g1_teleop_dependencies.py) | 112 | 목록 확인 | requirements, probe, validate, ensure, main | `94234b3d339b` |
| [tools/replay_omni_velocity_mujoco.py](../tools/replay_omni_velocity_mujoco.py) | 144 | 목록 확인 | roll_pitch, load_commands, main | `0b80637b5646` |
| [tools/run_logged_standard_mink.py](../tools/run_logged_standard_mink.py) | 64 | 목록 확인 | main | `934e15f603a5` |
| [tools/test_convert_omni_csv_body_velocity.py](../tools/test_convert_omni_csv_body_velocity.py) | 38 | 목록 확인 | ConvertOmniCsvTests | `2992c1de8f2f` |
