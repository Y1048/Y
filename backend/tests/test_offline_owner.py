"""Invoke only the local memory-only owner harness with a saved packet fixture."""
import base64
import json
from pathlib import Path
import subprocess
import time
import pytest

def load_fixture():
    root=Path(__file__).resolve().parents[2]
    capture=root/"logs/test_results/twist2_vr_shadow_20260907_175950_1b96b661/samples.jsonl"
    for line in capture.read_text().splitlines():
        row=json.loads(line)
        if not row.get("payload_base64"):continue
        packet=json.loads(base64.b64decode(row["payload_base64"]))
        if packet.get("input_command_mode")=="active":break
    else:raise AssertionError("no fixture active packet")
    return root,packet

@pytest.mark.parametrize("executable",["test_offline_owner","test_owner_startup","test_offline_dispatch","test_owner_torque_fade","test_native_vr_policy_adapter"])
def test_owner_fault_latches(executable):
    root,packet=load_fixture()
    result=subprocess.run([str(root/"logs/test_results"/(executable+".exe"))],
        input=json.dumps(packet)+"\n",text=True,capture_output=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    assert "PASS " in result.stdout

def test_autonomous_timeout_without_stdin(monkeypatch):
    root,packet=load_fixture()
    monkeypatch.syspath_prepend(str(root/'experiments/twist2_right_arm_manual'))
    from run_owner_cpu_offline import Owner
    owner=Owner()
    try:
        initial=owner.call(op='init',packet=packet,wall_clock=True,dispatch=True,autonomous_tick=True)
        # No state/tick/finish requests during the wait: C++ must enforce the deadline.
        time.sleep(.06)
        stopped=owner.call(op='status')
        assert stopped['background_ticks']>0
        assert stopped['reason']=='policy_deadline',stopped
        assert stopped['commits']==0 and stopped['dispatch_count']==0
        late=owner.call(op='finish',token=initial['token'],action=[0.0]*29)
        assert not late['accepted'] and late['handoff_required'] and late['desired'] is None
        assert late['commits']==0 and late['dispatch_count']==0
    finally:
        owner.close()
    assert owner.p.returncode==0  # EOF joins the periodic thread cleanly.

def test_existing_relay_packet_reaches_native_adapter(monkeypatch):
    """Serialize through the real relay into a memory sink; no UDP or DDS."""
    root,packet=load_fixture()
    monkeypatch.syspath_prepend(str(root/'hardware/g1_arm_bridge'))
    from gate7_mink_wsl_relay import ValidateAndForward, MinkOrderGuard
    from arm_sdk_teleop_contract import Gate7ContractError
    from test_gate7_mink_wsl_relay import _packet
    class MemorySink:
        payload=None
        def sendto(self,payload,target):
            self.payload=payload
    sink=MemorySink()
    with pytest.raises(Gate7ContractError,match='invalid_command_provenance'):
        ValidateAndForward(json.dumps(packet).encode(),MinkOrderGuard(),sink,
                           ('127.0.0.1',5013),relay_token='offlineContractTest1234')
    assert sink.payload is None  # Saved simulation input must never become live.
    ValidateAndForward(_packet(1),MinkOrderGuard(),sink,
                       ('127.0.0.1',5013),relay_token='offlineContractTest1234')
    assert sink.payload is not None
    assert len(sink.payload)<=1400
    result=subprocess.run([str(root/'logs/test_results/test_native_vr_policy_adapter.exe')],
        input=sink.payload+b'\n',capture_output=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
