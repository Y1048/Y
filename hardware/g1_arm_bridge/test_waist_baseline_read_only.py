import io
import math
import pytest

from waist_baseline_read_only import Capture, Summarize


def State():
    return {"q_rad": [0.0]*29, "dq_rad_s": [0.0]*29, "mode_pr": 0, "mode_machine": 5}


def test_fresh_recording_and_summary():
    clock = [0.0]
    stream = io.StringIO()

    def Sleep(dt):
        clock[0] += dt

    def Snapshot():
        state = State()
        state["q_rad"][13] = clock[0]*0.1
        state["dq_rad_s"][13] = 0.1
        return state, round(clock[0]*30), clock[0]

    samples = Capture(Snapshot, lambda state: state, stream, duration=1,
                      monotonic=lambda: clock[0], sleep=Sleep)
    result = Summarize(samples)
    assert result["observed_duration_s"] >= 1
    assert result["waist"]["roll"]["span_deg"] == pytest.approx(math.degrees(clock[0]*0.1))
    assert result["waist"]["yaw"]["span_deg"] == 0
    assert result["hardware_authorized"] is False
    assert len(stream.getvalue().splitlines()) == len(samples)


@pytest.mark.parametrize("loss", ("initial", "stale", "absent", "invalid_age"))
def test_loss_never_completes(loss):
    clock = [0.0]
    stream = io.StringIO()

    def Sleep(dt):
        clock[0] += dt

    def Snapshot():
        if loss == "initial" or (loss == "absent" and clock[0] > 0.1):
            return None, 0, 0
        rx = math.nan if loss == "invalid_age" and clock[0] > 0.1 else 0
        return State(), 1, rx

    with pytest.raises(TimeoutError):
        Capture(Snapshot, lambda state: state, stream, duration=1, wait_s=0.4,
                monotonic=lambda: clock[0], sleep=Sleep)
    assert len(stream.getvalue().splitlines()) <= 1


def test_summary_rejects_empty_and_bad_vectors():
    with pytest.raises(ValueError):
        Summarize([])
    sample = dict(State(), elapsed_s=0, age_s=0)
    bad = dict(State(), elapsed_s=1, age_s=0)
    bad["q_rad"][12] = math.nan
    with pytest.raises(ValueError):
        Summarize([sample, bad])
