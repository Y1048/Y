"""Offline real bridge/C++ contract replay of wall-clock decimation. No network."""
import ast,json,subprocess
from types import SimpleNamespace as N
from test_mink_live_cycle_bridge import BridgeTests,ROOT
source=ROOT/'MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
condition=next(n.test for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=='live_cycle or now >= next_state')
code=compile(ast.Expression(condition),str(source),'eval')
def run(old):
 b=BridgeTests().make();b.dt=1/60
 lines=[json.dumps(dict(home=[0.]*29,profile='today'))];dt=b.dt;next_state=0.;q=0.;v=0.
 for n in range(60):
  # One short wall interval can skip a sample under the old display gate.
  now=(n+1)*dt-(.0002 if n==8 else 0.)
  if n>=2:v+=.5*dt;q+=v*dt
  send=(now>=next_state) if old else eval(code,dict(live_cycle=True,now=now,next_state=next_state))
  if not send:continue
  p=BridgeTests().packet();p['right_arm']['active']=n>=1;p['right_arm']['joints']=[q]+[0.]*6
  b.send(p,N(return_state='ready',return_epoch=0))
  lines.append(json.dumps(dict(now=now,q=[0.]*29,dq=[0.]*29,packet=b.sock.sent[-1])))
  next_state=now+dt
 result=subprocess.run([str(ROOT/'logs/test_results/mink_live_cycle_stdio_test.exe')],input='\n'.join(lines)+'\n',text=True,capture_output=True,check=True)
 return [json.loads(line) for line in result.stdout.splitlines()]
old=run(True);new=run(False)
assert any(x['reason']=='acceleration' for x in old),old
assert len(new)==60 and all(x['accepted'] for x in new),new
print('PASS: old timer reproduces acceleration rejection; 60 live IK samples accepted without decimation')
