"""Engine selection regressions. No Quest, Unity, or physical robot execution."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_runtime as runtime


def fake_engine(path, package='3.12.0', native='3.12.0'):
    return SimpleNamespace(__file__=str(path/'mujoco/__init__.py'),
                           __version__=package, mj_versionString=lambda: native)


class RuntimeTests(unittest.TestCase):
    def test_matching_package_and_native_are_required(self):
        good = fake_engine(Path('/validated'))
        with patch.object(runtime.importlib, 'import_module', return_value=good):
            self.assertIs(runtime.require_validated_engine(), good)
        for package, native in [('3.11.0', '3.11.0'), ('3.12.0', '3.11.0'), ('3.11.0', '3.12.0')]:
            with self.subTest(package=package, native=native):
                bad = fake_engine(Path('/wrong'), package, native)
                with patch.object(runtime.importlib, 'import_module', return_value=bad):
                    with self.assertRaisesRegex(RuntimeError, 'requires MuJoCo 3.12.0'):
                        runtime.require_validated_engine()

    def test_explicit_missing_engine_has_no_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runtime, 'require_validated_engine') as load:
                with self.assertRaisesRegex(RuntimeError, 'missing'):
                    runtime.load_engine(Path(directory)/'absent')
                load.assert_not_called()

    def test_environment_missing_engine_has_no_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {runtime.ENGINE_ENV: str(Path(directory)/'absent')}):
                with patch.object(runtime, 'require_validated_engine') as load:
                    with self.assertRaisesRegex(RuntimeError, 'missing'):
                        runtime.load_engine()
                    load.assert_not_called()

    def test_explicit_engine_wins_and_children_inherit_it(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory).resolve()
            (selected/'mujoco').mkdir()
            (selected/'mujoco/__init__.py').touch()
            engine = fake_engine(selected)
            with patch.dict(os.environ, {runtime.ENGINE_ENV: str(selected/'wrong'), 'PYTHONPATH': 'existing'}):
                with patch.dict(sys.modules, {'mujoco': engine}):
                    with patch.object(runtime, 'require_validated_engine', return_value=engine):
                        self.assertIs(runtime.load_engine(selected), engine)
                        self.assertEqual(os.environ['PYTHONPATH'].split(os.pathsep), [str(selected), 'existing'])
                        runtime.load_engine(selected)
                        self.assertEqual(os.environ['PYTHONPATH'].split(os.pathsep), [str(selected), 'existing'])

    def test_default_project_engine_is_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory).resolve()
            (selected/'mujoco').mkdir()
            (selected/'mujoco/__init__.py').touch()
            engine = fake_engine(selected)
            with patch.dict(os.environ, {runtime.ENGINE_ENV: ''}):
                with patch.object(runtime, 'DEFAULT_ENGINE_ROOT', selected):
                    with patch.dict(sys.modules, {'mujoco': engine}):
                        with patch.object(runtime, 'require_validated_engine', return_value=engine):
                            self.assertIs(runtime.load_engine(), engine)

    def test_installed_validated_engine_needs_no_local_root(self):
        engine = fake_engine(Path('/site-packages'))
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {runtime.ENGINE_ENV: '', 'PYTHONPATH': 'unchanged'}):
                with patch.object(runtime, 'DEFAULT_ENGINE_ROOT', Path(directory)/'absent'):
                    with patch.object(runtime, 'require_validated_engine', return_value=engine):
                        self.assertIs(runtime.load_engine(), engine)
                        self.assertEqual(os.environ['PYTHONPATH'], 'unchanged')

    def test_cannot_switch_preloaded_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory).resolve()
            (selected/'mujoco').mkdir()
            (selected/'mujoco/__init__.py').touch()
            with patch.dict(sys.modules, {'mujoco': fake_engine(selected/'elsewhere')}):
                with self.assertRaisesRegex(RuntimeError, 'fresh Python process'):
                    runtime.load_engine(selected)

    def test_validation_does_not_import_runner(self):
        engine = fake_engine(Path('/validated'))
        with patch.object(runtime, 'load_engine', return_value=engine):
            with patch.object(runtime, 'runtime_metadata', return_value={'simulation_only': True}):
                with patch.object(runtime.importlib, 'import_module') as imports:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(runtime.main(['--validate-only']), 0)
                    imports.assert_not_called()

    def test_startup_failure_does_not_import_runner(self):
        with patch.object(runtime, 'load_engine', side_effect=RuntimeError('wrong engine')):
            with patch.object(runtime.importlib, 'import_module') as imports:
                with self.assertRaisesRegex(RuntimeError, 'wrong engine'):
                    runtime.main(['--mode', 'unity', '--headless'])
                imports.assert_not_called()

    def test_core_guard_precedes_model_preparation(self):
        import g1_bimanual_sim as simulation
        with patch.object(simulation, 'require_validated_engine', side_effect=RuntimeError('wrong engine')):
            with patch.object(simulation.base, '_prepare_mink_xml') as prepare:
                with self.assertRaisesRegex(RuntimeError, 'wrong engine'):
                    simulation.BimanualSimulation()
                prepare.assert_not_called()

    def test_metadata_is_simulation_only_and_hashes_source(self):
        metadata = runtime.runtime_metadata('validation_only')
        self.assertTrue(metadata['simulation_only'])
        self.assertFalse(metadata['hardware_output_authorized'])
        self.assertEqual(metadata['mujoco_version'], '3.12.0')
        self.assertEqual(metadata['mujoco_native_version'], '3.12.0')
        self.assertEqual(set(metadata['source_sha256']), {
            'g1_bimanual_runtime.py', 'g1_bimanual_sim.py', 'g1_bimanual_unity_sim.py',
            'g1_bimanual_motion_policy.py'})
        self.assertTrue(all(len(value) == 64 for value in metadata['source_sha256'].values()))
        json.dumps(metadata, allow_nan=False)

    def test_both_launchers_use_validated_runtime(self):
        for name, mode in [('START_BIMANUAL_UNITY_SIM.bat', 'unity'), ('START_BIMANUAL_SIM.bat', 'demo')]:
            text = (ROOT/'tools'/name).read_text()
            self.assertIn('g1_bimanual_runtime.py --mode '+mode, text)
            self.assertIn('%*', text)
            self.assertNotIn('pip install', text)


if __name__ == '__main__':
    unittest.main()
