import json
import unittest

try:
    from .g1_velocity_discovery import parse_discovery
except ImportError:
    from g1_velocity_discovery import parse_discovery


class DiscoveryContractTests(unittest.TestCase):
    def setUp(self):
        self.token = "a" * 32
        self.packet = {
            "schema": "g1.velocity.discovery.v1",
            "robot_id": "g1-test",
            "velocity_port": 5017,
            "sequence": 0,
            "relay_token": self.token,
        }

    def encode(self):
        return json.dumps(self.packet, separators=(",", ":")).encode()

    def test_valid_packet(self):
        self.assertEqual(parse_discovery(self.encode(), self.token)["velocity_port"], 5017)

    def test_wrong_token_rejected(self):
        with self.assertRaises(ValueError):
            parse_discovery(self.encode(), "b" * 32)

    def test_invalid_port_rejected(self):
        self.packet["velocity_port"] = 80
        with self.assertRaises(ValueError):
            parse_discovery(self.encode(), self.token)

    def test_duplicate_key_rejected(self):
        raw = ('{"schema":"g1.velocity.discovery.v1","schema":"x",'
               '"robot_id":"g1","velocity_port":5017,"sequence":0,'
               '"relay_token":"' + self.token + '"}').encode()
        with self.assertRaises(ValueError):
            parse_discovery(raw, self.token)


if __name__ == "__main__":
    unittest.main()
