"""File-only tests. Saved robot bytes use explicit synthetic test timestamps."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"experiments/twist2_right_arm_manual"))
from lowstate_seed_writer import SeedWriter,ReadSeed
from supply_lowstate_seed_readonly import JointNames

def Bytes():
    return bytes.fromhex(next(json.loads(x)["packed_hex"] for x in
        (ROOT/"logs/test_results/twist2_hg_readonly_capture_20260907.jsonl").read_text().splitlines()
        if "packed_hex" in x))

def test_write_replace_expiry_cleanup():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"seed.json";names=JointNames()
        writer=SeedWriter(path,"test-session",names)
        writer.write(Bytes(),100.,100.01)
        before=ReadSeed(path,"test-session",names,now=100.02)
        writer.write(Bytes(),100.1,100.11)
        after=ReadSeed(path,"test-session",names,now=100.12)
        assert before["q"]==after["q"]
        assert after["received_at_unix_s"]==100.1
        assert list(Path(d).iterdir())==[path]
        with pytest.raises(ValueError):ReadSeed(path,"test-session",names,now=100.351)
        writer.invalidate()
        assert not path.exists()

@pytest.mark.parametrize("failure",["crc","stale","receipt","replace"])
def test_failure_removes_previous_seed_and_temp(failure):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"seed.json"
        writer=SeedWriter(path,"test-session",JointNames())
        writer.write(Bytes(),100.,100.01)
        raw=Bytes();received=100.1;now=100.11
        if failure=="crc":raw=b"\xff"+raw[1:]
        if failure=="stale":now=101.
        if failure=="receipt":received=100.
        if failure=="replace":
            with patch("lowstate_seed_writer.os.replace",side_effect=OSError("test failure")):
                with pytest.raises(OSError):writer.write(raw,received,now)
        else:
            with pytest.raises(ValueError):writer.write(raw,received,now)
        assert list(Path(d).iterdir())==[]

def test_never_adopts_existing_seed():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"seed.json";path.write_text("other writer")
        with pytest.raises(FileExistsError):SeedWriter(path,"session",JointNames())
        assert path.read_text()=="other writer"
