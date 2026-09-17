"""Local tests only. Historical capture is timestamped with an injected test clock."""
import json
from pathlib import Path
import sys
import tempfile
import pytest
import mujoco
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"MuJoCo_G1_Controller/scripts"))
import g1_right_arm_common as g1
from g1_lowstate_seed import ReadSeed,ApplySeed

def Seed():
    source=ROOT/"logs/test_results/twist2_hg_readonly_capture_20260907.jsonl"
    row=next(json.loads(x) for x in source.read_text().splitlines() if "packed_hex" in x)
    return dict(schema="g1.mink.lowstate_seed.v1",session_id="synthetic-test-session",
        joint_names=g1.G1_29_JOINT_NAMES,received_at_unix_s=100.,
        representation="sdk_crc_packed_le2092_b95a5304",packed_hex=row["packed_hex"])

def Load(value,now=100.01,session="synthetic-test-session"):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"seed.json";path.write_text(json.dumps(value))
        return ReadSeed(path,session,g1.G1_29_JOINT_NAMES,now=now)

def test_all_29_joint_mapping_and_base_unchanged():
    seed=Load(Seed())
    model=mujoco.MjModel.from_xml_path(str(g1.G1_XML))
    original=model.qpos0.copy()
    q=ApplySeed(model,original,seed,g1.G1_29_JOINTS)
    addresses=[int(model.jnt_qposadr[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,n)])
               for n in g1.G1_29_JOINTS]
    assert list(q[addresses])==seed["q"]
    unused=[i for i in range(model.nq) if i not in addresses]
    assert np.array_equal(q[unused],original[unused])
    assert np.array_equal(original,model.qpos0)

@pytest.mark.parametrize("case",["stale","future","session","order","crc","size","schema","representation"])
def test_rejected_seed(case):
    value=Seed();now=100.01;session="synthetic-test-session"
    if case=="stale":now=100.251
    if case=="future":now=99.99
    if case=="session":session="different"
    if case=="order":value["joint_names"]=list(reversed(value["joint_names"]))
    if case=="crc":value["packed_hex"]="ff"+value["packed_hex"][2:]
    if case=="size":value["packed_hex"]=value["packed_hex"][:-2]
    if case=="schema":value["schema"]="mink_simulation"
    if case=="representation":value["representation"]="DDS_CDR"
    with pytest.raises(ValueError):Load(value,now,session)

def test_reject_model_limits_atomically():
    seed=Load(Seed())
    model=mujoco.MjModel.from_xml_path(str(g1.G1_XML));original=model.qpos0.copy()
    seed["q"][28]=100
    with pytest.raises(ValueError):ApplySeed(model,original,seed,g1.G1_29_JOINTS)
    assert np.array_equal(original,model.qpos0)
