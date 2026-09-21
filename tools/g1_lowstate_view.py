"""G1 29-joint read-only state over SSH -> Unity loopback UDP55073; no commands."""
import argparse
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import time
from g1_ssh_login import identity_options

NAMES = [side+'_'+joint for side in ('left','right') for joint in
         ('hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll')]
NAMES += ['waist_yaw','waist_roll','waist_pitch']
NAMES += [side+'_'+joint for side in ('left','right') for joint in
          ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw')]
REMOTE = r"""
import sys, os, time, json, uuid, math
wire=os.fdopen(os.dup(1),'w',1);os.dup2(2,1)
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.utils.crc import CRC
ChannelFactoryInitialize(0,'eth0')
reader=ChannelSubscriber('rt/lowstate',LowState_);reader.Init()
crc=CRC();session=uuid.uuid4().hex;seq=0;last=0
try:
 while True:
  msg=reader.Read(timeout=.1)
  now=time.monotonic()
  if msg is None or now-last < 1/60.:continue
  if len(msg.motor_state)<29 or crc.Crc(msg)!=msg.crc:continue
  motors=msg.motor_state[:29]
  packet=dict(schema='g1.lowstate.view.v1',session=session,sequence=seq,
    source_monotonic_s=now,age_s=0.,crc_valid=True,robot_tick=msg.tick,
    q_rad=[m.q for m in motors],dq_rad_s=[m.dq for m in motors],
    tau_est_nm=[m.tau_est for m in motors],temperature=[list(m.temperature) for m in motors],
    motor_status=[m.motorstate for m in motors],mode_machine=msg.mode_machine,
    imu_quaternion_wxyz=list(msg.imu_state.quaternion),
    imu_gyroscope_rad_s=list(msg.imu_state.gyroscope),
    imu_accelerometer_m_s2=list(msg.imu_state.accelerometer))
  wire.write(json.dumps(packet,allow_nan=False,separators=(',',':'))+'\n')
  last=now;seq+=1
finally:reader.Close()
"""


def validate(x):
    if not isinstance(x,dict) or x.get('schema')!='g1.lowstate.view.v1' or x.get('crc_valid') is not True:
        raise ValueError('schema/CRC')
    if not isinstance(x.get('session'),str) or not 1<=len(x['session'])<=64:
        raise ValueError('session')
    if type(x.get('sequence')) is not int or not 0<=x['sequence']<=2**53-1:raise ValueError('sequence')
    for name in ('source_monotonic_s','age_s'):
        if type(x.get(name)) not in (int,float) or not math.isfinite(x[name]) or x[name]<0:raise ValueError(name)
    if x['age_s']>.5:raise ValueError('stale')
    for name in ('q_rad','dq_rad_s','tau_est_nm'):
        values=x.get(name)
        if not isinstance(values,list) or len(values)!=29 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError(name)
    return x


def run(host):
    command=['ssh.exe']+identity_options()+['-T','-o','BatchMode=yes','-o','ConnectTimeout=5',
        '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','unitree@'+host,'python3 -u -']
    root=Path(__file__).resolve().parents[1]
    folder=root/'logs/test_results/lowstate_view';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(time.strftime('%Y%m%d_%H%M%S')+'_'+str(os.getpid())+'.jsonl')
    child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    print('[LOWSTATE READ ONLY] 29 joints -> localhost55073; log='+str(path),flush=True)
    last_seq=-1;last_source=-1.;session=None;offset=None
    try:
        child.stdin.write(REMOTE.encode());child.stdin.close()
        with path.open('x',encoding='utf-8') as log:
            log.write(json.dumps(dict(event='metadata',joint_names=NAMES,topic='rt/lowstate',
                q_unit='rad',dq_unit='rad/s',clock='G1 monotonic + PC monotonic',publisher_created=False))+'\n')
            while True:
                line=child.stdout.readline(16385)
                if not line:raise RuntimeError('LowState SSH stream ended')
                if len(line)>16384 or not line.endswith(b'\n'):raise RuntimeError('Oversized state line')
                x=validate(json.loads(line));received=time.monotonic()
                if session is None:session=x['session']
                if x['session']!=session or x['sequence']<=last_seq or x['source_monotonic_s']<=last_source:raise ValueError('state ordering')
                sample_offset=received-x['source_monotonic_s']
                offset=sample_offset if offset is None else min(offset,sample_offset)
                x['age_s']=max(0.,sample_offset-offset) # Excess transport delay; not absolute synchronized age.
                x['joint_names']=NAMES
                record=dict(x,pc_received_monotonic_s=received,source_gap=x['sequence']-last_seq-1)
                log.write(json.dumps(record,allow_nan=False)+'\n');log.flush()
                last_seq=x['sequence'];last_source=x['source_monotonic_s']
                if x['age_s']<=.5:sock.sendto(json.dumps(x,allow_nan=False).encode(),('127.0.0.1',55073))
    except KeyboardInterrupt:pass
    finally:
        sock.close()
        if child.poll() is None:child.terminate()
        child.wait(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host',required=True)
    run(parser.parse_args().host)
