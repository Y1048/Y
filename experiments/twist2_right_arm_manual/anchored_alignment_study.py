"""Memory-only relative alignment hypothesis, not a live input validator/controller.

Caller must supply already validated input and an independently approved body-ready
decision. This study does not establish either. It has no transport or SDK imports.
"""
import math

LOWER = (-3.0892, -2.2515, -2.618, -1.0472, -1.97222, -1.61443, -1.61443)
UPPER = (2.6704, 1.5882, 2.618, 2.0944, 1.97222, 1.61443, 1.61443)


class AnchoredAlignmentStudy:
    def __init__(self, command, now):
        if len(command) != 29 or not all(math.isfinite(x) for x in command):
            raise ValueError('invalid_command')
        if not math.isfinite(now) or now < 0:
            raise ValueError('invalid_time')
        if any(not lo+.05 <= q <= hi-.05 for q, lo, hi in zip(command[22:], LOWER, UPPER)):
            raise ValueError('command_limit')
        self.start = tuple(command)
        self.target = tuple(command)
        self.anchor = None
        self.session = None
        self.sequence = -1
        self.last_tick = now
        self.last_packet = None
        self.reason = ''

    def stop(self, reason):
        if not self.reason:
            self.reason = reason
        return self.target

    def tick(self, now, *, goal=None, measured=None, state_receipt=None,
             session=None, sequence=None, body_ready=False, event='active'):
        if self.reason:
            return self.target
        if not math.isfinite(now) or now <= self.last_tick:
            return self.stop('invalid_clock')
        dt = min(now-self.last_tick, .02)
        self.last_tick = now
        if self.last_packet is not None and now-self.last_packet > .25:
            return self.stop('timeout')
        if event != 'active':
            return self.stop('disengage' if event == 'disengage' else 'input_error')
        if goal is None:
            return self.target  # Missing updates freeze, even before timeout.
        if not body_ready:
            return self.stop('body_not_ready')
        if not isinstance(session, str) or not session or (self.session is not None and session != self.session):
            return self.stop('session_error')
        if type(sequence) is not int or sequence <= self.sequence:
            return self.stop('sequence_error')
        if (measured is None or len(measured) != 7 or len(goal) != 7
                or not all(math.isfinite(x) for x in tuple(measured)+tuple(goal))):
            return self.stop('nonfinite_or_shape')
        if (state_receipt is None or not math.isfinite(state_receipt)
                or state_receipt < 0 or not 0 <= now-state_receipt <= .02):
            return self.stop('stale_state')
        if any(not lo+.05 <= q <= hi-.05 for values in (goal, measured)
               for q, lo, hi in zip(values, LOWER, UPPER)):
            return self.stop('joint_limit')
        if self.anchor is None:
            if any(abs(g-q) > .025 for g, q in zip(goal, measured)):
                return self.stop('initial_mismatch')
            self.anchor = tuple(goal)
            self.session = session
            self.sequence = sequence
            self.last_packet = now
            return self.target  # Do not replace the current command with measured q.
        mapped = tuple(self.start[i+22] + g-a for i, (g, a) in enumerate(zip(goal, self.anchor)))
        if any(abs(g-a) > math.radians(10) for g, a in zip(goal, self.anchor)):
            return self.stop('relative_limit')
        if any(not lo+.05 <= q <= hi-.05 for q, lo, hi in zip(mapped, LOWER, UPPER)):
            return self.stop('mapped_limit')
        arm = tuple(q + math.copysign(min(abs(g-q), .08*dt), g-q)
                    for q, g in zip(self.target[22:], mapped))
        self.target = self.start[:22] + arm
        self.sequence = sequence
        self.last_packet = now
        return self.target
