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
from g1_session_journal import SessionJournal


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


def _stop_groot_supervisor(child, request_path=None):
    """Ask the GROOT supervisor to complete actuator damping before exit."""
    if child.poll() is not None:
        return child.returncode
    if request_path is not None:
        # CREATE_NEW_CONSOLE workers cannot reliably receive the parent's console
        # control event. A unique per-session file reaches the polling supervisor.
        pending = request_path.with_suffix('.tmp')
        pending.write_text('stop\n', encoding='utf-8')
        pending.replace(request_path)
    else:
        ctrl_break = getattr(signal, 'CTRL_BREAK_EVENT', None)
        child.send_signal(signal.SIGINT if ctrl_break is None else ctrl_break)
    try:
        return child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        print(
            'GROOT controlled shutdown is still running. '
            'Keeping this manager open; do not force-close it while G1 may be active.',
            flush=True,
        )
        return child.wait()


def run_workers(root, workers, host, env):
    bind_session_lifetime()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = root / 'logs/test_results/teleop_background' / stamp
    folder.mkdir(parents=True, exist_ok=False)
    groot_stop_request = folder / 'groot.stop'
    journal = SessionJournal(folder / 'supervisor.jsonl')
    journal.record('session_start', workers=list(workers), host=host)
    children = []
    stopped = threading.Event()
    result = 0
    reason = 'operator_stop'
    stop_request = ['enter']

    def wait_for_stop():
        try:
            input(
                'Press Enter to request controlled shutdown. '
                'Wait for the GROOT shutdown result; reused controllers may remain active. '
                'do not close this window to stop normally. ')
        except EOFError:
            stop_request[0] = 'stdin_eof'
        stopped.set()

    try:
        for worker in workers:
            logfile = folder / (worker + '.log')
            if worker == 'camera':
                child = subprocess.Popen(
                    [sys.executable, '-I', '-u', '-B',
                     str(root / 'tools/G1_CAMERA_LAUNCH.py'),
                     '--robot-host', host,
                     '--camera-codec', env.get('G1_CAMERA_CODEC', 'h264')],
                    cwd=root, env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
            elif worker == 'groot':
                child = subprocess.Popen(
                    [sys.executable, '-I', '-u', '-B',
                     str(root / 'tools/G1_GROOT_REMOTE_LAUNCH.py'),
                     '--host', host, '--confirmed',
                     '--stop-request-file', str(groot_stop_request)],
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
            journal.record('worker_started', worker=worker, pid=child.pid,
                           log=str(logfile) if worker not in ('camera', 'groot') else None)
        print('Input/send console output saved to:', folder, flush=True)
        threading.Thread(target=wait_for_stop, daemon=True).start()
        while True:
            requested = stopped.wait(0.5)
            exited = []
            for name, child in children:
                code = child.poll()
                if code is not None:
                    exited.append((name, code))
            if exited:
                result = 1
                reason = 'unexpected_worker_exit'
                journal.record(reason, workers=exited)
                print(
                    'Worker ended:', exited, 'Review logs:', folder,
                    flush=True)
                break
            if requested:
                reason = stop_request[0]
                if reason == 'stdin_eof':
                    result = 1
                journal.record('stop_requested', source=reason)
                break
    except KeyboardInterrupt:
        reason = 'keyboard_interrupt'
        journal.record('stop_requested', source=reason)
    except Exception as error:
        result = 1
        reason = 'supervisor_exception'
        journal.record(reason, error=repr(error))
        print('[SUPERVISOR FAILED]', repr(error), flush=True)
    finally:
        # Stop GROOT first and wait for its controlled damping sequence.
        for name, child in reversed(children):
            if name == 'groot':
                journal.record('groot_shutdown_requested', pid=child.pid,
                               request_file=str(groot_stop_request))
                try:
                    code = _stop_groot_supervisor(child, groot_stop_request)
                    journal.record('groot_supervisor_exit', returncode=code)
                    if code != 0:
                        result = 2
                        print('[GROOT STOP UNVERIFIED] See GROOT logs; '
                              'do not assume the robot controller stopped.', flush=True)
                except Exception as error:
                    result = 2
                    journal.record('groot_shutdown_exception', error=repr(error))
                    print('[GROOT STOP UNVERIFIED]', repr(error), flush=True)
        # Only exact non-GROOT children launched by this invocation.
        for name, child in reversed(children):
            if name == 'groot' or child.poll() is not None:
                continue
            try:
                subprocess.run(
                    ['taskkill.exe', '/PID', str(child.pid), '/T', '/F'],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                child.wait(timeout=10)
                journal.record('worker_stopped', worker=name, pid=child.pid)
            except Exception as error:
                result = 2
                journal.record('worker_cleanup_exception', worker=name, error=repr(error))
        journal.record('session_end', reason=reason, returncode=result)
        print('[SUPERVISOR EXIT]', reason, 'code=', result,
              'Log:', journal.path, flush=True)
    return result


if __name__ == '__main__':
    raise SystemExit(receive(sys.argv[1], sys.argv[2]))
