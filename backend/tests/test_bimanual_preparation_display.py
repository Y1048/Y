"""Run the actual pure C# preparation-message function without starting Unity."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SENDER = ROOT / 'Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs'


class PreparationDisplayTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'PowerShell C# compiler required')
    def test_stage_priority_and_ready_clears_prompt(self):
        text = SENDER.read_text(encoding='utf-8-sig')
        start = text.index('    public static string PreparationMessage(')
        end = text.index('    private double leftReadyUntil', start)
        method = text[start:end]
        script = "Add-Type -TypeDefinition @'\npublic static class Preparation {\n" + method + "}\n'@\n"
        cases = [
            ('false,false,false,null', '준비 중 · G1 모델 불러오는 중'),
            ('true,false,false,null', '준비 중 · IK 연결 기다리는 중'),
            ('true,true,false,"settling_measurement"', '준비 중 · 실측 자세 안정 확인 중'),
            ('true,true,false,"waiting_fresh_measurement"', '준비 중 · 최신 G1 실측 수신 대기'),
            ('true,true,false,"synchronized"', '준비 중 · 모델과 IK 초기화 확인 중'),
            ('true,true,false,"waiting_head_alignment"', '준비 중 · 헤드셋 기준 정렬 중'),
            ('true,true,false,"measured_start_pose_clearance"', '시작 대기 · 실측 시작 자세의 모델 충돌 여유 부족 (재확인 중)'),
            ('true,true,false,"settling_measurement","measured_start_pose_clearance"', '시작 대기 · 실측 시작 자세의 모델 충돌 여유 부족 (재확인 중)'),
            ('true,true,false,"measured_start_home_clearance"', '시작 대기 · 복귀 자세의 모델 충돌 여유 부족 (재확인 중)'),
            ('true,true,false,"measured_start_waypoint_clearance"', '시작 대기 · 복귀 자세의 모델 충돌 여유 부족 (재확인 중)'),
            ('true,false,false,"settling_measurement","measured_start_pose_clearance"', '준비 중 · IK 연결 기다리는 중'),
            ('true,true,false,"waiting_fresh_measurement","measured_start_pose_clearance"', '준비 중 · 최신 G1 실측 수신 대기'),
        ]
        for args, expected in cases:
            script += 'if ([Preparation]::PreparationMessage(' + args.replace('true', '$true').replace('false', '$false').replace('null', '$null') + ") -ne '" + expected + "') { throw 'wrong stage' }\n"
        script += "if ($null -ne [Preparation]::PreparationMessage($true,$true,$true,$null)) { throw 'ready prompt' }; 'PASS'"
        script += "\nif ($null -ne [Preparation]::PreparationMessage($true,$true,$true,'synchronized','measured_start_pose_clearance')) { throw 'stale blocker after ready' }"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertIn(b'PASS', result.stdout)

    def test_startup_overlay_does_not_change_control_requirements(self):
        text = SENDER.read_text(encoding='utf-8-sig')
        ui = text.split('private void UpdateStatusBar(', 1)[1].split('private void OnGUI()', 1)[0]
        self.assertIn('preview.IsModelReady', ui)
        self.assertIn('if (preparation != null)', ui)
        self.assertIn('statusBar.localPosition = new Vector3(0, -.05f, .75f)', ui)
        self.assertIn('else if (cameraRect != null)', ui)
        for forbidden in ('active =', 'measuredStartReady =', 'client.Send(', 'Calibrate('):
            self.assertNotIn(forbidden, ui)
        self.assertIn('CanEngage(fresh && measuredStartReady', text)


if __name__ == '__main__':
    unittest.main()
