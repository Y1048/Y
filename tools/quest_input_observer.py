"""Quest raw-input recorder. UDP observation only; never forwards control data."""
import argparse
import json
import math
import socket
import time
import uuid
from pathlib import Path

PORT = 55100
SCHEMA = "g1.quest.raw_input.v1"
FRAME = "unity_tracking_origin_lh_xright_yup_zforward"
CLOCK = "quest_unity_realtime_since_startup"


def strict_load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("nonfinite JSON")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def pose(value):
    if not isinstance(value, dict):
        raise ValueError("missing pose")
    for key, size in (("position_m", 3), ("quaternion_xyzw", 4)):
        values = value.get(key)
        if not isinstance(values, list) or len(values) != size or not all(number(v) for v in values):
            raise ValueError("pose values")
    if abs(sum(v*v for v in value["quaternion_xyzw"]) - 1) > .01:
        raise ValueError("quaternion norm")


def validate(x):
    if not isinstance(x, dict) or x.get("schema") != SCHEMA or x.get("observation_only") is not True:
        raise ValueError("observation schema")
    if x.get("frame") != FRAME or x.get("clock_source") != CLOCK or x.get("send_hz") != 60:
        raise ValueError("frame/clock/rate")
    session = x.get("session_id")
    if not isinstance(session, str) or len(session) != 32 or any(c not in "0123456789abcdef" for c in session):
        raise ValueError("session")
    if type(x.get("sequence")) is not int or x["sequence"] < 0:
        raise ValueError("sequence")
    if not number(x.get("source_time_s")) or x["source_time_s"] < 0:
        raise ValueError("source timestamp")
    for key in ("focused", "head_tracked"):
        if type(x.get(key)) is not bool:
            raise ValueError("tracking flag")
    if x["head_tracked"]:
        pose(x.get("head"))
    for side in ("left", "right"):
        hand = x.get(side)
        if not isinstance(hand, dict):
            raise ValueError("missing hand")
        for key in ("tracked", "high_confidence", "pinch"):
            if type(hand.get(key)) is not bool:
                raise ValueError("hand flag")
        if not hand["tracked"] and (hand["high_confidence"] or hand["pinch"]):
            raise ValueError("untracked hand flags")
        if hand["tracked"]:
            for key in ("wrist", "index_base", "middle_base", "pinky_base"):
                pose(hand.get(key))
    # Reject nonfinite numbers even in optional/untracked fields.
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite sample")
        if isinstance(value, dict):
            for child in value.values(): finite(child)
        if isinstance(value, list):
            for child in value: finite(child)
    finite(x)
    return x


class Recorder:
    def __init__(self, output):
        self.output = output
        self.receiver_id = uuid.uuid4().hex
        self.discovered = set()
        self.order = {}
        self.accepted = self.rejected = 0
        self.latest = None
        self.latest_receive_s = None

    def handle(self, raw, peer, receive_s):
        if len(raw) > 8192:
            raise ValueError("oversized packet")
        x = strict_load(raw)
        if isinstance(x, dict) and x.get("schema") == "g1.quest.observation.discover.v1":
            nonce = x.get("nonce")
            if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
                raise ValueError("discovery nonce")
            self.discovered.add(peer)
            return {"schema": "g1.quest.observation.offer.v1", "nonce": nonce, "receiver_id": self.receiver_id}
        validate(x)
        if peer not in self.discovered:
            raise ValueError("no discovery")
        key = (peer, x["session_id"])
        previous = self.order.get(key)
        gap = 0
        if previous:
            seq, source = previous
            if x["sequence"] <= seq or x["source_time_s"] <= source:
                raise ValueError("non-monotonic sample")
            gap = x["sequence"] - seq - 1
        record = {"schema": "g1.quest.observation.record.v1", "peer": list(peer),
                  "pc_receive_monotonic_s": receive_s, "pc_clock_source": "python_time_monotonic",
                  "clock_alignment": "not_established", "sequence_gap": gap,
                  "session_first_sample": previous is None, "sample": x,
                  "raw_json_utf8": raw.decode("utf-8"),
                  "acceptance": "PC_validated_recorded_only"}
        self.output.write(json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n")
        self.order[key] = (x["sequence"], x["source_time_s"])
        self.accepted += 1
        self.latest = x
        self.latest_receive_s = receive_s
        return {"schema": "g1.quest.observation.ack.v1", "session_id": x["session_id"], "sequence": x["sequence"]}


def run(output, seconds=0, bind="0.0.0.0"):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((bind, PORT))
        sock.settimeout(.2)
        with open(output, "x", encoding="utf-8", buffering=65536) as stream:
            recorder = Recorder(stream)
            start = last_report = time.monotonic()
            print(f"OBSERVATION ONLY UDP {PORT}. Same LAN/Wi-Fi. No G1 forwarding.\nLog: {output}", flush=True)
            try:
                while not seconds or time.monotonic() - start < seconds:
                    try:
                        raw, peer = sock.recvfrom(8193)
                        received = time.monotonic()
                        reply = recorder.handle(raw, peer, received)
                        # Replies go only to the source of discovery/data, never G1/control ports.
                        sock.sendto(json.dumps(reply).encode("utf-8"), peer)
                    except socket.timeout:
                        pass
                    except ConnectionResetError:
                        # Windows reports ICMP when a discovered APK closes its UDP socket.
                        pass
                    except (ValueError, UnicodeError, TypeError, OverflowError) as error:
                        recorder.rejected += 1
                        if recorder.rejected <= 5:
                            print("REJECT:", error, flush=True)
                    now = time.monotonic()
                    if now - last_report >= 1:
                        stream.flush()
                        detail = "waiting for Quest"
                        if recorder.latest:
                            x = recorder.latest
                            detail = (f"seq={x['sequence']} L={x['left']['tracked']} R={x['right']['tracked']} "
                                      f"head={x['head_tracked']} focused={x['focused']} age={now-recorder.latest_receive_s:.2f}s")
                        print(f"accepted={recorder.accepted} rejected={recorder.rejected} {detail}", flush=True)
                        last_report = now
            except KeyboardInterrupt:
                pass
            finally:
                stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args()
    output = args.output or Path(__file__).resolve().parents[1] / "logs/test_results/quest_apk" / (time.strftime("quest_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8] + ".jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    run(output, args.seconds)


if __name__ == "__main__":
    main()
