"""Mirror the launcher console output to a local log; never authorize output."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    directory = root / "logs" / "test_results"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    kind = "logging_self_test" if args.self_test else "standard_mink_launcher"
    path = directory / f"g1_gate7_{kind}_{stamp}.log"
    shell = os.environ.get("COMSPEC", "cmd.exe")
    if args.self_test:
        command = [shell, "/d", "/c",
                   "echo STDOUT_TEST & echo STDERR_TEST 1>&2 & choice /C YN /D N /T 0 /M INPUT_TEST"]
    else:
        command = [shell, "/d", "/c",
                   str(root / "tools" / "START_G1_GATE7_STANDARD_MINK.bat"), "--logged"]
    environment = dict(os.environ, PYTHONUNBUFFERED="1")
    print(f"[LOG] Full launcher output: {path}", flush=True)
    # Inherit the console input so CHOICE and PAUSE retain their normal behavior.
    # Read bytes, not lines: CHOICE prompts do not end with a newline.
    with path.open("wb", buffering=0) as log:
        process = subprocess.Popen(command, cwd=root, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            while True:
                try:
                    chunk = os.read(process.stdout.fileno(), 4096)
                except KeyboardInterrupt:
                    # Windows also delivers Ctrl+C to the child console process.
                    # Do not kill a command-capable child during its cleanup.
                    continue
                if not chunk:
                    break
                log.write(chunk)
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            while True:
                try:
                    result = process.wait()
                    break
                except KeyboardInterrupt:
                    continue
        finally:
            process.stdout.close()
        log.write(f"\r\n[EXIT CODE] {result}\r\n".encode("ascii"))
    print(f"\n[LOG] Result saved to: {path}", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
