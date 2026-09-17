import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"experiments/twist2_right_arm_manual"))
from compare_seed_windows_offline import Metrics

def test_spike_and_drift_are_separate():
    t=np.arange(201)*.001;q=np.zeros((201,29));dq=q.copy()
    dq[100,21]=.15;q[:,2]=np.linspace(0,.02,201)
    m=Metrics(t,q,dq)
    assert m["peak"]==.15 and m["p99"]==0
    assert m["fraction"]==pytest.approx(1/201)
    assert m["q_range"]==.02

@pytest.mark.parametrize("case",["gap","reverse","nan"])
def test_invalid_windows_rejected(case):
    t=np.array([0.,.01]);q=np.zeros((2,29));dq=q.copy()
    if case=="gap":t[1]=.03
    if case=="reverse":t[1]=0
    if case=="nan":dq[0,0]=np.nan
    with pytest.raises(ValueError):Metrics(t,q,dq)
