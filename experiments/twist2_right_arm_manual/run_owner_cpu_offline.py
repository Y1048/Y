"""Actual CPU model -> synthetic memory-only owner via local pipes. No robot IO."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
from pathlib import Path
import queue
import subprocess
import threading
import time
from policy_worker_client_offline import PolicyWorkerClient

ROOT=Path(__file__).resolve().parents[2]
class Owner:
    def __init__(self):
        self.p=subprocess.Popen([str(ROOT/'logs/test_results/owner_policy_stdio.exe')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        self.replies=queue.Queue()
        def Read():
            for line in self.p.stdout:self.replies.put(line)
            self.replies.put(None)
        self.reader=threading.Thread(target=Read,daemon=True);self.reader.start()
    def call(self,**value):
        self.p.stdin.write(json.dumps(value,allow_nan=False)+'\n');self.p.stdin.flush()
        line=self.replies.get(timeout=5)
        if line is None:raise RuntimeError('owner_eof')
        return json.loads(line)
    def close(self):
        self.p.stdin.close()
        try:self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=2)
        self.reader.join(timeout=2);self.p.stdout.close()

def Main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    capture=ROOT/'logs/test_results/twist2_vr_shadow_20260907_175950_1b96b661/samples.jsonl'
    for line in capture.read_text().splitlines():
        row=json.loads(line)
        if not row.get('payload_base64'):continue
        packet=json.loads(base64.b64decode(row['payload_base64']))
        if packet.get('input_command_mode')=='active':break
    else:raise ValueError('no active fixture')
    python=ROOT/'logs/diagnostics/twist2_cpu_venv/Scripts/python.exe'
    worker=PolicyWorkerClient([str(python),'-B',str(ROOT/'experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py')])
    results=[]
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            for scenario in ('normal','pinch','late'):
                owner=Owner()
                try:
                    initial=owner.call(op='init',packet=packet)
                    def Infer():
                        start=time.perf_counter();reply=worker.infer(initial['observation'])
                        return reply,time.perf_counter()-start
                    future=pool.submit(Infer)
                    # Deterministic simulated events during an outstanding request.
                    # No claim of hard real-time concurrency on the Windows host.
                    state=owner.call(op='state',now=2.024)
                    interrupted=None
                    if scenario=='pinch':
                        release=dict(packet,input_command_mode='pinch_disengaged')
                        interrupted=owner.call(op='vr',packet=release,now=2.025)
                    if scenario=='late':interrupted=owner.call(op='tick',now=2.032)
                    reply,duration=future.result(timeout=5)
                    # Account for measured worker turnaround; injected events also precede Finish.
                    finish_at=2.02+max(duration,.006 if scenario!='late' else .013)
                    finish=owner.call(op='finish',token=initial['token'],action=reply['action'],now=finish_at)
                    tick=owner.call(op='tick',now=finish_at+.002)
                    expected='' if scenario=='normal' else ('input_disengaged' if scenario=='pinch' else 'policy_deadline')
                    passed=(finish['reason']==expected and finish['commits']==(1 if scenario=='normal' else 0)
                        and tick['accepted']==(scenario=='normal') and state['request_state']==initial['request_state']
                        and state['latest_state']>initial['latest_state'])
                    results.append(dict(scenario=scenario,passed=passed,worker_roundtrip_ms=duration*1000,
                        worker_request_id=reply['request_id'],owner_token=initial['token'],state_update=state,
                        interrupted=interrupted,finish=finish,tick=tick))
                finally:owner.close()
    finally:worker.close()
    report=dict(offline_only=True,robot_output=False,synthetic_state=True,
        event_clock='deterministic with measured worker duration; not a live scheduler',
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            capture,ROOT/'logs/test_results/owner_policy_stdio.exe',
            ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt')},results=results)
    with args.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps([dict(scenario=r['scenario'],passed=r['passed'],worker_ms=r['worker_roundtrip_ms'],
        reason=r['finish']['reason']) for r in results],indent=2))
    if not all(r['passed'] for r in results):raise SystemExit(1)

if __name__=='__main__':Main()
