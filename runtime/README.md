# Bundled CPython Runtime

This directory is the self-contained Windows x64 Python runtime used by G1 teleoperation.

- CPython: 3.11.9 embeddable x64
- Base archive identity: `python/RUNTIME_MANIFEST.json`
- Python dependencies: preinstalled under `python/Lib/site-packages`
- Runtime isolation/path contract: `python/python311._pth`
- No system Python, venv, user-site, or runtime pip installation is required.

Operator PCs must consume this directory as-is. If validation fails, restore the complete `runtime/python` directory from a known-good project copy.

For developers only, `tools/BUILD_EMBEDDED_RUNTIME.py` rebuilds the directory from the official CPython archive and exact `tools/requirements-teleop.txt` pins. The builder verifies the CPython archive SHA-256, removes absolute-path console-script wrappers, normalizes package RECORD metadata, writes the manifest, and validates MuJoCo/DAQP imports.

External dependencies remain external by design: Unity 6000.5.4f1, Windows OpenSSH, Meta Quest tooling/drivers, Omni Connect, G1 network access, and privileged Windows networking administration.
