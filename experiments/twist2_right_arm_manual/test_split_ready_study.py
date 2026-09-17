import pytest
from split_ready_study import Limits, SplitReadyStudy


def gate():return SplitReadyStudy(Limits(1,.005,.01,.1,.1,.15))


def feed(g,t,**overrides):
    values=dict(now=t,receipt=t,q=[0]*29,dq=[0]*29,rpy=[0]*3,gyro=[0]*3,
                target=[.03]*29,r1=True,stop_button=False,external_checks_passed=True,blend_complete=True)
    values.update(overrides)
    return g.update(**values)


def settle(g):
    for i in range(1,61):feed(g,i*.02)


def test_static_load_offset_and_alignment_are_separate():
    g=gate();settle(g)
    assert g.candidate and g.initial_alignment([0]*7,1.2)
    assert not g.initial_alignment([.03]*7,1.2)
    assert g.reason=='initial_mismatch'


def test_slow_drift_blocks_even_when_velocity_reports_zero():
    g=gate()
    for i in range(1,61):
        q=[0]*29;q[4]=i*.0002
        feed(g,i*.02,q=q)
    assert not g.candidate and not g.reason


@pytest.mark.parametrize('change,reason',[
    ({'r1':False},'operator_stop'),({'stop_button':True},'operator_stop'),
    ({'external_checks_passed':False},'external_safety_stop'),
    ({'receipt':0},'stale_state'),({'q':[float('nan')]*29},'nonfinite'),
    ({'target':[.26]*29},'upper_tracking_stop')])
def test_stop_stays_latched(change,reason):
    g=gate();settle(g);feed(g,1.22,**change)
    assert g.reason==reason and feed(g,1.24)=='stopped'
    assert not g.initial_alignment([0]*7,1.24)


def test_motion_and_gap_restart_window():
    g=gate();settle(g)
    feed(g,1.22,gyro=[.2,0,0]);assert not g.candidate
    feed(g,1.24);assert not g.candidate
    feed(g,2.5);assert not g.candidate


def test_stale_alignment_stops():
    g=gate();settle(g)
    assert not g.initial_alignment([0]*7,1.3)
    assert g.reason=='stale_alignment'
