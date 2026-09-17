"""Mock transport, loopback UDP and return gate checks. No publisher/robot."""
import sys,json,unittest,socket,select
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'));sys.path.insert(0,str(ROOT/'hardware/g1_arm_bridge'))
import numpy as np
from g1_mink_live_cycle_bridge import LiveCycleBridge,live_tracking_active
from g1_mink_return_cycle import SimulationReturnCycle
from gate7_mink_cycle_relay import validate,open_feedback_socket
import gate7_mink_cycle_relay as relay
class Socket:
 def __init__(self):self.sent=[];self.incoming=[]
 def sendto(self,data,peer):self.sent.append(json.loads(data));return len(data)
 def recvfrom(self,size):
  if not self.incoming:raise BlockingIOError()
  return self.incoming.pop(0)
class BridgeTests(unittest.TestCase):
 def test_stale_idle_is_dropped_before_and_after_active(self):
  b=self.make();p=self.packet();p['right_arm']['active']=False
  b.send(p,N(return_state='ready',return_epoch=0));idle=b.sock.sent[0]
  stale=dict(idle,source_age_s=.5)
  active=dict(idle,event='active',sequence=2)
  inbound=MagicMock();outbound=MagicMock()
  inbound.recvfrom.side_effect=[*((json.dumps(x).encode(),('127.0.0.1',1234)) for x in (stale,idle,active,stale)),BlockingIOError()]
  outbound.recvfrom.side_effect=BlockingIOError()
  with patch.object(sys,'argv',['relay','--relay-token','a'*32,'--profile','today']),patch.object(relay.socket,'socket',return_value=inbound),patch.object(relay,'open_feedback_socket',return_value=outbound),patch.object(relay.time,'sleep',side_effect=KeyboardInterrupt()),patch('builtins.print'):
   with self.assertRaises(KeyboardInterrupt):relay.main()
  self.assertEqual(outbound.sendto.call_count,2)
  self.assertEqual([json.loads(c.args[0])['event'] for c in outbound.sendto.call_args_list],['idle','active'])
 def test_clearance_and_sample_errors_are_distinct(self):
  b=self.make();b.send(self.packet(),N(return_state='ready',return_epoch=0));x=b.sock.sent[0]
  for field,value in [('clearance_m',.004),('sample_time_s',-1)]:
   with self.assertRaisesRegex(ValueError,field+'='):validate(dict(x,**{field:value}),'today')
 def test_relay_windows_reset_on_both_sockets(self):
  reset=ConnectionResetError('UDP port unreachable');reset.winerror=10054
  inbound=MagicMock();outbound=MagicMock()
  inbound.recvfrom.side_effect=[reset,BlockingIOError()]
  outbound.recvfrom.side_effect=[reset,BlockingIOError()]
  with patch.object(sys,'argv',['relay','--relay-token','a'*32,'--profile','today']),patch.object(relay.socket,'socket',return_value=inbound),patch.object(relay,'open_feedback_socket',return_value=outbound),patch.object(relay.time,'sleep',side_effect=KeyboardInterrupt()),patch('builtins.print'):
   with self.assertRaises(KeyboardInterrupt):relay.main()
  inbound.close.assert_called_once();outbound.close.assert_called_once()
  inbound.sendto.assert_not_called();outbound.sendto.assert_not_called()
 def test_windows_udp_reset_does_not_refresh_ack_or_bypass_timeout(self):
  b=self.make();reset=ConnectionResetError('UDP port unreachable');reset.winerror=10054
  with patch.object(b.sock,'recvfrom',side_effect=[reset,BlockingIOError()]):b.poll()
  self.assertIsNone(b.ack);self.assertEqual(b.ack_time,0)
  b.started=True;b.started_at=10
  with patch.object(b.sock,'recvfrom',side_effect=[reset,BlockingIOError()]),patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.3):
   with self.assertRaisesRegex(RuntimeError,'before bound ACK'):b.poll()
  with patch.object(b.sock,'recvfrom',side_effect=ConnectionResetError('other reset')):
   with self.assertRaises(ConnectionResetError):b.poll()
 def test_relay_feedback_before_first_send_and_roundtrip(self):
  with open_feedback_socket() as outbound,socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as peer:
   self.assertNotEqual(outbound.getsockname()[1],0)
   with self.assertRaises(BlockingIOError):outbound.recvfrom(4097)
   peer.bind(('127.0.0.1',0));peer.settimeout(1)
   outbound.sendto(b'input',peer.getsockname())
   raw,address=peer.recvfrom(4097);self.assertEqual(raw,b'input')
   peer.sendto(b'ack',address)
   self.assertTrue(select.select([outbound],[],[],1)[0])
   raw,address=outbound.recvfrom(4097)
   self.assertEqual(raw,b'ack');self.assertEqual(address,peer.getsockname())
 def make(self):
  b=LiveCycleBridge.__new__(LiveCycleBridge);b.token='a'*32;b.profile='today';b.dt=1/60;b.sequence=0;b.last_epoch=0;b.ack=None;b.ack_time=0;b.ack_sequence=-1;b.started=False;b.started_at=0;b.feedback_return_requested=False;b.sock=Socket();return b
 def packet(self):return dict(command_provenance='live_mink',session_id='test',input_packet_age_s=0,right_arm=dict(active=True,joints=[0]*7,minimum_clearance_m=.04))
 def test_transient_idle_hold_remains_tracking_event(self):
  b=self.make();stream=N(return_state='ready',return_epoch=0)
  packet=self.packet();b.send(packet,stream)
  packet['right_arm']['active']=False;packet['right_arm']['command_state']='hold'
  b.send(packet,stream)
  self.assertEqual([x['event'] for x in b.sock.sent],['active','active'])
  self.assertEqual(b.sock.sent[-1]['joints'],[0]*7)
  for x in b.sock.sent:validate(x,'today')
 def test_transient_hold_keeps_local_trajectory_active(self):
  self.assertTrue(live_tracking_active(N(command_active=True,control_state='active')))
  self.assertTrue(live_tracking_active(N(command_active=False,control_state='hold')))
  self.assertFalse(live_tracking_active(N(command_active=False,control_state='idle')))
 def test_return_ignores_active_hand(self):
  b=self.make();stream=N(return_state='returning',return_epoch=1);p=self.packet()
  b.send(p,stream);b.send(p,stream)
  self.assertEqual([(x['event'],x['epoch']) for x in b.sock.sent],[('pinch',0),('return',1)])
  for x in b.sock.sent:validate(x,'today')
 def test_simulation_not_upgraded(self):
  b=self.make();p=self.packet();p['simulation_only']=True
  with self.assertRaises(ValueError):b.send(p,N(return_state='ready',return_epoch=0))
  self.assertFalse(b.sock.sent)
 def test_ack_binding_and_freshness(self):
  b=self.make();b.ack=dict(state='waiting',epoch=2,session='test');b.ack_time=10
  with patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.1):
   self.assertTrue(b.can_ack(2,'test'));self.assertFalse(b.can_ack(1,'test'));self.assertFalse(b.can_ack(2,'other'))
  with patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.3):self.assertFalse(b.can_ack(2,'test'))
 def test_robot_initiated_return_starts_local_checked_return(self):
  b=self.make();stream=MagicMock();stream.request_external_return.return_value=True
  ack=dict(schema='g1.mink.cycle.ack.v1',relay_token='a'*32,profile='today',sequence=1,epoch=1,session='test',state='returning')
  b.sock.incoming=[(json.dumps(ack).encode(),('127.0.0.1',123))]
  b.poll(stream)
  stream.request_external_return.assert_called_once_with(1,'test')
  self.assertEqual(b.last_epoch,1)
 def test_ack_timeout_and_wrong_token(self):
  b=self.make();b.started=True;b.started_at=10
  with patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.1):b.poll()
  with patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.3):
   with self.assertRaisesRegex(RuntimeError,'before bound ACK'):b.poll()
  b=self.make();b.sock.incoming=[(json.dumps(dict(schema='g1.mink.cycle.ack.v1',relay_token='wrong',profile='today')).encode(),('127.0.0.1',123))]
  with self.assertRaises(RuntimeError):b.poll()
 def test_bound_ack_timeout_requests_checked_return_once(self):
  b=self.make();b.started=True;b.ack=dict(state='waiting',epoch=0,session='test');b.ack_time=10
  stream=MagicMock();stream.request_external_return.return_value=True
  with patch('g1_mink_live_cycle_bridge.time.monotonic',return_value=10.3),patch('builtins.print'):
   b.poll(stream);b.poll(stream)
  stream.request_external_return.assert_called_once_with(1,'test')
  self.assertTrue(b.feedback_return_requested)
 def test_return_waits_for_external_gate(self):
  allowed=False;home=np.zeros(29);configuration=N(q=home.copy());configuration.update=lambda q:setattr(configuration,'q',q)
  trajectory=N(right_qpos_ids=np.arange(22,29),Reset=lambda q:None)
  trajectory.Step=lambda q,h:N(applied=True,q=h.copy(),velocity_rad_s=[0]*7)
  calls=[];stream=N(return_state='returning',return_epoch=1,return_session='test')
  stream.acknowledge_simulation_return=lambda e,s:calls.append((e,s)) or True
  cycle=SimulationReturnCycle(home,trajectory,lambda e,s:allowed)
  for n in range(160):cycle.step(stream,configuration,n*.01)
  self.assertFalse(calls);allowed=True;cycle.step(stream,configuration,1.6);self.assertEqual(calls,[(1,'test')])
 def test_relay_rejects_wrong_profile(self):
  b=self.make();b.send(self.packet(),N(return_state='ready',return_epoch=0))
  with self.assertRaises(ValueError):validate(b.sock.sent[0],'yesterday')
if __name__=='__main__':unittest.main()
