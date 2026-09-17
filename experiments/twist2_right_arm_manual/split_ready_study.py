"""Offline readiness hypothesis. Never imported by native control or transport.

Limits must be explicitly supplied. A settled candidate is not physical approval.
External checks represent the unchanged caller safety checks, not replacements.
"""
from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Limits:
    window_s: float
    joint_excursion: float
    attitude_excursion: float
    speed: float
    gyro: float
    attitude: float


class SplitReadyStudy:
    def __init__(self, limits):
        if not all(math.isfinite(v) and v>0 for v in vars(limits).values()):
            raise ValueError('invalid_study_limits')
        self.limits=limits
        self.window=deque()
        self.reason=''
        self.candidate=False
        self.previous=None
        self.latest=None

    def stop(self, reason):
        if not self.reason:self.reason=reason
        self.candidate=False
        self.window.clear()
        return 'stopped'

    def update(self, now, receipt, q, dq, rpy, gyro, target, *, r1,
               stop_button, external_checks_passed, blend_complete):
        if self.reason:return 'stopped'
        self.candidate=False
        if not r1 or stop_button:return self.stop('operator_stop')
        if not external_checks_passed:return self.stop('external_safety_stop')
        if tuple(map(len,(q,dq,rpy,gyro,target)))!=(29,29,3,3,29):
            return self.stop('shape')
        values=[now,receipt]+list(q)+list(dq)+list(rpy)+list(gyro)+list(target)
        if not all(math.isfinite(v) for v in values):return self.stop('nonfinite')
        if receipt<0 or not 0<=now-receipt<=.02:return self.stop('stale_state')
        if self.previous is not None and (now<=self.previous[0] or receipt<=self.previous[1]):
            return self.stop('nonadvancing_time')
        if self.previous is not None and receipt-self.previous[1]>.05:self.window.clear()
        self.previous=(now,receipt)
        self.latest=(tuple(q),receipt)
        if any(abs(q[i]-target[i])>.25 or abs(dq[i])>1.5 for i in range(12,29)):
            return self.stop('upper_tracking_stop')
        lim=self.limits
        quiet=(blend_complete and max(map(abs,dq))<=lim.speed
               and max(map(abs,gyro))<=lim.gyro
               and max(abs(rpy[0]),abs(rpy[1]))<=lim.attitude)
        if not quiet:
            self.window.clear()
            return 'waiting_motion'
        self.window.append((receipt,tuple(q),tuple(rpy)))
        while len(self.window)>1 and self.window[1][0]<=receipt-lim.window_s:
            self.window.popleft()
        if receipt-self.window[0][0]<lim.window_s:return 'waiting_window'
        qspan=max(max(r[1][i] for r in self.window)-min(r[1][i] for r in self.window) for i in range(29))
        # Roll/pitch only; gyro handles yaw motion without Euler wrap artifacts.
        span=max(max(r[2][i] for r in self.window)-min(r[2][i] for r in self.window) for i in range(2))
        self.candidate=qspan<=lim.joint_excursion and span<=lim.attitude_excursion
        return 'settled_candidate' if self.candidate else 'waiting_drift'

    def initial_alignment(self, goal, now):
        if self.reason:return False
        if not self.candidate:return False
        if (not math.isfinite(now) or not 0<=now-self.latest[1]<=.02):
            self.stop('stale_alignment');return False
        if len(goal)!=7 or not all(math.isfinite(g) for g in goal):
            self.stop('invalid_goal');return False
        if any(abs(g-q)>.025 for g,q in zip(goal,self.latest[0][22:])):
            self.stop('initial_mismatch');return False
        return True  # Diagnostic only; does not generate a command or bypass input validation.
