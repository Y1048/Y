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
| [MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py](../MuJoCo_G1_Controller/scripts/export_g1_mink_fk_reference.py) | 81 | 목록 확인 | mujoco_to_unity_delta, main | `f12675084b20` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py) | 8 | 목록 확인 | - | `d2d8d9b6e9b4` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py) | 305 | 목록 확인 | ElbowClearanceTask, ShoulderComfortTask, ArmMotionPolicy | `4ee0fd6e406d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_return.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_return.py) | 288 | 목록 확인 | BimanualReturnMotion | `379a49a2315b` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py) | 130 | 목록 확인 | startup_stage, require_validated_engine, load_engine, runtime_metadata, main | `c92c5cdafe0f` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py) | 586 | 목록 확인 | _recorded_motion_limits, _current_motion_limits, _open_text, _percentiles, _current_source_hashes (+7) | `100d56344e2d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py) | 408 | 목록 확인 | BimanualSimulation, targets_from_json, main | `ca697a3f785e` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_udp_cycle.py) | 317 | 목록 확인 | make_packet, free_loopback_port, send_packet, valid_feedback, wait_feedback (+6) | `7820bd59b50d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py) | 447 | 목록 확인 | decode, PairedHandFilter, UnityCycle, main | `203e77a5f6ab` |
| [MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py](../MuJoCo_G1_Controller/scripts/g1_gate7_feedback.py) | 77 | 목록 확인 | drain_gate7_simulation_feedback, apply_gate7_simulation_feedback | `a3b14b20de41` |
| [MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py](../MuJoCo_G1_Controller/scripts/g1_lowstate_seed.py) | 83 | 목록 확인 | ReadSeedBytes, ReadSeed, ApplySeed | `40b9a82decb2` |
| [MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py](../MuJoCo_G1_Controller/scripts/g1_mink_collision_policy.py) | 27 | 목록 확인 | ResolveCollisionProfile | `690f7acc0dbd` |
| [MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/g1_mink_command_provenance.py) | 45 | 목록 확인 | mark_simulation_cycle_packet, mark_live_mink_packet, wrap_state_packet_factory | `51ddeae5e507` |
| [MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py](../MuJoCo_G1_Controller/scripts/g1_mink_diagnostics.py) | 10 | 목록 확인 | orientation_diagnostics | `a3b8dbe9cd27` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 입출력 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `8147bb9f7c17` |
| [MuJoCo_G1_Controller/scripts/g1_mink_live_cycle_bridge.py](../MuJoCo_G1_Controller/scripts/g1_mink_live_cycle_bridge.py) | 86 | 목록 확인 | live_tracking_active, LiveCycleBridge | `bf7082f653a2` |
| [MuJoCo_G1_Controller/scripts/g1_mink_return_cycle.py](../MuJoCo_G1_Controller/scripts/g1_mink_return_cycle.py) | 83 | 목록 확인 | SimulationReturnCycle | `559469d25aae` |
| [MuJoCo_G1_Controller/scripts/g1_mink_speed_profiles.py](../MuJoCo_G1_Controller/scripts/g1_mink_speed_profiles.py) | 26 | 목록 확인 | speed_profile, live_joint_bounds | `ce82f78cc72e` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 124 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `63245c475273` |
| [MuJoCo_G1_Controller/scripts/g1_right_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_right_arm_common.py) | 425 | 목록 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `a2f245b04714` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `a0f98164bca0` |
| [MuJoCo_G1_Controller/scripts/g1_tracking_diagnostic.py](../MuJoCo_G1_Controller/scripts/g1_tracking_diagnostic.py) | 47 | 목록 확인 | TrackingDiagnostic | `b22e53d57388` |
| [MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py](../MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py) | 502 | 목록 확인 | AccelerationBound, ElbowClearanceTask, ShoulderComfortTask, UpstreamMinkTracking | `5ca03dc2c9a2` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 269 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `989afa4361e5` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype.py) | 930 | 목록 확인 | parse_args, _update_reachability_limit, _find_body, _prepare_mink_xml, LoadMinkModel (+26) | `96b4b6d84716` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_prototype_entry.py) | 20 | 목록 확인 | main | `aebdd2dc962a` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py) | 1167 | 입출력 확인 | cycle_velocity_limits, parse_args, _write_right_arm_csv_row, main | `5259a299e02e` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live_entry.py) | 41 | 목록 확인 | main | `fb03f1d7da12` |
| [MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py](../MuJoCo_G1_Controller/scripts/run_mink_g1_simulation_312.py) | 80 | 목록 확인 | LoadEngine, MarkSimulation, main | `36be8e5dc299` |
| [MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py](../MuJoCo_G1_Controller/scripts/test_mink_command_provenance.py) | 101 | 목록 확인 | MinkCommandProvenanceTests | `7d25329d76b6` |
| [MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py](../MuJoCo_G1_Controller/scripts/test_mink_wrist_frame_contract.py) | 99 | 목록 확인 | require, require_pattern, forbid, main | `30cc0d077b66` |
| [START_MUJOCO_ONLY.bat](../START_MUJOCO_ONLY.bat) | 55 | 목록 확인 | - | `006b807a3319` |
| [START_VR_HAND_TO_MUJOCO.bat](../START_VR_HAND_TO_MUJOCO.bat) | 327 | 입출력 확인 | - | `b2256ac6ad6d` |
| [START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat](../START_VR_HAND_TO_MUJOCO_VANILLA_MINK.bat) | 33 | 목록 확인 | - | `142187d98e6b` |
| [START_VR_STANDARD_MINK.bat](../START_VR_STANDARD_MINK.bat) | 5 | 목록 확인 | - | `c81bbd809590` |
| [Unity_G1_VR/Assets/Editor/G1BimanualSimulationSetup.cs](../Unity_G1_VR/Assets/Editor/G1BimanualSimulationSetup.cs) | 59 | 목록 확인 | - | `a3ce77578102` |
| [Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs](../Unity_G1_VR/Assets/Editor/G1ExistingSceneSetup.cs) | 431 | 목록 확인 | - | `84c6850d4c57` |
| [Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs](../Unity_G1_VR/Assets/Editor/G1MinkFkParityValidator.cs) | 134 | 목록 확인 | - | `3a842c8567a3` |
| [Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs](../Unity_G1_VR/Assets/Editor/G1OfficialModelImporter.cs) | 591 | 목록 확인 | - | `0cc491e3db1b` |
| [Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs](../Unity_G1_VR/Assets/Editor/G1SameSceneBimanualSetup.cs) | 92 | 목록 확인 | - | `fd1e225def8d` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 638 | 목록 확인 | - | `f4ac67032122` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 67 | 목록 확인 | - | `3f198318b963` |
| [Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs](../Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs) | 222 | 목록 확인 | - | `fd7a7ec659d2` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs) | 40 | 목록 확인 | - | `df0560f6d8dd` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs) | 588 | 목록 확인 | - | `9a89db62fe7e` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 962 | 입출력 확인 | - | `a721e96e6405` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 539 | 입출력 확인 | - | `2de01db7eff5` |
| [Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1HandUdpDiagnostics.cs) | 98 | 목록 확인 | - | `40a96eb5264c` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 652 | 목록 확인 | - | `9fcbda59e81b` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 288 | 목록 확인 | - | `e6b5bc0732e9` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1KeypadLocomotionUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1KeypadLocomotionUdpSender.cs) | 251 | 목록 확인 | - | `57c9e499aaa5` |
| [Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs](../Unity_G1_VR/Assets/G1Teleop/G1LiveTeleopTrace.cs) | 280 | 목록 확인 | - | `99a798753602` |
| [Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs](../Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs) | 100 | 목록 확인 | - | `d560f0a9416c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 375 | 목록 확인 | - | `db28be0dcd81` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs) | 105 | 목록 확인 | - | `95ec4689277c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs) | 46 | 목록 확인 | - | `43571574c2ee` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 798 | 입출력 확인 | - | `de657432b645` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 1087 | 입출력 확인 | - | `f67b180ed3c4` |
| [Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs](../Unity_G1_VR/Assets/G1Teleop/G1WristSourceCompatibility.cs) | 50 | 목록 확인 | - | `3124aab0e080` |
| [VIEW_IK_COMPARISON.bat](../VIEW_IK_COMPARISON.bat) | 19 | 목록 확인 | - | `17ffd9697177` |
| [VIEW_TRAJECTORY_AB.bat](../VIEW_TRAJECTORY_AB.bat) | 14 | 목록 확인 | - | `9f40194143f6` |
| [backend/g1_teleop/__init__.py](../backend/g1_teleop/__init__.py) | 101 | 목록 확인 | - | `86664979265c` |
| [backend/g1_teleop/calibration.py](../backend/g1_teleop/calibration.py) | 363 | 목록 확인 | _pose_matrix, _scale_vector, _pose_to_dict, _pose_from_dict, ArmCalibration (+8) | `85896a984f22` |
| [backend/g1_teleop/camera.py](../backend/g1_teleop/camera.py) | 314 | 목록 확인 | CameraIntrinsics, CameraFrame, HeadCameraSource, MuJoCoHeadCameraSource, RealSenseD435iSource (+1) | `cea6222b9f0b` |
| [backend/g1_teleop/camera_factory.py](../backend/g1_teleop/camera_factory.py) | 103 | 목록 확인 | load_camera_profile, validate_camera_profile, validate_teleimager_profile, create_head_camera_source | `be67122afd33` |
| [backend/g1_teleop/command_adapter.py](../backend/g1_teleop/command_adapter.py) | 182 | 입출력 확인 | InternalCommand, _decode_object, _legacy_integer, _legacy_source_time_ns, _legacy_vector (+4) | `eb251eba6545` |
| [backend/g1_teleop/config.py](../backend/g1_teleop/config.py) | 240 | 목록 확인 | NetworkConfig, RuntimeConfig, MotionConfig, IKConfig, CollisionConfig (+11) | `39c5230afa90` |
| [backend/g1_teleop/g1_camera_mount.py](../backend/g1_teleop/g1_camera_mount.py) | 60 | 목록 확인 | _find_body, add_g1_d435i_camera | `6ce8092bf39b` |
| [backend/g1_teleop/gate7_simulation_feedback.py](../backend/g1_teleop/gate7_simulation_feedback.py) | 153 | 목록 확인 | Gate7SimulationFeedbackError, Gate7SimulationFeedback, _finite_vector, build_packet, parse_packet (+1) | `89aa873e72b0` |
| [backend/g1_teleop/inspection_contact.py](../backend/g1_teleop/inspection_contact.py) | 161 | 목록 확인 | InspectionContactState, InspectionContactTransition, InspectionContactStateMachine, install_inspection_contact_monitor | `8241c3028ba3` |
| [backend/g1_teleop/inspection_demo.py](../backend/g1_teleop/inspection_demo.py) | 159 | 목록 확인 | InspectionDemoState, InspectionDemoSnapshot, InspectionDemoTracker, append_inspection_result | `92a6711f4497` |
| [backend/g1_teleop/live_receiver.py](../backend/g1_teleop/live_receiver.py) | 136 | 입출력 확인 | DatagramSocket, ReceiveBatch, receive_available_commands | `1d02a4ee903a` |
| [backend/g1_teleop/mapping.py](../backend/g1_teleop/mapping.py) | 36 | 목록 확인 | map_unity_ovr_wrist_to_head_yaw | `5166bfed6876` |
| [backend/g1_teleop/mink_command_stream.py](../backend/g1_teleop/mink_command_stream.py) | 268 | 입출력 확인 | MinkCommandUpdate, MinkCommandStream | `16c73cd7e8f5` |
| [backend/g1_teleop/motion_reference.py](../backend/g1_teleop/motion_reference.py) | 64 | 목록 확인 | step_position, step_rotation | `cef1334bbb00` |
| [backend/g1_teleop/protocol.py](../backend/g1_teleop/protocol.py) | 370 | 목록 확인 | ProtocolError, _boolean, _finite_vector, _integer, _nonempty_string (+7) | `88c342204ae4` |
| [backend/g1_teleop/runtime_state.py](../backend/g1_teleop/runtime_state.py) | 91 | 목록 확인 | RuntimeTransition, TeleopRuntimeStateMachine | `43b826597eb4` |
| [backend/g1_teleop/source_provenance.py](../backend/g1_teleop/source_provenance.py) | 135 | 목록 확인 | SourceAcceptance, _SessionClock, CommandSourceGuard | `4e152f262150` |
| [backend/g1_teleop/transforms.py](../backend/g1_teleop/transforms.py) | 243 | 목록 확인 | validate_rotation_matrix, validate_pose_matrix, normalize_quaternion, quaternion_to_matrix, matrix_to_quaternion (+9) | `fbb8ca833758` |
| [backend/g1_teleop/unitree_image_transport.py](../backend/g1_teleop/unitree_image_transport.py) | 111 | 목록 확인 | shared_memory_name, UnitreeImageHeader, UnitreeSimImageWriter | `d2c08bb150f2` |
| [backend/g1_teleop/watchdog.py](../backend/g1_teleop/watchdog.py) | 227 | 목록 확인 | PacketAcceptance, SequenceWatchdog, SessionSequenceWatchdog, WorkspaceFaultLatch, WorkspaceExitDebounce | `b53c34c946c1` |
| [backend/tests/BimanualEngageGateTest.cs](../backend/tests/BimanualEngageGateTest.cs) | 32 | 목록 확인 | - | `2a05b9a1edc9` |
| [backend/tests/BimanualFeedbackGateTest.cs](../backend/tests/BimanualFeedbackGateTest.cs) | 35 | 목록 확인 | - | `fdd9e6c5a16c` |
| [backend/tests/bimanual_replay_profiles.py](../backend/tests/bimanual_replay_profiles.py) | 29 | 목록 확인 | historical_recording_profile | `4e78221ae01f` |
| [backend/tests/csharp/G1OmniHeadingStateTests.cs](../backend/tests/csharp/G1OmniHeadingStateTests.cs) | 34 | 목록 확인 | - | `36f1f4de84fd` |
| [backend/tests/fixtures/bimanual_return_near_hands_20260918.json](../backend/tests/fixtures/bimanual_return_near_hands_20260918.json) | 636 | 목록 확인 | - | `e6f50f455377` |
| [backend/tests/fixtures/bimanual_return_starts_20260918.json](../backend/tests/fixtures/bimanual_return_starts_20260918.json) | 127 | 목록 확인 | - | `0e42927f9660` |
| [backend/tests/fixtures/mink_elbow_boundary_20260909.json](../backend/tests/fixtures/mink_elbow_boundary_20260909.json) | 63 | 목록 확인 | - | `c13defb346d4` |
| [backend/tests/fixtures/mink_front_elbow_20260917.json](../backend/tests/fixtures/mink_front_elbow_20260917.json) | 104 | 목록 확인 | - | `648f33cbe876` |
| [backend/tests/fixtures/mink_projected_wrist_rotation_20260917.json](../backend/tests/fixtures/mink_projected_wrist_rotation_20260917.json) | 104 | 목록 확인 | - | `11d50dfd2e5d` |
| [backend/tests/fixtures/mink_wrist_priority_20260909.json](../backend/tests/fixtures/mink_wrist_priority_20260909.json) | 126 | 목록 확인 | - | `1a546d5f50e4` |
| [backend/tests/test_arm_cycle_stream_integration.py](../backend/tests/test_arm_cycle_stream_integration.py) | 72 | 목록 확인 | IntegratedCycleTest | `0437cd06c7d6` |
| [backend/tests/test_batch_failure_guidance.py](../backend/tests/test_batch_failure_guidance.py) | 70 | 목록 확인 | BatchFailureGuidanceTest | `05e261289c21` |
| [backend/tests/test_bimanual_boundaries.py](../backend/tests/test_bimanual_boundaries.py) | 210 | 목록 확인 | OutputContinuityTests, ProtocolBoundaryTests | `7ec74c8d6626` |
| [backend/tests/test_bimanual_marker_feedback.py](../backend/tests/test_bimanual_marker_feedback.py) | 132 | 목록 확인 | MarkerFeedbackTests | `47ad0def0fec` |
| [backend/tests/test_bimanual_motion_quality.py](../backend/tests/test_bimanual_motion_quality.py) | 289 | 목록 확인 | quality_case, replay_recorded_motion, MotionQualityTests, PoseFilterTests | `ae5294506d54` |
| [backend/tests/test_bimanual_near_hands_sweep.py](../backend/tests/test_bimanual_near_hands_sweep.py) | 269 | 목록 확인 | TriggerDecisionReached, fixture_q14, full_q, find_threshold_fraction, find_safe_lower_fraction (+4) | `a2b3093612ff` |
| [backend/tests/test_bimanual_quest_reengage.py](../backend/tests/test_bimanual_quest_reengage.py) | 149 | 목록 확인 | rows, QuestReengageReplayTests | `b9c810f2463c` |
| [backend/tests/test_bimanual_recorded_session.py](../backend/tests/test_bimanual_recorded_session.py) | 178 | 목록 확인 | load_fixture, RecordedStagedSessionTests | `b5171d78b2f4` |
| [backend/tests/test_bimanual_return.py](../backend/tests/test_bimanual_return.py) | 480 | 목록 확인 | assert_output, recorded_return, StagedReturnTests | `ebfff5ccb53d` |
| [backend/tests/test_bimanual_runtime.py](../backend/tests/test_bimanual_runtime.py) | 156 | 목록 확인 | fake_engine, RuntimeTests | `71409c57a605` |
| [backend/tests/test_bimanual_session_report.py](../backend/tests/test_bimanual_session_report.py) | 413 | 목록 확인 | SessionReportTests | `e29f4d7925d9` |
| [backend/tests/test_bimanual_sim.py](../backend/tests/test_bimanual_sim.py) | 245 | 목록 확인 | BimanualTests | `f5a0afee7364` |
| [backend/tests/test_bimanual_unity_sim.py](../backend/tests/test_bimanual_unity_sim.py) | 271 | 목록 확인 | packet, CycleTests | `85eb715512ee` |
| [backend/tests/test_capture_output_isolation.py](../backend/tests/test_capture_output_isolation.py) | 67 | 목록 확인 | test_same_second_names_are_unique, test_existing_outputs_never_overwritten | `347052b473b3` |
| [backend/tests/test_code_index.py](../backend/tests/test_code_index.py) | 42 | 목록 확인 | CodeIndexTests | `bfd86a963b9d` |
| [backend/tests/test_dds_firewall_rollback.py](../backend/tests/test_dds_firewall_rollback.py) | 128 | 목록 확인 | test_transaction, test_adapter_selection, run_mock | `976cf7e761ac` |
| [backend/tests/test_diagnostic_exit_contract.py](../backend/tests/test_diagnostic_exit_contract.py) | 351 | 목록 확인 | test_camera_read_deadline_csharp_without_network, test_camera_play_stop_never_waits_on_receiver_task, test_camera_cli_rejects_nonfinite_without_transport, test_network_final_state_is_verified, test_adapter_selection_is_unambiguous (+5) | `242bee7959d4` |
| [backend/tests/test_ethernet_dns_transaction.py](../backend/tests/test_ethernet_dns_transaction.py) | 77 | 목록 확인 | test_dns_mode_recovery, test_snapshot_precedes_ip_changes | `30ba34915632` |
| [backend/tests/test_ethernet_transaction.py](../backend/tests/test_ethernet_transaction.py) | 105 | 목록 확인 | test_ethernet_transaction | `ad0a42498213` |
| [backend/tests/test_feasible_target_return.py](../backend/tests/test_feasible_target_return.py) | 79 | 목록 확인 | ReturnTests | `d7ee47e95e29` |
| [backend/tests/test_foundation.py](../backend/tests/test_foundation.py) | 380 | 목록 확인 | RigidPoseValidationTest, FoundationTest | `2095699d540f` |
| [backend/tests/test_g1_body_translation_math.py](../backend/tests/test_g1_body_translation_math.py) | 31 | 목록 확인 | BodyTranslationTests | `79376e3dcf64` |
| [backend/tests/test_g1_camera_ssh.py](../backend/tests/test_g1_camera_ssh.py) | 52 | 목록 확인 | CameraTests | `13f331072539` |
| [backend/tests/test_g1_input_console.py](../backend/tests/test_g1_input_console.py) | 86 | 목록 확인 | arm_row, ConsoleTests | `9d264ab75632` |
| [backend/tests/test_g1_lowstate_view.py](../backend/tests/test_g1_lowstate_view.py) | 28 | 목록 확인 | LowStateTests | `51a289d5a2b5` |
| [backend/tests/test_g1_observation_audit.py](../backend/tests/test_g1_observation_audit.py) | 330 | 목록 확인 | packet, source_packet, AuditTests | `6037c1f78ca9` |
| [backend/tests/test_g1_observation_pipeline.py](../backend/tests/test_g1_observation_pipeline.py) | 375 | 목록 확인 | ObservationPipelineTests, ObservationLauncherTests | `1002fff2e907` |
| [backend/tests/test_g1_observation_tap.py](../backend/tests/test_g1_observation_tap.py) | 223 | 목록 확인 | ObservationTapTests, ProducerPreservationTests | `8ca75624d2cb` |
| [backend/tests/test_g1_omni_transport_recovery.py](../backend/tests/test_g1_omni_transport_recovery.py) | 152 | 목록 확인 | LocalOmniServer, OmniTransportRecoveryTests | `dcc10160c2aa` |
| [backend/tests/test_g1_portable_environment.py](../backend/tests/test_g1_portable_environment.py) | 174 | 목록 확인 | PortableTests | `80d97f0ff9cf` |
| [backend/tests/test_g1_process_lifetime.py](../backend/tests/test_g1_process_lifetime.py) | 62 | 목록 확인 | LifetimeTests | `ebcce528a3f2` |
| [backend/tests/test_g1_quiet_observation.py](../backend/tests/test_g1_quiet_observation.py) | 52 | 목록 확인 | QuietTests | `cc779d373adf` |
| [backend/tests/test_g1_ssh_login.py](../backend/tests/test_g1_ssh_login.py) | 56 | 목록 확인 | LoginTests | `1fca27bf0d14` |
| [backend/tests/test_g1_teleop_dependencies.py](../backend/tests/test_g1_teleop_dependencies.py) | 60 | 목록 확인 | DependencyTests | `285271629dd5` |
| [backend/tests/test_g1_vr_teleop_launch.py](../backend/tests/test_g1_vr_teleop_launch.py) | 331 | 목록 확인 | worker_row, WorkerRecognitionTests, UnityLaunchTests, RedirectorTests, OrchestrationTests (+2) | `3368a64c8f34` |
| [backend/tests/test_gate7_mujoco_feedback_receiver.py](../backend/tests/test_gate7_mujoco_feedback_receiver.py) | 120 | 목록 확인 | _payload, Gate7MujocoFeedbackReceiverTest | `bb3ba70e7bef` |
| [backend/tests/test_gate7_simulation_feedback.py](../backend/tests/test_gate7_simulation_feedback.py) | 89 | 목록 확인 | Gate7SimulationFeedbackTest | `fc81a75e405d` |
| [backend/tests/test_ik_visual_comparison.py](../backend/tests/test_ik_visual_comparison.py) | 112 | 목록 확인 | test_composite_goals_are_closed_multiaxis_pose_paths, test_invalid_standard_velocity_holds_pose_without_hiding_failure, test_playback_speed_preserves_fixed_steps_and_pause, test_comparison_keys_do_not_use_mujoco_shortcuts, test_comparison_reset_and_independent_joint_states | `d11d16adf214` |
| [backend/tests/test_inspection_contact.py](../backend/tests/test_inspection_contact.py) | 67 | 목록 확인 | InspectionContactStateMachineTest | `8029e94d123e` |
| [backend/tests/test_inspection_demo.py](../backend/tests/test_inspection_demo.py) | 74 | 목록 확인 | InspectionDemoTrackerTest | `bcbbbeecca0b` |
| [backend/tests/test_live_receiver.py](../backend/tests/test_live_receiver.py) | 243 | 목록 확인 | FakeSocket, legacy_packet, legacy_disengage_packet, legacy_tracking_disengage_packet, legacy_workspace_exit_packet (+2) | `b1f1f90f6d43` |
| [backend/tests/test_lowstate_firewall_scope.py](../backend/tests/test_lowstate_firewall_scope.py) | 112 | 목록 확인 | test_scope_without_admin_or_network | `050ca8881601` |
| [backend/tests/test_lowstate_mink_seed.py](../backend/tests/test_lowstate_mink_seed.py) | 57 | 목록 확인 | Seed, Load, test_all_29_joint_mapping_and_base_unchanged, test_rejected_seed, test_reject_model_limits_atomically | `2651741a42f2` |
| [backend/tests/test_lowstate_seed_writer.py](../backend/tests/test_lowstate_seed_writer.py) | 55 | 목록 확인 | Bytes, test_write_replace_expiry_cleanup, test_failure_removes_previous_seed_and_temp, test_never_adopts_existing_seed | `293bafe3fe0c` |
| [backend/tests/test_mink_candidate_benchmark.py](../backend/tests/test_mink_candidate_benchmark.py) | 383 | 목록 확인 | BenchmarkTests, test_real_render_process_lifecycle | `dfcb6871fd34` |
| [backend/tests/test_mink_collision_diagnostics.py](../backend/tests/test_mink_collision_diagnostics.py) | 205 | 목록 확인 | MinkCollisionDiagnosticsTest | `5c52112a1e24` |
| [backend/tests/test_mink_collision_feasibility.py](../backend/tests/test_mink_collision_feasibility.py) | 129 | 목록 확인 | CollisionFeasibilityTests | `725ff0bd0180` |
| [backend/tests/test_mink_command_stream.py](../backend/tests/test_mink_command_stream.py) | 272 | 목록 확인 | FakeSocket, packet, MinkCommandStreamTest | `1fc5b8f38131` |
| [backend/tests/test_mink_distance_invariance.py](../backend/tests/test_mink_distance_invariance.py) | 120 | 목록 확인 | DistanceInvarianceTests | `3dc5048606a4` |
| [backend/tests/test_mink_feasible_target.py](../backend/tests/test_mink_feasible_target.py) | 459 | 목록 확인 | FeasibleTargetTest | `0042bf944210` |
| [backend/tests/test_mink_model_return.py](../backend/tests/test_mink_model_return.py) | 96 | 목록 확인 | ModelReturnTest | `d6c13d49bf7b` |
| [backend/tests/test_mink_reachability_limit.py](../backend/tests/test_mink_reachability_limit.py) | 33 | 목록 확인 | MinkReachabilityLimitTest | `d3feecf0bd93` |
| [backend/tests/test_mink_return_handshake.py](../backend/tests/test_mink_return_handshake.py) | 124 | 목록 확인 | ReturnHandshakeTests | `3e7a4ce56f8e` |
| [backend/tests/test_mink_runtime_refactor_compatibility.py](../backend/tests/test_mink_runtime_refactor_compatibility.py) | 71 | 목록 확인 | MinkRuntimeRefactorCompatibilityTest | `d5ab8c5e505c` |
| [backend/tests/test_mink_stateful_trajectory.py](../backend/tests/test_mink_stateful_trajectory.py) | 82 | 목록 확인 | MinkStatefulTrajectoryTest | `36bed68783c8` |
| [backend/tests/test_mink_step_acceptance_comparison.py](../backend/tests/test_mink_step_acceptance_comparison.py) | 503 | 목록 확인 | MinkStepAcceptanceComparisonTests | `2f79b0783952` |
| [backend/tests/test_mink_task_cost_contract.py](../backend/tests/test_mink_task_cost_contract.py) | 47 | 목록 확인 | ExampleTask, MinkTaskCostContractTest | `62ece4cc7488` |
| [backend/tests/test_mink_tracking_lag.py](../backend/tests/test_mink_tracking_lag.py) | 60 | 목록 확인 | TrackingLagTests | `48bae66a9caf` |
| [backend/tests/test_mink_virtual_center_trajectory.py](../backend/tests/test_mink_virtual_center_trajectory.py) | 212 | 목록 확인 | rotation_error_degrees, MinkVirtualCenterTrajectoryTest | `58f6f40661f1` |
| [backend/tests/test_motion_reference.py](../backend/tests/test_motion_reference.py) | 52 | 목록 확인 | MotionReferenceTest | `1003f5d2d186` |
| [backend/tests/test_mujoco312_simulation_entry.py](../backend/tests/test_mujoco312_simulation_entry.py) | 135 | 목록 확인 | test_simulation_packet_cannot_enter_hardware, test_seed_environment_forwarding_without_shell_interpolation, test_right_arm_csv_forwarding, test_partial_seed_environment_rejected_before_engine, test_isolated_import_validation (+6) | `728d41e3b471` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `87ba04dd2d7d` |
| [backend/tests/test_mujoco_inspection_scene_visibility.py](../backend/tests/test_mujoco_inspection_scene_visibility.py) | 75 | 목록 확인 | MujocoInspectionSceneVisibilityTest | `92cbb62e9b3e` |
| [backend/tests/test_offline_model_isolation.py](../backend/tests/test_offline_model_isolation.py) | 594 | 목록 확인 | test_render_replay_xml_lifetime, test_render_replay_loads_isolated_model, test_live_entry_model_block_isolated, test_jog_provenance_uses_validator_model, shared_bytes (+18) | `4518ec107d26` |
| [backend/tests/test_offline_owner.py](../backend/tests/test_offline_owner.py) | 70 | 목록 확인 | load_fixture, test_owner_fault_latches, test_autonomous_timeout_without_stdin, test_existing_relay_packet_reaches_native_adapter | `faf4d4fc2ba2` |
| [backend/tests/test_protocol_v2.py](../backend/tests/test_protocol_v2.py) | 196 | 목록 확인 | tracked, pose_v2, ProtocolV1IntegerTest, ProtocolV2Test | `f8242ba88526` |
| [backend/tests/test_recorded_ik_hierarchy.py](../backend/tests/test_recorded_ik_hierarchy.py) | 174 | 목록 확인 | test_goal_rebase_preserves_delta_and_neutral, test_fixed_basis_and_clutch_preserve_rotation_step, test_operator_quaternion_sign_does_not_change_target, test_qp_summary_includes_small_rotation_errors, test_short_stationary_comparison (+8) | `2f0f2aa865ac` |
| [backend/tests/test_recorded_pose_speed_comparison.py](../backend/tests/test_recorded_pose_speed_comparison.py) | 61 | 목록 확인 | MakePacket, RecordedPoseSpeedComparisonTest | `f667723f00c9` |
| [backend/tests/test_recorded_reach_bound.py](../backend/tests/test_recorded_reach_bound.py) | 140 | 목록 확인 | RecordedReachBoundTest | `50b026a2c898` |
| [backend/tests/test_rotation_trace_analysis.py](../backend/tests/test_rotation_trace_analysis.py) | 83 | 목록 확인 | MakeRow, test_sign_and_duplicate_packet_are_not_events, test_semantic_change_is_distinguished_from_source, test_new_session_does_not_compare_packet_rotation, test_packet_jump_and_cli_output (+2) | `2cbb375a88f1` |
| [backend/tests/test_runtime_architecture.py](../backend/tests/test_runtime_architecture.py) | 62 | 목록 확인 | command, RuntimeArchitectureTest | `e39e40892b1e` |
| [backend/tests/test_seed_file_sharing.py](../backend/tests/test_seed_file_sharing.py) | 35 | 목록 확인 | test_open_snapshot_allows_delete_sharing, test_missing_and_oversized_file | `29fe349c01c0` |
| [backend/tests/test_seed_observer_failure.py](../backend/tests/test_seed_observer_failure.py) | 24 | 목록 확인 | test_permission_error_is_reported_and_fails | `fc99147155a4` |
| [backend/tests/test_seed_velocity_review.py](../backend/tests/test_seed_velocity_review.py) | 30 | 목록 확인 | test_trigger_context_clipping_and_no_event, test_spikes_runs_and_gap_are_distinct, test_bad_data_rejected | `4f723e0055cf` |
| [backend/tests/test_seed_window_comparison.py](../backend/tests/test_seed_window_comparison.py) | 22 | 목록 확인 | test_spike_and_drift_are_separate, test_invalid_windows_rejected | `b00147156437` |
| [backend/tests/test_simulation_handoff_boundary.py](../backend/tests/test_simulation_handoff_boundary.py) | 81 | 목록 확인 | SimulationHandoffBoundaryTests | `f49b591ba187` |
| [backend/tests/test_source_provenance.py](../backend/tests/test_source_provenance.py) | 123 | 목록 확인 | command, CommandSourceGuardTests | `a49810e1a73c` |
| [backend/tests/test_standard_mink_live.py](../backend/tests/test_standard_mink_live.py) | 204 | 목록 확인 | test_standard_qp_shared_limits_and_goal, test_launcher_selection_and_locked_profile, test_live_parser_preserves_default_and_selects_vanilla, test_embedded_csv_preserves_exact_transmitted_json, test_local_launcher_default_without_starting_runtime (+1) | `8350e0abca16` |
| [backend/tests/test_startup_ready_pose_editor.py](../backend/tests/test_startup_ready_pose_editor.py) | 75 | 목록 확인 | StartupReadyPoseEditorTest | `9ef3c18fabae` |
| [backend/tests/test_synthetic_ik_cases.py](../backend/tests/test_synthetic_ik_cases.py) | 194 | 목록 확인 | test_path_observer_preserves_decision_and_records_joint_rejection, test_single_qp_cost_changes_only_proximal_damping_and_restores, test_single_qp_cost_rejects_nonfinite_or_negative, test_out_of_range_start_is_rejected_before_output, test_wrist_axes_are_distinct_and_positions_stay_fixed (+9) | `4ced3d4fac62` |
| [backend/tests/test_teleop_config.py](../backend/tests/test_teleop_config.py) | 154 | 목록 확인 | TeleopConfigTest | `1febc9e2a1c0` |
| [backend/tests/test_trajectory_ab.py](../backend/tests/test_trajectory_ab.py) | 66 | 목록 확인 | test_live_tracking_reaches_acceleration_limit_within_one_control_tick, test_forward_then_wrist_keeps_requested_position_fixed, test_candidate_bounds_and_stop_without_changing_baseline, test_candidate_rejects_nonfinite | `ab4396545e18` |
| [backend/tests/test_unity_display_mode_launcher.py](../backend/tests/test_unity_display_mode_launcher.py) | 53 | 목록 확인 | UnityDisplayModeLauncherTests, ReadOnlyPreviewLauncherTests | `ab173b13f922` |
| [backend/tests/test_unity_workspace_policy.py](../backend/tests/test_unity_workspace_policy.py) | 278 | 목록 확인 | UnityWorkspacePolicyTest | `dd45c6254105` |
| [backend/tests/test_upstream_mink_tracking.py](../backend/tests/test_upstream_mink_tracking.py) | 416 | 목록 확인 | UpstreamTrackingTests | `5847f94c66af` |
| [backend/tests/test_virtual_center_kinematics_regression.py](../backend/tests/test_virtual_center_kinematics_regression.py) | 96 | 목록 확인 | VirtualCenterKinematicsRegressionTest | `104e609c6cc7` |
| [backend/tests/test_virtual_center_orientation_policy.py](../backend/tests/test_virtual_center_orientation_policy.py) | 135 | 목록 확인 | VirtualCenterOrientationPolicyTest | `78fb4e5ad242` |
| [backend/tests/test_windows_tool_paths.py](../backend/tests/test_windows_tool_paths.py) | 299 | 목록 확인 | PathContractTests, UnityEditorDiscoveryTests, OtherToolPathTests | `76eee9712054` |
| [backend/tests/test_wrist_target_mapping_audit.py](../backend/tests/test_wrist_target_mapping_audit.py) | 50 | 목록 확인 | MappingAuditTests | `4c7b69cdb5a9` |
| [backend/tools/analyze_rotation_trace.py](../backend/tools/analyze_rotation_trace.py) | 95 | 목록 확인 | GetQuaternion, GetAngle, AnalyzeRows, main | `43abcea65acb` |
| [backend/tools/audit_bimanual_known_targets.py](../backend/tools/audit_bimanual_known_targets.py) | 105 | 목록 확인 | main | `50fc638cf51a` |
| [backend/tools/audit_bimanual_reachability.py](../backend/tools/audit_bimanual_reachability.py) | 137 | 목록 확인 | main | `ddd3b8461d24` |
| [backend/tools/audit_bimanual_settling.py](../backend/tools/audit_bimanual_settling.py) | 68 | 목록 확인 | main | `85d1214b9daf` |
| [backend/tools/audit_wrist_target_mapping.py](../backend/tools/audit_wrist_target_mapping.py) | 180 | 목록 확인 | OperatorToRobotDelta, GetNecessaryScale, ReadUnitySegments, GetVectors, AuditSender (+2) | `ed50d803271a` |
| [backend/tools/benchmark_mink_candidate.py](../backend/tools/benchmark_mink_candidate.py) | 274 | 목록 확인 | CachedClearance, BoundedClearance, CachedCollisionLimit, BuildCandidate, SummarizeTiming (+3) | `fcb18699486b` |
| [backend/tools/benchmark_mink_rendered_replay.py](../backend/tools/benchmark_mink_rendered_replay.py) | 316 | 목록 확인 | WaitForRelease, GetNextRelease, LoadReplay, ReplayRenderer, RunRenderedReplay (+3) | `a45929d1f6b2` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 121 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `bae8666a7a4d` |
| [backend/tools/compare_bimanual_single_arm.py](../backend/tools/compare_bimanual_single_arm.py) | 101 | 목록 확인 | main | `a102e8834be5` |
| [backend/tools/compare_mink_step_acceptance.py](../backend/tools/compare_mink_step_acceptance.py) | 774 | 목록 확인 | GetLimitMetadata, WristPositionTask, FullOrientationErrorTask, IncrementCollisionLimit, ResolvedCollisionLimit (+12) | `f350e5937d0e` |
| [backend/tools/compare_mink_trajectory.py](../backend/tools/compare_mink_trajectory.py) | 130 | 목록 확인 | ForwardWristGoal, ThroughTrajectory, TrajectoryComparison | `d29ca8d6e588` |
| [backend/tools/compare_recorded_ik_hierarchy.py](../backend/tools/compare_recorded_ik_hierarchy.py) | 289 | 목록 확인 | UseOfflineProximalCost, GetNormalizedGoal, RunDiagnosedPlan, SummarizeQP, SummarizeTargetEvents (+3) | `5bcc1153782c` |
| [backend/tools/compare_recorded_pose_speeds.py](../backend/tools/compare_recorded_pose_speeds.py) | 116 | 목록 확인 | GetActiveSegments, GetRecordedTargets, GetTargetIndex, main | `32a7a3d78448` |
| [backend/tools/compare_synthetic_ik.py](../backend/tools/compare_synthetic_ik.py) | 298 | 목록 확인 | ObservePathChecks, UseSingleQPCost, UseMeritAblation, ProgressBand, TargetErrorBand (+3) | `32e8f3a120f5` |
| [backend/tools/diagnose_mink_collision_feasibility.py](../backend/tools/diagnose_mink_collision_feasibility.py) | 282 | 목록 확인 | EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, main | `f611d443b6ac` |
| [backend/tools/diagnose_mink_distance_invariance.py](../backend/tools/diagnose_mink_distance_invariance.py) | 214 | 목록 확인 | GetSupportGap, GetWorldVertices, GetEnclosingVertices, GetSeparationCertificate, InspectTrace (+3) | `34cfacf54ffe` |
| [backend/tools/diagnose_mink_tracking_lag.py](../backend/tools/diagnose_mink_tracking_lag.py) | 189 | 목록 확인 | GetSchedule, GetSustainedSettleTime, GetReachSummary, Step, GetSample (+4) | `767a1f3dd01b` |
| [backend/tools/diagnose_recorded_reach.py](../backend/tools/diagnose_recorded_reach.py) | 123 | 목록 확인 | GetReachUpperBound, SaveInputFailure, main, RunDiagnosis | `8e2d24f51fba` |
| [backend/tools/inspect_feasible_target_return.py](../backend/tools/inspect_feasible_target_return.py) | 194 | 목록 확인 | InterpolateGoal, SummarizePreview, GetVerdict, Run, main (+1) | `47b03f324642` |
| [backend/tools/offline_render_worker.py](../backend/tools/offline_render_worker.py) | 193 | 목록 확인 | LatestStateSlot, RunRenderWorker, ProcessRenderer | `500a438ebeba` |
| [backend/tools/reconcile_review_ledger.py](../backend/tools/reconcile_review_ledger.py) | 176 | 목록 확인 | _read_csv, _semantic_map, _static_check, build_rows, _csv_text (+1) | `91ee37c20ba9` |
| [backend/tools/verify_camera_simulation.py](../backend/tools/verify_camera_simulation.py) | 271 | 목록 확인 | parse_args, quaternion_rotation_matrix, official_optical_axes, verify_transport, main | `e2a27b9f60cc` |
| [backend/tools/verify_feasible_target.py](../backend/tools/verify_feasible_target.py) | 137 | 목록 확인 | BuildPlanner, RunSequence, main | `d40c1658ab0c` |
| [backend/tools/verify_unity_state_packets.ps1](../backend/tools/verify_unity_state_packets.ps1) | 149 | 목록 확인 | - | `59b7da362e29` |
| [backend/tools/verify_virtual_center_kinematics.py](../backend/tools/verify_virtual_center_kinematics.py) | 269 | 목록 확인 | LegacyOrientationTask, ExactOrientationTask, CheckJacobian, GetStepCount, RunCase (+1) | `686bb6b4b874` |
| [backend/tools/view_ik_comparison.py](../backend/tools/view_ik_comparison.py) | 358 | 목록 확인 | NextPlaybackSpeed, GetCompositeGoal, HandleComparisonKey, RecordedPlayback, Comparison (+2) | `4121914b0b6a` |
| [config/camera_profile.json](../config/camera_profile.json) | 42 | 목록 확인 | - | `00b755866d6e` |
| [config/g1_gate6_hold.json](../config/g1_gate6_hold.json) | 31 | 목록 확인 | - | `5423eca13b84` |
| [config/g1_gate6_interrupt_release_test.json](../config/g1_gate6_interrupt_release_test.json) | 31 | 목록 확인 | - | `02040744b4fc` |
| [config/g1_gate7_first_live_hardware_output.json](../config/g1_gate7_first_live_hardware_output.json) | 33 | 목록 확인 | - | `e34cc263326e` |
| [config/g1_gate7_first_live_mink_arm_sdk.json](../config/g1_gate7_first_live_mink_arm_sdk.json) | 20 | 목록 확인 | - | `ca6dd3b90d84` |
| [config/g1_gate7_live_hardware_output.json](../config/g1_gate7_live_hardware_output.json) | 33 | 목록 확인 | - | `5e91cd5adcba` |
| [config/g1_gate7_mink_arm_sdk.json](../config/g1_gate7_mink_arm_sdk.json) | 20 | 목록 확인 | - | `4f1ab28f00ce` |
| [config/g1_gate7_visible_motion_hardware_output.json](../config/g1_gate7_visible_motion_hardware_output.json) | 33 | 목록 확인 | - | `111d6a4c44a8` |
| [config/g1_gate7_visible_motion_mink_arm_sdk.json](../config/g1_gate7_visible_motion_mink_arm_sdk.json) | 20 | 목록 확인 | - | `44fa4ecaff39` |
| [config/g1_regular_arm_pose.json](../config/g1_regular_arm_pose.json) | 61 | 목록 확인 | - | `fc0b80702dfb` |
| [config/g1_right_arm_jog.json](../config/g1_right_arm_jog.json) | 39 | 목록 확인 | - | `b974a756fbe4` |
| [config/g1_right_shoulder_pitch_full_authority_trial.json](../config/g1_right_shoulder_pitch_full_authority_trial.json) | 47 | 목록 확인 | - | `916cedef6059` |
| [config/g1_startup_precheck.json](../config/g1_startup_precheck.json) | 19 | 목록 확인 | - | `3fca74fe17f7` |
| [config/g1_waist_hold_trial_draft.json](../config/g1_waist_hold_trial_draft.json) | 45 | 목록 확인 | - | `99c1f85e94a9` |
| [config/startup_recovery.json](../config/startup_recovery.json) | 15 | 목록 확인 | - | `75e9a6d9be3a` |
| [config/teleimager_real_d435i.yaml](../config/teleimager_real_d435i.yaml) | 36 | 목록 확인 | - | `2646f08cfc76` |
| [config/teleimager_simulation.yaml](../config/teleimager_simulation.yaml) | 36 | 목록 확인 | - | `65127fae537d` |
| [config/teleop.json](../config/teleop.json) | 83 | 목록 확인 | - | `e3498304c8b4` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/manifest.json](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/manifest.json) | 32 | 목록 확인 | - | `347fff96cfb8` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_contract.hpp) | 190 | 목록 확인 | - | `bca168cf72bb` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `f9556d12cdd7` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_udp_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/mink_udp_target.hpp) | 53 | 목록 확인 | - | `de32b2bb7c9f` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_relay_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_relay_contract.hpp) | 22 | 목록 확인 | - | `d3fe4a0fdf3c` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_snapshot_freshness.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `7b9026980e86` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_state_tick.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_state_tick.hpp) | 8 | 목록 확인 | - | `ff86033bf355` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_cycle_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `2424fa527778` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_policy_adapter.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `0c1ad7b3890c` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/offline_twist2_constants.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `517a651ecfc9` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_gain_options.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_gain_options.hpp) | 59 | 목록 확인 | - | `a992fe6591f1` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_joint_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `e760154bb5a4` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_reference.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `ca0f771ddfd2` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `a58197aaec1e` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_ready_settle.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `a33e931e51aa` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_small_signal_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `a7b8562ab1ac` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/periodic_csv.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/periodic_csv.hpp) | 64 | 목록 확인 | - | `a2c406b1e65d` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/raw_input_watch_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `7f614be48562` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_common.hpp) | 376 | 목록 확인 | - | `2db4dea94bf4` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.cpp) | 1284 | 목록 확인 | - | `f2b507dd2658` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.remote_current.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/twist2_mink_cycle_trial.remote_current.cpp) | 1590 | 목록 확인 | - | `c309da057467` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/upper_target_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/upper_target_offline.hpp) | 140 | 목록 확인 | - | `4ce96f2ae645` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/validate_input.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/validate_input.hpp) | 178 | 목록 확인 | - | `a28785a3f42b` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/vendor/json.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/vendor/json.hpp) | 25526 | 목록 확인 | - | `5f09d1eebe9b` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/verified_regular_handoff.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/verified_regular_handoff.hpp) | 31 | 목록 확인 | - | `72aabbc6e625` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/writer_frame.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_right_arm/writer_frame.hpp) | 37 | 목록 확인 | - | `16f2ec354c74` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/g1_velocity_policy.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/g1_velocity_policy.hpp) | 302 | 목록 확인 | - | `97fd27227c47` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/run_continuous_gait.sh](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/run_continuous_gait.sh) | 11 | 목록 확인 | - | `e4bfdaddc03b` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_common.hpp) | 384 | 목록 확인 | - | `8f591c905291` |
| [experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_static_stand.cpp](../experiments/g1_velocity_mink_right_arm_20260914/base_velocity/twist2_static_stand.cpp) | 1687 | 목록 확인 | - | `5b2e5476d47e` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_mink_keypad_right_arm.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_mink_keypad_right_arm.cpp) | 1823 | 목록 확인 | - | `d4d81f757613` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_policy.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/g1_velocity_policy.hpp) | 315 | 목록 확인 | - | `0214800838e5` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/leg_policy_switch.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/leg_policy_switch.hpp) | 101 | 목록 확인 | - | `bc49ce045444` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_contract.hpp) | 198 | 목록 확인 | - | `040183d233dc` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `ba5ef1140818` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_udp_target.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/mink_udp_target.hpp) | 53 | 목록 확인 | - | `de32b2bb7c9f` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_relay_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_relay_contract.hpp) | 22 | 목록 확인 | - | `d3fe4a0fdf3c` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_snapshot_freshness.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `7b9026980e86` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_state_tick.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_state_tick.hpp) | 8 | 목록 확인 | - | `ff86033bf355` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_velocity_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_velocity_udp.hpp) | 155 | 목록 확인 | - | `b6c73d10bbb8` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_cycle_udp.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `2424fa527778` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_policy_adapter.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `0c1ad7b3890c` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/offline_twist2_constants.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `517a651ecfc9` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_gain_options.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_gain_options.hpp) | 60 | 목록 확인 | - | `f7ba9c1ccdc4` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_joint_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `e760154bb5a4` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_reference.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `ca0f771ddfd2` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `a58197aaec1e` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_ready_settle.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `a33e931e51aa` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_small_signal_trial.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `a7b8562ab1ac` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/periodic_csv.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/periodic_csv.hpp) | 64 | 목록 확인 | - | `a2c406b1e65d` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/raw_input_watch_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `7f614be48562` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_static_stand_handoff_probe.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_static_stand_handoff_probe.sh) | 6 | 목록 확인 | - | `25912e7b7a12` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_axis_trial.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_axis_trial.sh) | 16 | 목록 확인 | - | `9adca7344b06` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_mink_keypad.sh](../experiments/g1_velocity_mink_right_arm_20260914/candidate/run_velocity_mink_keypad.sh) | 21 | 목록 확인 | - | `a90cb043e5bf` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_initial_ready_continuous_gait.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_initial_ready_continuous_gait.cpp) | 55 | 목록 확인 | - | `dc537e322244` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_leg_policy_switch.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_leg_policy_switch.cpp) | 49 | 목록 확인 | - | `9d49562027d6` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/test_velocity_keypad_contract.cpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/test_velocity_keypad_contract.cpp) | 44 | 목록 확인 | - | `1204e46b9354` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/twist2_common.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/twist2_common.hpp) | 384 | 목록 확인 | - | `8f591c905291` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/upper_target_offline.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/upper_target_offline.hpp) | 140 | 목록 확인 | - | `4ce96f2ae645` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/validate_input.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/validate_input.hpp) | 178 | 목록 확인 | - | `a28785a3f42b` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/velocity_keypad_contract.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/velocity_keypad_contract.hpp) | 78 | 목록 확인 | - | `a0d2b744a19c` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/vendor/json.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/vendor/json.hpp) | 25526 | 목록 확인 | - | `5f09d1eebe9b` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/verified_regular_handoff.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/verified_regular_handoff.hpp) | 31 | 목록 확인 | - | `72aabbc6e625` |
| [experiments/g1_velocity_mink_right_arm_20260914/candidate/writer_frame.hpp](../experiments/g1_velocity_mink_right_arm_20260914/candidate/writer_frame.hpp) | 37 | 목록 확인 | - | `16f2ec354c74` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_arm_ready_decouple_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_arm_ready_decouple_20260915.sh) | 30 | 목록 확인 | - | `7643463d8642` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_build_continuous_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_build_continuous_20260915.sh) | 40 | 목록 확인 | - | `641e6c7e502e` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_continuous_gait_arm_ready_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_continuous_gait_arm_ready_20260915.sh) | 32 | 목록 확인 | - | `0e5d1e6c7dbb` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_dual_policy_idle_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_dual_policy_idle_20260915.sh) | 19 | 목록 확인 | - | `88744eb4d9e1` |
| [experiments/g1_velocity_mink_right_arm_20260914/deploy_keypad_latched_08_20260915.sh](../experiments/g1_velocity_mink_right_arm_20260914/deploy_keypad_latched_08_20260915.sh) | 28 | 목록 확인 | - | `040010a2ae09` |
| [experiments/independent_locomotion/data/mink_command_trajectories_v1.json](../experiments/independent_locomotion/data/mink_command_trajectories_v1.json) | 89 | 목록 확인 | - | `0d30f8242e40` |
| [experiments/independent_locomotion/evaluate_upper_body_conditioned.py](../experiments/independent_locomotion/evaluate_upper_body_conditioned.py) | 160 | 목록 확인 | _state_snapshot, _unchanged, evaluate_seed, main | `b6491eb74b9e` |
| [experiments/independent_locomotion/evaluation_protocol_v1.json](../experiments/independent_locomotion/evaluation_protocol_v1.json) | 33 | 목록 확인 | - | `51493834e452` |
| [experiments/independent_locomotion/matched_training_stage1.json](../experiments/independent_locomotion/matched_training_stage1.json) | 15 | 목록 확인 | - | `49d5b7637f33` |
| [experiments/independent_locomotion/mink_trajectory_dataset.py](../experiments/independent_locomotion/mink_trajectory_dataset.py) | 111 | 목록 확인 | sha256, read_active_episode, build_bank, load_split | `3530d43aa774` |
| [experiments/independent_locomotion/prepare_mink_trajectory_split.py](../experiments/independent_locomotion/prepare_mink_trajectory_split.py) | 32 | 목록 확인 | - | `016706a25704` |
| [experiments/independent_locomotion/run_matched_training_continuation.sh](../experiments/independent_locomotion/run_matched_training_continuation.sh) | 46 | 목록 확인 | - | `26c8b4334339` |
| [experiments/independent_locomotion/run_matched_training_stage1.sh](../experiments/independent_locomotion/run_matched_training_stage1.sh) | 26 | 목록 확인 | - | `7d5ce9160214` |
| [experiments/independent_locomotion/run_recorded_curriculum.sh](../experiments/independent_locomotion/run_recorded_curriculum.sh) | 53 | 목록 확인 | - | `b0bb629795f5` |
| [experiments/independent_locomotion/select_matched_resume.py](../experiments/independent_locomotion/select_matched_resume.py) | 71 | 목록 확인 | checkpoint_from_result, select_checkpoint, main | `34f228e06492` |
| [experiments/independent_locomotion/smoke_mjlab.py](../experiments/independent_locomotion/smoke_mjlab.py) | 63 | 목록 확인 | check_finite, main | `3c3cd679d8d1` |
| [experiments/independent_locomotion/smoke_upper_body_conditioned.py](../experiments/independent_locomotion/smoke_upper_body_conditioned.py) | 82 | 목록 확인 | main | `e35521e46b63` |
| [experiments/independent_locomotion/summarize_matched_training.py](../experiments/independent_locomotion/summarize_matched_training.py) | 70 | 목록 확인 | summarize, main | `7c083a0e9bec` |
| [experiments/independent_locomotion/test_mink_trajectory_dataset.py](../experiments/independent_locomotion/test_mink_trajectory_dataset.py) | 46 | 목록 확인 | SplitValidationTest | `6d9a9985f647` |
| [experiments/independent_locomotion/test_recorded_curriculum.py](../experiments/independent_locomotion/test_recorded_curriculum.py) | 21 | 목록 확인 | RecordedCurriculumTest | `69bdb85214b6` |
| [experiments/independent_locomotion/test_select_matched_resume.py](../experiments/independent_locomotion/test_select_matched_resume.py) | 67 | 목록 확인 | ResumeSelectionTest | `31482bee93df` |
| [experiments/independent_locomotion/train_upper_body_conditioned.py](../experiments/independent_locomotion/train_upper_body_conditioned.py) | 151 | 목록 확인 | main | `940b3252f6c3` |
| [experiments/independent_locomotion/upper_body_conditioned_env.py](../experiments/independent_locomotion/upper_body_conditioned_env.py) | 229 | 목록 확인 | _upper_state, apply_smooth_upper_target, apply_fixed_upper_target, recorded_scale_at_step, apply_recorded_upper_target (+2) | `363d9e6cb9fc` |
| [experiments/independent_locomotion/verify_mjlab.sh](../experiments/independent_locomotion/verify_mjlab.sh) | 26 | 목록 확인 | - | `393f509c6d40` |
| [experiments/independent_locomotion/verify_upper_body_conditioned.sh](../experiments/independent_locomotion/verify_upper_body_conditioned.sh) | 27 | 목록 확인 | - | `fb4c583664c4` |
| [experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat](../experiments/startup_recovery_multistrategy/TEST_MULTI_STRATEGY.bat) | 30 | 목록 확인 | - | `c17f8f5e265c` |
| [experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat](../experiments/startup_recovery_multistrategy/VIEW_SELECTED.bat) | 26 | 목록 확인 | - | `07f85ccfcd9f` |
| [experiments/startup_recovery_multistrategy/candidate_runner.py](../experiments/startup_recovery_multistrategy/candidate_runner.py) | 39 | 목록 확인 | parse_arguments, main | `20b2e8d8ebca` |
| [experiments/startup_recovery_multistrategy/run_experiment.py](../experiments/startup_recovery_multistrategy/run_experiment.py) | 248 | 목록 확인 | RecoveryCandidate, parse_arguments, load_initial_pose, candidate_score, select_candidate (+3) | `a3e6a8dec3ae` |
| [experiments/startup_recovery_multistrategy/test_experiment.py](../experiments/startup_recovery_multistrategy/test_experiment.py) | 87 | 목록 확인 | MultiStrategyRecoveryExperimentTest | `c97dd80049c2` |
| [experiments/startup_recovery_multistrategy/view_selected.py](../experiments/startup_recovery_multistrategy/view_selected.py) | 37 | 목록 확인 | main | `f277d289ab9e` |
| [experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_POSTURE_SWEEP.bat) | 30 | 목록 확인 | - | `874505042940` |
| [experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat](../experiments/startup_recovery_posture_sweep/RUN_STANDARD_POSTURE_SWEEP.bat) | 37 | 목록 확인 | - | `a804d7c63a0d` |
| [experiments/startup_recovery_posture_sweep/run_sweep.py](../experiments/startup_recovery_posture_sweep/run_sweep.py) | 653 | 목록 확인 | SweepCase, ParseOffsets, ParseArguments, LoadPose, BuildProvenance (+12) | `43b1e62e9c31` |
| [experiments/startup_recovery_posture_sweep/single_pose_runner.py](../experiments/startup_recovery_posture_sweep/single_pose_runner.py) | 62 | 목록 확인 | ParseArguments, UseIsolatedModel, Main | `0c58f76471f6` |
| [experiments/startup_recovery_posture_sweep/test_sweep.py](../experiments/startup_recovery_posture_sweep/test_sweep.py) | 191 | 목록 확인 | StartupRecoveryPostureSweepTests | `62616b76c696` |
| [experiments/twist2_right_arm_manual/TEST_OFFLINE.bat](../experiments/twist2_right_arm_manual/TEST_OFFLINE.bat) | 18 | 목록 확인 | - | `53a20610cefb` |
| [experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1](../experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1) | 31 | 목록 확인 | - | `45806b68d3b1` |
| [experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat](../experiments/twist2_right_arm_manual/VIEW_PHYSICAL_CSV_MUJOCO.bat) | 34 | 목록 확인 | - | `f1af8630a586` |
| [experiments/twist2_right_arm_manual/analyze_cycle_packets.py](../experiments/twist2_right_arm_manual/analyze_cycle_packets.py) | 45 | 목록 확인 | - | `b6e86e95db26` |
| [experiments/twist2_right_arm_manual/analyze_pd_abort.py](../experiments/twist2_right_arm_manual/analyze_pd_abort.py) | 35 | 목록 확인 | sha, analyze | `f7c3e0627fe9` |
| [experiments/twist2_right_arm_manual/analyze_pd_reach_com.py](../experiments/twist2_right_arm_manual/analyze_pd_reach_com.py) | 55 | 목록 확인 | coefficients, analyze, main | `5b7148ebda27` |
| [experiments/twist2_right_arm_manual/analyze_pd_sweep.py](../experiments/twist2_right_arm_manual/analyze_pd_sweep.py) | 56 | 목록 확인 | rms, analyze, main | `30aa288fdd6e` |
| [experiments/twist2_right_arm_manual/analyze_vr_pd_replay.py](../experiments/twist2_right_arm_manual/analyze_vr_pd_replay.py) | 105 | 목록 확인 | _rms, _percentile, _best_lag, analyze, main | `9f7ce634d947` |
| [experiments/twist2_right_arm_manual/anchored_alignment_study.py](../experiments/twist2_right_arm_manual/anchored_alignment_study.py) | 81 | 목록 확인 | AnchoredAlignmentStudy | `c2362aa08263` |
| [experiments/twist2_right_arm_manual/anchored_upper_study.hpp](../experiments/twist2_right_arm_manual/anchored_upper_study.hpp) | 122 | 목록 확인 | - | `4156b4d38961` |
| [experiments/twist2_right_arm_manual/arm_cycle_offline.hpp](../experiments/twist2_right_arm_manual/arm_cycle_offline.hpp) | 101 | 목록 확인 | - | `acf91e868205` |
| [experiments/twist2_right_arm_manual/arm_cycle_stdio_offline.cpp](../experiments/twist2_right_arm_manual/arm_cycle_stdio_offline.cpp) | 26 | 목록 확인 | - | `b2cd59c9ba8a` |
| [experiments/twist2_right_arm_manual/audit_fresh_seed_mink.py](../experiments/twist2_right_arm_manual/audit_fresh_seed_mink.py) | 67 | 목록 확인 | Main | `925e92a453ba` |
| [experiments/twist2_right_arm_manual/audit_identification_run.py](../experiments/twist2_right_arm_manual/audit_identification_run.py) | 66 | 목록 확인 | sha, audit | `1a29e787a15f` |
| [experiments/twist2_right_arm_manual/audit_mink_precision.py](../experiments/twist2_right_arm_manual/audit_mink_precision.py) | 299 | 목록 확인 | pose, residual, witness, run_case, main | `660574d3ffac` |
| [experiments/twist2_right_arm_manual/audit_mink_resampler_geometry.py](../experiments/twist2_right_arm_manual/audit_mink_resampler_geometry.py) | 42 | 목록 확인 | - | `580c4e17a8bd` |
| [experiments/twist2_right_arm_manual/audit_mink_torch_combined_geometry.py](../experiments/twist2_right_arm_manual/audit_mink_torch_combined_geometry.py) | 52 | 목록 확인 | - | `57a09b2dc954` |
| [experiments/twist2_right_arm_manual/audit_native_relay.cpp](../experiments/twist2_right_arm_manual/audit_native_relay.cpp) | 16 | 목록 확인 | - | `02ac5aedd1fd` |
| [experiments/twist2_right_arm_manual/audit_saved_alignment.cpp](../experiments/twist2_right_arm_manual/audit_saved_alignment.cpp) | 38 | 목록 확인 | - | `16e1eaf32a65` |
| [experiments/twist2_right_arm_manual/capture_hg_readonly.py](../experiments/twist2_right_arm_manual/capture_hg_readonly.py) | 79 | 목록 확인 | SelectInterface, Pack, Main | `d78532b85133` |
| [experiments/twist2_right_arm_manual/check_pc_receive_under_load.py](../experiments/twist2_right_arm_manual/check_pc_receive_under_load.py) | 69 | 목록 확인 | Worker, Main | `458e5529857a` |
| [experiments/twist2_right_arm_manual/compare_feedback_recorded_offline.py](../experiments/twist2_right_arm_manual/compare_feedback_recorded_offline.py) | 86 | 목록 확인 | Gyro, Run | `5f5771716798` |
| [experiments/twist2_right_arm_manual/compare_ik_targets.py](../experiments/twist2_right_arm_manual/compare_ik_targets.py) | 73 | 목록 확인 | load, compare | `b180aa2f5de8` |
| [experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py](../experiments/twist2_right_arm_manual/compare_mink_rotation_replay.py) | 156 | 목록 확인 | read_episode, run, main | `cbba964ddd83` |
| [experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py](../experiments/twist2_right_arm_manual/compare_mink_stationary_rotation.py) | 84 | 목록 확인 | run, main | `68ec15488ade` |
| [experiments/twist2_right_arm_manual/compare_native_writer_csv.py](../experiments/twist2_right_arm_manual/compare_native_writer_csv.py) | 49 | 목록 확인 | Compare | `fbc8648ced9a` |
| [experiments/twist2_right_arm_manual/compare_seed_windows_offline.py](../experiments/twist2_right_arm_manual/compare_seed_windows_offline.py) | 49 | 목록 확인 | Metrics, Main | `79230cf58de0` |
| [experiments/twist2_right_arm_manual/data/pitch_wrist_episode_20260910.provenance.json](../experiments/twist2_right_arm_manual/data/pitch_wrist_episode_20260910.provenance.json) | 12 | 목록 확인 | - | `44acc4b965f8` |
| [experiments/twist2_right_arm_manual/diagnose_mink_wrist_tradeoff.py](../experiments/twist2_right_arm_manual/diagnose_mink_wrist_tradeoff.py) | 50 | 목록 확인 | - | `8b0eb3a24e58` |
| [experiments/twist2_right_arm_manual/diagnose_mujoco_stance_offline.py](../experiments/twist2_right_arm_manual/diagnose_mujoco_stance_offline.py) | 53 | 목록 확인 | contact_snapshot, run, main | `db12e8d310d8` |
| [experiments/twist2_right_arm_manual/guarded_composition_offline.hpp](../experiments/twist2_right_arm_manual/guarded_composition_offline.hpp) | 145 | 목록 확인 | - | `d522ffb07928` |
| [experiments/twist2_right_arm_manual/inspect_g1_native_readonly.sh](../experiments/twist2_right_arm_manual/inspect_g1_native_readonly.sh) | 26 | 목록 확인 | - | `01ef2f146a92` |
| [experiments/twist2_right_arm_manual/inspect_wsl_sdk_readonly.py](../experiments/twist2_right_arm_manual/inspect_wsl_sdk_readonly.py) | 58 | 목록 확인 | Inspect, Main | `f1c19197d99f` |
| [experiments/twist2_right_arm_manual/joint_limit_guard.py](../experiments/twist2_right_arm_manual/joint_limit_guard.py) | 194 | 목록 확인 | vector, LimitViolation, JointLimitEnvelope, JointLimitMonitor | `79fedc75b0d3` |
| [experiments/twist2_right_arm_manual/lowstate_seed_writer.py](../experiments/twist2_right_arm_manual/lowstate_seed_writer.py) | 42 | 목록 확인 | SeedWriter | `a2da68d54a5f` |
| [experiments/twist2_right_arm_manual/measured_composition_offline.hpp](../experiments/twist2_right_arm_manual/measured_composition_offline.hpp) | 143 | 목록 확인 | - | `a7b571e3e065` |
| [experiments/twist2_right_arm_manual/mink_cycle_candidate_offline.hpp](../experiments/twist2_right_arm_manual/mink_cycle_candidate_offline.hpp) | 124 | 목록 확인 | - | `63ee3dbefadd` |
| [experiments/twist2_right_arm_manual/mink_cycle_candidate_stdio_offline.cpp](../experiments/twist2_right_arm_manual/mink_cycle_candidate_stdio_offline.cpp) | 21 | 목록 확인 | - | `607c37a434da` |
| [experiments/twist2_right_arm_manual/mink_cycle_owner_offline.hpp](../experiments/twist2_right_arm_manual/mink_cycle_owner_offline.hpp) | 147 | 목록 확인 | - | `c651da46acc9` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_contract.hpp](../experiments/twist2_right_arm_manual/mink_live_cycle_contract.hpp) | 190 | 목록 확인 | - | `bca168cf72bb` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_stdio_test.cpp](../experiments/twist2_right_arm_manual/mink_live_cycle_stdio_test.cpp) | 15 | 목록 확인 | - | `fd15c1c611a9` |
| [experiments/twist2_right_arm_manual/mink_live_cycle_target.hpp](../experiments/twist2_right_arm_manual/mink_live_cycle_target.hpp) | 84 | 목록 확인 | - | `f9556d12cdd7` |
| [experiments/twist2_right_arm_manual/mink_resampler_batch_offline.cpp](../experiments/twist2_right_arm_manual/mink_resampler_batch_offline.cpp) | 21 | 목록 확인 | - | `4d60980a4edb` |
| [experiments/twist2_right_arm_manual/mink_resampler_offline.hpp](../experiments/twist2_right_arm_manual/mink_resampler_offline.hpp) | 81 | 목록 확인 | - | `ed2bda7c1160` |
| [experiments/twist2_right_arm_manual/mink_torch_owner_stdio_offline.cpp](../experiments/twist2_right_arm_manual/mink_torch_owner_stdio_offline.cpp) | 78 | 목록 확인 | - | `f7a0b837fed1` |
| [experiments/twist2_right_arm_manual/mink_udp_target.hpp](../experiments/twist2_right_arm_manual/mink_udp_target.hpp) | 53 | 목록 확인 | - | `de32b2bb7c9f` |
| [experiments/twist2_right_arm_manual/mujoco_feedback_offline.py](../experiments/twist2_right_arm_manual/mujoco_feedback_offline.py) | 58 | 목록 확인 | Dynamics, main | `830ae7327de2` |
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
| [experiments/twist2_right_arm_manual/native_command_limits.hpp](../experiments/twist2_right_arm_manual/native_command_limits.hpp) | 17 | 목록 확인 | - | `2d0c8078eab9` |
| [experiments/twist2_right_arm_manual/native_composition_offline.hpp](../experiments/twist2_right_arm_manual/native_composition_offline.hpp) | 39 | 목록 확인 | - | `1d073dcc0706` |
| [experiments/twist2_right_arm_manual/native_relative_reference.hpp](../experiments/twist2_right_arm_manual/native_relative_reference.hpp) | 17 | 목록 확인 | - | `fba48ae16915` |
| [experiments/twist2_right_arm_manual/native_relay_contract.hpp](../experiments/twist2_right_arm_manual/native_relay_contract.hpp) | 22 | 목록 확인 | - | `d3fe4a0fdf3c` |
| [experiments/twist2_right_arm_manual/native_snapshot_freshness.hpp](../experiments/twist2_right_arm_manual/native_snapshot_freshness.hpp) | 7 | 목록 확인 | - | `7b9026980e86` |
| [experiments/twist2_right_arm_manual/native_state_audit.hpp](../experiments/twist2_right_arm_manual/native_state_audit.hpp) | 43 | 목록 확인 | - | `f0ded84a35ec` |
| [experiments/twist2_right_arm_manual/native_state_tick.hpp](../experiments/twist2_right_arm_manual/native_state_tick.hpp) | 8 | 목록 확인 | - | `ff86033bf355` |
| [experiments/twist2_right_arm_manual/native_stop_audit.hpp](../experiments/twist2_right_arm_manual/native_stop_audit.hpp) | 34 | 목록 확인 | - | `32fca833c526` |
| [experiments/twist2_right_arm_manual/native_vr_cycle_udp.hpp](../experiments/twist2_right_arm_manual/native_vr_cycle_udp.hpp) | 69 | 목록 확인 | - | `2424fa527778` |
| [experiments/twist2_right_arm_manual/native_vr_invocation.hpp](../experiments/twist2_right_arm_manual/native_vr_invocation.hpp) | 10 | 목록 확인 | - | `2b7f8dc20a03` |
| [experiments/twist2_right_arm_manual/native_vr_policy_adapter.hpp](../experiments/twist2_right_arm_manual/native_vr_policy_adapter.hpp) | 78 | 목록 확인 | - | `0c1ad7b3890c` |
| [experiments/twist2_right_arm_manual/native_vr_udp.hpp](../experiments/twist2_right_arm_manual/native_vr_udp.hpp) | 53 | 목록 확인 | - | `1cefbd02ec25` |
| [experiments/twist2_right_arm_manual/observe_seed_file_offline.py](../experiments/twist2_right_arm_manual/observe_seed_file_offline.py) | 32 | 목록 확인 | Main | `3d871e405f8f` |
| [experiments/twist2_right_arm_manual/offline_blend.hpp](../experiments/twist2_right_arm_manual/offline_blend.hpp) | 39 | 목록 확인 | - | `f0b675042952` |
| [experiments/twist2_right_arm_manual/offline_dispatch.hpp](../experiments/twist2_right_arm_manual/offline_dispatch.hpp) | 63 | 목록 확인 | - | `005c9089f2dc` |
| [experiments/twist2_right_arm_manual/offline_hg_native_decoder.hpp](../experiments/twist2_right_arm_manual/offline_hg_native_decoder.hpp) | 62 | 목록 확인 | - | `28c50c6a0ff8` |
| [experiments/twist2_right_arm_manual/offline_lag_fixture.hpp](../experiments/twist2_right_arm_manual/offline_lag_fixture.hpp) | 11 | 목록 확인 | - | `7512e87f46e6` |
| [experiments/twist2_right_arm_manual/offline_observation_history.hpp](../experiments/twist2_right_arm_manual/offline_observation_history.hpp) | 69 | 목록 확인 | - | `a2bd5e545e00` |
| [experiments/twist2_right_arm_manual/offline_owner.hpp](../experiments/twist2_right_arm_manual/offline_owner.hpp) | 185 | 목록 확인 | - | `1f790188512a` |
| [experiments/twist2_right_arm_manual/offline_policy_adapter.py](../experiments/twist2_right_arm_manual/offline_policy_adapter.py) | 39 | 목록 확인 | ReadVerifiedPolicy, AdaptOutput | `aa3a949056a0` |
| [experiments/twist2_right_arm_manual/offline_state_continuity.hpp](../experiments/twist2_right_arm_manual/offline_state_continuity.hpp) | 35 | 목록 확인 | - | `6034473953f7` |
| [experiments/twist2_right_arm_manual/offline_twist2_constants.hpp](../experiments/twist2_right_arm_manual/offline_twist2_constants.hpp) | 45 | 목록 확인 | - | `517a651ecfc9` |
| [experiments/twist2_right_arm_manual/offline_word_crc.hpp](../experiments/twist2_right_arm_manual/offline_word_crc.hpp) | 21 | 목록 확인 | - | `74030c3679aa` |
| [experiments/twist2_right_arm_manual/offline_writer_study.hpp](../experiments/twist2_right_arm_manual/offline_writer_study.hpp) | 93 | 목록 확인 | - | `3bc456b139c6` |
| [experiments/twist2_right_arm_manual/owner_policy_stdio.cpp](../experiments/twist2_right_arm_manual/owner_policy_stdio.cpp) | 151 | 목록 확인 | - | `2b0c4d8eeed0` |
| [experiments/twist2_right_arm_manual/pc_native_receive_probe.cpp](../experiments/twist2_right_arm_manual/pc_native_receive_probe.cpp) | 73 | 목록 확인 | - | `957d89df5f0b` |
| [experiments/twist2_right_arm_manual/pd_gain_comparison.py](../experiments/twist2_right_arm_manual/pd_gain_comparison.py) | 115 | 목록 확인 | sha, candidates, evaluate, main | `50e09ad58b2f` |
| [experiments/twist2_right_arm_manual/pd_gain_options.hpp](../experiments/twist2_right_arm_manual/pd_gain_options.hpp) | 59 | 목록 확인 | - | `a992fe6591f1` |
| [experiments/twist2_right_arm_manual/pd_joint_trial.hpp](../experiments/twist2_right_arm_manual/pd_joint_trial.hpp) | 46 | 목록 확인 | - | `e760154bb5a4` |
| [experiments/twist2_right_arm_manual/pd_reach_reference.hpp](../experiments/twist2_right_arm_manual/pd_reach_reference.hpp) | 17 | 목록 확인 | - | `ca0f771ddfd2` |
| [experiments/twist2_right_arm_manual/pd_reach_timing.py](../experiments/twist2_right_arm_manual/pd_reach_timing.py) | 74 | 목록 확인 | check_acceleration, make_timing, choose_timing | `a039a07ca898` |
| [experiments/twist2_right_arm_manual/pd_reach_trial.hpp](../experiments/twist2_right_arm_manual/pd_reach_trial.hpp) | 51 | 목록 확인 | - | `a58197aaec1e` |
| [experiments/twist2_right_arm_manual/pd_ready_settle.hpp](../experiments/twist2_right_arm_manual/pd_ready_settle.hpp) | 41 | 목록 확인 | - | `a33e931e51aa` |
| [experiments/twist2_right_arm_manual/pd_small_signal_trial.hpp](../experiments/twist2_right_arm_manual/pd_small_signal_trial.hpp) | 133 | 목록 확인 | - | `a7b8562ab1ac` |
| [experiments/twist2_right_arm_manual/pd_trial_offline.py](../experiments/twist2_right_arm_manual/pd_trial_offline.py) | 138 | 목록 확인 | duration, segment, generate, review, main | `2801c5616dd4` |
| [experiments/twist2_right_arm_manual/periodic_csv.hpp](../experiments/twist2_right_arm_manual/periodic_csv.hpp) | 67 | 목록 확인 | - | `4cd81484c2f5` |
| [experiments/twist2_right_arm_manual/plan_pd_followup_from_vr.py](../experiments/twist2_right_arm_manual/plan_pd_followup_from_vr.py) | 45 | 목록 확인 | build, main | `87228b9d4fb3` |
| [experiments/twist2_right_arm_manual/plan_pd_reach_offline.py](../experiments/twist2_right_arm_manual/plan_pd_reach_offline.py) | 147 | 목록 확인 | plan | `fb359a228180` |
| [experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py](../experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py) | 37 | 목록 확인 | - | `0d6b209be8fa` |
| [experiments/twist2_right_arm_manual/policy_worker_client_offline.py](../experiments/twist2_right_arm_manual/policy_worker_client_offline.py) | 108 | 목록 확인 | PolicyWorkerError, PolicyWorkerClient | `1f09ea45e318` |
| [experiments/twist2_right_arm_manual/prepare_hg_class_fixture.py](../experiments/twist2_right_arm_manual/prepare_hg_class_fixture.py) | 22 | 목록 확인 | Prepare | `abee46353ec5` |
| [experiments/twist2_right_arm_manual/prepare_observation_reference.py](../experiments/twist2_right_arm_manual/prepare_observation_reference.py) | 33 | 목록 확인 | PrepareObservation | `70c84594864b` |
| [experiments/twist2_right_arm_manual/probe_mujoco_pd_contacts.py](../experiments/twist2_right_arm_manual/probe_mujoco_pd_contacts.py) | 67 | 목록 확인 | main | `0d34e7c6ab10` |
| [experiments/twist2_right_arm_manual/probe_seed_file_sharing.py](../experiments/twist2_right_arm_manual/probe_seed_file_sharing.py) | 53 | 목록 확인 | Main | `699d68903785` |
| [experiments/twist2_right_arm_manual/probe_udp_receive_only.py](../experiments/twist2_right_arm_manual/probe_udp_receive_only.py) | 29 | 목록 확인 | main | `eae6c6f28bb9` |
| [experiments/twist2_right_arm_manual/prototype_mink_task_priority.py](../experiments/twist2_right_arm_manual/prototype_mink_task_priority.py) | 64 | 목록 확인 | TaskPriorityPrototype | `d63be18bc6e0` |
| [experiments/twist2_right_arm_manual/queued_input_offline.hpp](../experiments/twist2_right_arm_manual/queued_input_offline.hpp) | 111 | 목록 확인 | - | `aee5d2dfcd0c` |
| [experiments/twist2_right_arm_manual/raw_input_watch_offline.hpp](../experiments/twist2_right_arm_manual/raw_input_watch_offline.hpp) | 28 | 목록 확인 | - | `7f614be48562` |
| [experiments/twist2_right_arm_manual/real_response_frame.hpp](../experiments/twist2_right_arm_manual/real_response_frame.hpp) | 79 | 목록 확인 | - | `b47e4def6d9c` |
| [experiments/twist2_right_arm_manual/real_response_identification.py](../experiments/twist2_right_arm_manual/real_response_identification.py) | 63 | 목록 확인 | _matrix, estimate, main | `a944d7d5764f` |
| [experiments/twist2_right_arm_manual/real_response_log.py](../experiments/twist2_right_arm_manual/real_response_log.py) | 167 | 목록 확인 | _strict_loads, _finite_number, validate_record, Trace, parse_trace (+1) | `33d98438c179` |
| [experiments/twist2_right_arm_manual/receive_only.cpp](../experiments/twist2_right_arm_manual/receive_only.cpp) | 109 | 목록 확인 | - | `635e026486f4` |
| [experiments/twist2_right_arm_manual/receive_target_shadow.cpp](../experiments/twist2_right_arm_manual/receive_target_shadow.cpp) | 258 | 목록 확인 | - | `5b32379fe690` |
| [experiments/twist2_right_arm_manual/receive_vr_shadow.py](../experiments/twist2_right_arm_manual/receive_vr_shadow.py) | 124 | 목록 확인 | Run, main | `d9ebb54637da` |
| [experiments/twist2_right_arm_manual/regular_handoff_safety.hpp](../experiments/twist2_right_arm_manual/regular_handoff_safety.hpp) | 93 | 목록 확인 | - | `9b1408f2edb1` |
| [experiments/twist2_right_arm_manual/replay_cpp_input_tick.py](../experiments/twist2_right_arm_manual/replay_cpp_input_tick.py) | 147 | 목록 확인 | LoadEncoder, BuildTicks, Replay, main | `47f315730589` |
| [experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py](../experiments/twist2_right_arm_manual/replay_cpp_receiver_log.py) | 117 | 목록 확인 | Replay | `9158256c689e` |
| [experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py](../experiments/twist2_right_arm_manual/replay_guarded_quest_fixture.py) | 104 | 목록 확인 | F32, Run | `8025512c5853` |
| [experiments/twist2_right_arm_manual/replay_live_cycle_protocol.py](../experiments/twist2_right_arm_manual/replay_live_cycle_protocol.py) | 43 | 목록 확인 | run | `28df25411938` |
| [experiments/twist2_right_arm_manual/replay_mink_boundary.py](../experiments/twist2_right_arm_manual/replay_mink_boundary.py) | 74 | 목록 확인 | main | `7dd7c107f017` |
| [experiments/twist2_right_arm_manual/replay_mink_cycle_candidate_offline.py](../experiments/twist2_right_arm_manual/replay_mink_cycle_candidate_offline.py) | 89 | 목록 확인 | main | `b93cfb2fff1d` |
| [experiments/twist2_right_arm_manual/replay_mink_torch_owner.py](../experiments/twist2_right_arm_manual/replay_mink_torch_owner.py) | 85 | 목록 확인 | exchange | `6091c33bf7df` |
| [experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/replay_physical_csv_mujoco.py) | 219 | 목록 확인 | PhysicalSample, _FiniteValue, LoadPhysicalCsv, BuildSummary, ParseArguments (+1) | `9d611fbdf982` |
| [experiments/twist2_right_arm_manual/replay_upstream_mink.py](../experiments/twist2_right_arm_manual/replay_upstream_mink.py) | 72 | 목록 확인 | build, main | `854abe3a160b` |
| [experiments/twist2_right_arm_manual/replay_writer_policy_trace.py](../experiments/twist2_right_arm_manual/replay_writer_policy_trace.py) | 168 | 목록 확인 | Run | `646da9cdafea` |
| [experiments/twist2_right_arm_manual/review_hg_capture_offline.py](../experiments/twist2_right_arm_manual/review_hg_capture_offline.py) | 56 | 목록 확인 | Crc, Review | `adbabf26508c` |
| [experiments/twist2_right_arm_manual/review_loaded_settle.py](../experiments/twist2_right_arm_manual/review_loaded_settle.py) | 68 | 목록 확인 | Windows, Review | `2bc58b3b2195` |
| [experiments/twist2_right_arm_manual/review_pd_terms.py](../experiments/twist2_right_arm_manual/review_pd_terms.py) | 53 | 목록 확인 | terms, review | `c2679ef07888` |
| [experiments/twist2_right_arm_manual/review_ready_components.py](../experiments/twist2_right_arm_manual/review_ready_components.py) | 63 | 목록 확인 | Review | `0ff0bec1f9f9` |
| [experiments/twist2_right_arm_manual/review_seed_velocity.py](../experiments/twist2_right_arm_manual/review_seed_velocity.py) | 58 | 목록 확인 | TriggerWindow, JointStats, Main | `d47804eac701` |
| [experiments/twist2_right_arm_manual/run_event_clock_offline.py](../experiments/twist2_right_arm_manual/run_event_clock_offline.py) | 211 | 목록 확인 | Run | `8dd370b0f636` |
| [experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py](../experiments/twist2_right_arm_manual/run_owner_continuous_cpu.py) | 133 | 목록 확인 | Main | `251e7efef2d4` |
| [experiments/twist2_right_arm_manual/run_owner_cpu_offline.py](../experiments/twist2_right_arm_manual/run_owner_cpu_offline.py) | 90 | 목록 확인 | Owner, Main | `0e5d1c1eef4d` |
| [experiments/twist2_right_arm_manual/run_pc_twist2.sh](../experiments/twist2_right_arm_manual/run_pc_twist2.sh) | 44 | 목록 확인 | - | `e3a47b8fa3cf` |
| [experiments/twist2_right_arm_manual/run_policy_cpu_offline.py](../experiments/twist2_right_arm_manual/run_policy_cpu_offline.py) | 51 | 목록 확인 | Smoke | `e88890dd4b2b` |
| [experiments/twist2_right_arm_manual/run_policy_history_offline.py](../experiments/twist2_right_arm_manual/run_policy_history_offline.py) | 105 | 목록 확인 | F32, Run | `ab42d8e0f1d7` |
| [experiments/twist2_right_arm_manual/split_ready_study.py](../experiments/twist2_right_arm_manual/split_ready_study.py) | 82 | 목록 확인 | Limits, SplitReadyStudy | `3873b46a983f` |
| [experiments/twist2_right_arm_manual/split_settle_window.hpp](../experiments/twist2_right_arm_manual/split_settle_window.hpp) | 50 | 목록 확인 | - | `b84615ea47d5` |
| [experiments/twist2_right_arm_manual/split_vr_adapter_study.hpp](../experiments/twist2_right_arm_manual/split_vr_adapter_study.hpp) | 97 | 목록 확인 | - | `2cc30c8bd64b` |
| [experiments/twist2_right_arm_manual/study_vr_packet_spacing.cpp](../experiments/twist2_right_arm_manual/study_vr_packet_spacing.cpp) | 39 | 목록 확인 | - | `388e55f1e6a2` |
| [experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py](../experiments/twist2_right_arm_manual/supply_lowstate_seed_readonly.py) | 64 | 목록 확인 | JointNames, Main | `0729bed9f54c` |
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
| [experiments/twist2_right_arm_manual/test_analyze_vr_pd_replay.py](../experiments/twist2_right_arm_manual/test_analyze_vr_pd_replay.py) | 33 | 목록 확인 | ReplayAnalysisTest | `9a4be55aa116` |
| [experiments/twist2_right_arm_manual/test_anchored_alignment_study.py](../experiments/twist2_right_arm_manual/test_anchored_alignment_study.py) | 95 | 목록 확인 | send, test_recorded_loaded_pose_first_packet_does_not_jump, test_rate_no_overshoot_other_joints_and_fixed_anchor, test_stop_latches, test_missing_packet_freezes_then_timeout_latches (+3) | `ed1a6f8db6cd` |
| [experiments/twist2_right_arm_manual/test_arm_cycle_offline.cpp](../experiments/twist2_right_arm_manual/test_arm_cycle_offline.cpp) | 66 | 목록 확인 | - | `aa34c5e7e11e` |
| [experiments/twist2_right_arm_manual/test_capture_hg_pack.py](../experiments/twist2_right_arm_manual/test_capture_hg_pack.py) | 36 | 목록 확인 | PackingTests | `4e8f0cbd0a91` |
| [experiments/twist2_right_arm_manual/test_compare_ik_targets.py](../experiments/twist2_right_arm_manual/test_compare_ik_targets.py) | 52 | 목록 확인 | fixture, ComparisonTests | `eb5249a255a2` |
| [experiments/twist2_right_arm_manual/test_compare_native_writer_csv.py](../experiments/twist2_right_arm_manual/test_compare_native_writer_csv.py) | 30 | 목록 확인 | test_old_csv_is_not_reconstructed, test_uses_paired_writer_state_and_skips_rejected_duplicate_attempts | `586dec0e0fbe` |
| [experiments/twist2_right_arm_manual/test_controller_handoff_offline.py](../experiments/twist2_right_arm_manual/test_controller_handoff_offline.py) | 200 | 목록 확인 | ControllerHandoffOfflineTest | `8e41f2ba00d6` |
| [experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py](../experiments/twist2_right_arm_manual/test_cpp_guarded_composition.py) | 26 | 목록 확인 | GuardedTests | `3c91a93432e9` |
| [experiments/twist2_right_arm_manual/test_cpp_input_contract.py](../experiments/twist2_right_arm_manual/test_cpp_input_contract.py) | 174 | 목록 확인 | Idle, PythonDisposition, InputContractTests | `226756d805b4` |
| [experiments/twist2_right_arm_manual/test_cpp_input_tick.py](../experiments/twist2_right_arm_manual/test_cpp_input_tick.py) | 125 | 목록 확인 | Received, Tick, InputTickTests, ReplayTests | `7fa16a70eecd` |
| [experiments/twist2_right_arm_manual/test_cpp_measured_composition.py](../experiments/twist2_right_arm_manual/test_cpp_measured_composition.py) | 127 | 목록 확인 | Event, CompositionTests | `21b1d0c8b1e0` |
| [experiments/twist2_right_arm_manual/test_cpp_queued_input.py](../experiments/twist2_right_arm_manual/test_cpp_queued_input.py) | 171 | 목록 확인 | Push, Tick, QueuedInputTests | `9a8b09775031` |
| [experiments/twist2_right_arm_manual/test_cpp_receive_only.py](../experiments/twist2_right_arm_manual/test_cpp_receive_only.py) | 41 | 목록 확인 | ReceiveOnlyTest | `a00f849ed9c2` |
| [experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py](../experiments/twist2_right_arm_manual/test_cpp_receive_target_shadow.py) | 258 | 목록 확인 | ReadRows, ReceiveTargetShadowTests | `480e16d429ff` |
| [experiments/twist2_right_arm_manual/test_cpp_upper_target.py](../experiments/twist2_right_arm_manual/test_cpp_upper_target.py) | 140 | 목록 확인 | Packet, Event, UpperTargetTests | `57ba31765a63` |
| [experiments/twist2_right_arm_manual/test_cpp_validator.py](../experiments/twist2_right_arm_manual/test_cpp_validator.py) | 98 | 목록 확인 | EncodePacket, ValidatorTests | `ce4ff75a211d` |
| [experiments/twist2_right_arm_manual/test_event_clock_loop.cpp](../experiments/twist2_right_arm_manual/test_event_clock_loop.cpp) | 103 | 목록 확인 | - | `a9ee9a027657` |
| [experiments/twist2_right_arm_manual/test_feedback_gyro.py](../experiments/twist2_right_arm_manual/test_feedback_gyro.py) | 16 | 목록 확인 | test_recorded_gyro_order_sign_and_scale, test_missing_is_explicit_and_partial_is_rejected, test_nonfinite_is_rejected | `850f47dbfb2e` |
| [experiments/twist2_right_arm_manual/test_guarded_composition.cpp](../experiments/twist2_right_arm_manual/test_guarded_composition.cpp) | 78 | 목록 확인 | - | `0547ad1698bb` |
| [experiments/twist2_right_arm_manual/test_guarded_replay.cpp](../experiments/twist2_right_arm_manual/test_guarded_replay.cpp) | 49 | 목록 확인 | - | `d61a6ffee1f4` |
| [experiments/twist2_right_arm_manual/test_hg_native_decoder.cpp](../experiments/twist2_right_arm_manual/test_hg_native_decoder.cpp) | 72 | 목록 확인 | - | `9da61848c411` |
| [experiments/twist2_right_arm_manual/test_identification_audit.py](../experiments/twist2_right_arm_manual/test_identification_audit.py) | 43 | 목록 확인 | AuditTest | `3069bddf07e9` |
| [experiments/twist2_right_arm_manual/test_input_validator.cpp](../experiments/twist2_right_arm_manual/test_input_validator.cpp) | 17 | 목록 확인 | - | `81e49b88cd5f` |
| [experiments/twist2_right_arm_manual/test_joint_limit_guard.py](../experiments/twist2_right_arm_manual/test_joint_limit_guard.py) | 134 | 목록 확인 | envelope, EnvelopeTest, DynamicsLimitTest | `016910115a71` |
| [experiments/twist2_right_arm_manual/test_live_cycle_cadence.py](../experiments/twist2_right_arm_manual/test_live_cycle_cadence.py) | 27 | 목록 확인 | run | `3d35e900e547` |
| [experiments/twist2_right_arm_manual/test_measured_composition.cpp](../experiments/twist2_right_arm_manual/test_measured_composition.cpp) | 37 | 목록 확인 | - | `eb9407fcfd25` |
| [experiments/twist2_right_arm_manual/test_mink_cycle_candidate_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_cycle_candidate_offline.cpp) | 97 | 목록 확인 | - | `c181501976fc` |
| [experiments/twist2_right_arm_manual/test_mink_cycle_owner_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_cycle_owner_offline.cpp) | 55 | 목록 확인 | - | `1ca9a276d400` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_bridge.py](../experiments/twist2_right_arm_manual/test_mink_live_cycle_bridge.py) | 127 | 목록 확인 | Socket, BridgeTests | `c643d0b48814` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_contract.cpp](../experiments/twist2_right_arm_manual/test_mink_live_cycle_contract.cpp) | 164 | 목록 확인 | - | `4f42616a6938` |
| [experiments/twist2_right_arm_manual/test_mink_live_cycle_target.cpp](../experiments/twist2_right_arm_manual/test_mink_live_cycle_target.cpp) | 23 | 목록 확인 | - | `b57ffb6c641b` |
| [experiments/twist2_right_arm_manual/test_mink_policy_hold_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_policy_hold_offline.cpp) | 67 | 목록 확인 | - | `fd7b2b189518` |
| [experiments/twist2_right_arm_manual/test_mink_resampled_owner_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_resampled_owner_offline.cpp) | 80 | 목록 확인 | - | `09bd4b083913` |
| [experiments/twist2_right_arm_manual/test_mink_resampler_offline.cpp](../experiments/twist2_right_arm_manual/test_mink_resampler_offline.cpp) | 67 | 목록 확인 | - | `04dfdab0802f` |
| [experiments/twist2_right_arm_manual/test_mink_speed_comparison.py](../experiments/twist2_right_arm_manual/test_mink_speed_comparison.py) | 51 | 목록 확인 | Profiles | `0f7a198669b5` |
| [experiments/twist2_right_arm_manual/test_mink_udp_target.cpp](../experiments/twist2_right_arm_manual/test_mink_udp_target.cpp) | 46 | 목록 확인 | - | `6265a846b1bc` |
| [experiments/twist2_right_arm_manual/test_mujoco_feedback_offline.py](../experiments/twist2_right_arm_manual/test_mujoco_feedback_offline.py) | 27 | 목록 확인 | FeedbackTests | `e54c7202179e` |
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
| [experiments/twist2_right_arm_manual/test_native_composition.cpp](../experiments/twist2_right_arm_manual/test_native_composition.cpp) | 70 | 목록 확인 | - | `894cd3aa0ece` |
| [experiments/twist2_right_arm_manual/test_native_cycle_build_contract.py](../experiments/twist2_right_arm_manual/test_native_cycle_build_contract.py) | 48 | 목록 확인 | NativeCycleBuildContractTest | `020f1d34459b` |
| [experiments/twist2_right_arm_manual/test_native_snapshot_freshness.cpp](../experiments/twist2_right_arm_manual/test_native_snapshot_freshness.cpp) | 16 | 목록 확인 | - | `365759fc82a9` |
| [experiments/twist2_right_arm_manual/test_native_state_audit.cpp](../experiments/twist2_right_arm_manual/test_native_state_audit.cpp) | 56 | 목록 확인 | - | `9e26bb80f12d` |
| [experiments/twist2_right_arm_manual/test_native_vr_invocation.cpp](../experiments/twist2_right_arm_manual/test_native_vr_invocation.cpp) | 16 | 목록 확인 | - | `186728f93df0` |
| [experiments/twist2_right_arm_manual/test_native_vr_policy_adapter.cpp](../experiments/twist2_right_arm_manual/test_native_vr_policy_adapter.cpp) | 78 | 목록 확인 | - | `2e4fbf1b0d48` |
| [experiments/twist2_right_arm_manual/test_no_overlap_runtime.py](../experiments/twist2_right_arm_manual/test_no_overlap_runtime.py) | 30 | 목록 확인 | NoOverlapRuntimeTest | `d6361b410538` |
| [experiments/twist2_right_arm_manual/test_observation_history.cpp](../experiments/twist2_right_arm_manual/test_observation_history.cpp) | 38 | 목록 확인 | - | `18f256bd4968` |
| [experiments/twist2_right_arm_manual/test_offline_dispatch.cpp](../experiments/twist2_right_arm_manual/test_offline_dispatch.cpp) | 53 | 목록 확인 | - | `e98981f6b0f2` |
| [experiments/twist2_right_arm_manual/test_offline_input_adapters.py](../experiments/twist2_right_arm_manual/test_offline_input_adapters.py) | 62 | 목록 확인 | ReferenceCrc, AdapterTests | `bf93b80c781c` |
| [experiments/twist2_right_arm_manual/test_offline_owner.cpp](../experiments/twist2_right_arm_manual/test_offline_owner.cpp) | 79 | 목록 확인 | - | `69b03332b6a8` |
| [experiments/twist2_right_arm_manual/test_offline_word_crc.cpp](../experiments/twist2_right_arm_manual/test_offline_word_crc.cpp) | 18 | 목록 확인 | - | `2b49042da100` |
| [experiments/twist2_right_arm_manual/test_offline_writer_study.cpp](../experiments/twist2_right_arm_manual/test_offline_writer_study.cpp) | 87 | 목록 확인 | - | `ab1880fd7434` |
| [experiments/twist2_right_arm_manual/test_owner_startup.cpp](../experiments/twist2_right_arm_manual/test_owner_startup.cpp) | 129 | 목록 확인 | - | `20f2bb3ffbb7` |
| [experiments/twist2_right_arm_manual/test_owner_torque_fade.cpp](../experiments/twist2_right_arm_manual/test_owner_torque_fade.cpp) | 51 | 목록 확인 | - | `5115adedacbe` |
| [experiments/twist2_right_arm_manual/test_pd_gain_comparison.py](../experiments/twist2_right_arm_manual/test_pd_gain_comparison.py) | 61 | 목록 확인 | GainTests | `52adaf8b6bbf` |
| [experiments/twist2_right_arm_manual/test_pd_gain_options.cpp](../experiments/twist2_right_arm_manual/test_pd_gain_options.cpp) | 49 | 목록 확인 | - | `81bb7c7b7e08` |
| [experiments/twist2_right_arm_manual/test_pd_joint_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_joint_trial.cpp) | 22 | 목록 확인 | - | `a8982671f031` |
| [experiments/twist2_right_arm_manual/test_pd_reach_timing.py](../experiments/twist2_right_arm_manual/test_pd_reach_timing.py) | 42 | 목록 확인 | TimingTests | `6545f60d247d` |
| [experiments/twist2_right_arm_manual/test_pd_reach_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_reach_trial.cpp) | 31 | 목록 확인 | - | `de25a79d8922` |
| [experiments/twist2_right_arm_manual/test_pd_ready_settle.cpp](../experiments/twist2_right_arm_manual/test_pd_ready_settle.cpp) | 46 | 목록 확인 | - | `eaeae7a41916` |
| [experiments/twist2_right_arm_manual/test_pd_small_signal_trial.cpp](../experiments/twist2_right_arm_manual/test_pd_small_signal_trial.cpp) | 56 | 목록 확인 | - | `7a2f5da19a6b` |
| [experiments/twist2_right_arm_manual/test_pd_trial_offline.py](../experiments/twist2_right_arm_manual/test_pd_trial_offline.py) | 88 | 목록 확인 | TrialTests | `deb46156afc4` |
| [experiments/twist2_right_arm_manual/test_periodic_csv.cpp](../experiments/twist2_right_arm_manual/test_periodic_csv.cpp) | 39 | 목록 확인 | - | `572802cbea41` |
| [experiments/twist2_right_arm_manual/test_periodic_csv_failure.cpp](../experiments/twist2_right_arm_manual/test_periodic_csv_failure.cpp) | 27 | 목록 확인 | - | `09a655c5610a` |
| [experiments/twist2_right_arm_manual/test_persistent_pd_runtime.py](../experiments/twist2_right_arm_manual/test_persistent_pd_runtime.py) | 85 | 목록 확인 | PersistentPdRuntimeTest | `d61de3fe8266` |
| [experiments/twist2_right_arm_manual/test_policy_history_loop.cpp](../experiments/twist2_right_arm_manual/test_policy_history_loop.cpp) | 84 | 목록 확인 | - | `015f9b2be346` |
| [experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py](../experiments/twist2_right_arm_manual/test_policy_worker_client_offline.py) | 56 | 목록 확인 | Command, WorkerClientTests | `18e5ffcb674c` |
| [experiments/twist2_right_arm_manual/test_policy_worker_offline.py](../experiments/twist2_right_arm_manual/test_policy_worker_offline.py) | 39 | 목록 확인 | WorkerTests | `ccd50d795dda` |
| [experiments/twist2_right_arm_manual/test_preinfer_blend.cpp](../experiments/twist2_right_arm_manual/test_preinfer_blend.cpp) | 56 | 목록 확인 | - | `2fe9e0adfc8a` |
| [experiments/twist2_right_arm_manual/test_queued_input.cpp](../experiments/twist2_right_arm_manual/test_queued_input.cpp) | 68 | 목록 확인 | - | `fdee42db4188` |
| [experiments/twist2_right_arm_manual/test_raw_event_clock.py](../experiments/twist2_right_arm_manual/test_raw_event_clock.py) | 103 | 목록 확인 | Raw, RawEventTests | `3f5c53d6c216` |
| [experiments/twist2_right_arm_manual/test_real_response_frame.cpp](../experiments/twist2_right_arm_manual/test_real_response_frame.cpp) | 27 | 목록 확인 | - | `21867c44099a` |
| [experiments/twist2_right_arm_manual/test_real_response_identification.py](../experiments/twist2_right_arm_manual/test_real_response_identification.py) | 57 | 목록 확인 | record, RealResponseTest | `e0ec0c2d658e` |
| [experiments/twist2_right_arm_manual/test_real_state_continuity.cpp](../experiments/twist2_right_arm_manual/test_real_state_continuity.cpp) | 37 | 목록 확인 | - | `3e2fb92ba897` |
| [experiments/twist2_right_arm_manual/test_receive_vr_shadow.py](../experiments/twist2_right_arm_manual/test_receive_vr_shadow.py) | 71 | 목록 확인 | ReceiverTests | `ebd4b084ddb4` |
| [experiments/twist2_right_arm_manual/test_regular_handoff_safety.cpp](../experiments/twist2_right_arm_manual/test_regular_handoff_safety.cpp) | 149 | 목록 확인 | - | `e677ff55f33b` |
| [experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py](../experiments/twist2_right_arm_manual/test_replay_physical_csv_mujoco.py) | 81 | 목록 확인 | ReplayPhysicalCsvMuJoCoTests | `37e735e9b405` |
| [experiments/twist2_right_arm_manual/test_review_loaded_settle.py](../experiments/twist2_right_arm_manual/test_review_loaded_settle.py) | 38 | 목록 확인 | rows, test_stationary_offset_does_not_imply_motion_or_ready, test_slow_drift_visible_even_when_reported_velocity_zero, test_invalid_sample_breaks_window, test_midwindow_excursion_not_hidden_by_matching_endpoints | `f0efbde5012c` |
| [experiments/twist2_right_arm_manual/test_review_ready_components.py](../experiments/twist2_right_arm_manual/test_review_ready_components.py) | 37 | 목록 확인 | row, test_load_error_is_separate_but_arm_error_still_blocks, test_uses_previous_target_not_current_target, test_gap_and_invalid_state_break_sampled_run | `00d29b44aac8` |
| [experiments/twist2_right_arm_manual/test_split_ready_study.py](../experiments/twist2_right_arm_manual/test_split_ready_study.py) | 55 | 목록 확인 | gate, feed, settle, test_static_load_offset_and_alignment_are_separate, test_slow_drift_blocks_even_when_velocity_reports_zero (+3) | `474210f69575` |
| [experiments/twist2_right_arm_manual/test_split_vr_adapter_study.cpp](../experiments/twist2_right_arm_manual/test_split_vr_adapter_study.cpp) | 217 | 목록 확인 | - | `c776ddb64187` |
| [experiments/twist2_right_arm_manual/test_state_watchdog.cpp](../experiments/twist2_right_arm_manual/test_state_watchdog.cpp) | 20 | 목록 확인 | - | `b533f925cecb` |
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
| [experiments/twist2_right_arm_manual/test_upper_target_offline.cpp](../experiments/twist2_right_arm_manual/test_upper_target_offline.cpp) | 50 | 목록 확인 | - | `b2ffdfeaa874` |
| [experiments/twist2_right_arm_manual/test_verified_regular_handoff.cpp](../experiments/twist2_right_arm_manual/test_verified_regular_handoff.cpp) | 64 | 목록 확인 | - | `4f74fe2ce105` |
| [experiments/twist2_right_arm_manual/test_vr_input_offline.py](../experiments/twist2_right_arm_manual/test_vr_input_offline.py) | 90 | 목록 확인 | MakePacket, VRInputTests | `f26ebf2db1e7` |
| [experiments/twist2_right_arm_manual/test_vr_rate_limits.cpp](../experiments/twist2_right_arm_manual/test_vr_rate_limits.cpp) | 31 | 목록 확인 | - | `c0a71a08952e` |
| [experiments/twist2_right_arm_manual/test_writer_frame.cpp](../experiments/twist2_right_arm_manual/test_writer_frame.cpp) | 21 | 목록 확인 | - | `f08138e06758` |
| [experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp](../experiments/twist2_right_arm_manual/test_writer_trace_loop.cpp) | 35 | 목록 확인 | - | `90f1cb463ec9` |
| [experiments/twist2_right_arm_manual/test_wsl_sdk_inventory.py](../experiments/twist2_right_arm_manual/test_wsl_sdk_inventory.py) | 22 | 목록 확인 | InventoryTests | `afce766f9d61` |
| [experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp](../experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp) | 1778 | 목록 확인 | - | `bc37a8ad0949` |
| [experiments/twist2_right_arm_manual/twist2_mink_udp_trial.cpp](../experiments/twist2_right_arm_manual/twist2_mink_udp_trial.cpp) | 1264 | 목록 확인 | - | `1e1bfc21daec` |
| [experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp](../experiments/twist2_right_arm_manual/twist2_right_arm_trial.cpp) | 1205 | 목록 확인 | - | `e61d8a3cf830` |
| [experiments/twist2_right_arm_manual/twist2_vr_native_draft.cpp](../experiments/twist2_right_arm_manual/twist2_vr_native_draft.cpp) | 1214 | 목록 확인 | - | `2c1c0f4d5a5b` |
| [experiments/twist2_right_arm_manual/upper_target_offline.hpp](../experiments/twist2_right_arm_manual/upper_target_offline.hpp) | 138 | 목록 확인 | - | `0bc6acba2a7a` |
| [experiments/twist2_right_arm_manual/validate_input.hpp](../experiments/twist2_right_arm_manual/validate_input.hpp) | 178 | 목록 확인 | - | `a28785a3f42b` |
| [experiments/twist2_right_arm_manual/vendor/json.hpp](../experiments/twist2_right_arm_manual/vendor/json.hpp) | 25526 | 목록 확인 | - | `5f09d1eebe9b` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/IMUState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/IMUState_.hpp) | 503 | 목록 확인 | - | `74afc17e89e5` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/LowState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/LowState_.hpp) | 762 | 목록 확인 | - | `b733d299c4cc` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/MotorState_.hpp](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/MotorState_.hpp) | 691 | 목록 확인 | - | `001af42d4692` |
| [experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/manifest.json](../experiments/twist2_right_arm_manual/vendor/unitree_hg_reference/manifest.json) | 23 | 목록 확인 | - | `457599b6dfe4` |
| [experiments/twist2_right_arm_manual/verified_regular_handoff.hpp](../experiments/twist2_right_arm_manual/verified_regular_handoff.hpp) | 64 | 목록 확인 | - | `c072a624d0f9` |
| [experiments/twist2_right_arm_manual/verify_offline.py](../experiments/twist2_right_arm_manual/verify_offline.py) | 213 | 목록 확인 | CheckCondition, GetFunction, GetDeclaration, GetLinuxPath, RunLocal (+4) | `2cf29eb56f5e` |
| [experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py](../experiments/twist2_right_arm_manual/verify_regular_handoff_offline.py) | 89 | 목록 확인 | main | `f233967c614c` |
| [experiments/twist2_right_arm_manual/vr_input_offline.py](../experiments/twist2_right_arm_manual/vr_input_offline.py) | 103 | 목록 확인 | VRInputStudy | `8726e5026cb4` |
| [experiments/twist2_right_arm_manual/writer_frame.hpp](../experiments/twist2_right_arm_manual/writer_frame.hpp) | 37 | 목록 확인 | - | `16f2ec354c74` |
| [experiments/twist2_right_arm_manual/writer_reference_study.hpp](../experiments/twist2_right_arm_manual/writer_reference_study.hpp) | 31 | 목록 확인 | - | `83053e08fb51` |
| [hardware/g1_arm_bridge/arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/arm_sdk_hold_contract.py) | 368 | 목록 확인 | ArmSdkHoldConfig, HoldValidation, ArmSdkCommandFrame, _finite_vector, _uint8 (+6) | `318d4fd1a75a` |
| [hardware/g1_arm_bridge/arm_sdk_release_contract.py](../hardware/g1_arm_bridge/arm_sdk_release_contract.py) | 138 | 목록 확인 | ReleaseEvidence, _validate_release_arguments, execute_release_sequence | `64072ef0df8b` |
| [hardware/g1_arm_bridge/arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/arm_sdk_teleop_contract.py) | 873 | 목록 확인 | Gate7ContractError, RegularArmPose, Gate7Config, MinkArmSample, TrajectorySample (+11) | `99c7cc7339d8` |
| [hardware/g1_arm_bridge/check_startup_readiness.py](../hardware/g1_arm_bridge/check_startup_readiness.py) | 601 | 목록 확인 | PrecheckConfig, TimedPacket, Blocker, _positive_float, load_config (+12) | `4659e086065f` |
| [hardware/g1_arm_bridge/check_startup_readiness_entry.py](../hardware/g1_arm_bridge/check_startup_readiness_entry.py) | 176 | 목록 확인 | _pop_option, _option_path, validate_forward_token, _finite_vector, _validated_raw_odom (+3) | `77da5a14e8db` |
| [hardware/g1_arm_bridge/diagnose_initial_pose_collision.py](../hardware/g1_arm_bridge/diagnose_initial_pose_collision.py) | 304 | 목록 확인 | _joint_pose, _has_exact_geom_contact, _probe_zero_mesh_distance, _robust_geom_distance, _nearby_pairs (+1) | `a4f1ed1c0714` |
| [hardware/g1_arm_bridge/edit_startup_ready_pose.py](../hardware/g1_arm_bridge/edit_startup_ready_pose.py) | 462 | 목록 확인 | PoseAssessment, EditorState, ParseArguments, LoadPose, SafeLimitsDegrees (+11) | `21c4f7e692f9` |
| [hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/experimental_stateful_gate7_controller.py) | 29 | 목록 확인 | ExperimentalStatefulGate7TeleopController | `a93f2c85b9b1` |
| [hardware/g1_arm_bridge/g1_base_state.py](../hardware/g1_arm_bridge/g1_base_state.py) | 212 | 목록 확인 | InvalidBaseStateError, NormalizedBaseState, _FiniteVector, NormalizeQuaternionWXYZ, MultiplyQuaternionWXYZ (+4) | `11c6f8e1e985` |
| [hardware/g1_arm_bridge/g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/g1_camera_replay_tcp.py) | 321 | 목록 확인 | LoadFont, BuildReplayJpeg, ParseArguments, ValidateArguments, WriteResult (+1) | `93bfe4888a37` |
| [hardware/g1_arm_bridge/g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/g1_camera_tcp_bridge.py) | 211 | 목록 확인 | BuildFramePacket, ParseArguments, CreateVideoClient, ConnectUnity, ValidateArguments (+1) | `cf49862ac617` |
| [hardware/g1_arm_bridge/g1_joint_contract.py](../hardware/g1_arm_bridge/g1_joint_contract.py) | 39 | 목록 확인 | - | `bb33790cb1af` |
| [hardware/g1_arm_bridge/g1_mink_right_arm_csv_logger.py](../hardware/g1_arm_bridge/g1_mink_right_arm_csv_logger.py) | 178 | 목록 확인 | _finite_number, parse_mink_state, row_for, main | `9a80e77eff07` |
| [hardware/g1_arm_bridge/g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/g1_omni_velocity_gateway.py) | 648 | 목록 확인 | clamp, deadzone, wrapped_delta_degrees, omni_to_body_velocity, OmniVelocityConfig (+10) | `aaa87a6c459c` |
| [hardware/g1_arm_bridge/g1_right_arm_jog.py](../hardware/g1_arm_bridge/g1_right_arm_jog.py) | 1284 | 목록 확인 | RuntimeConfig, KeyboardReader, _number, load_config, validate_config (+18) | `145b347a6268` |
| [hardware/g1_arm_bridge/g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/g1_right_arm_jog_entry.py) | 234 | 목록 확인 | _argument_path, _config_path, apply_release_result_guard, install_jog_safety_guards, main | `2d16551f17eb` |
| [hardware/g1_arm_bridge/g1_unity_state_bridge.py](../hardware/g1_arm_bridge/g1_unity_state_bridge.py) | 224 | 목록 확인 | _FiniteVector, _QuaternionAngleDegrees, _RequireFullBody, BuildUnityHardwareStatePacket, EncodeUnityHardwareStatePacket (+1) | `4d820db4d806` |
| [hardware/g1_arm_bridge/g1_velocity_axis_trial_sender.py](../hardware/g1_arm_bridge/g1_velocity_axis_trial_sender.py) | 110 | 목록 확인 | velocity_for, discover, main | `74d23a91809b` |
| [hardware/g1_arm_bridge/g1_velocity_discovery.py](../hardware/g1_arm_bridge/g1_velocity_discovery.py) | 43 | 목록 확인 | parse_discovery, make_listener | `a41ab9086893` |
| [hardware/g1_arm_bridge/g1_velocity_keypad_relay.py](../hardware/g1_arm_bridge/g1_velocity_keypad_relay.py) | 160 | 목록 확인 | StalePacket, strict_load, validate, validate_order, main | `ae938aaf2fc5` |
| [hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/gate5_lowstate_safety_monitor.py) | 803 | 목록 확인 | LowStatePacketError, BaseStateTelemetry, LowStateTelemetry, PacketOrderTracker, _finite_joint_vector (+16) | `1081cdcd9e21` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold.py) | 886 | 목록 확인 | RuntimeConfig, LowStateSnapshot, LowStateBuffer, _finite_number, load_runtime_config (+12) | `1c33ee6274c1` |
| [hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py](../hardware/g1_arm_bridge/gate6_arm_sdk_hold_entry.py) | 72 | 목록 확인 | install_supported_gate6_guards, main | `2a8dcda852e6` |
| [hardware/g1_arm_bridge/gate6_weight_hold_trial.py](../hardware/g1_arm_bridge/gate6_weight_hold_trial.py) | 156 | 목록 확인 | BuildTrialConfig, LocalToWSL, RunChecked, RunTrial, main | `5b13762395f4` |
| [hardware/g1_arm_bridge/gate7_acquisition_guard.py](../hardware/g1_arm_bridge/gate7_acquisition_guard.py) | 126 | 목록 확인 | ActiveAcquisitionGuard, validate_full_body_snapshot_matches_precheck, validate_acquisition_hold_target | `d7dcaf61ae8a` |
| [hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py](../hardware/g1_arm_bridge/gate7_capture_mujoco_replay.py) | 268 | 목록 확인 | SleepUntilStep, SelectReplayWindow, _replace_dual, CheckReplayModelIdentity, BuildExperimentalLimitedFrames (+2) | `2a2ff88904dd` |
| [hardware/g1_arm_bridge/gate7_capture_quality.py](../hardware/g1_arm_bridge/gate7_capture_quality.py) | 876 | 목록 확인 | _percentile, _round, _replace_dual, _decode_capture, _series_metrics (+9) | `8da69d0dfdc7` |
| [hardware/g1_arm_bridge/gate7_capture_regression.py](../hardware/g1_arm_bridge/gate7_capture_regression.py) | 217 | 목록 확인 | _replace_dual, _file_sha256, BuildRegressionTrace, CompareTrace, _automatic_result_path (+2) | `6ea4853ec628` |
| [hardware/g1_arm_bridge/gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/gate7_fault_injection_matrix.py) | 317 | 목록 확인 | _replace_dual, _synthetic_active_value, _load_active_value, _payload, _new_controller (+5) | `46f4cef501a3` |
| [hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/gate7_hardware_virtual_e2e.py) | 372 | 목록 확인 | _replace_dual, _packet, _automatic_result_path, _parse_args, main | `5aea861f5f63` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk.py) | 963 | 입출력 확인 | LiveHardwareConfig, _finite, LoadLiveHardwareConfig, ValidateLiveHardwareConfig, ValidateRuckigRuntime (+13) | `0b71b1540a00` |
| [hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py](../hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py) | 270 | 목록 확인 | _argument_path, _pop_argument, install_supported_path_guards, main | `2d1ec7edd149` |
| [hardware/g1_arm_bridge/gate7_live_dry_run.py](../hardware/g1_arm_bridge/gate7_live_dry_run.py) | 743 | 목록 확인 | DryRunTick, _finite_all_joints, _replace_dual_arm, _automatic_path, _resolve_output_path (+6) | `c23e7372b0d1` |
| [hardware/g1_arm_bridge/gate7_live_safety_guard.py](../hardware/g1_arm_bridge/gate7_live_safety_guard.py) | 120 | 목록 확인 | ArmSegmentPoint, LinearDualArmSegment, require_active_collision_evidence, _finite_all_joints, build_final_command_segment (+1) | `c89e7f456590` |
| [hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py](../hardware/g1_arm_bridge/gate7_mink_arm_sdk_offline.py) | 515 | 목록 확인 | _set_full_body_pose, CollisionPathValidator, _replace_dual_arm, _mink_packet, _target_right_arm (+3) | `36c29b7c21ab` |
| [hardware/g1_arm_bridge/gate7_mink_capture.py](../hardware/g1_arm_bridge/gate7_mink_capture.py) | 149 | 목록 확인 | _automatic_path, _write_line, _parse_args, main | `74b9748e6803` |
| [hardware/g1_arm_bridge/gate7_mink_cycle_relay.py](../hardware/g1_arm_bridge/gate7_mink_cycle_relay.py) | 102 | 목록 확인 | strict_load, validate, open_feedback_socket, main | `c547fb5ef8e6` |
| [hardware/g1_arm_bridge/gate7_mink_replay.py](../hardware/g1_arm_bridge/gate7_mink_replay.py) | 152 | 목록 확인 | CapturedPacket, LoadCapture, NormalizePayload, CaptureSha256, validate_replay_destination (+2) | `60e2e3c2814f` |
| [hardware/g1_arm_bridge/gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/gate7_mink_wsl_relay.py) | 244 | 입출력 확인 | MinkOrderGuard, ValidateRelayEndpoint, ValidateAndForward, _automatic_result_path, _parse_args (+1) | `933c08a7ea2f` |
| [hardware/g1_arm_bridge/gate7_relay_provenance_guard.py](../hardware/g1_arm_bridge/gate7_relay_provenance_guard.py) | 174 | 목록 확인 | validate_relay_token, _payload_object, require_relay_token, command_provenance, require_live_candidate_for_relay (+3) | `93b82a749c38` |
| [hardware/g1_arm_bridge/generate_fake_mink_targets.py](../hardware/g1_arm_bridge/generate_fake_mink_targets.py) | 117 | 목록 확인 | parse_args, main | `eeb5c6e0e331` |
| [hardware/g1_arm_bridge/hardware_state.py](../hardware/g1_arm_bridge/hardware_state.py) | 91 | 목록 확인 | HardwarePhase, FaultCode, build_status, write_status | `81f126c94061` |
| [hardware/g1_arm_bridge/live_lowstate_mujoco.py](../hardware/g1_arm_bridge/live_lowstate_mujoco.py) | 652 | 목록 확인 | StreamState, BaseBodyPose, ParseArguments, ResolveMeasurementLogPath, BuildMirrorMeasurement (+14) | `869447d2b77d` |
| [hardware/g1_arm_bridge/lowstate_health_guard.py](../hardware/g1_arm_bridge/lowstate_health_guard.py) | 119 | 목록 확인 | _value, _temperature_max_c, validate_lowstate_health_message, install_lowstate_health_tracking, require_latest_lowstate_health | `c8715c8899a3` |
| [hardware/g1_arm_bridge/mink_target_dry_run.py](../hardware/g1_arm_bridge/mink_target_dry_run.py) | 127 | 목록 확인 | _fmt_deg, main | `372002c8b23c` |
| [hardware/g1_arm_bridge/plan_startup_transition.py](../hardware/g1_arm_bridge/plan_startup_transition.py) | 686 | 목록 확인 | _inside_pairs, _waypoints_for_order, _dense_segment, _evaluate_order, _joint_limits (+6) | `c80cd65a8d28` |
| [hardware/g1_arm_bridge/precheck_provenance_guard.py](../hardware/g1_arm_bridge/precheck_provenance_guard.py) | 39 | 목록 확인 | require_provenance_bound_precheck | `aa8fbdd33530` |
| [hardware/g1_arm_bridge/probe_joint_motion.py](../hardware/g1_arm_bridge/probe_joint_motion.py) | 177 | 목록 확인 | parse_args, current_positions, collect_positions, summarize, main | `6b43271de626` |
| [hardware/g1_arm_bridge/query_motion_mode.py](../hardware/g1_arm_bridge/query_motion_mode.py) | 110 | 목록 확인 | _write_json, parse_args, main | `d86bc3ea68ba` |
| [hardware/g1_arm_bridge/query_motion_mode_wsl.sh](../hardware/g1_arm_bridge/query_motion_mode_wsl.sh) | 24 | 목록 확인 | - | `19cdf2097714` |
| [hardware/g1_arm_bridge/read_only_lowstate.py](../hardware/g1_arm_bridge/read_only_lowstate.py) | 563 | 목록 확인 | JointSample, ReadOnlyG1LowState, ReadOnlyG1BaseState, _motor_value, _state_uint8 (+9) | `bfaef913f786` |
| [hardware/g1_arm_bridge/read_only_lowstate_entry.py](../hardware/g1_arm_bridge/read_only_lowstate_entry.py) | 154 | 목록 확인 | _pop_option, _finite_vector, install_raw_odom_binding, install_forward_token, main | `a38ce663d019` |
| [hardware/g1_arm_bridge/receive_initial_state.py](../hardware/g1_arm_bridge/receive_initial_state.py) | 199 | 목록 확인 | parse_args, _raw_object, _validate_provenance, _validate_full_body_consistency, main | `4285ba83ada2` |
| [hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py](../hardware/g1_arm_bridge/replay_saved_lowstate_mujoco.py) | 354 | 목록 확인 | SavedLowState, _FiniteVector, _JointNames, _OptionalMode, LoadSnapshot (+5) | `a869fd552b3d` |
| [hardware/g1_arm_bridge/replay_startup_recovery.py](../hardware/g1_arm_bridge/replay_startup_recovery.py) | 186 | 목록 확인 | ParseArguments, LoadViewerSettings, LoadRecovery, InterpolatePose, ApplyRightArmPose (+1) | `3efdfb293bda` |
| [hardware/g1_arm_bridge/right_arm_jog_contract.py](../hardware/g1_arm_bridge/right_arm_jog_contract.py) | 194 | 목록 확인 | ArmJointJogLimits, ArmJointJogTick, validate_jog_limits, ArmJointJogController | `83f51c0a80df` |
| [hardware/g1_arm_bridge/right_arm_jog_safety_guard.py](../hardware/g1_arm_bridge/right_arm_jog_safety_guard.py) | 92 | 목록 확인 | file_sha256, build_jog_permit_provenance, validate_jog_permit_provenance, validate_jog_runtime_full_body, validate_jog_final_segment | `4255ba07f81a` |
| [hardware/g1_arm_bridge/ruckig_gate7_controller.py](../hardware/g1_arm_bridge/ruckig_gate7_controller.py) | 121 | 목록 확인 | RuckigGate7TeleopController | `dcc46f5329c7` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 98 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `3767274abcdf` |
| [hardware/g1_arm_bridge/run_omni_fake_g1_integration.py](../hardware/g1_arm_bridge/run_omni_fake_g1_integration.py) | 173 | 목록 확인 | discovery_loop, validate_command, main | `5c28d8e52590` |
| [hardware/g1_arm_bridge/runtime_base_state_guard.py](../hardware/g1_arm_bridge/runtime_base_state_guard.py) | 316 | 목록 확인 | RuntimeBaseSnapshot, RuntimeBaseStateMonitor, _relative_yaw_rad, _finite_vector, _quaternion_angle_delta_rad (+5) | `9f1816007448` |
| [hardware/g1_arm_bridge/safety_gate.py](../hardware/g1_arm_bridge/safety_gate.py) | 149 | 목록 확인 | SafetyConfig, SafetyDecision, _vector, _within_joint_limits, evaluate_target | `20d483a19afa` |
| [hardware/g1_arm_bridge/simulate_startup_recovery.py](../hardware/g1_arm_bridge/simulate_startup_recovery.py) | 1181 | 목록 확인 | _load_startup_safe_ready_degrees, _right_qpos_ids, _minimum_clearance, _minimum_clearance_extended, _recovery_edge_is_valid (+10) | `370af1261378` |
| [hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh](../hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh) | 69 | 목록 확인 | - | `7cd8933586e9` |
| [hardware/g1_arm_bridge/start_gate6_hold_wsl.sh](../hardware/g1_arm_bridge/start_gate6_hold_wsl.sh) | 24 | 목록 확인 | - | `02803d8b764f` |
| [hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh](../hardware/g1_arm_bridge/start_gate7_live_arm_sdk_wsl.sh) | 29 | 목록 확인 | - | `1040c430ca14` |
| [hardware/g1_arm_bridge/start_read_only_wsl.sh](../hardware/g1_arm_bridge/start_read_only_wsl.sh) | 22 | 목록 확인 | - | `969530765469` |
| [hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh](../hardware/g1_arm_bridge/start_right_arm_jog_wsl.sh) | 24 | 목록 확인 | - | `bf6fc5424ee2` |
| [hardware/g1_arm_bridge/startup_state_binding_guard.py](../hardware/g1_arm_bridge/startup_state_binding_guard.py) | 143 | 목록 확인 | file_sha256, build_state_binding, base_state_to_dict, _require_finite_vector, require_state_binding | `386687ebca94` |
| [hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_hold_contract.py) | 159 | 목록 확인 | _safe_all_q, ArmSdkHoldContractTests | `a004f9246ac4` |
| [hardware/g1_arm_bridge/test_arm_sdk_release_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_release_contract.py) | 192 | 목록 확인 | FakeClock, ReleaseContractTests | `28006040442e` |
| [hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py](../hardware/g1_arm_bridge/test_arm_sdk_teleop_contract.py) | 438 | 목록 확인 | _replace_dual, _sample, ArmSdkTeleopContractTests | `e63af96526f8` |
| [hardware/g1_arm_bridge/test_check_startup_readiness.py](../hardware/g1_arm_bridge/test_check_startup_readiness.py) | 196 | 목록 확인 | _config, _timed_packet, _mode_query, StartupReadinessTests | `37e1032193bc` |
| [hardware/g1_arm_bridge/test_check_startup_readiness_entry.py](../hardware/g1_arm_bridge/test_check_startup_readiness_entry.py) | 111 | 목록 확인 | _raw_base_state, StartupPrecheckEntryTests | `6a1c5cdb14eb` |
| [hardware/g1_arm_bridge/test_collision_diagnostics.py](../hardware/g1_arm_bridge/test_collision_diagnostics.py) | 60 | 목록 확인 | _FakeG1, _FakeController, CollisionDiagnosticTests | `b2642345a203` |
| [hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py](../hardware/g1_arm_bridge/test_experimental_stateful_gate7_controller.py) | 43 | 목록 확인 | ExperimentalStatefulGate7ControllerTests | `cc444df0124f` |
| [hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py](../hardware/g1_arm_bridge/test_fake_mink_safety_e2e.py) | 82 | 목록 확인 | main | `fa397980398b` |
| [hardware/g1_arm_bridge/test_g1_base_state.py](../hardware/g1_arm_bridge/test_g1_base_state.py) | 118 | 목록 확인 | YawQuaternionWXYZ, G1BaseStateTests | `11a58e53ca27` |
| [hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py](../hardware/g1_arm_bridge/test_g1_camera_replay_tcp.py) | 93 | 목록 확인 | G1CameraReplayTcpTest | `ebacf12bcae6` |
| [hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py](../hardware/g1_arm_bridge/test_g1_camera_tcp_bridge.py) | 44 | 목록 확인 | G1CameraTcpBridgeTest | `e1047b89e99b` |
| [hardware/g1_arm_bridge/test_g1_mink_right_arm_csv_logger.py](../hardware/g1_arm_bridge/test_g1_mink_right_arm_csv_logger.py) | 95 | 목록 확인 | packet, MinkCsvLoggerTests | `8372e5954c96` |
| [hardware/g1_arm_bridge/test_g1_omni_body_mapping.py](../hardware/g1_arm_bridge/test_g1_omni_body_mapping.py) | 84 | 목록 확인 | raw_body_vector, OmniBodyMappingTests | `bec8041b85d9` |
| [hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py](../hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py) | 459 | 목록 확인 | CaptureTap, SyntheticTimeout, BurstyConnection, ScriptedConnection, ClockedOmniObservationTests | `1ec08add17a5` |
| [hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py](../hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py) | 123 | 목록 확인 | omni_handler, serve, discovery_sender, main | `9d8bace5948a` |
| [hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py) | 137 | 목록 확인 | OmniVelocityGatewayTests | `fb49ddeff1cd` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog.py) | 359 | 목록 확인 | G1RightArmJogTests | `5a4c8aad4722` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_direct_release.py) | 50 | 목록 확인 | DirectJogReleaseIntegrationTests | `1b11145d8b85` |
| [hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py](../hardware/g1_arm_bridge/test_g1_right_arm_jog_entry.py) | 107 | 목록 확인 | RightArmJogReleaseGuardTests | `808ab9f76a81` |
| [hardware/g1_arm_bridge/test_g1_unity_state_bridge.py](../hardware/g1_arm_bridge/test_g1_unity_state_bridge.py) | 175 | 목록 확인 | LowStatePacket, G1UnityStateBridgeTests | `0c91cc2833b5` |
| [hardware/g1_arm_bridge/test_g1_velocity_axis_trial_sender.py](../hardware/g1_arm_bridge/test_g1_velocity_axis_trial_sender.py) | 14 | 목록 확인 | AxisTrialSenderTests | `21ac239eab0b` |
| [hardware/g1_arm_bridge/test_g1_velocity_discovery.py](../hardware/g1_arm_bridge/test_g1_velocity_discovery.py) | 45 | 목록 확인 | DiscoveryContractTests | `a9508519e6a7` |
| [hardware/g1_arm_bridge/test_g1_velocity_keypad_relay.py](../hardware/g1_arm_bridge/test_g1_velocity_keypad_relay.py) | 75 | 목록 확인 | packet, RelayContractTests | `7e45f0263e57` |
| [hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py](../hardware/g1_arm_bridge/test_gate5_lowstate_safety_monitor.py) | 218 | 목록 확인 | _packet, _base_state, _unused_local_port, Gate5LowStateSafetyTests | `5ab06a9f3908` |
| [hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py](../hardware/g1_arm_bridge/test_gate6_arm_sdk_hold.py) | 215 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, Gate6ArmSdkHoldTests | `f1fb524a6d05` |
| [hardware/g1_arm_bridge/test_gate6_fault_release.py](../hardware/g1_arm_bridge/test_gate6_fault_release.py) | 154 | 목록 확인 | _FakeMotorCommand, _FakeLowCmd, _FakeCRC, _FakeBuffer, _FakePublisher (+2) | `697a9ab1c6a9` |
| [hardware/g1_arm_bridge/test_gate6_interrupt_release.py](../hardware/g1_arm_bridge/test_gate6_interrupt_release.py) | 130 | 목록 확인 | validate_interrupt_release_contract, Gate6InterruptReleaseTests, main | `fad40aefbdfa` |
| [hardware/g1_arm_bridge/test_gate6_weight_hold_trial.py](../hardware/g1_arm_bridge/test_gate6_weight_hold_trial.py) | 89 | 목록 확인 | WeightHoldTrialTests | `d29542ea9f45` |
| [hardware/g1_arm_bridge/test_gate7_acquisition_guard.py](../hardware/g1_arm_bridge/test_gate7_acquisition_guard.py) | 95 | 목록 확인 | sample, Gate7AcquisitionGuardTests | `646fe47e3b73` |
| [hardware/g1_arm_bridge/test_gate7_capture_quality.py](../hardware/g1_arm_bridge/test_gate7_capture_quality.py) | 155 | 목록 확인 | Gate7CaptureQualityTests | `bce6e4a4e5f2` |
| [hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py](../hardware/g1_arm_bridge/test_gate7_fault_injection_matrix.py) | 32 | 목록 확인 | Gate7FaultInjectionMatrixTests | `63b8b799b54f` |
| [hardware/g1_arm_bridge/test_gate7_first_live_profile.py](../hardware/g1_arm_bridge/test_gate7_first_live_profile.py) | 130 | 목록 확인 | Gate7FirstLiveProfileTests | `5e7e22cb6c1c` |
| [hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py](../hardware/g1_arm_bridge/test_gate7_hardware_virtual_e2e.py) | 66 | 목록 확인 | _free_udp_port, Gate7HardwareVirtualE2ETests | `f905f33e9bfa` |
| [hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py](../hardware/g1_arm_bridge/test_gate7_live_arm_sdk.py) | 277 | 목록 확인 | Gate7LiveArmSdkTests | `4755e64b6e17` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run.py) | 361 | 목록 확인 | _replace_dual, _sample, Gate7LiveDryRunTests | `7a777136e907` |
| [hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py](../hardware/g1_arm_bridge/test_gate7_live_dry_run_e2e.py) | 136 | 목록 확인 | _free_udp_port, Gate7LiveDryRunE2ETests | `0eeb63044d28` |
| [hardware/g1_arm_bridge/test_gate7_live_entrypoint.py](../hardware/g1_arm_bridge/test_gate7_live_entrypoint.py) | 136 | 목록 확인 | Gate7LiveEntrypointTests | `1f6cc5c8200e` |
| [hardware/g1_arm_bridge/test_gate7_live_safety_guard.py](../hardware/g1_arm_bridge/test_gate7_live_safety_guard.py) | 89 | 목록 확인 | Gate7LiveSafetyGuardTests | `398bb4186f52` |
| [hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py](../hardware/g1_arm_bridge/test_gate7_mink_capture_replay.py) | 119 | 목록 확인 | _free_udp_port, Gate7MinkCaptureReplayTests | `a67b307d7562` |
| [hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py](../hardware/g1_arm_bridge/test_gate7_mink_wsl_relay.py) | 258 | 목록 확인 | _packet, Gate7MinkWslRelayTests | `985b9d9cb7e4` |
| [hardware/g1_arm_bridge/test_gate7_release_finalization.py](../hardware/g1_arm_bridge/test_gate7_release_finalization.py) | 192 | 목록 확인 | Gate7ReleaseFinalizationTests | `7ff539cd1924` |
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
| [hardware/g1_arm_bridge/test_run_omni_fake_g1_integration.py](../hardware/g1_arm_bridge/test_run_omni_fake_g1_integration.py) | 98 | 목록 확인 | omni_handler, serve, main | `a48c4bde2a6b` |
| [hardware/g1_arm_bridge/test_runtime_base_state_guard.py](../hardware/g1_arm_bridge/test_runtime_base_state_guard.py) | 212 | 목록 확인 | _Message, _yaw_quaternion_wxyz, _precheck, RuntimeBaseStateGuardTests | `9cd231d92daf` |
| [hardware/g1_arm_bridge/test_safety_gate.py](../hardware/g1_arm_bridge/test_safety_gate.py) | 124 | 목록 확인 | SafetyGateTests | `021ebefe3f9f` |
| [hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/test_validate_right_arm_jog_collision_path.py) | 73 | 목록 확인 | ValidateRightArmJogCollisionPathTests | `fdf09a9611a9` |
| [hardware/g1_arm_bridge/test_waist_baseline_read_only.py](../hardware/g1_arm_bridge/test_waist_baseline_read_only.py) | 62 | 목록 확인 | State, test_fresh_recording_and_summary, test_loss_never_completes, test_summary_rejects_empty_and_bad_vectors | `587fe88143f5` |
| [hardware/g1_arm_bridge/test_waist_guard_offline.py](../hardware/g1_arm_bridge/test_waist_guard_offline.py) | 197 | 목록 확인 | WaistGuardTests | `49be997370ed` |
| [hardware/g1_arm_bridge/test_waist_hold_offline.py](../hardware/g1_arm_bridge/test_waist_hold_offline.py) | 124 | 목록 확인 | WaistHoldStudyTests, test_each_axis_pd_direction_without_cross_axis_terms | `0d12e832278e` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path.py) | 262 | 목록 확인 | load_precheck, measured_pose, build_offset_trajectory, build_endpoint_trajectories, validate_offset_path (+5) | `7bba7acde6ee` |
| [hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py](../hardware/g1_arm_bridge/validate_right_arm_jog_collision_path_entry.py) | 43 | 목록 확인 | _argument_path, main | `433f4f489701` |
| [hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py](../hardware/g1_arm_bridge/verify_arm_sdk_message_offline.py) | 64 | 목록 확인 | main | `172f652bdf8b` |
| [hardware/g1_arm_bridge/verify_initial_pose_sync.py](../hardware/g1_arm_bridge/verify_initial_pose_sync.py) | 130 | 목록 확인 | _load_captured_pose, main | `d25fb0303ca3` |
| [hardware/g1_arm_bridge/waist_baseline_read_only.py](../hardware/g1_arm_bridge/waist_baseline_read_only.py) | 134 | 목록 확인 | Summarize, Capture, Run, main | `34f9c923beda` |
| [hardware/g1_arm_bridge/waist_guard_offline.py](../hardware/g1_arm_bridge/waist_guard_offline.py) | 127 | 목록 확인 | WaistGuardStudy, AnalyzeCapture, main | `734da92b7cf9` |
| [hardware/g1_arm_bridge/waist_hold_offline.py](../hardware/g1_arm_bridge/waist_hold_offline.py) | 102 | 목록 확인 | BuildStudyFrame, AnalyzeEvents, main | `11432841a3e6` |
| [tools/ALLOW_G1_DDS_WSL.bat](../tools/ALLOW_G1_DDS_WSL.bat) | 12 | 목록 확인 | - | `015728155ef4` |
| [tools/ALLOW_G1_DDS_WSL_ADMIN.ps1](../tools/ALLOW_G1_DDS_WSL_ADMIN.ps1) | 137 | 목록 확인 | - | `085cec408f91` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS.bat) | 14 | 목록 확인 | - | `7e295f183ed1` |
| [tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1](../tools/ALLOW_G1_LOWSTATE_TO_WINDOWS_ADMIN.ps1) | 112 | 목록 확인 | - | `c5ae1a541243` |
| [tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat](../tools/ANALYZE_G1_GATE7_LATEST_CAPTURE.bat) | 32 | 목록 확인 | - | `bd53ccf085f5` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 108 | 목록 확인 | - | `a999bb9fc290` |
| [tools/CHECK_G1_TELEOP_STARTUP.bat](../tools/CHECK_G1_TELEOP_STARTUP.bat) | 66 | 목록 확인 | - | `bbaa4c38b10e` |
| [tools/CHECK_MJLAB_MATCHED_TRAINING.bat](../tools/CHECK_MJLAB_MATCHED_TRAINING.bat) | 25 | 목록 확인 | - | `47a288a96acf` |
| [tools/CHECK_MJLAB_SETUP.bat](../tools/CHECK_MJLAB_SETUP.bat) | 10 | 목록 확인 | - | `63f178c7626d` |
| [tools/CHECK_MJLAB_SETUP.ps1](../tools/CHECK_MJLAB_SETUP.ps1) | 54 | 목록 확인 | - | `823e83063e61` |
| [tools/CHECK_OMNI_GATEWAY_OFFLINE.bat](../tools/CHECK_OMNI_GATEWAY_OFFLINE.bat) | 15 | 목록 확인 | - | `33b096e6f4d0` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 11 | 목록 확인 | - | `308b1b54bec6` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `f9342a380804` |
| [tools/CONVERT_OMNI_CSV_BODY_VELOCITY.py](../tools/CONVERT_OMNI_CSV_BODY_VELOCITY.py) | 93 | 목록 확인 | _number, convert, main | `e8f154cc3771` |
| [tools/DETECT_G1_NETWORK.bat](../tools/DETECT_G1_NETWORK.bat) | 11 | 목록 확인 | - | `be9f63666f9c` |
| [tools/DETECT_G1_NETWORK_ADMIN.ps1](../tools/DETECT_G1_NETWORK_ADMIN.ps1) | 48 | 목록 확인 | - | `7512a1fa0065` |
| [tools/EDIT_G1_STARTUP_READY_POSE.bat](../tools/EDIT_G1_STARTUP_READY_POSE.bat) | 33 | 목록 확인 | - | `64872de03943` |
| [tools/G1_CAMERA_LAUNCH.py](../tools/G1_CAMERA_LAUNCH.py) | 31 | 목록 확인 | main | `f6d11f6ffebb` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `8405c5e3187b` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 126 | 목록 확인 | - | `e49e43ff9063` |
| [tools/G1_INPUT_OBSERVATION_LAUNCH.py](../tools/G1_INPUT_OBSERVATION_LAUNCH.py) | 131 | 목록 확인 | worker_command, engine_environment, preflight, main | `780d2da11eca` |
| [tools/G1_INPUT_RECEIVE_AUDIT.py](../tools/G1_INPUT_RECEIVE_AUDIT.py) | 597 | 목록 확인 | _stdout_line, LatestOutput, _aged_payload, display_view, AsyncLog (+15) | `338dfea129c7` |
| [tools/G1_VR_TELEOP_LAUNCH.py](../tools/G1_VR_TELEOP_LAUNCH.py) | 318 | 목록 확인 | windows_arguments, process_arguments, collapse_venv_redirectors, option, option_casefold (+10) | `3ad1fb4ca67e` |
| [tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat](../tools/PREFLIGHT_BIMANUAL_QUEST_SIM.bat) | 29 | 목록 확인 | - | `9ef96c249aea` |
| [tools/PREPARE_G1_GATE6_HOLD.bat](../tools/PREPARE_G1_GATE6_HOLD.bat) | 39 | 목록 확인 | - | `3153383c91bf` |
| [tools/PRINT_G1_INPUTS_50HZ.bat](../tools/PRINT_G1_INPUTS_50HZ.bat) | 7 | 목록 확인 | - | `25a7ecef1de6` |
| [tools/PRINT_G1_INPUTS_50HZ.py](../tools/PRINT_G1_INPUTS_50HZ.py) | 228 | 목록 확인 | finite, arm_value, omni_value, LogTail, newest (+1) | `ea02e5193e41` |
| [tools/RECORD_G1_WAIST_BASELINE_READ_ONLY.bat](../tools/RECORD_G1_WAIST_BASELINE_READ_ONLY.bat) | 11 | 목록 확인 | - | `a082f6292224` |
| [tools/RECORD_MINK_RIGHT_ARM_CSV.bat](../tools/RECORD_MINK_RIGHT_ARM_CSV.bat) | 12 | 목록 확인 | - | `7e8de62cc4c4` |
| [tools/RECORD_OMNI_TIMESERIES_CSV.bat](../tools/RECORD_OMNI_TIMESERIES_CSV.bat) | 34 | 목록 확인 | - | `269a3f332f93` |
| [tools/REPORT_LATEST_BIMANUAL_SESSION.bat](../tools/REPORT_LATEST_BIMANUAL_SESSION.bat) | 14 | 목록 확인 | - | `0cd69260bbd3` |
| [tools/RESOLVE_UNITY_EDITOR.bat](../tools/RESOLVE_UNITY_EDITOR.bat) | 39 | 목록 확인 | - | `1f109dbfe2a5` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 11 | 목록 확인 | - | `698638321bb5` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 23 | 목록 확인 | - | `f83e2c335106` |
| [tools/RUN_BIMANUAL_NEAR_HANDS_SWEEP.bat](../tools/RUN_BIMANUAL_NEAR_HANDS_SWEEP.bat) | 10 | 목록 확인 | - | `d96767840c9b` |
| [tools/RUN_BIMANUAL_UDP_CYCLE.bat](../tools/RUN_BIMANUAL_UDP_CYCLE.bat) | 11 | 목록 확인 | - | `d55daa8ab157` |
| [tools/RUN_MUJOCO_PD_FINAL.bat](../tools/RUN_MUJOCO_PD_FINAL.bat) | 16 | 목록 확인 | - | `b13b5ff4d843` |
| [tools/RUN_MUJOCO_PD_SWEEP.bat](../tools/RUN_MUJOCO_PD_SWEEP.bat) | 13 | 목록 확인 | - | `96f245582275` |
| [tools/RUN_PC_TWIST2.ps1](../tools/RUN_PC_TWIST2.ps1) | 21 | 목록 확인 | - | `37b87cb40f89` |
| [tools/SEND_G1_INPUT_AUDIT.bat](../tools/SEND_G1_INPUT_AUDIT.bat) | 7 | 목록 확인 | - | `cb77a658ccfb` |
| [tools/SETUP_G1_VR_TELEOP.bat](../tools/SETUP_G1_VR_TELEOP.bat) | 8 | 목록 확인 | - | `d974167e2a60` |
| [tools/SETUP_G1_VR_TELEOP.py](../tools/SETUP_G1_VR_TELEOP.py) | 54 | 목록 확인 | main | `9187c1d018d6` |
| [tools/SET_UNITY_DISPLAY_MODE.ps1](../tools/SET_UNITY_DISPLAY_MODE.ps1) | 25 | 입출력 확인 | - | `d9f1eb1f0fca` |
| [tools/START_BIMANUAL_SIM.bat](../tools/START_BIMANUAL_SIM.bat) | 8 | 목록 확인 | - | `d8545f04a54f` |
| [tools/START_BIMANUAL_UNITY_SIM.bat](../tools/START_BIMANUAL_UNITY_SIM.bat) | 8 | 목록 확인 | - | `ab8da2e2a374` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 13 | 목록 확인 | - | `c499e73573b3` |
| [tools/START_G1_GATE5_READ_ONLY.bat](../tools/START_G1_GATE5_READ_ONLY.bat) | 37 | 목록 확인 | - | `5315ab2202d3` |
| [tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat](../tools/START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat) | 112 | 목록 확인 | - | `8ec7aff5f329` |
| [tools/START_G1_GATE6_WEIGHT_HOLD.bat](../tools/START_G1_GATE6_WEIGHT_HOLD.bat) | 12 | 목록 확인 | - | `45b2e59a0fcd` |
| [tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat](../tools/START_G1_GATE7_FIRST_LIVE_TRIAL.bat) | 25 | 목록 확인 | - | `dd1f983d674a` |
| [tools/START_G1_GATE7_LIVE_DRY_RUN.bat](../tools/START_G1_GATE7_LIVE_DRY_RUN.bat) | 57 | 목록 확인 | - | `411a69e4014c` |
| [tools/START_G1_GATE7_LIVE_HARDWARE.bat](../tools/START_G1_GATE7_LIVE_HARDWARE.bat) | 235 | 목록 확인 | - | `9526377d71a0` |
| [tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat](../tools/START_G1_GATE7_LOWSTATE_DRY_RUN.bat) | 92 | 목록 확인 | - | `264801696a18` |
| [tools/START_G1_GATE7_STANDARD_MINK.bat](../tools/START_G1_GATE7_STANDARD_MINK.bat) | 11 | 목록 확인 | - | `58a204cd299e` |
| [tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat](../tools/START_G1_GATE7_VISIBLE_MOTION_TRIAL.bat) | 25 | 목록 확인 | - | `20b8d69ecc4c` |
| [tools/START_G1_GATE7_VR_RECORDING.bat](../tools/START_G1_GATE7_VR_RECORDING.bat) | 59 | 목록 확인 | - | `776bbf43bd4e` |
| [tools/START_G1_INPUT_OBSERVATION.bat](../tools/START_G1_INPUT_OBSERVATION.bat) | 13 | 목록 확인 | - | `9c4af5a4f27d` |
| [tools/START_G1_READ_ONLY.bat](../tools/START_G1_READ_ONLY.bat) | 15 | 목록 확인 | - | `a7662ec59842` |
| [tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat](../tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat) | 128 | 목록 확인 | - | `cb2107ef0a12` |
| [tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat](../tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat) | 128 | 목록 확인 | - | `e059a027d941` |
| [tools/START_G1_STATIC_STAND_HANDOFF_PROBE.bat](../tools/START_G1_STATIC_STAND_HANDOFF_PROBE.bat) | 27 | 목록 확인 | - | `d24d5a64cb7d` |
| [tools/START_G1_VELOCITY_MINK_KEYPAD.bat](../tools/START_G1_VELOCITY_MINK_KEYPAD.bat) | 10 | 목록 확인 | - | `73e947bf5fb1` |
| [tools/START_G1_VELOCITY_MINK_KEYPAD.ps1](../tools/START_G1_VELOCITY_MINK_KEYPAD.ps1) | 70 | 목록 확인 | - | `fe26678ddb81` |
| [tools/START_G1_VR_PREVIEW_READ_ONLY.bat](../tools/START_G1_VR_PREVIEW_READ_ONLY.bat) | 43 | 목록 확인 | - | `fa0790232256` |
| [tools/START_G1_VR_TELEOP.bat](../tools/START_G1_VR_TELEOP.bat) | 21 | 목록 확인 | - | `fa80b93ee095` |
| [tools/START_MINK_ARM_CYCLE_SIMULATION.bat](../tools/START_MINK_ARM_CYCLE_SIMULATION.bat) | 28 | 목록 확인 | - | `4f83aa04dcfa` |
| [tools/START_MINK_G1_HARDWARE_SYNC.bat](../tools/START_MINK_G1_HARDWARE_SYNC.bat) | 66 | 목록 확인 | - | `fa24c6c45e36` |
| [tools/START_MINK_SPEED_COMPARISON.bat](../tools/START_MINK_SPEED_COMPARISON.bat) | 15 | 목록 확인 | - | `980356feaa05` |
| [tools/START_MJLAB_MATCHED_CONTINUATION.bat](../tools/START_MJLAB_MATCHED_CONTINUATION.bat) | 21 | 목록 확인 | - | `21865cf94e8c` |
| [tools/START_MJLAB_RECORDED_CURRICULUM.bat](../tools/START_MJLAB_RECORDED_CURRICULUM.bat) | 23 | 목록 확인 | - | `d354de792eff` |
| [tools/START_OMNI_FAKE_G1_INTEGRATION.bat](../tools/START_OMNI_FAKE_G1_INTEGRATION.bat) | 27 | 목록 확인 | - | `00f2fd6afff2` |
| [tools/START_OMNI_GATEWAY_READONLY.bat](../tools/START_OMNI_GATEWAY_READONLY.bat) | 11 | 목록 확인 | - | `113abb94d1a6` |
| [tools/START_TWIST2_MINK_CYCLE_CANDIDATE.bat](../tools/START_TWIST2_MINK_CYCLE_CANDIDATE.bat) | 11 | 목록 확인 | - | `8b95955679a1` |
| [tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1](../tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1) | 70 | 목록 확인 | - | `cfc3deae56f9` |
| [tools/START_TWIST2_MINK_UDP.bat](../tools/START_TWIST2_MINK_UDP.bat) | 11 | 목록 확인 | - | `5618fa28e5df` |
| [tools/START_TWIST2_MINK_UDP.ps1](../tools/START_TWIST2_MINK_UDP.ps1) | 56 | 목록 확인 | - | `766856c8ed96` |
| [tools/START_TWIST2_PD_SWEEP_TO_VR.bat](../tools/START_TWIST2_PD_SWEEP_TO_VR.bat) | 6 | 목록 확인 | - | `4758db14907e` |
| [tools/START_TWIST2_VR_INPUT_SHADOW.bat](../tools/START_TWIST2_VR_INPUT_SHADOW.bat) | 30 | 목록 확인 | - | `20557b578097` |
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
| [tools/TEST_G1_WAIST_HOLD_OFFLINE.bat](../tools/TEST_G1_WAIST_HOLD_OFFLINE.bat) | 16 | 목록 확인 | - | `3159df379046` |
| [tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat](../tools/TEST_MINK_COLLISION_TANGENT_OFFLINE.bat) | 27 | 목록 확인 | - | `fb79771d5d08` |
| [tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat](../tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat) | 47 | 목록 확인 | - | `0d6db212eebb` |
| [tools/TEST_MINK_SAFETY_PIPELINE.bat](../tools/TEST_MINK_SAFETY_PIPELINE.bat) | 35 | 목록 확인 | - | `3592659bb64f` |
| [tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat](../tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat) | 32 | 목록 확인 | - | `cc44ceb0ae2a` |
| [tools/TEST_MINK_WRIST_FRAME.bat](../tools/TEST_MINK_WRIST_FRAME.bat) | 34 | 목록 확인 | - | `414187888f10` |
| [tools/VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1](../tools/VERIFY_DESKTOP_SOURCE_CHECKOUT.ps1) | 60 | 목록 확인 | - | `bb978c800f09` |
| [tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat](../tools/VERIFY_HEAD_CAMERA_FOUNDATION.bat) | 27 | 목록 확인 | - | `eae096375075` |
| [tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat](../tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat) | 24 | 목록 확인 | - | `bbccd6e78e11` |
| [tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LATEST_CAPTURE_MUJOCO.bat) | 29 | 목록 확인 | - | `863b6b3bab9c` |
| [tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat](../tools/VIEW_G1_GATE7_LIMITED_CAPTURE_MUJOCO.bat) | 35 | 목록 확인 | - | `6a5931f23923` |
| [tools/VIEW_G1_LIVE_MUJOCO.bat](../tools/VIEW_G1_LIVE_MUJOCO.bat) | 45 | 목록 확인 | - | `212ae0343251` |
| [tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat](../tools/VIEW_G1_SAVED_LOWSTATE_MUJOCO.bat) | 35 | 목록 확인 | - | `2169a22c9d3f` |
| [tools/VIEW_G1_STARTUP_RECOVERY.bat](../tools/VIEW_G1_STARTUP_RECOVERY.bat) | 28 | 목록 확인 | - | `401c61f102ba` |
| [tools/audit_ik_licenses.py](../tools/audit_ik_licenses.py) | 82 | 목록 확인 | collect, main | `deb296665481` |
| [tools/bimanual_preflight.py](../tools/bimanual_preflight.py) | 205 | 목록 확인 | sha256, require, check_runtime_scene, check_source_installer, check_tool_contracts (+5) | `2af48db04afa` |
| [tools/evaluate_g1_velocity_direction_mujoco.py](../tools/evaluate_g1_velocity_direction_mujoco.py) | 173 | 목록 확인 | sha256, gravity_orientation, yaw_from_quaternion, wrapped, step_policy (+2) | `72b792d82dcc` |
| [tools/g1_camera_ssh.py](../tools/g1_camera_ssh.py) | 115 | 목록 확인 | read_exact, read_packet, check_environment, run | `46724a85e7aa` |
| [tools/g1_lowstate_view.py](../tools/g1_lowstate_view.py) | 103 | 목록 확인 | validate, run | `4a4e83208060` |
| [tools/g1_observation_tap.py](../tools/g1_observation_tap.py) | 85 | 목록 확인 | next_deadline, ObservationTap | `2f68783b528c` |
| [tools/g1_portable_environment.py](../tools/g1_portable_environment.py) | 145 | 목록 확인 | select_robot_host, prepare_camera_sources, configure_mirrored_network, wsl_prefix, wsl_path (+3) | `12c4324479b4` |
| [tools/g1_process_lifetime.py](../tools/g1_process_lifetime.py) | 57 | 목록 확인 | bind_session_lifetime | `73562a1df329` |
| [tools/g1_quiet_observation.py](../tools/g1_quiet_observation.py) | 91 | 목록 확인 | receive, run_workers | `96069601f1e4` |
| [tools/g1_source_archive_check.py](../tools/g1_source_archive_check.py) | 35 | 목록 확인 | verify | `feb0f37a71c3` |
| [tools/g1_ssh_login.py](../tools/g1_ssh_login.py) | 86 | 목록 확인 | key_path, identity_options, registration_command, probe, ensure_login (+1) | `c19bc5adaefe` |
| [tools/g1_teleop_dependencies.py](../tools/g1_teleop_dependencies.py) | 112 | 목록 확인 | requirements, probe, validate, ensure, main | `94234b3d339b` |
| [tools/replay_omni_velocity_mujoco.py](../tools/replay_omni_velocity_mujoco.py) | 144 | 목록 확인 | roll_pitch, load_commands, main | `7c991a1bedf2` |
| [tools/run_logged_standard_mink.py](../tools/run_logged_standard_mink.py) | 64 | 목록 확인 | main | `d8bd86884b7f` |
| [tools/test_convert_omni_csv_body_velocity.py](../tools/test_convert_omni_csv_body_velocity.py) | 38 | 목록 확인 | ConvertOmniCsvTests | `2992c1de8f2f` |
