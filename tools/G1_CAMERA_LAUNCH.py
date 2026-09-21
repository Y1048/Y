"""Launch only the read-only camera bridge, or inspect/install its dependencies."""
import argparse
import subprocess
import sys
from g1_portable_environment import camera_run, select_robot_host


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--setup', action='store_true')
    parser.add_argument('--robot-host', default='auto')
    args = parser.parse_args()
    host = args.robot_host if args.setup or args.check_only else select_robot_host(args.robot_host)
    camera_run('--setup' if args.setup else '--check-only' if args.check_only else '--run', host)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('CAMERA: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
