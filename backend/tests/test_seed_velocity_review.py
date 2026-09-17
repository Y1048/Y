import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"experiments/twist2_right_arm_manual"))
from review_seed_velocity import JointStats,TriggerWindow

def test_trigger_context_clipping_and_no_event():
    times=[0,.5,1,1.5,2,2.5,3]
    velocities=[[0] for _ in times];velocities[3]=[.2]
    result=TriggerWindow(times,velocities)
    assert result["first_sequence"]==2 and result["last_sequence"]==6
    assert result["pre_span_s"]==1 and result["post_span_s"]==1
    assert result["joint_velocities"]==[dict(index=0,dq=.2)]
    assert TriggerWindow([0],[[.1]]) is None
    result=TriggerWindow([0,.5],[[.2],[0]])
    assert result["pre_span_s"]==0 and result["post_span_s"]==.5

def test_spikes_runs_and_gap_are_distinct():
    r=JointStats([0,.01,.02,.03,.1,.11],[0,.001,.002,.002,.003,.004],[.1,.2,.3,0,.4,.5])
    assert r["exceed_samples"]==4
    assert r["sampled_exceed_runs"]==2
    assert r["longest_sampled_exceed_span_s"]==pytest.approx(.01)
    assert r["q_range_rad"]==.004
    r=JointStats([0,.1],[0,0],[.2,.2])
    assert r["sampled_exceed_runs"]==2
    assert r["longest_sampled_exceed_span_s"]==0

@pytest.mark.parametrize("times,q,dq",[([0,0],[0,0],[0,0]),([0],[0],[float('nan')]),([],[],[])])
def test_bad_data_rejected(times,q,dq):
    with pytest.raises(ValueError):JointStats(times,q,dq)
