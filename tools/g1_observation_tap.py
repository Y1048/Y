"""Opt-in loopback observation copy; never sends a robot command.

The port is deliberately fixed outside every control protocol. Failed/dropped
copies do not change the producer's result. No socket exists unless enabled.
"""
import json
import math
import os
import socket
import uuid

ADDRESS = ('127.0.0.1', 55071)
UNITY_HEADING_ADDRESS = ('127.0.0.1', 55072)
SCHEMA = 'g1.observation.source.v1'


def next_deadline(previous, now, period):
    """Advance the clock grid, skipping missed slots instead of bursting."""
    deadline = previous + period
    missed = 0
    if deadline <= now:
        missed = int(math.floor((now-deadline)/period)) + 1
        deadline += missed * period
    return deadline, missed


class ObservationTap:
    def __init__(self, stream):
        if stream not in ('arm', 'omni'):
            raise ValueError('observation stream')
        self.stream = stream
        self.session = uuid.uuid4().hex
        self.sequence = 0
        self.dropped = 0
        self.error = None
        self.visual_dropped = 0
        self.sock = None
        if os.environ.get('G1_OBSERVATION_TAP') == '1':
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.setblocking(False)
                if hasattr(socket, 'SIO_UDP_CONNRESET'):
                    self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            except OSError as error:
                self.error = str(error)
                self.dropped += 1
                self.close()

    def publish(self, values, source_monotonic_s):
        if self.sock is None:
            return False
        sequence = self.sequence
        self.sequence += 1
        try:
            if not math.isfinite(source_monotonic_s) or source_monotonic_s < 0:
                raise ValueError('source timestamp')
            raw = json.dumps(dict(schema=SCHEMA, observation_only=True,
                stream=self.stream, session=self.session, sequence=sequence,
                source_monotonic_s=source_monotonic_s, values=values,
                producer_dropped=self.dropped), allow_nan=False,
                separators=(',', ':')).encode('utf-8')
            if len(raw) > 6000:
                raise ValueError('observation packet budget')
            self.sock.sendto(raw, ADDRESS)
            if self.stream == 'omni' and os.environ.get('G1_OMNI_UNITY_HEADING') == '1':
                # Independent view-only copy. Failure must not change audit delivery.
                try:
                    yaw = values['arm_yaw_deg']
                    if type(yaw) not in (int, float) or not math.isfinite(yaw):
                        raise ValueError('heading')
                    view = json.dumps(dict(schema='g1.omni.unity.heading.v1',
                        session=self.session, sample=[sequence, source_monotonic_s, yaw]),
                        allow_nan=False, separators=(',', ':')).encode('utf-8')
                    self.sock.sendto(view, UNITY_HEADING_ADDRESS)
                except (OSError, KeyError, ValueError, TypeError):
                    self.visual_dropped += 1
            return True
        except (OSError, ValueError, TypeError, OverflowError):
            self.dropped += 1
            return False

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
