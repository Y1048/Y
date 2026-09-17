import pytest
from compare_feedback_recorded_offline import Gyro


def test_recorded_gyro_order_sign_and_scale():
    assert Gyro(dict(gyro_x_rad_s='1',gyro_y_rad_s='-2',gyro_z_rad_s='.5')) == ([.25,-.5,.125],'recorded_policy_state')


def test_missing_is_explicit_and_partial_is_rejected():
    assert Gyro({})[1]=='missing_assumed_zero'
    with pytest.raises(ValueError,match='partial'):Gyro(dict(gyro_x_rad_s=0))


def test_nonfinite_is_rejected():
    with pytest.raises(ValueError,match='nonfinite'):
        Gyro(dict(gyro_x_rad_s='nan',gyro_y_rad_s=0,gyro_z_rad_s=0))
