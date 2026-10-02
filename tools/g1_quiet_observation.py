"""Own integrated teleop workers, including the confirmed GROOT remote supervisor."""
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import sys
import threading
import ctypes
import G1_INPUT_OBSERVATION_LAUNCH as observation
from g1_process_lifetime import bind_session_lifetime


def receive(host, log):
    # Authentication stays visible; stdout starts only after the remote command runs.
    child = subprocess.Popen(observation.worker_command('receive', host, ''),
                             stdout=subprocess.PIPE, text=True, errors='replace')
    ctypes.windll.kernel32.GetConsoleWindow.restype = ctypes.c_void_p
    ctypes.windll.user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    window = ctypes.windll.kernel32.GetConsoleWindow()
    try:
        with open(log, 'a', encoding='utf-8') as output:
            for line in child.stdout:
                output.write(line)
                output.flush()
                if window:
                    ctypes.windll.user32.ShowWindow(window, 0)
        result = child.wait()
        if result:
            if window:
                ctypes.windll.user32.ShowWindow(window, 5)
            print('Receiver ended with code', result, 'Log:', log)
            input('Press Enter to close.')
        return result
    finally:
        if child.poll() is None:
            child.terminate()


def _stop_groot_supervisor(child):
    """Ask the GROOT supervisor to complete actuator damping before exit."""
    if child.poll() is not None:
        return
    ctrl_break = getattr(signal, 'CTRL_BREAK_EVENT', None)
    if ctrl_break is None:
        child.send_signal(signal.SIGINT)
    else:
        child.send_signal(ctrl_break)
    try:
        child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        print(
            'GROOT controlled shutdown is still running. '
            'Keeping this manager open; do not force-close it while G1 may be active.',
            flush=True,
        )
        child.wait()


def run_workers(root, workers, host, env):
    bind_session_lifetime()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = root / 'logs/test_results/teleop_background' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    children = []
    stopped = threading.Event()

    def wait_for_stop():
        try:
            input(
                'Press Enter for controlled shutdown. '
                'G1 actuator damping is completed before other workers stop; '
                'do not close this window to stop normally. ')
        except EOFError:
            pass
        stopped.set()

    try:
        for worker in workers:
            logfile = folder / (worker + '.log')
            if worker == 'camera':
                child = subprocess.Popen(
                    [sys.executable, '-I', '-u', '-B',
                     str(root / 'tools/G1_CAMERA_LAUNCH.py'),
                     '--robot-host', host],
                    cwd=root, env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif worker == 'groot':
                child = subprocess.Popen(
                    [sys.executable, '-I', '-u', '-B',
                     str(root / 'tools/G1_GROOT_REMOTE_LAUNCH.py'),
                     '--host', host, '--confirmed'],
                    cwd=root, env=env,
                    creationflags=(
                        subprocess.CREATE_NEW_CONSOLE
                        | subprocess.CREATE_NEW_PROCESS_GROUP))
            elif worker == 'camera_follow':
                with logfile.open('ab') as output:
                    child = subprocess.Popen(
                        [sys.executable, '-I', '-u', '-B',
                         str(root / 'tools/G1_CAMERA_FOLLOW_LAUNCH.py'), '--host', host],
                        cwd=root, env=env, stdin=subprocess.DEVNULL,
                        stdout=output, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
            elif worker == 'receive':
                command = [
                    sys.executable, '-I', '-u', '-B',
                    str(Path(__file__).resolve()), host, str(logfile)]
                child = subprocess.Popen(
                    command, cwd=root, env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                with logfile.open('ab') as output:
                    command = observation.worker_command(worker, host, stamp)
                    if worker == 'send':
                        command[command.index('--print-hz') + 1] = '1'
                    child = subprocess.Popen(
                        command,
                        cwd=root, env=env, stdin=subprocess.DEVNULL,
                        stdout=output, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
            children.append((worker, child))
        print('Input/send console output saved to:', folder, flush=True)
        threading.Thread(target=wait_for_stop, daemon=True).start()
        while not stopped.wait(0.5):
            exited = [
                (name, child.poll())
                for name, child in children
                if child.poll() is not None
            ]
            if exited:
                print(
                    'Worker ended:', exited, 'Review logs:', folder,
                    flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        # Stop GROOT first and wait for its controlled damping sequence.
        for name, child in reversed(children):
            if name == 'groot':
                _stop_groot_supervisor(child)
        # Only exact non-GROOT children launched by this invocation.
        for name, child in reversed(children):
            if name == 'groot' or child.poll() is not None:
                continue
            subprocess.run(
                ['taskkill.exe', '/PID', str(child.pid), '/T', '/F'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            child.wait(timeout=10)
    return 0


if __name__ == '__main__':
    raise SystemExit(receive(sys.argv[1], sys.argv[2]))
