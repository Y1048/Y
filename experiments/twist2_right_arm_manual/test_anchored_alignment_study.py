import csv
from pathlib import Path
import pytest
from anchored_alignment_study import AnchoredAlignmentStudy


def send(study, t, goal, sequence, **changes):
    args = dict(goal=goal, measured=goal, state_receipt=t, session='synthetic',
                sequence=sequence, body_ready=True)
    args.update(changes)
    return study.tick(t, **args)


def test_recorded_loaded_pose_first_packet_does_not_jump():
    path = Path(__file__).resolve().parents[2] / 'logs/test_results/twist2_writer_trial2_20260908.csv'
    with path.open() as stream:
        row = next(r for r in csv.DictReader(stream) if float(r['elapsed_s']) > 10)
    command = tuple(float(row[f'writer_target_{i}']) for i in range(29))
    measured = tuple(float(row[f'writer_q_{i}']) for i in range(22,29))
    assert abs(command[23]-measured[1]) > .025
    study = AnchoredAlignmentStudy(command, 0)
    assert send(study, .02, measured, 1) == command
    assert study.reason == ''  # Synthetic body-ready assumption, not a physical verdict.


def test_rate_no_overshoot_other_joints_and_fixed_anchor():
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [0]*7, 1)
    goal = [.003, -.003, 0, 0, 0, 0, 0]
    before = study.target
    for seq in range(2,6):
        after = send(study, .02*seq, goal, seq)
        assert after[:22] == (0,)*22
        assert max(abs(a-b) for a,b in zip(after,before)) <= .00160000001
        assert 0 <= after[22] <= .003 and -.003 <= after[23] <= 0
        before = after
    assert after[22:24] == (.003,-.003)
    assert study.anchor == (0,)*7


@pytest.mark.parametrize('change,reason', [
    ({'session':'other'}, 'session_error'),
    ({'sequence':1}, 'sequence_error'),
    ({'state_receipt':0}, 'stale_state'),
    ({'body_ready':False}, 'body_not_ready'),
    ({'event':'disengage'}, 'disengage'),
    ({'event':'invalid'}, 'input_error'),
])
def test_stop_latches(change, reason):
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [0]*7, 1)
    args = dict(sequence=2); args.update(change)
    before = study.target
    send(study, .04, [.01]*7, **args)
    assert study.reason == reason
    assert send(study, .06, [.02]*7, 3) == before


def test_missing_packet_freezes_then_timeout_latches():
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [0]*7, 1)
    before = study.target
    assert study.tick(.04) == before
    study.tick(.28)
    assert study.reason == 'timeout'
    assert send(study, .30, [.01]*7, 2) == before


def test_first_mismatch_and_relative_limit():
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [.03]*7, 1, measured=[0]*7)
    assert study.reason == 'initial_mismatch'
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [0]*7, 1)
    send(study, .04, [.18]*7, 2)
    assert study.reason == 'relative_limit' and study.target == (0,)*29


def test_mapped_limit_and_nonfinite_rejected_before_motion():
    command = [0]*29
    command[22] = 2.61
    study = AnchoredAlignmentStudy(command, 0)
    send(study, .02, [2.5,0,0,0,0,0,0], 1)
    send(study, .04, [2.52,0,0,0,0,0,0], 2)
    assert study.reason == 'mapped_limit' and study.target == tuple(command)
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [float('nan')]*7, 1)
    assert study.reason == 'nonfinite_or_shape'


def test_delayed_tick_does_not_accumulate_motion_budget():
    study = AnchoredAlignmentStudy([0]*29, 0)
    send(study, .02, [0]*7, 1)
    after = send(study, .20, [.1]*7, 2)
    assert max(abs(q) for q in after) <= .00160000001
