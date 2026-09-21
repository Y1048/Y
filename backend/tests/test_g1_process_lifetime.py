"""Actual Windows process fixtures; no network, SDK or hardware."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[2] / 'tools'

@unittest.skipUnless(os.name == 'nt', 'Windows Job Object integration')
class LifetimeTests(unittest.TestCase):
    def test_normal_and_forced_supervisor_exit_kill_descendants_only(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        outsider = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        try:
            for forced in (False, True):
                with self.subTest(forced=forced), tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / 'ready.json'
                    leaf = "import time;time.sleep(60)"
                    child = ("import subprocess,sys,time,json;from pathlib import Path;"
                             "p=subprocess.Popen([sys.executable,'-c'," + repr(leaf) + "],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW);"
                             "Path(" + repr(str(path)) + ").write_text(json.dumps([__import__('os').getpid(),p.pid]));time.sleep(60)")
                    parent = ("import sys,subprocess;sys.path.insert(0," + repr(str(TOOLS)) + ");"
                              "from g1_process_lifetime import bind_session_lifetime;"
                              "bind_session_lifetime();bind_session_lifetime();"
                              "subprocess.Popen([sys.executable,'-c'," + repr(child) + "],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW);input()")
                    supervisor = subprocess.Popen([sys.executable, '-c', parent], stdin=subprocess.PIPE,
                                                  creationflags=subprocess.CREATE_NO_WINDOW)
                    handles = []
                    try:
                        deadline = time.monotonic() + 10
                        while not path.exists() and time.monotonic() < deadline and supervisor.poll() is None:
                            time.sleep(.02)
                        self.assertTrue(path.exists(), 'supervisor failed to start fixtures')
                        pids = json.loads(path.read_text())
                        for pid in pids:
                            handle = kernel.OpenProcess(0x100000, False, pid)
                            self.assertTrue(handle)
                            handles.append(handle)
                        if forced:
                            supervisor.terminate()
                        else:
                            supervisor.stdin.write(b'\n'); supervisor.stdin.flush()
                        supervisor.wait(timeout=10)
                        for handle in handles:
                            self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
                        self.assertIsNone(outsider.poll(), 'unrelated process must survive')
                    finally:
                        if supervisor.poll() is None: supervisor.kill(); supervisor.wait(timeout=5)
                        if supervisor.stdin: supervisor.stdin.close()
                        for handle in handles: kernel.CloseHandle(handle)
        finally:
            outsider.terminate(); outsider.wait(timeout=5)
