"""Architectural guards; behavioral rig/FK checks live in the Unity edit-mode validator."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'Unity_G1_VR/Assets/G1Teleop'


class MeasuredDisplayContractTests(unittest.TestCase):
    def test_measured_display_is_not_gated_off_by_bilateral_mode(self):
        text = (CS / 'G1UnityRightArmPreview.cs').read_text(encoding='utf-8-sig')
        branch = text.split('private void UpdateOfficialRobotPose()', 1)[1].split('G1RobotStateUdpReceiver display_receiver', 1)[0]
        self.assertIn('measured_pose_applied = measured_view.ApplyMeasuredPose()', branch)
        self.assertIn('measured_view.LatestState != null', branch)
        self.assertNotIn('ApplyJointPosition(bimanual_simulation.LatestJointNames', branch)
        self.assertLess(branch.index('command_frame.Refresh('), branch.index('measured_pose_applied = measured_view.ApplyMeasuredPose()'))

    def test_control_world_frame_uses_command_snapshot(self):
        text = (CS / 'G1UnityRightArmPreview.cs').read_text(encoding='utf-8-sig')
        frame = text.split('public bool TryGetBimanualWorldFrame(', 1)[1].split('public float UnityBaseMirrorPositionError', 1)[0]
        self.assertIn('root_position = command_frame.RootPosition', frame)
        self.assertIn('shoulder_center = command_frame.ShoulderCenter', frame)
        self.assertIn('left_wrist_position = command_frame.LeftWrist.position', frame)
        self.assertIn('? command_frame.HeadMount', text)

    def test_command_fk_restores_rendered_pose(self):
        text = (CS / 'G1BimanualCommandFrame.cs').read_text(encoding='utf-8-sig')
        self.assertIn('finally', text)
        self.assertIn('nodes[i].transform.localRotation = savedRotations[i]', text)
        for forbidden in ('LowState', 'ChannelPublisher', 'UdpClient', 'solve_ik', 'Renderer'):
            self.assertNotIn(forbidden, text.split('public sealed class', 1)[1].replace('pre-LowState', 'startup'))

    def test_lowstate_application_reports_success_and_leaves_root_unchanged(self):
        text = (CS / 'G1LowStateLegView.cs').read_text(encoding='utf-8-sig')
        method = text.split('public bool ApplyMeasuredPose()', 1)[1].split('private void OnDestroy()', 1)[0]
        self.assertIn('!rig.ApplyAllJointPositions(names, latest.q_rad)', method)
        self.assertNotIn('transform.localPosition', method)
        self.assertNotIn('LatestJoints', text)
        self.assertIn('retiredSessions.Contains(value.session)', text)
        self.assertIn('now - received + latest.age_s <= 0.5', text)

    def test_diagnostics_never_write_command_or_ik_state(self):
        text = (CS / 'G1MeasuredTrackingDiagnostics.cs').read_text(encoding='utf-8-sig')
        for required in ('q_measured_rad', 'dq_measured_rad_s', 'q_command_rad', 'comparison_valid',
                         'absolute_transport_latency_available', 'measured_excess_transport_delay_s'):
            self.assertIn('"' + required + '"', text)
        for forbidden in ('Calibrate(', 'config.update', 'Socket(', 'UdpClient', 'ChannelPublisher', 'sender.LatestJoints ='):
            self.assertNotIn(forbidden, text)
        sender = (CS / 'G1BimanualSimulationSender.cs').read_text(encoding='utf-8-sig')
        packet = sender.split('[Serializable] private class Packet', 1)[1].split('[Serializable] private class Feedback', 1)[0]
        self.assertNotIn('q_measured', packet)
        self.assertNotIn('LowState', packet)

    def test_visible_source_label_uses_applied_source(self):
        preview = (CS / 'G1UnityRightArmPreview.cs').read_text(encoding='utf-8-sig')
        sender = (CS / 'G1BimanualSimulationSender.cs').read_text(encoding='utf-8-sig')
        self.assertIn('DisplayStatus = PoseSourceStatus +', preview)
        self.assertIn('preview.ModelStatusText', sender)
        self.assertNotIn('G1 MEASURED 29 JOINTS / IK TARGET', preview)

    def test_unity_behavioral_validator_is_edit_mode_only(self):
        text = (ROOT / 'Unity_G1_VR/Assets/Editor/G1MeasuredDisplayValidation.cs').read_text(encoding='utf-8-sig')
        self.assertIn('EditorApplication.isPlayingOrWillChangePlaymode', text)
        self.assertIn('EditorSceneManager.NewPreviewScene()', text)
        self.assertIn('PoseEquals(rig, measured, "Stale measured render holds")', text)
        self.assertIn('JsonUtility.ToJson(Get(sender, "packet")) == beforePacket', text)
        self.assertNotIn('isPlaying = true', text)


if __name__ == '__main__':
    unittest.main()
