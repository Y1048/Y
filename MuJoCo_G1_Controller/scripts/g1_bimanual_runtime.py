"""Validated engine bootstrap and provenance for bimanual simulation only.

No package installation, Unity launch, hardware transport, or global environment
changes. An explicit engine root is a trusted local Python package directory.
"""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
VALIDATED_MUJOCO = '3.12.0'
ENGINE_ENV = 'G1_BIMANUAL_ENGINE_ROOT'
DEFAULT_ENGINE_ROOT = ROOT / 'logs/diagnostics/mujoco_versions' / VALIDATED_MUJOCO


def startup_stage(stage):
    print(f'[BIMANUAL STARTUP] {stage} perf_counter_ns={time.perf_counter_ns()}', flush=True)


def require_validated_engine():
    """Also guard direct simulator construction; never silently use 3.11."""
    engine = importlib.import_module('mujoco')
    package = engine.__version__
    native = engine.mj_versionString()
    if package != VALIDATED_MUJOCO or native != VALIDATED_MUJOCO:
        raise RuntimeError(
            f'Bimanual simulation requires MuJoCo {VALIDATED_MUJOCO}; '
            f'imported package={package}, native={native}, path={engine.__file__}. '
            'Use g1_bimanual_runtime.py with --engine-root or '
            f'{ENGINE_ENV}; no simulator or transport has been started.')
    return engine


def load_engine(engine_root=None):
    """Select before importing Mink/MuJoCo; propagate only to child processes."""
    requested = engine_root if engine_root is not None else os.environ.get(ENGINE_ENV)
    selected = Path(requested).expanduser().resolve() if requested else None
    if selected is None and DEFAULT_ENGINE_ROOT.exists():
        selected = DEFAULT_ENGINE_ROOT.resolve()
    if selected is not None:
        if not (selected / 'mujoco/__init__.py').is_file():
            raise RuntimeError(f'Isolated engine package is missing: {selected}')
        cached = sys.modules.get('mujoco')
        if cached is not None and Path(cached.__file__).resolve() != (selected/'mujoco/__init__.py').resolve():
            raise RuntimeError('A different MuJoCo is already imported; start a fresh Python process.')
        if cached is None:
            sys.path.insert(0, str(selected))
    engine = require_validated_engine()
    if selected is not None:
        if Path(engine.__file__).resolve() != (selected/'mujoco/__init__.py').resolve():
            raise RuntimeError('MuJoCo was not loaded from the selected engine root.')
        # The loopback regression uses a fresh Python child. It must use the
        # same selected engine, not the machine-wide site-packages version.
        paths = [str(selected)] + [p for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) if p]
        os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(paths))
    return engine


def runtime_metadata(input_kind):
    engine = require_validated_engine()
    packages = {}
    for name in ('mink', 'qpsolvers', 'daqp', 'numpy'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    scripts = Path(__file__).resolve().parent
    sources = {name: hashlib.sha256((scripts/name).read_bytes()).hexdigest()
               for name in ('g1_bimanual_runtime.py', 'g1_bimanual_sim.py', 'g1_bimanual_unity_sim.py',
                            'g1_bimanual_motion_policy.py')}
    return dict(schema='g1.bimanual.sim.run.v1', simulation_only=True,
                hardware_output_authorized=False, input_kind=input_kind,
                started_utc=datetime.now(timezone.utc).isoformat(),
                python_version=sys.version, python_executable=sys.executable,
                mujoco_version=engine.__version__, mujoco_native_version=engine.mj_versionString(),
                mujoco_module=str(Path(engine.__file__).resolve()), packages=packages,
                source_sha256=sources)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-root', type=Path,
                        help='Directory containing the validated mujoco package; no auto-install.')
    parser.add_argument('--mode', choices=('unity', 'demo', 'test'), default='unity')
    parser.add_argument('--validate-only', action='store_true')
    args, forwarded = parser.parse_known_args(argv)
    if (args.validate_only or args.mode == 'test') and forwarded:
        parser.error('Runtime arguments are only accepted for unity/demo execution.')
    startup_stage('engine_begin')
    engine = load_engine(args.engine_root)
    startup_stage('engine_ready')
    print(f'SIMULATION ONLY | MuJoCo {engine.__version__} | {engine.__file__}', flush=True)
    if args.validate_only:
        print(json.dumps(runtime_metadata('validation_only'), allow_nan=False), flush=True)
        return 0
    if args.mode == 'test':
        import unittest
        suite = unittest.defaultTestLoader.discover(str(ROOT/'backend/tests'), pattern='test_bimanual*.py')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    startup_stage('controller_import_begin')
    module = importlib.import_module('g1_bimanual_unity_sim' if args.mode == 'unity' else 'g1_bimanual_sim')
    startup_stage('controller_import_ready')
    previous = sys.argv
    try:
        sys.argv = [module.__file__] + forwarded
        module.main()
    finally:
        sys.argv = previous
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ImportError, OSError) as error:
        print(f'BIMANUAL SIMULATION ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
