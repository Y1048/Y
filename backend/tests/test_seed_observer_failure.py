"""The file observer must preserve read failures and return failure, without DDS."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"experiments/twist2_right_arm_manual"))
import observe_seed_file_offline as observer

def test_permission_error_is_reported_and_fails(tmp_path):
    output=tmp_path/"result.json"
    argv=["observer","--seed",str(tmp_path/"seed.json"),"--session","test",
          "--output",str(output)]
    with patch.object(sys,"argv",argv), \
         patch.object(observer.time,"monotonic",side_effect=[0,0,36]), \
         patch.object(observer.time,"sleep"), \
         patch.object(observer,"ReadSeed",side_effect=PermissionError("denied")):
        with pytest.raises(SystemExit) as failure:observer.Main()
    assert failure.value.code==1
    result=json.loads(output.read_text())
    assert result["errors"]==["PermissionError: denied"]
    assert result["validated_updates"]==0
    assert result["robot_output"] is False
