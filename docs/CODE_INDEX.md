# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **107개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

## 포함 범위

루트 실행 파일과 다음 폴더의 코드/설정 파일:

- `backend/tests`
- `backend/tools`
- `hardware/g1_arm_bridge`
- `tools`
- `MuJoCo_G1_Controller/scripts`
- `Unity_G1_VR/Assets/G1Teleop`
- `Unity_G1_VR/Assets/Editor`
- `Unity_G1_VR/Assets/Scenes`

원본 `references`, 로그·캡처, 로봇 mesh/XML, Unity 씬/prefab/meta,
외부 SDK·Packages·Library·빌드 산출물은 이 코드 색인에서 제외한다.
제외 항목을 미사용 또는 검토 완료로 판정한 것은 아니다.

## 갱신

```powershell
runtime\python\python.exe -B backend/tools/build_code_index.py
runtime\python\python.exe -B backend/tools/build_code_index.py --check
```

## 파일 목록

| 파일 | 줄 수 | 상태 | Python 최상위 선언(최대 5개) | SHA256 앞 12자리 |
| --- | ---: | --- | --- | --- |
| [MuJoCo_G1_Controller/scripts/g1_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_arm_common.py) | 377 | 입출력 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `4e6b4e1f7753` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_legacy_input.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_legacy_input.py) | 95 | 목록 확인 | PairedHandFilter, relative_target, relative_targets | `90f7bd0d3ad0` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py) | 23 | 목록 확인 | - | `da6eb9f39482` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py) | 323 | 목록 확인 | ElbowClearanceTask, ShoulderComfortTask, ArmMotionPolicy | `021f5ef5408f` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_profile.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_profile.py) | 109 | 목록 확인 | TrackingProfile, ReturnProfile | `1540dad94d75` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_return.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_return.py) | 291 | 목록 확인 | BimanualReturnMotion | `bfc0e653c132` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py) | 133 | 입출력 확인 | startup_stage, require_validated_engine, load_engine, runtime_metadata, main | `6e3af3855616` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_safety.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_safety.py) | 232 | 목록 확인 | BimanualSafetyEnvelope | `3254375ffc00` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py) | 592 | 목록 확인 | _recorded_motion_limits, _current_motion_limits, _open_text, _percentiles, _current_source_hashes (+7) | `416ae9b06f99` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py) | 344 | 입출력 확인 | BimanualSimulation, targets_from_json, main | `7654e00242df` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_target.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_target.py) | 44 | 목록 확인 | copy_world_hands, world_target, world_targets | `e63b69232532` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py) | 515 | 입출력 확인 | decode, UnityCycle, main | `609af5f08d08` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 목록 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `63e4696e742a` |
| [MuJoCo_G1_Controller/scripts/g1_mink_shared.py](../MuJoCo_G1_Controller/scripts/g1_mink_shared.py) | 396 | 입출력 확인 | _find_body, _prepare_mink_xml, _joint_id, _apply_operational_joint_limits, _body_distance (+13) | `c6a535194ee3` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 124 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `63245c475273` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `a0f98164bca0` |
| [MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py](../MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py) | 502 | 목록 확인 | AccelerationBound, ElbowClearanceTask, ShoulderComfortTask, UpstreamMinkTracking | `5ca03dc2c9a2` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 269 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `3e45baa3009a` |
| [START_G1_VR_TELEOP.bat](../START_G1_VR_TELEOP.bat) | 3 | 입출력 확인 | - | `2712c52593af` |
| [Unity_G1_VR/Assets/Editor/G1TeleopAutoPlay.cs](../Unity_G1_VR/Assets/Editor/G1TeleopAutoPlay.cs) | 78 | 목록 확인 | - | `62759cf1f077` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 615 | 목록 확인 | - | `c69b4fbf9f33` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 273 | 목록 확인 | - | `c03de8ba314d` |
| [Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs](../Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs) | 222 | 목록 확인 | - | `fd7a7ec659d2` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs) | 40 | 목록 확인 | - | `df0560f6d8dd` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs) | 711 | 입출력 확인 | - | `6571df39858d` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 927 | 목록 확인 | - | `df348c799da6` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 777 | 입출력 확인 | - | `25f2e9c39596` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 340 | 입출력 확인 | - | `c851c245bdc6` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs](../Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs) | 100 | 목록 확인 | - | `d560f0a9416c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 393 | 목록 확인 | - | `cbc4394f1b39` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs) | 314 | 목록 확인 | - | `3d34ed8b7b23` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs) | 49 | 목록 확인 | - | `b99755ed996b` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 798 | 입출력 확인 | - | `de657432b645` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 894 | 목록 확인 | - | `daa53b3560b6` |
| [backend/tests/bimanual_replay_profiles.py](../backend/tests/bimanual_replay_profiles.py) | 53 | 목록 확인 | _historical_prepare, historical_recording_profile | `5c47bec8717e` |
| [backend/tests/fixtures/bimanual_return_near_hands_20260918.json](../backend/tests/fixtures/bimanual_return_near_hands_20260918.json) | 636 | 목록 확인 | - | `e6f50f455377` |
| [backend/tests/fixtures/bimanual_return_starts_20260918.json](../backend/tests/fixtures/bimanual_return_starts_20260918.json) | 127 | 목록 확인 | - | `0e42927f9660` |
| [backend/tests/test_bimanual_boundaries.py](../backend/tests/test_bimanual_boundaries.py) | 210 | 목록 확인 | OutputContinuityTests, ProtocolBoundaryTests | `7ec74c8d6626` |
| [backend/tests/test_bimanual_marker_feedback.py](../backend/tests/test_bimanual_marker_feedback.py) | 139 | 목록 확인 | MarkerFeedbackTests | `dbfd084d7593` |
| [backend/tests/test_bimanual_motion_quality.py](../backend/tests/test_bimanual_motion_quality.py) | 291 | 목록 확인 | quality_case, replay_recorded_motion, MotionQualityTests, PoseFilterTests | `3e9e60130f15` |
| [backend/tests/test_bimanual_near_hands_sweep.py](../backend/tests/test_bimanual_near_hands_sweep.py) | 269 | 목록 확인 | TriggerDecisionReached, fixture_q14, full_q, find_threshold_fraction, find_safe_lower_fraction (+4) | `a2b3093612ff` |
| [backend/tests/test_bimanual_profile.py](../backend/tests/test_bimanual_profile.py) | 60 | 목록 확인 | BimanualProfileTests | `5b00a9ca26ca` |
| [backend/tests/test_bimanual_quest_reengage.py](../backend/tests/test_bimanual_quest_reengage.py) | 149 | 목록 확인 | rows, QuestReengageReplayTests | `b9c810f2463c` |
| [backend/tests/test_bimanual_recorded_session.py](../backend/tests/test_bimanual_recorded_session.py) | 178 | 목록 확인 | load_fixture, RecordedStagedSessionTests | `b5171d78b2f4` |
| [backend/tests/test_bimanual_return.py](../backend/tests/test_bimanual_return.py) | 483 | 목록 확인 | assert_output, recorded_return, StagedReturnTests | `4195b0221e6c` |
| [backend/tests/test_bimanual_runtime.py](../backend/tests/test_bimanual_runtime.py) | 151 | 목록 확인 | fake_engine, RuntimeTests | `8c7bf70f9b99` |
| [backend/tests/test_bimanual_safety_boundary.py](../backend/tests/test_bimanual_safety_boundary.py) | 129 | 목록 확인 | BimanualSafetyBoundaryTests | `813e1e2f6a31` |
| [backend/tests/test_bimanual_session_report.py](../backend/tests/test_bimanual_session_report.py) | 399 | 목록 확인 | SessionReportTests | `ba5cfc1c7067` |
| [backend/tests/test_bimanual_sim.py](../backend/tests/test_bimanual_sim.py) | 264 | 목록 확인 | BimanualTests | `9dbb5af5bd31` |
| [backend/tests/test_bimanual_unity_sim.py](../backend/tests/test_bimanual_unity_sim.py) | 356 | 목록 확인 | packet, CycleTests | `46d71a90deb7` |
| [backend/tests/test_g1_archive_offline_validate.py](../backend/tests/test_g1_archive_offline_validate.py) | 107 | 목록 확인 | ArchiveOfflineValidatorTests | `a2aa97c846a8` |
| [backend/tests/test_g1_camera_follow_launch.py](../backend/tests/test_g1_camera_follow_launch.py) | 123 | 목록 확인 | FollowTests | `24067d746285` |
| [backend/tests/test_g1_camera_ssh.py](../backend/tests/test_g1_camera_ssh.py) | 33 | 목록 확인 | CameraTransportTests | `3ad81aa6e714` |
| [backend/tests/test_g1_ethernet_auto_repair.py](../backend/tests/test_g1_ethernet_auto_repair.py) | 71 | 목록 확인 | G1EthernetAutoRepairTests | `644b0be5b747` |
| [backend/tests/test_g1_groot_remote_launch.py](../backend/tests/test_g1_groot_remote_launch.py) | 180 | 목록 확인 | CommandContractTests, SpawnAndShutdownTests | `711692a8f8c8` |
| [backend/tests/test_g1_input_console.py](../backend/tests/test_g1_input_console.py) | 86 | 목록 확인 | arm_row, ConsoleTests | `9d264ab75632` |
| [backend/tests/test_g1_lowstate_view.py](../backend/tests/test_g1_lowstate_view.py) | 28 | 목록 확인 | LowStateTests | `51a289d5a2b5` |
| [backend/tests/test_g1_observation_audit.py](../backend/tests/test_g1_observation_audit.py) | 330 | 목록 확인 | packet, source_packet, AuditTests | `6037c1f78ca9` |
| [backend/tests/test_g1_observation_pipeline.py](../backend/tests/test_g1_observation_pipeline.py) | 404 | 목록 확인 | ObservationPipelineTests, ObservationLauncherTests | `31ef6425aff3` |
| [backend/tests/test_g1_observation_tap.py](../backend/tests/test_g1_observation_tap.py) | 197 | 목록 확인 | ObservationTapTests, ProducerPreservationTests | `8996afa2af65` |
| [backend/tests/test_g1_omni_transport_recovery.py](../backend/tests/test_g1_omni_transport_recovery.py) | 152 | 목록 확인 | LocalOmniServer, OmniTransportRecoveryTests | `dcc10160c2aa` |
| [backend/tests/test_g1_portable_environment.py](../backend/tests/test_g1_portable_environment.py) | 89 | 목록 확인 | PortableTests | `e632cb85a3d8` |
| [backend/tests/test_g1_process_lifetime.py](../backend/tests/test_g1_process_lifetime.py) | 62 | 목록 확인 | LifetimeTests | `ebcce528a3f2` |
| [backend/tests/test_g1_quiet_observation.py](../backend/tests/test_g1_quiet_observation.py) | 128 | 목록 확인 | QuietTests | `5676087f3d07` |
| [backend/tests/test_g1_ssh_login.py](../backend/tests/test_g1_ssh_login.py) | 76 | 목록 확인 | LoginTests | `fa01204ce62a` |
| [backend/tests/test_g1_teleop_dependencies.py](../backend/tests/test_g1_teleop_dependencies.py) | 52 | 목록 확인 | DependencyTests | `80440d67256b` |
| [backend/tests/test_g1_vr_teleop_launch.py](../backend/tests/test_g1_vr_teleop_launch.py) | 519 | 목록 확인 | worker_row, WorkerRecognitionTests, UnityLaunchTests, OrchestrationTests, PreflightTests | `f9ee437964ba` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `7b14e62f9a94` |
| [backend/tests/test_omni_world_ik.py](../backend/tests/test_omni_world_ik.py) | 129 | 목록 확인 | packet, OmniWorldTests | `15c6549e4a3a` |
| [backend/tests/upstream_mink_replay.py](../backend/tests/upstream_mink_replay.py) | 71 | 목록 확인 | build, main | `aa11ee82166f` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 124 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `0921fe12c97e` |
| [hardware/g1_arm_bridge/g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/g1_omni_velocity_gateway.py) | 912 | 입출력 확인 | clamp, deadzone, wrapped_delta_degrees, omni_to_body_velocity, OmniVelocityConfig (+12) | `8d68a5019966` |
| [hardware/g1_arm_bridge/g1_velocity_discovery.py](../hardware/g1_arm_bridge/g1_velocity_discovery.py) | 43 | 목록 확인 | parse_discovery, make_listener | `a41ab9086893` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 98 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `a781ff78fde8` |
| [hardware/g1_arm_bridge/test_g1_omni_body_mapping.py](../hardware/g1_arm_bridge/test_g1_omni_body_mapping.py) | 89 | 목록 확인 | raw_body_vector, OmniBodyMappingTests | `5c7510615552` |
| [hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py](../hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py) | 619 | 목록 확인 | CaptureTap, SyntheticTimeout, BurstyConnection, ScriptedConnection, ClockedOmniObservationTests | `7c9335d0e2fd` |
| [hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py](../hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py) | 123 | 목록 확인 | omni_handler, serve, discovery_sender, main | `9d8bace5948a` |
| [hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py) | 142 | 목록 확인 | OmniVelocityGatewayTests | `d79e18577bb2` |
| [hardware/g1_arm_bridge/test_g1_velocity_discovery.py](../hardware/g1_arm_bridge/test_g1_velocity_discovery.py) | 45 | 목록 확인 | DiscoveryContractTests | `a9508519e6a7` |
| [hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py) | 75 | 목록 확인 | RuckigJointMotionLimiterTests | `9c8b5a2b35e6` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 3 | 목록 확인 | - | `9b124e557f03` |
| [tools/BUILD_EMBEDDED_RUNTIME.py](../tools/BUILD_EMBEDDED_RUNTIME.py) | 183 | 목록 확인 | sha256_file, requirement_pins, require_builder_python, remove_generated_launchers, write_manifest (+3) | `6884d012936c` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 3 | 목록 확인 | - | `b05c2e1d86fb` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 35 | 목록 확인 | - | `ca205d269069` |
| [tools/G1_ARCHIVE_OFFLINE_VALIDATE.py](../tools/G1_ARCHIVE_OFFLINE_VALIDATE.py) | 1034 | 목록 확인 | percentile, unique_entry, open_text, sha256_entry, verify_manifest (+19) | `ff810da6c03d` |
| [tools/G1_CAMERA_FOLLOW_LAUNCH.py](../tools/G1_CAMERA_FOLLOW_LAUNCH.py) | 192 | 목록 확인 | direct_to_observation, ssh_command, main | `e089fa33c9fa` |
| [tools/G1_CAMERA_LAUNCH.py](../tools/G1_CAMERA_LAUNCH.py) | 28 | 입출력 확인 | main | `d978cba03dfe` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `8405c5e3187b` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 155 | 목록 확인 | - | `ee13ad3e53b8` |
| [tools/G1_GROOT_REMOTE_LAUNCH.py](../tools/G1_GROOT_REMOTE_LAUNCH.py) | 492 | 입출력 확인 | actuator_argv, _ssh_base, _foreground_remote_command, ssh_command, inspect_remote (+11) | `353741422535` |
| [tools/G1_INPUT_OBSERVATION_LAUNCH.py](../tools/G1_INPUT_OBSERVATION_LAUNCH.py) | 128 | 입출력 확인 | worker_command, engine_environment, preflight, main | `e7ec3b339b1f` |
| [tools/G1_INPUT_RECEIVE_AUDIT.py](../tools/G1_INPUT_RECEIVE_AUDIT.py) | 597 | 목록 확인 | _stdout_line, LatestOutput, _aged_payload, display_view, AsyncLog (+15) | `338dfea129c7` |
| [tools/G1_PORTABLE.py](../tools/G1_PORTABLE.py) | 285 | 목록 확인 | stamp, run_checked, engine_env, check_runtime, teleop (+9) | `3ede00418caf` |
| [tools/G1_VR_TELEOP_LAUNCH.py](../tools/G1_VR_TELEOP_LAUNCH.py) | 483 | 입출력 확인 | windows_arguments, process_arguments, option, option_casefold, normalized_path (+16) | `31da29c1b9ab` |
| [tools/PRINT_G1_INPUTS_50HZ.py](../tools/PRINT_G1_INPUTS_50HZ.py) | 228 | 목록 확인 | finite, arm_value, omni_value, LogTail, newest (+1) | `ea02e5193e41` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 3 | 목록 확인 | - | `a481a444d468` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 23 | 목록 확인 | - | `f83e2c335106` |
| [tools/g1_camera_ssh.py](../tools/g1_camera_ssh.py) | 213 | 입출력 확인 | read_exact, read_packet, check_environment, run | `1d72018a53cd` |
| [tools/g1_embedded_runtime.py](../tools/g1_embedded_runtime.py) | 50 | 목록 확인 | is_embedded_interpreter, require_embedded_interpreter, child_environment, python_command | `54f56431ca84` |
| [tools/g1_lowstate_view.py](../tools/g1_lowstate_view.py) | 103 | 목록 확인 | validate, run | `4909ca337119` |
| [tools/g1_observation_tap.py](../tools/g1_observation_tap.py) | 85 | 목록 확인 | next_deadline, ObservationTap | `2f68783b528c` |
| [tools/g1_portable_environment.py](../tools/g1_portable_environment.py) | 78 | 목록 확인 | dedicated_wired_adapter_needing_address, select_robot_host, check_python | `08b15fedd0cb` |
| [tools/g1_process_lifetime.py](../tools/g1_process_lifetime.py) | 57 | 목록 확인 | bind_session_lifetime | `73562a1df329` |
| [tools/g1_quiet_observation.py](../tools/g1_quiet_observation.py) | 155 | 목록 확인 | receive, _stop_groot_supervisor, run_workers | `7bd7e9274f1c` |
| [tools/g1_ssh_login.py](../tools/g1_ssh_login.py) | 155 | 목록 확인 | _ssh_healthy, _ssh_candidates, ssh_executable, ssh_keygen_executable, key_path (+5) | `88aa8413a241` |
| [tools/g1_teleop_dependencies.py](../tools/g1_teleop_dependencies.py) | 132 | 목록 확인 | runtime_manifest, sha256, requirements, probe, validate (+2) | `f53e423d1a1b` |
