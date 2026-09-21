import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import g1_teleop_dependencies as deps

class DependencyTests(unittest.TestCase):
    def test_real_empty_venv_pip_check_is_not_sufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'tools').mkdir()
            shutil.copy2(deps.ROOT/'tools/g1_teleop_dependencies.py',root/'tools')
            shutil.copy2(deps.ROOT/'tools/requirements-teleop.txt',root/'tools')
            subprocess.run([sys.executable,'-m','venv',str(root/'.venv-teleop')],check=True,capture_output=True,timeout=60)
            python=root/'.venv-teleop/Scripts/python.exe'
            subprocess.run([str(python),'-m','pip','check'],check=True,capture_output=True,timeout=30)
            result=subprocess.run([str(python),'-I',str(root/'tools/g1_teleop_dependencies.py'),'--probe'],capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,1)
            report=json.loads(result.stdout)
            self.assertTrue(any('websocket-client' in error for error in report['errors']))
            self.assertTrue(any('mujoco' in error for error in report['errors']))

    def test_check_only_never_installs(self):
        with patch.object(deps,'validate',return_value=False), patch.object(deps.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):deps.ensure(False)
            run.assert_not_called()

    def test_healthy_environment_does_not_install(self):
        with patch.object(deps,'validate',return_value=True), patch.object(deps.subprocess,'run') as run:
            deps.ensure(True);run.assert_not_called()

    def test_repair_full_requirements_and_revalidate(self):
        for outcome in (True,False):
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);python=root/'.venv-teleop/Scripts/python.exe'
                python.parent.mkdir(parents=True);python.touch()
                with patch.object(deps,'ROOT',root),patch.object(deps,'validate',side_effect=[False,outcome]) as validate,patch.object(deps.subprocess,'run') as run:
                    if outcome:deps.ensure(True)
                    else:
                        with self.assertRaises(RuntimeError):deps.ensure(True)
                    self.assertEqual(validate.call_count,2)
                    self.assertEqual(run.call_args_list[-1].args[0][-2:],['-r',str(root/'tools/requirements-teleop.txt')])
                    self.assertTrue(all(call.args[0][0]==str(python) for call in run.call_args_list))

    def test_install_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);python=root/'.venv-teleop/Scripts/python.exe'
            python.parent.mkdir(parents=True);python.touch()
            with patch.object(deps,'ROOT',root),patch.object(deps,'validate',return_value=False),patch.object(deps.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'pip')):
                with self.assertRaises(subprocess.CalledProcessError):deps.ensure(True)

    def test_batch_gates_launcher_and_keeps_check_only_read_only(self):
        source=(deps.ROOT/'tools/START_G1_VR_TELEOP.bat').read_text()
        self.assertLess(source.index('g1_teleop_dependencies.py'),source.index('G1_VR_TELEOP_LAUNCH.py'))
        self.assertIn('if errorlevel 1',source)
        self.assertIn('DEP_CHECK=--check-only',source)
