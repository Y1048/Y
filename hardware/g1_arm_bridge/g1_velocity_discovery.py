"""SDK-free discovery contract shared by PC velocity senders."""

import json
import socket


SCHEMA = "g1.velocity.discovery.v1"
DEFAULT_DISCOVERY_PORT = 5018


def parse_discovery(raw: bytes, expected_token: str) -> dict:
    def reject_duplicates(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    if len(raw) > 2048:
        raise ValueError("discovery size")
    packet = json.loads(raw, object_pairs_hook=reject_duplicates)
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ValueError("discovery schema")
    if packet.get("relay_token") != expected_token:
        raise ValueError("discovery token")
    port = packet.get("velocity_port")
    sequence = packet.get("sequence")
    robot_id = packet.get("robot_id")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("discovery velocity port")
    if type(sequence) is not int or not 0 <= sequence < 2**63:
        raise ValueError("discovery sequence")
    if not isinstance(robot_id, str) or not robot_id or len(robot_id) > 128:
        raise ValueError("discovery robot id")
    return packet


def make_listener(port: int = DEFAULT_DISCOVERY_PORT) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", port))
    return listener
