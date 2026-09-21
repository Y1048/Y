"""Quiet observation workers only; no motor control. Logs retain worker output."""
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import threading
import ctypes
import G1_INPUT_OBSERVATION_LAUNCH as observation


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


def run_workers(root, workers, host, env):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = root / 'logs/test_results/teleop_background' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    children = []
    stopped = threading.Event()
    def wait_for_stop():
        try:
            input('Press Enter here to stop this session input/send workers. ')
        except EOFError:
            pass
        stopped.set()
    try:
        for worker in workers:
            logfile = folder / (worker + '.log')
            if worker == 'receive':
                command = [sys.executable, '-u', '-B', str(Path(__file__).resolve()), host, str(logfile)]
                child = subprocess.Popen(command, cwd=root, env=env,
                                         creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                with logfile.open('ab') as output:
                    child = subprocess.Popen(observation.worker_command(worker, host, stamp),
                        cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=output,
                        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            children.append((worker, child))
        print('Input/send console output saved to:', folder, flush=True)
        threading.Thread(target=wait_for_stop, daemon=True).start()
        while not stopped.wait(0.5):
            exited = [(name, child.poll()) for name, child in children if child.poll() is not None]
            if exited:
                print('Worker ended:', exited, 'Review logs:', folder, flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        # Only exact children launched by this invocation; no inventory-wide termination.
        for name, child in reversed(children):
            if child.poll() is None:
                if name == 'receive':
                    subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    child.terminate()
                child.wait(timeout=10)
    return 0


if __name__ == '__main__':
    raise SystemExit(receive(sys.argv[1], sys.argv[2]))
