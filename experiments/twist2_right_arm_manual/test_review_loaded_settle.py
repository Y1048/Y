import pytest
from review_loaded_settle import Review, Windows


def rows():
    result=[]
    for n in range(61):
        row=dict(elapsed_s=n*.02,alpha=1,state_age_ms=1,roll_rad=0,pitch_rad=0)
        for i in range(12,29):
            row.update({f'q_{i}':0,f'dq_{i}':0,f'desired_target_{i}':.03})
        result.append(row)
    return result


def test_stationary_offset_does_not_imply_motion_or_ready():
    result=Review(rows())
    assert result['complete_windows']>0
    assert result['metric_ranges']['maximum_upper_excursion_rad']['max']==0
    assert result['metric_ranges']['maximum_target_offset_rad']['min']==.03
    assert result['physical_ready'] is False


def test_slow_drift_visible_even_when_reported_velocity_zero():
    data=rows()
    for r in data:r['q_23']=.01*r['elapsed_s']
    assert min(w['maximum_upper_excursion_rad'] for w in Windows(data))>=.009999


@pytest.mark.parametrize('key,value', [('state_age_ms',21),('q_16',float('nan')),
    ('elapsed_s',3),('alpha',.9)])
def test_invalid_sample_breaks_window(key,value):
    data=rows();data[30][key]=value
    assert Windows(data)==[]


def test_midwindow_excursion_not_hidden_by_matching_endpoints():
    data=rows();data[30]['q_23']=.02
    assert all(w['maximum_upper_excursion_rad']==.02 for w in Windows(data))
