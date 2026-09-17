"""Actual PC emitter -> relay validation -> C++ sink via pipes, no network."""
import json,math,subprocess,time
from types import SimpleNamespace as N
from test_mink_live_cycle_bridge import BridgeTests,ROOT,validate

def run(profile):
 b=BridgeTests().make();b.profile=profile;b.dt=.02
 proc=subprocess.Popen([str(ROOT/'logs/test_results/mink_live_cycle_stdio_test.exe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 home=[0.]*29;measured=home.copy();seq=0;last=None;lag_checked=False
 proc.stdin.write(json.dumps(dict(home=home,profile=profile))+'\n');proc.stdin.flush()
 def send(state,epoch,q,active):
  nonlocal seq,last,measured
  p=BridgeTests().packet();p['right_arm']['active']=active;p['right_arm']['joints']=[q]+[0.]*6
  b.send(p,N(return_state=state,return_epoch=epoch));packet=b.sock.sent[-1];validate(packet,profile);seq+=1
  proc.stdin.write(json.dumps(dict(now=seq*.02,q=measured,dq=[0.]*29,packet=packet))+'\n');proc.stdin.flush()
  line=proc.stdout.readline()
  if not line:raise RuntimeError(proc.stderr.read())
  last=json.loads(line);assert last['accepted'],last
  assert last['q'][:22]==home[:22]
  b.ack=dict(last,relay_token=b.token,profile=profile);b.ack_time=time.monotonic()
  return last
 try:
  send('ready',0,0,False);send('ready',0,0,True)
  for n in range(1,201):
   q=.01*(1-math.cos(math.pi*n/100))
   state='ready' if n<100 else 'returning';epoch=0 if n<100 else 1
   send(state,epoch,q,True);measured=last['q'].copy()
  measured[22]=.1
  for _ in range(40):
   send('returning',1,0,True);assert last['state']=='returning';assert not b.can_ack(1,'test')
  lag_checked=True;measured=home.copy()
  for _ in range(40):
   send('returning',1,0,True)
   if b.can_ack(1,'test'):break
  assert b.can_ack(1,'test')
  # ACK does not itself enable motion. A new idle then active is still required.
  send('await_idle',1,0,False);send('ready',1,0,True);assert last['state']=='tracking'
  return dict(profile=profile,packets=seq,measured_lag_blocks_ack=lag_checked,reengaged=True)
 finally:
  proc.stdin.close();proc.wait(timeout=5)
  for pipe in (proc.stdout,proc.stderr):pipe.close()
report=dict(offline_only=True,cases=[run(p) for p in ('yesterday','today')],publisher_created=False,physical_safety_validated=False)
(ROOT/'logs/test_results/mink_live_cycle_protocol_replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
