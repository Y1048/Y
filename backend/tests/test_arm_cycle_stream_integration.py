"""Unity-format bytes -> real stream -> C++ synthetic cycle -> return ack.

Requires the explicitly built local stdio fixture; never starts a robot program.
"""
import json
from pathlib import Path
import subprocess
import unittest
import numpy as np
from test_mink_command_stream import FakeSocket, packet, MinkCommandStream


class IntegratedCycleTest(unittest.TestCase):
    def test_two_complete_cycles(self):
        root = Path(__file__).resolve().parents[2]
        exe = root / "logs/test_results/arm_cycle_stdio_offline.exe"
        self.assertTrue(exe.exists(), "Build arm_cycle_stdio_offline.cpp first")
        sock = FakeSocket()
        stream = MinkCommandStream(np.zeros(3), np.array([0., 0., 0., 1.]),
                                   input_timeout_s=.25, simulation_return_handshake=True)
        proc = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        sequence = 0

        def step(mode, joint=0.):
            nonlocal sequence
            sequence += 1
            sock.queue(packet(sequence, mode=mode))
            update = stream.poll(sock)
            event = ("fault" if stream.return_state == "fault" else
                     "pinch" if mode == "pinch_disengaged" else
                     "active" if update.command_active else "idle")
            proc.stdin.write(json.dumps({"time": sequence*.02, "event": event,
                                         "joints": [joint, 0, 0, 0, 0, 0, 0]})+"\n")
            proc.stdin.flush()
            result = json.loads(proc.stdout.readline())
            self.assertNotEqual(result["state"], "stopped", result)
            return update, result

        try:
            for cycle in range(2):
                step("idle")
                update, result = step("active")
                self.assertTrue(update.engage_clutch)
                self.assertEqual(result["state"], "tracking")
                for _ in range(100):
                    _, result = step("active", .5)
                self.assertGreater(result["q"][22], .1)
                _, result = step("pinch_disengaged")
                self.assertEqual(result["state"], "returning")
                for _ in range(1400):
                    update, result = step("active", .5)
                    self.assertFalse(update.command_active)
                    if result["state"] == "waiting":
                        break
                self.assertEqual(result["state"], "waiting")
                self.assertLess(abs(result["q"][22]), 1e-6)
                self.assertTrue(stream.acknowledge_simulation_return(cycle+1, "session-a"))
                update, result = step("active", .5)
                self.assertFalse(update.command_active)
            proc.stdin.close()
            self.assertEqual(proc.wait(timeout=5), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                pipe.close()


if __name__ == "__main__":
    unittest.main()
