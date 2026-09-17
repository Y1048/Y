import json
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import g1_velocity_keypad_relay as relay


def packet(**changes):
    value = dict(schema=relay.SCHEMA, command_provenance="unity_keypad",
                 simulation_only=False, session="a" * 32, sequence=1,
                 source_monotonic_s=1.25, velocity=[0.8, -0.8, 0.8])
    value.update(changes)
    return value


class RelayContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(relay.validate(packet())["velocity"], [0.8, -0.8, 0.8])

    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            relay.strict_load(b'{"schema":"a","schema":"b"}')

    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError, "range"):
            relay.validate(packet(velocity=[math.nan, 0, 0]))

    def test_out_of_range_rejected(self):
        with self.assertRaisesRegex(ValueError, "range"):
            relay.validate(packet(velocity=[0.801, 0, 0]))

    def test_wrong_provenance_rejected(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            relay.validate(packet(command_provenance="replay"))

    def test_no_unitree_or_dds_dependency(self):
        source = pathlib.Path(relay.__file__).read_text(encoding="utf-8").lower()
        self.assertNotIn("channelpublisher", source)
        self.assertNotIn("unitree_sdk", source)
        self.assertNotIn("rt/lowcmd", source)

    def test_windows_udp_reset_is_explicitly_handled(self):
        source = pathlib.Path(relay.__file__).read_text(encoding="utf-8")
        self.assertIn("except ConnectionResetError", source)
        self.assertIn('winerror", None) != 10054', source)

    def test_receive_and_forward_sockets_are_separate(self):
        source = pathlib.Path(relay.__file__).read_text(encoding="utf-8")
        self.assertIn("outbound = socket.socket", source)
        self.assertIn("outbound.sendto", source)
        self.assertNotIn("inbound.sendto", source)

    def test_play_restart_accepts_only_new_session_sequence_zero(self):
        self.assertTrue(relay.validate_order("a" * 32, 12,
                                            packet(session="b" * 32, sequence=0)))
        with self.assertRaisesRegex(ValueError, "restart sequence"):
            relay.validate_order("a" * 32, 12,
                                 packet(session="b" * 32, sequence=3))

    def test_same_session_must_remain_monotonic(self):
        self.assertFalse(relay.validate_order("a" * 32, 12,
                                             packet(sequence=13)))
        with self.assertRaisesRegex(relay.StalePacket, "sequence"):
            relay.validate_order("a" * 32, 12, packet(sequence=12))

    def test_stale_packet_is_distinct_from_invalid_packet(self):
        with self.assertRaises(relay.StalePacket):
            relay.validate_order("a" * 32, 12, packet(sequence=11))


if __name__ == "__main__":
    unittest.main()
