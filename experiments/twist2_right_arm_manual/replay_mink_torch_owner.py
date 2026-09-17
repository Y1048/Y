"""Verified TorchScript -> observation history -> new C++ owner, local pipes only."""
import io,json,math,subprocess,time,argparse,hashlib
from pathlib import Path
import torch
from offline_policy_adapter import ReadVerifiedPolicy,EXPECTED_SHA256
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--combined',action='store_true')
parser.add_argument('--dynamics',action='store_true')
args=parser.parse_args()
if args.dynamics:args.combined=True
torch.set_num_threads(1)
model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt')),map_location='cpu').eval()
with torch.inference_mode():
 for _ in range(10):model(torch.zeros((1,1432),dtype=torch.float32))
process=subprocess.Popen([str(ROOT/'logs/test_results/mink_torch_owner_stdio_offline.exe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
latest_state=None
physics=None
if args.dynamics:
 physics=subprocess.Popen(['py','-3.11','-B',str(Path(__file__).with_name('mujoco_feedback_offline.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def exchange(packet):
 global latest_state
 process.stdin.write(json.dumps(packet,allow_nan=False)+'\n');process.stdin.flush()
 while True:
  line=process.stdout.readline()
  if not line:raise RuntimeError(process.stderr.read())
  reply=json.loads(line)
  if not reply.get('dynamics'):return reply
  if physics is None:raise RuntimeError('unexpected dynamics callback')
  physics.stdin.write(json.dumps(reply,allow_nan=False)+'\n');physics.stdin.flush()
  state=physics.stdout.readline()
  if not state:raise RuntimeError(physics.stderr.read())
  latest_state=json.loads(state)
  process.stdin.write(state);process.stdin.flush()
results=[];trace=[];iterations=50;initial_reference=None;fixture_hash=None
if args.combined:
 payload=(ROOT/'logs/test_results/mink_resampler_generated_offline.json').read_bytes()
 fixture_hash=hashlib.sha256(payload).hexdigest()
 fixture=json.loads(payload)['batch']
 initial_reference=exchange(dict(op='configure_combined',home=fixture['home'],samples=fixture['samples'],dynamics=args.dynamics))['ready']
 iterations=int((len(fixture['samples'])/60.-.04)/.02)

failure=None
try:
 with torch.inference_mode():
  for index in range(iterations):
   request=exchange(dict(op='begin',tick=index*10))
   if args.dynamics:
    obs=request['observation'];state=latest_state
    # Verify actual MuJoCo -> native CRC decoder -> C++ observation mapping.
    default=[-.2,0,0,.4,-.2,0]*2+[0]*3+[0,.4,0,1.2,0,0,0]+[0,-.4,0,1.2,0,0,0]
    expected=[v*.25 for v in state['gyro']]+state['rpy'][:2]+[q-d for q,d in zip(state['q'],default)]+[0 if i in (4,5,10,11) else v*.05 for i,v in enumerate(state['dq'])]
    assert all(abs(a-b)<1e-5 for a,b in zip(obs[35:98],expected)), 'dynamics observation mapping'
   start=time.perf_counter();tensor=torch.tensor([request['observation']],dtype=torch.float32)
   if tensor.shape!=(1,1432) or not torch.isfinite(tensor).all():raise ValueError('observation')
   raw=model(tensor)
   if raw.shape!=(1,29) or raw.dtype!=torch.float32 or not torch.isfinite(raw).all():raise ValueError('output')
   action=raw.clamp(-2,2).tolist()[0];elapsed=(time.perf_counter()-start)*1000
   latency=0 if index==0 else max(1,math.ceil(elapsed/2))
   result=exchange(dict(op='finish',action=action,latency_ticks=latency))
   assert result['accepted'] and result['history_commits']==index+1
   trace.extend(result.get('trace',[]))
   results.append(dict(index=index,request_id=request['request_id'],state_sequence=request['state_sequence'],compute_ms=elapsed,logical_latency_ticks=latency,outputs=result['outputs'],q=result['q']))
 process.stdin.close();assert process.wait(timeout=5)==0
except Exception as exc:
 failure=str(exc)
finally:
 report=dict(output_count_scope='last completed policy response; failure may follow additional ticks',offline_only=True,torch_version=torch.__version__,policy_sha256=EXPECTED_SHA256,
  actual_model_inferences=len(results),output_ticks=results[-1]['outputs'] if results else 0,history_commits=len(results),
  compute_ms_max=max((r['compute_ms'] for r in results),default=0),compute_over_20ms=sum(r['compute_ms']>20 for r in results),
  dynamics_leg_blend_seconds=4 if args.dynamics else None,input='mujoco_dynamics' if args.dynamics else 'synthetic_native_state_follows_previous_reference_zero_dq',failure=failure,geometry_checked=False,
  bootstrap='logical output epoch begins after initial inference',
  timing='measured CPU durations rounded up to 2ms in logical scheduler; IPC and wall scheduling not validated',
  publisher_created=False,physical_safety_validated=False,combined_arm_fixture=args.combined,initial_reference=initial_reference,arm_fixture_sha256=fixture_hash,results=results,trace=trace)
 (ROOT/('logs/test_results/mink_torch_dynamics_replay.json' if args.dynamics else 'logs/test_results/mink_torch_combined_replay.json' if args.combined else 'logs/test_results/mink_torch_owner_replay.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k not in ('results','trace')}))
 if physics is not None:
  physics.stdin.close()
  try:physics.wait(timeout=10)
  except subprocess.TimeoutExpired:physics.kill();physics.wait(timeout=5)
  for pipe in (physics.stdout,physics.stderr):pipe.close()
 if process.poll() is None:process.kill();process.wait(timeout=5)
 for pipe in (process.stdin,process.stdout,process.stderr):pipe.close()

if failure:raise SystemExit(1)
