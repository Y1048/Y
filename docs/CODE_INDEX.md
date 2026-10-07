# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **127개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

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
| [MuJoCo_G1_Controller/scripts/g1_arm_common.py](../MuJoCo_G1_Controller/scripts/g1_arm_common.py) | 377 | 입출력 확인 | _load_hardware_initial_right_arm_degrees, find_body, make_demo_xml, joint_qpos_addr, set_joint (+5) | `2ab681447148` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_goal_preview.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_goal_preview.py) | 357 | 목록 확인 | _child_math_environment, _native_objects, _snapshot_objects, _contract_digest, _model_digest (+7) | `3f8d61223d90` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_legacy_input.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_legacy_input.py) | 95 | 목록 확인 | PairedHandFilter, relative_target, relative_targets | `5276d5d03843` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py) | 99 | 목록 확인 | onboard_compatible_joint_ranges | `b44971f061e4` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_measured_start.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_measured_start.py) | 222 | 목록 확인 | validate_snapshot, initialize_inactive_model, MeasuredStartGate | `9da5f659df1e` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py) | 344 | 목록 확인 | ElbowClearanceTask, ShoulderComfortTask, ArmMotionPolicy | `1b39ac317c0d` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_profile.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_profile.py) | 119 | 목록 확인 | TrackingProfile, ReturnProfile | `7ade2dd3f5ae` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_return.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_return.py) | 293 | 목록 확인 | BimanualReturnMotion | `e20917d6e189` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py) | 144 | 입출력 확인 | startup_stage, require_validated_engine, load_engine, runtime_metadata, main | `34e6bfaba572` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_safety.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_safety.py) | 262 | 목록 확인 | BimanualSafetyEnvelope | `0e5ae5a94686` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py) | 636 | 목록 확인 | _recorded_motion_limits, _current_motion_limits, _open_text, _percentiles, _current_source_hashes (+7) | `f2256d7a613b` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py) | 372 | 입출력 확인 | BimanualSimulation, targets_from_json, main | `1b2cea19a9c2` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_target.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_target.py) | 44 | 목록 확인 | copy_world_hands, world_target, world_targets | `3a7a438354ab` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py) | 593 | 입출력 확인 | decode, UnityCycle, main | `31886541fbd7` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 목록 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `63e4696e742a` |
| [MuJoCo_G1_Controller/scripts/g1_mink_shared.py](../MuJoCo_G1_Controller/scripts/g1_mink_shared.py) | 396 | 입출력 확인 | _find_body, _prepare_mink_xml, _joint_id, _apply_operational_joint_limits, _body_distance (+13) | `168b84f4cda4` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 124 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `63245c475273` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `a0f98164bca0` |
| [MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py](../MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py) | 502 | 목록 확인 | AccelerationBound, ElbowClearanceTask, ShoulderComfortTask, UpstreamMinkTracking | `5ca03dc2c9a2` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 269 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `3e45baa3009a` |
| [START_G1_VR_TELEOP.bat](../START_G1_VR_TELEOP.bat) | 3 | 입출력 확인 | - | `2712c52593af` |
| [Unity_G1_VR/Assets/Editor/G1GoalPreviewValidation.cs](../Unity_G1_VR/Assets/Editor/G1GoalPreviewValidation.cs) | 115 | 목록 확인 | - | `16fecacb7a99` |
| [Unity_G1_VR/Assets/Editor/G1MeasuredDisplayValidation.cs](../Unity_G1_VR/Assets/Editor/G1MeasuredDisplayValidation.cs) | 276 | 목록 확인 | - | `94a7be1b16b6` |
| [Unity_G1_VR/Assets/Editor/G1MeasuredStartValidation.cs](../Unity_G1_VR/Assets/Editor/G1MeasuredStartValidation.cs) | 149 | 목록 확인 | - | `0fa46a167a6b` |
| [Unity_G1_VR/Assets/Editor/G1TeleopAutoPlay.cs](../Unity_G1_VR/Assets/Editor/G1TeleopAutoPlay.cs) | 78 | 목록 확인 | - | `ddff9b9c8400` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 615 | 목록 확인 | - | `c69b4fbf9f33` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 273 | 목록 확인 | - | `c03de8ba314d` |
| [Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs](../Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs) | 222 | 목록 확인 | - | `fd7a7ec659d2` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualCommandFrame.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualCommandFrame.cs) | 116 | 목록 확인 | - | `44462eadf7ce` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs) | 40 | 목록 확인 | - | `df0560f6d8dd` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs) | 781 | 입출력 확인 | - | `7d40ca14bafc` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 927 | 목록 확인 | - | `df348c799da6` |
| [Unity_G1_VR/Assets/G1Teleop/G1GoalPreviewState.cs](../Unity_G1_VR/Assets/G1Teleop/G1GoalPreviewState.cs) | 75 | 목록 확인 | - | `00b470080e00` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 777 | 입출력 확인 | - | `25f2e9c39596` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 340 | 입출력 확인 | - | `c851c245bdc6` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs](../Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs) | 132 | 목록 확인 | - | `14438d125a00` |
| [Unity_G1_VR/Assets/G1Teleop/G1MeasuredStartState.cs](../Unity_G1_VR/Assets/G1Teleop/G1MeasuredStartState.cs) | 62 | 목록 확인 | - | `5a582929df1c` |
| [Unity_G1_VR/Assets/G1Teleop/G1MeasuredTrackingDiagnostics.cs](../Unity_G1_VR/Assets/G1Teleop/G1MeasuredTrackingDiagnostics.cs) | 129 | 목록 확인 | - | `65966ad18b27` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 393 | 목록 확인 | - | `cbc4394f1b39` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs) | 314 | 목록 확인 | - | `3d34ed8b7b23` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs) | 49 | 목록 확인 | - | `b99755ed996b` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 798 | 입출력 확인 | - | `de657432b645` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 950 | 목록 확인 | - | `d0f4a2923abe` |
| [backend/tests/bimanual_replay_profiles.py](../backend/tests/bimanual_replay_profiles.py) | 74 | 목록 확인 | _historical_prepare, historical_recording_profile | `262700d6771d` |
| [backend/tests/fixtures/bimanual_return_near_hands_20260918.json](../backend/tests/fixtures/bimanual_return_near_hands_20260918.json) | 636 | 목록 확인 | - | `e6f50f455377` |
| [backend/tests/fixtures/bimanual_return_starts_20260918.json](../backend/tests/fixtures/bimanual_return_starts_20260918.json) | 127 | 목록 확인 | - | `0e42927f9660` |
| [backend/tests/fixtures/g1_measured_start_20261007.json](../backend/tests/fixtures/g1_measured_start_20261007.json) | 67 | 목록 확인 | - | `aab687ef2bb0` |
| [backend/tests/fixtures/g1_onboard_arm_joint_ranges_20261007.json](../backend/tests/fixtures/g1_onboard_arm_joint_ranges_20261007.json) | 86 | 목록 확인 | - | `273bb908d0f0` |
| [backend/tests/test_bimanual_boundaries.py](../backend/tests/test_bimanual_boundaries.py) | 210 | 목록 확인 | OutputContinuityTests, ProtocolBoundaryTests | `753c16e7191c` |
| [backend/tests/test_bimanual_goal_preview.py](../backend/tests/test_bimanual_goal_preview.py) | 330 | 목록 확인 | encode, manager, result, GoalPreviewTests | `f61a84b579ae` |
| [backend/tests/test_bimanual_marker_feedback.py](../backend/tests/test_bimanual_marker_feedback.py) | 139 | 목록 확인 | MarkerFeedbackTests | `1421df605955` |
| [backend/tests/test_bimanual_measured_start.py](../backend/tests/test_bimanual_measured_start.py) | 271 | 목록 확인 | model_pose, snapshot, packet, MeasuredStartTests | `2fe29ef8e1e1` |
| [backend/tests/test_bimanual_motion_quality.py](../backend/tests/test_bimanual_motion_quality.py) | 291 | 목록 확인 | quality_case, replay_recorded_motion, MotionQualityTests, PoseFilterTests | `668901a86653` |
| [backend/tests/test_bimanual_near_hands_sweep.py](../backend/tests/test_bimanual_near_hands_sweep.py) | 269 | 목록 확인 | TriggerDecisionReached, fixture_q14, full_q, find_threshold_fraction, find_safe_lower_fraction (+4) | `09de8aa41d57` |
| [backend/tests/test_bimanual_onboard_joint_ranges.py](../backend/tests/test_bimanual_onboard_joint_ranges.py) | 154 | 목록 확인 | OnboardJointRangeTests | `1a91443f8e6f` |
| [backend/tests/test_bimanual_profile.py](../backend/tests/test_bimanual_profile.py) | 77 | 목록 확인 | BimanualProfileTests | `ea27688c2fd4` |
| [backend/tests/test_bimanual_quest_reengage.py](../backend/tests/test_bimanual_quest_reengage.py) | 149 | 목록 확인 | rows, QuestReengageReplayTests | `c4d0a0bb1d86` |
| [backend/tests/test_bimanual_recorded_session.py](../backend/tests/test_bimanual_recorded_session.py) | 182 | 목록 확인 | load_fixture, RecordedStagedSessionTests | `655124c56be6` |
| [backend/tests/test_bimanual_return.py](../backend/tests/test_bimanual_return.py) | 560 | 목록 확인 | assert_output, recorded_return, StagedReturnTests | `6bbb0f8380d0` |
| [backend/tests/test_bimanual_runtime.py](../backend/tests/test_bimanual_runtime.py) | 167 | 목록 확인 | fake_engine, RuntimeTests | `dceaf0136b5f` |
| [backend/tests/test_bimanual_safety_boundary.py](../backend/tests/test_bimanual_safety_boundary.py) | 129 | 목록 확인 | BimanualSafetyBoundaryTests | `b7d76073b4f9` |
| [backend/tests/test_bimanual_session_report.py](../backend/tests/test_bimanual_session_report.py) | 401 | 목록 확인 | SessionReportTests | `83f0a26e2e28` |
| [backend/tests/test_bimanual_sim.py](../backend/tests/test_bimanual_sim.py) | 298 | 목록 확인 | BimanualTests | `d15f72875bb4` |
| [backend/tests/test_bimanual_split_tracking.py](../backend/tests/test_bimanual_split_tracking.py) | 57 | 목록 확인 | SplitTrackingTests | `6176c51362c0` |
| [backend/tests/test_bimanual_unity_sim.py](../backend/tests/test_bimanual_unity_sim.py) | 457 | 목록 확인 | packet, CycleTests | `cc1d20f153f3` |
| [backend/tests/test_g1_archive_offline_validate.py](../backend/tests/test_g1_archive_offline_validate.py) | 107 | 목록 확인 | ArchiveOfflineValidatorTests | `605586c5102c` |
| [backend/tests/test_g1_camera_follow_launch.py](../backend/tests/test_g1_camera_follow_launch.py) | 123 | 목록 확인 | FollowTests | `24067d746285` |
| [backend/tests/test_g1_camera_ssh.py](../backend/tests/test_g1_camera_ssh.py) | 33 | 목록 확인 | CameraTransportTests | `3ad81aa6e714` |
| [backend/tests/test_g1_ethernet_adapter_selector.py](../backend/tests/test_g1_ethernet_adapter_selector.py) | 87 | 목록 확인 | EthernetAdapterSelectorTests | `1c37e350ee86` |
| [backend/tests/test_g1_ethernet_auto_repair.py](../backend/tests/test_g1_ethernet_auto_repair.py) | 76 | 목록 확인 | G1EthernetAutoRepairTests | `030f7557424e` |
| [backend/tests/test_g1_groot_remote_launch.py](../backend/tests/test_g1_groot_remote_launch.py) | 180 | 목록 확인 | CommandContractTests, SpawnAndShutdownTests | `711692a8f8c8` |
| [backend/tests/test_g1_input_console.py](../backend/tests/test_g1_input_console.py) | 86 | 목록 확인 | arm_row, ConsoleTests | `9d264ab75632` |
| [backend/tests/test_g1_lowstate_view.py](../backend/tests/test_g1_lowstate_view.py) | 28 | 목록 확인 | LowStateTests | `51a289d5a2b5` |
| [backend/tests/test_g1_measured_display_contract.py](../backend/tests/test_g1_measured_display_contract.py) | 71 | 목록 확인 | MeasuredDisplayContractTests | `ca06509a64b0` |
| [backend/tests/test_g1_observation_audit.py](../backend/tests/test_g1_observation_audit.py) | 330 | 목록 확인 | packet, source_packet, AuditTests | `6037c1f78ca9` |
| [backend/tests/test_g1_observation_pipeline.py](../backend/tests/test_g1_observation_pipeline.py) | 420 | 목록 확인 | ObservationPipelineTests, ObservationLauncherTests | `4f2ab34ff14c` |
| [backend/tests/test_g1_observation_tap.py](../backend/tests/test_g1_observation_tap.py) | 197 | 목록 확인 | ObservationTapTests, ProducerPreservationTests | `8996afa2af65` |
| [backend/tests/test_g1_omni_transport_recovery.py](../backend/tests/test_g1_omni_transport_recovery.py) | 152 | 목록 확인 | LocalOmniServer, OmniTransportRecoveryTests | `dcc10160c2aa` |
| [backend/tests/test_g1_onboard_omni_optional.py](../backend/tests/test_g1_onboard_omni_optional.py) | 297 | 목록 확인 | load_controller, packet, encoded, simulated_run, OptionalOmniTests | `be29734d6c59` |
| [backend/tests/test_g1_portable_environment.py](../backend/tests/test_g1_portable_environment.py) | 89 | 목록 확인 | PortableTests | `003768f06a79` |
| [backend/tests/test_g1_process_lifetime.py](../backend/tests/test_g1_process_lifetime.py) | 62 | 목록 확인 | LifetimeTests | `ebcce528a3f2` |
| [backend/tests/test_g1_quiet_observation.py](../backend/tests/test_g1_quiet_observation.py) | 128 | 목록 확인 | QuietTests | `5676087f3d07` |
| [backend/tests/test_g1_ssh_login.py](../backend/tests/test_g1_ssh_login.py) | 76 | 목록 확인 | LoginTests | `fa01204ce62a` |
| [backend/tests/test_g1_teleop_dependencies.py](../backend/tests/test_g1_teleop_dependencies.py) | 52 | 목록 확인 | DependencyTests | `6ef2692a5559` |
| [backend/tests/test_g1_vr_teleop_launch.py](../backend/tests/test_g1_vr_teleop_launch.py) | 519 | 목록 확인 | worker_row, WorkerRecognitionTests, UnityLaunchTests, OrchestrationTests, PreflightTests | `f9ee437964ba` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `7b14e62f9a94` |
| [backend/tests/test_omni_world_ik.py](../backend/tests/test_omni_world_ik.py) | 129 | 목록 확인 | packet, OmniWorldTests | `15c6549e4a3a` |
| [backend/tests/upstream_mink_replay.py](../backend/tests/upstream_mink_replay.py) | 71 | 목록 확인 | build, main | `aa11ee82166f` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 124 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `061cca06ef2e` |
| [hardware/g1_arm_bridge/g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/g1_omni_velocity_gateway.py) | 912 | 입출력 확인 | clamp, deadzone, wrapped_delta_degrees, omni_to_body_velocity, OmniVelocityConfig (+12) | `8d68a5019966` |
| [hardware/g1_arm_bridge/g1_velocity_discovery.py](../hardware/g1_arm_bridge/g1_velocity_discovery.py) | 43 | 목록 확인 | parse_discovery, make_listener | `a41ab9086893` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 98 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `9580b8339a73` |
| [hardware/g1_arm_bridge/test_g1_omni_body_mapping.py](../hardware/g1_arm_bridge/test_g1_omni_body_mapping.py) | 89 | 목록 확인 | raw_body_vector, OmniBodyMappingTests | `39ec556d8759` |
| [hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py](../hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py) | 619 | 목록 확인 | CaptureTap, SyntheticTimeout, BurstyConnection, ScriptedConnection, ClockedOmniObservationTests | `7c9335d0e2fd` |
| [hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py](../hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py) | 123 | 목록 확인 | omni_handler, serve, discovery_sender, main | `9d8bace5948a` |
| [hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py) | 142 | 목록 확인 | OmniVelocityGatewayTests | `60e723a5a873` |
| [hardware/g1_arm_bridge/test_g1_velocity_discovery.py](../hardware/g1_arm_bridge/test_g1_velocity_discovery.py) | 45 | 목록 확인 | DiscoveryContractTests | `a9508519e6a7` |
| [hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py) | 75 | 목록 확인 | RuckigJointMotionLimiterTests | `9c8b5a2b35e6` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 3 | 목록 확인 | - | `9b124e557f03` |
| [tools/BUILD_EMBEDDED_RUNTIME.py](../tools/BUILD_EMBEDDED_RUNTIME.py) | 183 | 목록 확인 | sha256_file, requirement_pins, require_builder_python, remove_generated_launchers, write_manifest (+3) | `620491d24589` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 3 | 목록 확인 | - | `b05c2e1d86fb` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `f85bd33841a1` |
| [tools/G1_ARCHIVE_OFFLINE_VALIDATE.py](../tools/G1_ARCHIVE_OFFLINE_VALIDATE.py) | 1034 | 목록 확인 | percentile, unique_entry, open_text, sha256_entry, verify_manifest (+19) | `782676dfcaa5` |
| [tools/G1_CAMERA_FOLLOW_LAUNCH.py](../tools/G1_CAMERA_FOLLOW_LAUNCH.py) | 192 | 목록 확인 | direct_to_observation, ssh_command, main | `e089fa33c9fa` |
| [tools/G1_CAMERA_LAUNCH.py](../tools/G1_CAMERA_LAUNCH.py) | 28 | 입출력 확인 | main | `d978cba03dfe` |
| [tools/G1_ETHERNET_ADAPTER.ps1](../tools/G1_ETHERNET_ADAPTER.ps1) | 82 | 목록 확인 | - | `b9b7fa41d384` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `8405c5e3187b` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 155 | 목록 확인 | - | `ee13ad3e53b8` |
| [tools/G1_GROOT_REMOTE_LAUNCH.py](../tools/G1_GROOT_REMOTE_LAUNCH.py) | 492 | 입출력 확인 | actuator_argv, _ssh_base, _foreground_remote_command, ssh_command, inspect_remote (+11) | `353741422535` |
| [tools/G1_INPUT_OBSERVATION_LAUNCH.py](../tools/G1_INPUT_OBSERVATION_LAUNCH.py) | 128 | 입출력 확인 | worker_command, engine_environment, preflight, main | `e7ec3b339b1f` |
| [tools/G1_INPUT_RECEIVE_AUDIT.py](../tools/G1_INPUT_RECEIVE_AUDIT.py) | 597 | 목록 확인 | _stdout_line, LatestOutput, _aged_payload, display_view, AsyncLog (+15) | `338dfea129c7` |
| [tools/G1_PORTABLE.py](../tools/G1_PORTABLE.py) | 285 | 목록 확인 | stamp, run_checked, engine_env, check_runtime, teleop (+9) | `2845dbbe5275` |
| [tools/G1_VR_TELEOP_LAUNCH.py](../tools/G1_VR_TELEOP_LAUNCH.py) | 483 | 입출력 확인 | windows_arguments, process_arguments, option, option_casefold, normalized_path (+16) | `31da29c1b9ab` |
| [tools/PRINT_G1_INPUTS_50HZ.py](../tools/PRINT_G1_INPUTS_50HZ.py) | 228 | 목록 확인 | finite, arm_value, omni_value, LogTail, newest (+1) | `ea02e5193e41` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 3 | 목록 확인 | - | `a481a444d468` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 13 | 목록 확인 | - | `9a61ea772cbc` |
| [tools/g1_camera_ssh.py](../tools/g1_camera_ssh.py) | 213 | 입출력 확인 | read_exact, read_packet, check_environment, run | `1d72018a53cd` |
| [tools/g1_embedded_runtime.py](../tools/g1_embedded_runtime.py) | 50 | 목록 확인 | is_embedded_interpreter, require_embedded_interpreter, child_environment, python_command | `aecfcf33d4aa` |
| [tools/g1_lowstate_view.py](../tools/g1_lowstate_view.py) | 103 | 목록 확인 | validate, run | `4909ca337119` |
| [tools/g1_observation_tap.py](../tools/g1_observation_tap.py) | 85 | 목록 확인 | next_deadline, ObservationTap | `2f68783b528c` |
| [tools/g1_portable_environment.py](../tools/g1_portable_environment.py) | 92 | 목록 확인 | dedicated_wired_adapter_needing_address, select_robot_host, check_python | `95da33f02b11` |
| [tools/g1_process_lifetime.py](../tools/g1_process_lifetime.py) | 57 | 목록 확인 | bind_session_lifetime | `73562a1df329` |
| [tools/g1_quiet_observation.py](../tools/g1_quiet_observation.py) | 155 | 목록 확인 | receive, _stop_groot_supervisor, run_workers | `7bd7e9274f1c` |
| [tools/g1_ssh_login.py](../tools/g1_ssh_login.py) | 155 | 목록 확인 | _ssh_healthy, _ssh_candidates, ssh_executable, ssh_keygen_executable, key_path (+5) | `88aa8413a241` |
| [tools/g1_teleop_dependencies.py](../tools/g1_teleop_dependencies.py) | 132 | 목록 확인 | runtime_manifest, sha256, requirements, probe, validate (+2) | `a0f0171925fe` |
| [tools/onboard/g1_omni_heading_controller.py](../tools/onboard/g1_omni_heading_controller.py) | 830 | 목록 확인 | AsyncJsonlLog, finite_number, clamp, angular_delta, RobotState (+10) | `d2e35cd28046` |
