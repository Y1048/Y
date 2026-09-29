"""Launch the read-only G1 camera over SSH, or check local prerequisites."""
import argparse
import sys

from g1_portable_environment import select_robot_host


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--setup', action='store_true')
    parser.add_argument('--robot-host', default='auto')
    args = parser.parse_args(argv)

    from g1_camera_ssh import run, check_environment
    check_environment()
    if args.setup or args.check_only:
        return
    return run(select_robot_host(args.robot_host))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('CAMERA: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
