"""Opt-in bidirectional cycle relay. No SDK/publisher; old relay unchanged."""
import argparse,json,math,socket,time
from pathlib import Path

def strict_load(raw):
 def pairs(items):
  result={}
  for k,v in items:
   if k in result:raise ValueError('duplicate key')
   result[k]=v
  return result
 return json.loads(raw,object_pairs_hook=pairs)

def validate(x,profile):
 if not isinstance(x,dict) or x.get('schema')!='g1.mink.cycle.live.v1' or x.get('command_provenance')!='live_mink' or x.get('simulation_only') or x.get('profile')!=profile:raise ValueError('cycle provenance/profile')
 if not isinstance(x.get('session'),str) or not x['session'].strip() or len(x['session'])>128 or x['session'].startswith('replay-'):raise ValueError('session')
 for key in ('sequence','epoch'):
  if type(x.get(key)) is not int or not 0<=x[key]<2**63:raise ValueError(key)
 for key in ('source_age_s','sample_time_s','clearance_m'):
  if type(x.get(key)) not in (int,float) or not math.isfinite(x[key]):raise ValueError(key)
 if not 0<=x['source_age_s']<=.25:raise ValueError(f"source_age_s={x['source_age_s']:.6f}; allowed 0..0.25 s")
 if x['sample_time_s']<0:raise ValueError(f"sample_time_s={x['sample_time_s']:.6f}; must be nonnegative")
 if x['clearance_m']<.005-1e-7:raise ValueError(f"clearance_m={x['clearance_m']:.6f}; minimum 0.005 m")
 if x.get('event') not in ('idle','active','pinch','tracking_disengaged','return','fault'):raise ValueError('event')
 if not isinstance(x.get('joints'),list) or len(x['joints'])!=7 or any(type(q) not in (int,float) or not math.isfinite(q) for q in x['joints']):raise ValueError('joints')
 return x

def open_feedback_socket():
 # Windows recvfrom requires a bound socket even before the first sendto.
 sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
 try:
  sock.bind(('0.0.0.0',0))
  sock.setblocking(False)
  return sock
 except BaseException:
  sock.close()
  raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--target-host',default='192.168.123.164');p.add_argument('--relay-token',required=True);p.add_argument('--profile',choices=['yesterday','today'],required=True);p.add_argument('--record',type=Path);args=p.parse_args()
 if not args.relay_token.isascii() or not args.relay_token.isalnum() or not 16<=len(args.relay_token)<=128:raise ValueError('token')
 inbound=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
 try:
  inbound.bind(('127.0.0.1',5008));inbound.setblocking(False)
  outbound=open_feedback_socket()
 except BaseException:
  inbound.close()
  raise
 record=None
 if args.record:
  args.record.parent.mkdir(parents=True,exist_ok=True)
  record=args.record.open('x',encoding='utf-8',buffering=1)
  print(f'[PACKET LOG] {args.record}',flush=True)
 session=None;seq=-1;ack_seq=-1;last_reject=-math.inf
 print(f'LIVE CYCLE {args.profile}: localhost5008 -> {args.target_host}:5014; feedback -> localhost5015',flush=True)
 try:
  while True:
   for _ in range(64):
    try:raw,peer=inbound.recvfrom(4097)
    except BlockingIOError:break
    except ConnectionResetError as exc:
     # Windows UDP ICMP port-unreachable; freshness watchdogs remain authoritative.
     if getattr(exc,'winerror',None)!=10054:raise
     continue
    if peer[0]!='127.0.0.1' or len(raw)>4096:raise ValueError('input source/size')
    x=strict_load(raw)
    try:validate(x,args.profile)
    except ValueError as exc:
     # Idle input is never a robot joint command. A paused Unity frame can age
     # after any completed engage/return cycle, so discard it regardless of
     # whether this relay has previously observed an active packet.
     if isinstance(x,dict) and x.get('event')=='idle' and str(exc).startswith('source_age_s='):
      now=time.monotonic()
      if now-last_reject>=1:
       print(f'[WAIT INPUT] dropped stale idle: {exc}',flush=True);last_reject=now
      continue
     raise
    if session is not None and (session!=x['session'] or x['sequence']<=seq):raise ValueError('session/sequence changed')
    session=x['session'];seq=x['sequence'];x['relay_token']=args.relay_token
    data=json.dumps(x,allow_nan=False,separators=(',',':')).encode()
    if len(data)>1400:raise ValueError('packet budget')
    if record:
     record.write(json.dumps(dict(kind='send_attempt',time=time.monotonic(),packet={k:v for k,v in x.items() if k!='relay_token'}),allow_nan=False)+'\n')
    outbound.sendto(data,(args.target_host,5014))
   for _ in range(64):
    try:raw,peer=outbound.recvfrom(4097)
    except BlockingIOError:break
    except ConnectionResetError as exc:
     # Windows UDP ICMP port-unreachable; freshness watchdogs remain authoritative.
     if getattr(exc,'winerror',None)!=10054:raise
     continue
    if peer!=(args.target_host,5014) or len(raw)>4096:raise ValueError('feedback source')
    x=strict_load(raw)
    if x.get('schema')!='g1.mink.cycle.ack.v1' or x.get('relay_token')!=args.relay_token or x.get('profile')!=args.profile:raise ValueError('feedback binding')
    if type(x.get('sequence')) is not int or x['sequence']<=ack_seq:continue
    if record:record.write(json.dumps(dict(kind='ack',time=time.monotonic(),packet={k:v for k,v in x.items() if k!='relay_token'}),allow_nan=False)+'\n')
    ack_seq=x['sequence'];inbound.sendto(raw,('127.0.0.1',5015))
   time.sleep(.001)
 finally:
  inbound.close();outbound.close()
  if record:record.close()
if __name__=='__main__':main()
