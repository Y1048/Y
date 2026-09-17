"""Real Unity packet parser/stream, fake socket; no UDP or robot output."""
import unittest
import numpy as np
from test_mink_command_stream import FakeSocket, packet, MinkCommandStream


class ReturnHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.sock = FakeSocket()
        self.stream = MinkCommandStream(np.zeros(3), np.array([0., 0., 0., 1.]),
                                        input_timeout_s=.25,
                                        simulation_return_handshake=True)
        self.seq = 0

    def send(self, mode, position=(.4, -.1, 1.)):
        self.seq += 1
        self.sock.queue(packet(self.seq, mode=mode, position=position))
        return self.stream.poll(self.sock)

    def test_repeat_and_new_hand_anchor(self):
        self.assertTrue(self.send("active").engage_clutch)
        for epoch in range(1, 4):
            self.assertFalse(self.send("pinch_disengaged").command_active)
            self.assertEqual(self.stream.return_epoch, epoch)
            self.assertFalse(self.send("active").engage_clutch)
            self.assertFalse(self.stream.acknowledge_simulation_return(epoch-1, "session-a"))
            self.assertFalse(self.stream.acknowledge_simulation_return(epoch, "wrong"))
            self.assertTrue(self.stream.acknowledge_simulation_return(epoch, "session-a"))
            self.assertFalse(self.send("active").command_active)
            self.send("idle")
            update = self.send("active", (.5, -.2, 1.1))
            self.assertTrue(update.engage_clutch)
            self.assertTrue(update.command_active)
            np.testing.assert_allclose(update.target_position_m, [.5, -.2, 1.1])

    def test_queued_pinch_is_not_hidden_by_active(self):
        self.send("active")
        self.sock.queue(packet(2, mode="pinch_disengaged"), packet(3))
        self.assertFalse(self.stream.poll(self.sock).command_active)
        self.assertEqual(self.stream.return_state, "returning")
        self.assertFalse(self.stream.poll(self.sock).command_active)

    def test_unity_latched_pinch_can_reengage_after_return(self):
        self.send("active")
        self.send("pinch_disengaged")
        self.assertFalse(self.send("active").command_active)
        self.assertTrue(self.stream.acknowledge_simulation_return(1, "session-a"))
        self.assertFalse(self.send("pinch_disengaged").command_active)
        update = self.send("active")
        self.assertTrue(update.command_active)
        self.assertTrue(update.engage_clutch)

    def test_return_feedback_blocks_early_calibration_until_inactive_ack(self):
        self.send("active")
        self.send("pinch_disengaged")
        # New Unity gate replaces premature active with inactive pinch packets.
        for _ in range(5):
            update = self.send("pinch_disengaged")
            self.assertFalse(update.engage_clutch)
            self.assertEqual(self.stream.return_state, "returning")
        self.assertTrue(self.stream.acknowledge_simulation_return(1, "session-a"))
        self.assertFalse(self.send("pinch_disengaged").command_active)
        self.assertEqual(self.stream.return_state, "await_active")
        update = self.send("active", (.52, -.18, .95))
        self.assertTrue(update.command_active)
        self.assertTrue(update.engage_clutch)

    def test_tracking_loss_returns_and_reengages_repeatedly(self):
        self.send("active")
        for epoch in range(1, 4):
            self.assertFalse(self.send("tracking_disengaged").command_active)
            self.assertEqual(self.stream.return_state, "returning")
            self.assertEqual(self.stream.return_epoch, epoch)
            self.assertFalse(self.send("active").engage_clutch)
            self.send("tracking_disengaged")
            self.assertEqual(self.stream.return_epoch, epoch)
            self.assertTrue(self.stream.acknowledge_simulation_return(epoch, "session-a"))
            self.assertFalse(self.send("active").command_active)
            self.assertFalse(self.send("tracking_disengaged").command_active)
            update = self.send("active", (.52, -.18, .95))
            self.assertTrue(update.command_active)
            self.assertTrue(update.engage_clutch)
            np.testing.assert_allclose(update.target_position_m, [.52, -.18, .95])

    def test_queued_tracking_loss_is_not_hidden_by_active(self):
        self.send("active")
        self.sock.queue(packet(2, mode="tracking_disengaged"), packet(3))
        self.assertFalse(self.stream.poll(self.sock).command_active)
        self.assertEqual(self.stream.return_state, "returning")

    def test_tracking_return_does_not_override_timeout(self):
        self.send("active")
        self.send("tracking_disengaged")
        self.stream.poll(self.sock, now_ns=self.stream.watchdog.last_arrival_time_ns+250000001)
        self.assertEqual(self.stream.return_state, "fault")
        self.assertEqual(self.stream.return_fault_reason, "input_timeout")
        self.assertFalse(self.stream.acknowledge_simulation_return(1, "session-a"))
        self.assertFalse(self.send("active").command_active)

    def test_preengage_previous_disengage_does_not_latch_or_return(self):
        for mode in ("tracking_disengaged", "pinch_disengaged", "idle"):
            self.assertFalse(self.send(mode).command_active)
            self.assertEqual(self.stream.return_state, "ready")
            self.assertEqual(self.stream.return_epoch, 0)
        self.assertTrue(self.send("active").engage_clutch)
        self.send("tracking_disengaged")
        self.assertEqual(self.stream.return_state, "returning")
        self.assertFalse(self.stream.return_fault_reason)

    def test_timeout_latches_before_first_pinch(self):
        self.send("active")
        self.stream.poll(self.sock, now_ns=self.stream.watchdog.last_arrival_time_ns+250000001)
        self.assertEqual(self.stream.return_state, "fault")
        self.assertFalse(self.send("active").command_active)

    def test_invalid_packet_latches(self):
        self.send("active")
        self.sock.queue(b"invalid json")
        self.assertFalse(self.stream.poll(self.sock).command_active)
        self.assertEqual(self.stream.return_state, "fault")


if __name__ == "__main__":
    unittest.main()
