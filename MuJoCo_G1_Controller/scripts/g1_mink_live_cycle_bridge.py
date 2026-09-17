"""Explicit opt-in cycle transport; never upgrades simulation/replay packets."""
import json,os,socket,time

def live_tracking_active(command_update):
 return bool(command_update.command_active or command_update.control_state=='hold')

class LiveCycleBridge:
 def __init__(self,profile,dt):
  self.token=os.environ.get('G1_CYCLE_RELAY_TOKEN','')
  if not self.token.isascii() or not self.token.isalnum() or not 16<=len(self.token)<=128:raise ValueError('explicit cycle relay token required')
  self.profile=profile;self.dt=dt;self.sequence=0;self.last_epoch=0;self.ack=None;self.ack_time=0;self.ack_sequence=-1;self.started=False;self.started_at=0.;self.feedback_return_requested=False
  self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind(('127.0.0.1',5015));self.sock.setblocking(False)
 def poll(self,stream=None):
  for _ in range(64):
   try:raw,peer=self.sock.recvfrom(4096)
   except BlockingIOError:break
   except ConnectionResetError as exc:
    # Windows UDP ICMP port-unreachable; freshness watchdogs remain authoritative.
    if getattr(exc,'winerror',None)!=10054:raise
    continue
   if peer[0]!='127.0.0.1':raise RuntimeError('cycle feedback source')
   x=json.loads(raw)
   if x.get('schema')!='g1.mink.cycle.ack.v1' or x.get('relay_token')!=self.token or x.get('profile')!=self.profile:raise RuntimeError('cycle feedback binding')
   if type(x.get('sequence')) is not int or x['sequence']<=self.ack_sequence:continue
   if type(x.get('epoch')) is not int or x['epoch']<0 or not isinstance(x.get('session'),str) or x.get('state') not in ('initializing','waiting','tracking','returning','stopped'):raise RuntimeError('cycle feedback format')
   self.ack=x;self.ack_time=time.monotonic();self.ack_sequence=x['sequence']
   self.feedback_return_requested=False
   if stream is not None and x['state']=='returning' and x['epoch']>self.last_epoch:
    if not stream.request_external_return(x['epoch'],x['session']):raise RuntimeError('robot return synchronization')
    self.last_epoch=x['epoch']
  self.report_robot_state()
  if self.started and time.monotonic()-(self.ack_time if self.ack is not None else self.started_at)>.25:
   if stream is None or self.ack is None:raise RuntimeError('robot cycle feedback timeout before bound ACK')
   if not self.feedback_return_requested:
    epoch=self.ack['epoch']+1
    if not stream.request_external_return(epoch,self.ack['session']):raise RuntimeError('robot feedback-loss return synchronization')
    self.feedback_return_requested=True
    print('[G1 ROBOT] feedback lost; commanding checked return while TWIST2 owner remains active',flush=True)
  if self.ack and self.ack['state']=='stopped':raise RuntimeError('robot cycle stopped')
 def report_robot_state(self):
  state=self.ack['state'] if self.ack and time.monotonic()-self.ack_time<=.25 else 'no_feedback'
  if state=='initializing' and time.monotonic()-getattr(self,'last_ready_detail',-float('inf'))>=1:
   self.last_ready_detail=time.monotonic()
   blockers=self.ack.get('ready_blockers',[])
   if isinstance(blockers,list):
    for item in blockers[:14]:
     if not isinstance(item,dict):continue
     print('[G1 WAIT] joint={joint} error={error_rad} rad / limit={limit_rad} rad; speed={speed_rad_s} rad/s / limit={speed_limit_rad_s} rad/s'.format_map({key:item.get(key,'?') for key in ('joint','error_rad','limit_rad','speed_rad_s','speed_limit_rad_s')}),flush=True)
    if not blockers:
     print('[G1 WAIT] finishing initial trajectory / measured settling dwell',flush=True)
  if state==getattr(self,'displayed_robot_state',None):return
  self.displayed_robot_state=state
  messages={
   'no_feedback':'WAIT - no fresh G1 feedback; do not engage',
   'initializing':'WAIT - G1 moving/settling at initial pose; do not engage',
   'waiting':'READY - G1 measured ready (udp_ready); new engage allowed',
   'tracking':'TRACKING - G1 arm control active',
   'returning':'RETURNING - wait for measured ready before new engage',
   'stopped':'STOPPED - G1 cycle stopped; do not engage',
  }
  print('[G1 ROBOT] '+messages[state],flush=True)
 def can_ack(self,epoch,session):
  return bool(self.ack and time.monotonic()-self.ack_time<=.25 and self.ack['state']=='waiting' and self.ack['epoch']==epoch and self.ack['session']==session)
 def send(self,packet,stream):
  if packet.get('simulation_only') or packet.get('command_provenance')!='live_mink':raise ValueError('non-live cycle packet')
  session=packet.get('session_id')
  if not session:return
  if session.startswith('replay-'):raise ValueError('replay session')
  state=stream.return_state;epoch=stream.return_epoch
  if state=='fault':event='fault'
  elif state=='returning':
   event='pinch' if epoch>self.last_epoch else 'return'
   if event=='pinch':self.last_epoch=epoch;epoch-=1
  else:
   control_state=packet['right_arm'].get('command_state')
   if control_state=='hold':
    # Unity can briefly report idle while the validated command stream holds
    # the last safe target. Native Tracking accepts a held target as active;
    # only explicit pinch/tracking disengage starts the return cycle.
    event='active'
   else:event='active' if packet['right_arm']['active'] else 'idle'
  self.sequence+=1
  payload=dict(schema='g1.mink.cycle.live.v1',command_provenance='live_mink',profile=self.profile,session=session,sequence=self.sequence,epoch=epoch,sample_time_s=self.sequence*self.dt,source_age_s=packet.get('input_packet_age_s'),event=event,joints=packet['right_arm']['joints'],clearance_m=packet['right_arm'].get('minimum_clearance_m'))
  if event=='active' and not self.started:self.started=True;self.started_at=time.monotonic()
  self.sock.sendto(json.dumps(payload,allow_nan=False,separators=(',',':')).encode(),('127.0.0.1',5008))
 def close(self):self.sock.close()
