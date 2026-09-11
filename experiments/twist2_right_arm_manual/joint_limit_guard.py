"""All-joint inner-limit screening and command governor; no SDK, DDS or I/O.

Stopping-distance bounds are explicit OFFLINE ASSUMPTIONS, not identified
physical braking authority. Refusal stops the simulation; it cannot physically
stop a real robot. Never project measured q/dq or modify model joint limits.
"""
from dataclasses import dataclass
import math
import numpy as np

DOFS = 29
RESERVE_RAD = 0.05
REACTION_S = 0.02
BRAKE_RAD_S2 = 1.0
OUTWARD_ACCEL_RAD_S2 = 2.0
EPS = 1e-10


def vector(value, name):
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (DOFS,) or not np.isfinite(result).all():
        raise ValueError(name + ' must contain 29 finite values')
    return result


class LimitViolation(ValueError):
    def __init__(self, event):
        self.event = event
        super().__init__(event['reason'])


@dataclass(frozen=True)
class JointLimitEnvelope:
    hard_lower: np.ndarray
    hard_upper: np.ndarray
    soft_lower: np.ndarray
    soft_upper: np.ndarray
    reserve: float = RESERVE_RAD
    reaction: float = REACTION_S
    brake: float = BRAKE_RAD_S2
    outward_acceleration: float = OUTWARD_ACCEL_RAD_S2

    def __post_init__(self):
        for name in ('hard_lower','hard_upper','soft_lower','soft_upper'):
            value = vector(getattr(self, name), name)
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if (not all(math.isfinite(x) for x in (self.reserve,self.reaction,self.brake,self.outward_acceleration))
                or self.reserve < RESERVE_RAD or self.reaction < REACTION_S
                or self.brake <= 0 or self.outward_acceleration < 0):
            raise ValueError('Invalid or relaxed offline guard assumptions')
        if not (np.all(self.hard_lower < self.hard_upper)
                and np.all(self.soft_lower >= self.hard_lower)
                and np.all(self.soft_upper <= self.hard_upper)
                and np.all(self.soft_lower + 2*self.reserve < self.soft_upper)):
            raise ValueError('Empty or inconsistent hard/soft/inner limit intervals')

    @classmethod
    def from_model(cls, model, qadr, contract):
        # Resolve the actual canonical q addresses, never assume XML ordering.
        qadr = np.asarray(qadr)
        if qadr.shape != (DOFS,) or len(set(qadr.tolist())) != DOFS:
            raise ValueError('Expected unique 29-joint q addresses')
        joint_ids=[]
        for adr in qadr:
            match=np.flatnonzero(model.jnt_qposadr == adr)
            if len(match) != 1: raise ValueError('Ambiguous model joint address')
            joint_ids.append(int(match[0]))
        if not np.all(model.jnt_limited[joint_ids]):
            raise ValueError('Every canonical model joint must have limits enabled')
        ranges=model.jnt_range[joint_ids]
        onset=model.jnt_margin[joint_ids]
        if not np.isfinite(onset).all() or np.any(onset < 0):
            raise ValueError('Invalid joint-limit activation margin')
        # Hard means XML range ONLY, not a measured physical hard-stop position.
        hard_lo,hard_hi=ranges[:,0],ranges[:,1]
        soft_lo=np.maximum(contract.lower,hard_lo+onset)
        soft_hi=np.minimum(contract.upper,hard_hi-onset)
        return cls(hard_lo,hard_hi,soft_lo,soft_hi)

    @property
    def inner_lower(self): return self.soft_lower + self.reserve

    @property
    def inner_upper(self): return self.soft_upper - self.reserve

    def stop_distance(self, outward_speed):
        v=np.maximum(0.,np.asarray(outward_speed,dtype=float))
        if not np.isfinite(v).all(): raise ValueError('Non-finite stopping velocity')
        after=v+self.outward_acceleration*self.reaction
        return (v*self.reaction + .5*self.outward_acceleration*self.reaction**2
                + after**2/(2*self.brake))

    def command_step(self, proposed, previous, dt):
        """Slow commanded motion before inner limits. Never a measured-state clamp.

        Caller must exclude an altered PD reference from normal gain ranking.
        This is a kinematic command governor, not proof of motor deceleration.
        """
        proposed,previous=vector(proposed,'command'),vector(previous,'previous command')
        if not math.isfinite(dt) or not 0 < dt <= .02:
            raise ValueError('Invalid command timestep')
        dl=previous-self.inner_lower;du=self.inner_upper-previous
        if np.any(dl <= EPS) or np.any(du <= EPS):
            raise ValueError('Previous command is outside the strict inner interval')
        # Invert v*T+v^2/(2*a)<=distance, retaining reaction acceleration reserve.
        t=self.reaction; a=self.brake; aa=self.outward_acceleration
        extra=.5*aa*t*t+(aa*t)**2/(2*a)
        effective=t+aa*t/a
        speed=lambda d: np.maximum(0.,-a*effective+np.sqrt((a*effective)**2+2*a*np.maximum(d-extra,0.)))
        lo=np.maximum(self.inner_lower+EPS,previous-speed(dl)*dt)
        hi=np.minimum(self.inner_upper-EPS,previous+speed(du)*dt)
        governed=np.clip(proposed,lo,hi)
        return governed, bool(np.any(np.abs(governed-proposed) > EPS))

    def manifest(self):
        return {'schema':'g1.joint-limit-envelope.v1','joints':DOFS,
            'hard_lower':self.hard_lower.tolist(),'hard_upper':self.hard_upper.tolist(),
            'soft_lower':self.soft_lower.tolist(),'soft_upper':self.soft_upper.tolist(),
            'inner_lower':self.inner_lower.tolist(),'inner_upper':self.inner_upper.tolist(),
            'reserve_rad':self.reserve,'reaction_s':self.reaction,
            'assumed_brake_rad_s2':self.brake,'assumed_outward_acceleration_rad_s2':self.outward_acceleration,
            'physical_braking_validated':False,'hard_limit_source':'XML joint range, not measured physical hard stop'}


class JointLimitMonitor:
    def __init__(self,envelope):
        self.envelope=envelope
        self.observations=0
        self.minimum_soft=np.full(DOFS,np.inf)
        self.minimum_hard=np.full(DOFS,np.inf)
        self.minimum_stop_slack=np.full(DOFS,np.inf)
        self.minimum_soft_witness=[None]*DOFS
        self.event=None

    def fail(self,reason,stage,time_s,q=None,dq=None,joints=()):
        if self.event is None:
            self.event={'reason':reason,'stage':stage,'time_s':float(time_s),
                'joints':[int(j) for j in joints],
                'q':None if q is None else np.asarray(q).tolist(),
                'dq':None if dq is None else np.asarray(dq).tolist()}
        raise LimitViolation(self.event)

    def latched(self):
        if self.event is not None: raise LimitViolation(self.event)

    def reference(self,lower,upper,time_s=0.,stage='reference'):
        self.latched()
        lo,hi=vector(lower,'reference lower'),vector(upper,'reference upper')
        bad=np.flatnonzero((lo <= self.envelope.inner_lower+EPS)
                         | (hi >= self.envelope.inner_upper-EPS) | (lo>hi))
        if len(bad): self.fail('joint_limit_reference_refused',stage,time_s,lo,None,bad)

    def state(self,q,dq,time_s,stage):
        self.latched()
        if not math.isfinite(time_s) or time_s < 0:
            self.fail('joint_limit_invalid_time',stage,0.)
        try: q,dq=vector(q,'state q'),vector(dq,'state dq')
        except ValueError: self.fail('joint_limit_nonfinite_state',stage,time_s)
        e=self.envelope
        soft=np.minimum(q-e.soft_lower,e.soft_upper-q)
        hard=np.minimum(q-e.hard_lower,e.hard_upper-q)
        slack=np.minimum(q-e.inner_lower-e.stop_distance(-dq),
                         e.inner_upper-q-e.stop_distance(dq))
        changed=np.flatnonzero(soft<self.minimum_soft)
        for j in changed:
            self.minimum_soft_witness[j]={'time_s':float(time_s),'stage':stage,'q':float(q[j]),'dq':float(dq[j])}
        self.minimum_soft=np.minimum(self.minimum_soft,soft)
        self.minimum_hard=np.minimum(self.minimum_hard,hard)
        self.minimum_stop_slack=np.minimum(self.minimum_stop_slack,slack)
        self.observations+=1
        for reason,values in (('joint_hard_limit_reached',hard),
                              ('joint_soft_limit_reached',soft),
                              ('joint_inner_reserve_reached',soft-e.reserve),
                              ('joint_stopping_envelope_exhausted',slack)):
            bad=np.flatnonzero(values <= EPS)
            if len(bad): self.fail(reason,stage,time_s,q,dq,bad)

    def command(self,proposed,previous,dt,time_s):
        self.latched()
        governed,changed=self.envelope.command_step(proposed,previous,dt)
        if changed:
            bad=np.flatnonzero(np.abs(governed-proposed)>EPS)
            self.fail('joint_limit_command_intervention','command',time_s,proposed,None,bad)
        return governed

    def summary(self):
        array=lambda a:[float(x) if np.isfinite(x) else None for x in a]
        return {'schema':'g1.joint-limit-monitor.v1','envelope':self.envelope.manifest(),
                'observations':self.observations,'minimum_soft_margin_rad':array(self.minimum_soft),
                'minimum_hard_margin_rad':array(self.minimum_hard),
                'minimum_stopping_slack_rad':array(self.minimum_stop_slack),
                'minimum_soft_witness':self.minimum_soft_witness,'event':self.event,
                'no_intervention':self.event is None,'hardware_validated':False}
