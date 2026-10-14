"""Launch the read-only Insta360 Link 2 Pro stream over SSH, or check prerequisites."""
import argparse
import sys

from g1_portable_environment import select_robot_host


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--setup', action='store_true')
    parser.add_argument('--robot-host', default='auto')
    parser.add_argument('--camera-codec', choices=('h264', 'mjpeg'), default='h264')
    parser.add_argument('--probe-seconds', type=float, default=0,
                        help='Bounded H264 capture/decode only; no Unity or motor connection')
    args = parser.parse_args(argv)

    from g1_camera_ssh import run, check_environment
    check_environment()
    if args.setup or args.check_only:
        return
    return run(select_robot_host(args.robot_host), codec=args.camera_codec,
               probe_seconds=args.probe_seconds)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('CAMERA: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
