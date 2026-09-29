# 코드 파일 색인

[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)

이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.
**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**

- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.
- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.
- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.
- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.

대상 파일: **101개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.

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
| [MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_limits.py) | 23 | 목록 확인 | - | `eebab49dff59` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_motion_policy.py) | 305 | 목록 확인 | ElbowClearanceTask, ShoulderComfortTask, ArmMotionPolicy | `99617a48acff` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_return.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_return.py) | 289 | 목록 확인 | BimanualReturnMotion | `283569341970` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py) | 128 | 입출력 확인 | startup_stage, require_validated_engine, load_engine, runtime_metadata, main | `3d61a42b0b1e` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_session_report.py) | 589 | 목록 확인 | _recorded_motion_limits, _current_motion_limits, _open_text, _percentiles, _current_source_hashes (+7) | `adf74f24e543` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_sim.py) | 450 | 입출력 확인 | BimanualSimulation, targets_from_json, main | `a4e0a88d18dd` |
| [MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py](../MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py) | 526 | 입출력 확인 | decode, PairedHandFilter, UnityCycle, main | `6fc85712de31` |
| [MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py](../MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py) | 426 | 목록 확인 | PositionProgressConstraint, FeasiblePlan, FeasibleTargetPlanner | `63e4696e742a` |
| [MuJoCo_G1_Controller/scripts/g1_mink_shared.py](../MuJoCo_G1_Controller/scripts/g1_mink_shared.py) | 396 | 입출력 확인 | _find_body, _prepare_mink_xml, _joint_id, _apply_operational_joint_limits, _body_distance (+13) | `168b84f4cda4` |
| [MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py](../MuJoCo_G1_Controller/scripts/g1_mink_trajectory.py) | 124 | 목록 확인 | TrajectoryStep, StatefulMinkTrajectory | `63245c475273` |
| [MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py](../MuJoCo_G1_Controller/scripts/g1_standard_mink_planner.py) | 81 | 목록 확인 | StandardMinkPlanner | `a0f98164bca0` |
| [MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py](../MuJoCo_G1_Controller/scripts/g1_upstream_mink_tracking.py) | 502 | 목록 확인 | AccelerationBound, ElbowClearanceTask, ShoulderComfortTask, UpstreamMinkTracking | `5ca03dc2c9a2` |
| [MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py](../MuJoCo_G1_Controller/scripts/g1_virtual_center_tasks.py) | 269 | 목록 확인 | virtual_center_damping_costs, virtual_center_posture_costs, virtual_center_velocity_limits, hierarchical_position_damping_costs, hierarchical_orientation_damping_costs (+3) | `3e45baa3009a` |
| [Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs](../Unity_G1_VR/Assets/Editor/G1TeleopBatchValidator.cs) | 691 | 목록 확인 | - | `83b5aaa2b861` |
| [Unity_G1_VR/Assets/Editor/G1VRBuild.cs](../Unity_G1_VR/Assets/Editor/G1VRBuild.cs) | 67 | 목록 확인 | - | `3f198318b963` |
| [Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs](../Unity_G1_VR/Assets/G1Teleop/G1AmbientOperatorEnvironment.cs) | 222 | 목록 확인 | - | `fd7a7ec659d2` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualFeedbackGate.cs) | 40 | 목록 확인 | - | `df0560f6d8dd` |
| [Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs) | 687 | 입출력 확인 | - | `c8bd9bf6fcf3` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs) | 970 | 목록 확인 | - | `340ddef9ffe8` |
| [Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs](../Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs) | 539 | 목록 확인 | - | `2de01db7eff5` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadCameraPiP.cs) | 694 | 입출력 확인 | - | `7df0063d6c77` |
| [Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs](../Unity_G1_VR/Assets/G1Teleop/G1HeadLockedCamera.cs) | 343 | 입출력 확인 | - | `64479cd12b7a` |
| [Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs](../Unity_G1_VR/Assets/G1Teleop/G1JointNode.cs) | 18 | 목록 확인 | - | `93bf9cf822c3` |
| [Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs](../Unity_G1_VR/Assets/G1Teleop/G1LowStateLegView.cs) | 100 | 목록 확인 | - | `d560f0a9416c` |
| [Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs](../Unity_G1_VR/Assets/G1Teleop/G1OfficialRig.cs) | 393 | 목록 확인 | - | `cbc4394f1b39` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs) | 95 | 목록 확인 | - | `d5f107baa82a` |
| [Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs](../Unity_G1_VR/Assets/G1Teleop/G1OmniHeadingState.cs) | 48 | 목록 확인 | - | `c369105085a4` |
| [Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs](../Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs) | 798 | 입출력 확인 | - | `de657432b645` |
| [Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs](../Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs) | 1122 | 목록 확인 | - | `3da7f0ae47e6` |
| [backend/tests/bimanual_replay_profiles.py](../backend/tests/bimanual_replay_profiles.py) | 49 | 목록 확인 | _historical_prepare, historical_recording_profile | `e15a2a5b7250` |
| [backend/tests/fixtures/bimanual_return_near_hands_20260918.json](../backend/tests/fixtures/bimanual_return_near_hands_20260918.json) | 636 | 목록 확인 | - | `e6f50f455377` |
| [backend/tests/fixtures/bimanual_return_starts_20260918.json](../backend/tests/fixtures/bimanual_return_starts_20260918.json) | 127 | 목록 확인 | - | `0e42927f9660` |
| [backend/tests/test_bimanual_boundaries.py](../backend/tests/test_bimanual_boundaries.py) | 210 | 목록 확인 | OutputContinuityTests, ProtocolBoundaryTests | `7ec74c8d6626` |
| [backend/tests/test_bimanual_marker_feedback.py](../backend/tests/test_bimanual_marker_feedback.py) | 132 | 목록 확인 | MarkerFeedbackTests | `47ad0def0fec` |
| [backend/tests/test_bimanual_motion_quality.py](../backend/tests/test_bimanual_motion_quality.py) | 288 | 목록 확인 | quality_case, replay_recorded_motion, MotionQualityTests, PoseFilterTests | `661fb469f8a7` |
| [backend/tests/test_bimanual_near_hands_sweep.py](../backend/tests/test_bimanual_near_hands_sweep.py) | 269 | 목록 확인 | TriggerDecisionReached, fixture_q14, full_q, find_threshold_fraction, find_safe_lower_fraction (+4) | `a2b3093612ff` |
| [backend/tests/test_bimanual_quest_reengage.py](../backend/tests/test_bimanual_quest_reengage.py) | 149 | 목록 확인 | rows, QuestReengageReplayTests | `b9c810f2463c` |
| [backend/tests/test_bimanual_recorded_session.py](../backend/tests/test_bimanual_recorded_session.py) | 178 | 목록 확인 | load_fixture, RecordedStagedSessionTests | `b5171d78b2f4` |
| [backend/tests/test_bimanual_return.py](../backend/tests/test_bimanual_return.py) | 483 | 목록 확인 | assert_output, recorded_return, StagedReturnTests | `4195b0221e6c` |
| [backend/tests/test_bimanual_runtime.py](../backend/tests/test_bimanual_runtime.py) | 165 | 목록 확인 | fake_engine, RuntimeTests | `e7c5b079f784` |
| [backend/tests/test_bimanual_session_report.py](../backend/tests/test_bimanual_session_report.py) | 415 | 목록 확인 | SessionReportTests | `3a2765a2510c` |
| [backend/tests/test_bimanual_sim.py](../backend/tests/test_bimanual_sim.py) | 264 | 목록 확인 | BimanualTests | `2caea488127a` |
| [backend/tests/test_bimanual_unity_sim.py](../backend/tests/test_bimanual_unity_sim.py) | 271 | 목록 확인 | packet, CycleTests | `85eb715512ee` |
| [backend/tests/test_g1_camera_ssh.py](../backend/tests/test_g1_camera_ssh.py) | 75 | 목록 확인 | CameraTests | `040b3f661067` |
| [backend/tests/test_g1_input_console.py](../backend/tests/test_g1_input_console.py) | 86 | 목록 확인 | arm_row, ConsoleTests | `9d264ab75632` |
| [backend/tests/test_g1_lowstate_view.py](../backend/tests/test_g1_lowstate_view.py) | 28 | 목록 확인 | LowStateTests | `51a289d5a2b5` |
| [backend/tests/test_g1_observation_audit.py](../backend/tests/test_g1_observation_audit.py) | 330 | 목록 확인 | packet, source_packet, AuditTests | `6037c1f78ca9` |
| [backend/tests/test_g1_observation_pipeline.py](../backend/tests/test_g1_observation_pipeline.py) | 402 | 목록 확인 | ObservationPipelineTests, ObservationLauncherTests | `ce23230cdcd7` |
| [backend/tests/test_g1_observation_tap.py](../backend/tests/test_g1_observation_tap.py) | 223 | 목록 확인 | ObservationTapTests, ProducerPreservationTests | `8ca75624d2cb` |
| [backend/tests/test_g1_omni_transport_recovery.py](../backend/tests/test_g1_omni_transport_recovery.py) | 152 | 목록 확인 | LocalOmniServer, OmniTransportRecoveryTests | `dcc10160c2aa` |
| [backend/tests/test_g1_portable_environment.py](../backend/tests/test_g1_portable_environment.py) | 80 | 목록 확인 | PortableTests | `ecce2908e58b` |
| [backend/tests/test_g1_process_lifetime.py](../backend/tests/test_g1_process_lifetime.py) | 62 | 목록 확인 | LifetimeTests | `ebcce528a3f2` |
| [backend/tests/test_g1_quiet_observation.py](../backend/tests/test_g1_quiet_observation.py) | 52 | 목록 확인 | QuietTests | `cc779d373adf` |
| [backend/tests/test_g1_ssh_login.py](../backend/tests/test_g1_ssh_login.py) | 56 | 목록 확인 | LoginTests | `1fca27bf0d14` |
| [backend/tests/test_g1_teleop_dependencies.py](../backend/tests/test_g1_teleop_dependencies.py) | 52 | 목록 확인 | DependencyTests | `266491b50a9d` |
| [backend/tests/test_g1_vr_teleop_launch.py](../backend/tests/test_g1_vr_teleop_launch.py) | 308 | 목록 확인 | worker_row, WorkerRecognitionTests, UnityLaunchTests, OrchestrationTests, PreflightTests | `b8fbc79084bd` |
| [backend/tests/test_mujoco_control_math.py](../backend/tests/test_mujoco_control_math.py) | 43 | 목록 확인 | MuJoCoControlMathTest | `7b14e62f9a94` |
| [backend/tests/test_omni_world_ik.py](../backend/tests/test_omni_world_ik.py) | 129 | 목록 확인 | packet, OmniWorldTests | `15c6549e4a3a` |
| [backend/tests/upstream_mink_replay.py](../backend/tests/upstream_mink_replay.py) | 71 | 목록 확인 | build, main | `aa11ee82166f` |
| [backend/tools/build_code_index.py](../backend/tools/build_code_index.py) | 123 | 목록 확인 | CollectFiles, GetPythonSymbols, BuildIndex, main | `d3b97269bfca` |
| [hardware/g1_arm_bridge/g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/g1_omni_velocity_gateway.py) | 648 | 입출력 확인 | clamp, deadzone, wrapped_delta_degrees, omni_to_body_velocity, OmniVelocityConfig (+10) | `aaa87a6c459c` |
| [hardware/g1_arm_bridge/g1_velocity_discovery.py](../hardware/g1_arm_bridge/g1_velocity_discovery.py) | 43 | 목록 확인 | parse_discovery, make_listener | `a41ab9086893` |
| [hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/ruckig_joint_motion_limiter.py) | 98 | 목록 확인 | _finite_vector, RuckigJointMotionLimiter | `9580b8339a73` |
| [hardware/g1_arm_bridge/test_g1_omni_body_mapping.py](../hardware/g1_arm_bridge/test_g1_omni_body_mapping.py) | 89 | 목록 확인 | raw_body_vector, OmniBodyMappingTests | `39ec556d8759` |
| [hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py](../hardware/g1_arm_bridge/test_g1_omni_clocked_observation.py) | 463 | 목록 확인 | CaptureTap, SyntheticTimeout, BurstyConnection, ScriptedConnection, ClockedOmniObservationTests | `ef60f5aa2045` |
| [hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py](../hardware/g1_arm_bridge/test_g1_omni_gateway_e2e.py) | 123 | 목록 확인 | omni_handler, serve, discovery_sender, main | `9d8bace5948a` |
| [hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py](../hardware/g1_arm_bridge/test_g1_omni_velocity_gateway.py) | 142 | 목록 확인 | OmniVelocityGatewayTests | `60e723a5a873` |
| [hardware/g1_arm_bridge/test_g1_velocity_discovery.py](../hardware/g1_arm_bridge/test_g1_velocity_discovery.py) | 45 | 목록 확인 | DiscoveryContractTests | `a9508519e6a7` |
| [hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py](../hardware/g1_arm_bridge/test_ruckig_joint_motion_limiter.py) | 75 | 목록 확인 | RuckigJointMotionLimiterTests | `9c8b5a2b35e6` |
| [tools/BUILD_AND_INSTALL_VR_APK.bat](../tools/BUILD_AND_INSTALL_VR_APK.bat) | 3 | 목록 확인 | - | `9b124e557f03` |
| [tools/BUILD_EMBEDDED_RUNTIME.py](../tools/BUILD_EMBEDDED_RUNTIME.py) | 183 | 목록 확인 | sha256_file, requirement_pins, require_builder_python, remove_generated_launchers, write_manifest (+3) | `620491d24589` |
| [tools/CONFIGURE_G1_ETHERNET.bat](../tools/CONFIGURE_G1_ETHERNET.bat) | 3 | 목록 확인 | - | `b05c2e1d86fb` |
| [tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1](../tools/CONFIGURE_G1_ETHERNET_ADMIN.ps1) | 25 | 목록 확인 | - | `f9342a380804` |
| [tools/G1_CAMERA_LAUNCH.py](../tools/G1_CAMERA_LAUNCH.py) | 28 | 입출력 확인 | main | `4dd859cd3bc0` |
| [tools/G1_ETHERNET_DNS.ps1](../tools/G1_ETHERNET_DNS.ps1) | 60 | 목록 확인 | - | `8405c5e3187b` |
| [tools/G1_ETHERNET_TRANSACTION.ps1](../tools/G1_ETHERNET_TRANSACTION.ps1) | 126 | 목록 확인 | - | `e49e43ff9063` |
| [tools/G1_INPUT_OBSERVATION_LAUNCH.py](../tools/G1_INPUT_OBSERVATION_LAUNCH.py) | 128 | 입출력 확인 | worker_command, engine_environment, preflight, main | `e767f04935e6` |
| [tools/G1_INPUT_RECEIVE_AUDIT.py](../tools/G1_INPUT_RECEIVE_AUDIT.py) | 597 | 목록 확인 | _stdout_line, LatestOutput, _aged_payload, display_view, AsyncLog (+15) | `338dfea129c7` |
| [tools/G1_PORTABLE.py](../tools/G1_PORTABLE.py) | 257 | 목록 확인 | stamp, run_checked, engine_env, check_runtime, teleop (+8) | `180d62975df9` |
| [tools/G1_VR_TELEOP_LAUNCH.py](../tools/G1_VR_TELEOP_LAUNCH.py) | 297 | 입출력 확인 | windows_arguments, process_arguments, option, option_casefold, normalized_path (+9) | `8b60769c8925` |
| [tools/PRINT_G1_INPUTS_50HZ.py](../tools/PRINT_G1_INPUTS_50HZ.py) | 228 | 목록 확인 | finite, arm_value, omni_value, LogTail, newest (+1) | `ea02e5193e41` |
| [tools/REPORT_LATEST_BIMANUAL_SESSION.bat](../tools/REPORT_LATEST_BIMANUAL_SESSION.bat) | 3 | 목록 확인 | - | `0c85f421d077` |
| [tools/RESOLVE_UNITY_EDITOR.bat](../tools/RESOLVE_UNITY_EDITOR.bat) | 3 | 목록 확인 | - | `d5b5cf6ab7a6` |
| [tools/RESTORE_G1_ETHERNET_DHCP.bat](../tools/RESTORE_G1_ETHERNET_DHCP.bat) | 3 | 목록 확인 | - | `a481a444d468` |
| [tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1](../tools/RESTORE_G1_ETHERNET_DHCP_ADMIN.ps1) | 23 | 목록 확인 | - | `f83e2c335106` |
| [tools/SETUP_G1_VR_TELEOP.bat](../tools/SETUP_G1_VR_TELEOP.bat) | 3 | 목록 확인 | - | `12924dd1aea8` |
| [tools/START_BIMANUAL_SIM.bat](../tools/START_BIMANUAL_SIM.bat) | 3 | 목록 확인 | - | `17163b6225ae` |
| [tools/START_BIMANUAL_UNITY_SIM.bat](../tools/START_BIMANUAL_UNITY_SIM.bat) | 3 | 목록 확인 | - | `e9cbfc40f97a` |
| [tools/START_G1_CAMERA_TO_UNITY.bat](../tools/START_G1_CAMERA_TO_UNITY.bat) | 3 | 목록 확인 | - | `61299b51e2e6` |
| [tools/START_G1_VR_TELEOP.bat](../tools/START_G1_VR_TELEOP.bat) | 3 | 입출력 확인 | - | `297389d91107` |
| [tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat](../tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat) | 3 | 목록 확인 | - | `3f010dd8e2d2` |
| [tools/g1_camera_ssh.py](../tools/g1_camera_ssh.py) | 115 | 입출력 확인 | read_exact, read_packet, check_environment, run | `9ac0e96bcf28` |
| [tools/g1_embedded_runtime.py](../tools/g1_embedded_runtime.py) | 50 | 목록 확인 | is_embedded_interpreter, require_embedded_interpreter, child_environment, python_command | `aecfcf33d4aa` |
| [tools/g1_lowstate_view.py](../tools/g1_lowstate_view.py) | 103 | 목록 확인 | validate, run | `4a4e83208060` |
| [tools/g1_observation_tap.py](../tools/g1_observation_tap.py) | 85 | 목록 확인 | next_deadline, ObservationTap | `2f68783b528c` |
| [tools/g1_portable_environment.py](../tools/g1_portable_environment.py) | 46 | 목록 확인 | select_robot_host, check_python | `f42974bdaabb` |
| [tools/g1_process_lifetime.py](../tools/g1_process_lifetime.py) | 57 | 목록 확인 | bind_session_lifetime | `73562a1df329` |
| [tools/g1_quiet_observation.py](../tools/g1_quiet_observation.py) | 92 | 목록 확인 | receive, run_workers | `44f6bd429db2` |
| [tools/g1_ssh_login.py](../tools/g1_ssh_login.py) | 86 | 목록 확인 | key_path, identity_options, registration_command, probe, ensure_login (+1) | `c19bc5adaefe` |
| [tools/g1_teleop_dependencies.py](../tools/g1_teleop_dependencies.py) | 132 | 목록 확인 | runtime_manifest, sha256, requirements, probe, validate (+2) | `a0f0171925fe` |
