from review_ready_components import Review


def row(t):
    result = dict(elapsed_s=t, alpha=1, state_age_ms=1, roll_rad=0, pitch_rad=0)
    for i in range(29):
        result.update({f'q_{i}': 0, f'dq_{i}': 0, f'desired_target_{i}': 0})
    return result


def test_load_error_is_separate_but_arm_error_still_blocks():
    rows = [row(i*.02) for i in range(60)]
    for r in rows:
        r['desired_target_4'] = .4
        r['desired_target_23'] = .03
    result = Review(rows)
    assert result['components']['body_attitude_velocity_proxy']['longest_sampled_run_s'] > 1
    assert result['components']['current_all29']['passing_samples'] == 0
    assert result['components']['right_arm_tracking']['passing_samples'] == 0
    assert result['components']['split_proxy_and_right']['passing_samples'] == 0
    assert result['physical_ready'] is False


def test_uses_previous_target_not_current_target():
    a, b = row(0), row(.02)
    b['desired_target_23'] = 1
    assert Review([a,b])['components']['right_arm_tracking']['passing_samples'] == 1


def test_gap_and_invalid_state_break_sampled_run():
    rows = [row(i*.02) for i in range(110)]
    rows[30]['q_0'] = float('nan')
    rows[60]['state_age_ms'] = 21
    rows[90]['elapsed_s'] += .1
    result = Review(rows)
    assert result['components']['current_all29']['longest_sampled_run_s'] < 1
    assert result['physical_ready'] is False
