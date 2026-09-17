"""Path timing with sampled speed/acceleration checks and duration selection."""
import math
import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.interpolate import PchipInterpolator, CubicHermiteSpline

MAX_ACCELERATION_RAD_S2 = 10.0


def check_acceleration(peak):
    if not math.isfinite(peak) or peak < 0 or peak > MAX_ACCELERATION_RAD_S2:
        raise ValueError('reach acceleration exceeds 10 rad/s^2 or is invalid')


def make_timing(polynomials, seconds=2.0):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('positive finite duration required')
    u=np.linspace(0,1,100001)
    metric=np.max(np.abs(np.column_stack([p.deriv()(u) for p in polynomials])),axis=1)
    if np.min(metric)<=1e-8:
        raise ValueError('stationary path segment needs separate timing')
    arc=cumulative_trapezoid(metric,u,initial=0)
    length=float(arc[-1]);cap=math.radians(44.94)
    ramp=seconds-length/cap
    if not 0<ramp<=seconds/2:
        raise ValueError(f'duration incompatible with cruise profile; speed-only lower bound={length/(math.pi/4):.6f}s')
    inverse=PchipInterpolator(arc,u)
    times=np.linspace(0,seconds,round(seconds*500)+1)
    def ramp_distance(t):return cap/2*(t-ramp/math.pi*np.sin(math.pi*t/ramp))
    distance=np.where(times<ramp,ramp_distance(times),
        np.where(times>seconds-ramp,length-ramp_distance(seconds-times),cap*(times-ramp/2)))
    velocity=np.where(times<ramp,cap/2*(1-np.cos(math.pi*times/ramp)),
        np.where(times>seconds-ramp,cap/2*(1-np.cos(math.pi*(seconds-times)/ramp)),cap))
    values=inverse(np.clip(distance,0,length));slopes=inverse(np.clip(distance,0,length),1)*velocity
    values[0]=0;values[-1]=1;slopes[0]=slopes[-1]=0
    interpolation=CubicHermiteSpline(times,values,slopes)
    return interpolation,times,values,slopes,dict(
        speed_only_lower_bound_s=length/(math.pi/4),ramp_seconds=ramp,
        metric_length_rad=length,cruise_peak_deg_s=44.94)


def choose_timing(polynomials):
    """First passing 2-ms duration in this cosine-ramp profile family.

    This is a sampled search, not a continuous-time optimality proof.
    Fail explicitly if this family cannot attain cruise speed within the caps.
    """
    u=np.linspace(0,1,100001)
    derivatives=np.column_stack([p.deriv()(u) for p in polynomials])
    metric=np.max(np.abs(derivatives),axis=1)
    if not np.isfinite(metric).all() or np.min(metric)<=1e-8:
        raise ValueError('invalid or stationary path')
    cruise_seconds=float(cumulative_trapezoid(metric,u,initial=0)[-1])/math.radians(44.94)
    first=math.floor(cruise_seconds*500)+1
    last=math.floor(2*cruise_seconds*500)
    if last-first>10000:
        raise ValueError('duration search exceeds bounded offline budget')
    for ticks in range(first,last+1):
        seconds=ticks/500
        result=make_timing(polynomials,seconds)
        timing=result[0]
        times=np.linspace(0,seconds,20001)
        parameter=timing(times);speed=timing(times,1);accel=timing(times,2)
        dq=np.column_stack([p.deriv()(parameter) for p in polynomials])*speed[:,None]
        ddq=(np.column_stack([p.deriv(2)(parameter) for p in polynomials])*speed[:,None]**2
             +np.column_stack([p.deriv()(parameter) for p in polynomials])*accel[:,None])
        peak_v=float(np.max(np.abs(dq)));peak_a=float(np.max(np.abs(ddq)))
        if (np.isfinite(dq).all() and np.isfinite(ddq).all()
                and peak_v<=math.pi/4 and peak_a<=MAX_ACCELERATION_RAD_S2):
            result[-1].update(selection='first passing 2-ms profile candidate; sampled, not globally optimal',
                              duration_candidates=ticks-first+1,
                              checked_peak_speed_rad_s=peak_v,checked_peak_acceleration_rad_s2=peak_a)
            return result
    raise ValueError('no cruise-reaching profile satisfies speed and acceleration limits')
