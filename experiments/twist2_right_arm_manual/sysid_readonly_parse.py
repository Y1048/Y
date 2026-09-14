"""Strict parser for subscriber-only DDS captures; never initializes DDS."""
from pathlib import Path
import argparse
import hashlib
import json
import math

from sysid_capture import JOINT_NAMES

SCHEMA='g1.sysid.readonly-dds.v1'
COMMAND=('command_q','command_dq','kp','kd','tau_ff')
MEASURED=('measured_q','measured_dq','torque_estimate','temperature','motor_status')


def _decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate_key')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
    def finite(x):
        if isinstance(x,float) and not math.isfinite(x):raise ValueError('nonfinite')
        if isinstance(x,list):
            for item in x:finite(item)
        if isinstance(x,dict):
            for item in x.values():finite(item)
    finite(value);return value


def _vector(row,key,n=29):
    value=row[key]
    if not isinstance(value,list) or len(value)!=n or any(type(x) not in (int,float) for x in value):raise ValueError(key)


def read(path):
    path=Path(path);receipt_path=Path(str(path)+'.receipt.json')
    receipt=_decode(receipt_path.read_bytes())
    if receipt.get('schema')!='g1.sysid.readonly-dds.receipt.v1' or not receipt.get('complete') or receipt.get('dropped')!=0:raise ValueError('incomplete_receipt')
    rows=[_decode(line) for line in path.read_bytes().splitlines() if line]
    if len(rows)!=receipt.get('written') or not rows:raise ValueError('count')
    prior=None
    for row in rows:
        required={'schema','session','sequence','provenance','clock','joint_indices','joint_names','units','acceptance',
          'state_receive_ns','state_tick','state_crc','mode_pr','mode_machine','has_command','command_receive_ns','command_age_ns','command_crc',
          *COMMAND,*MEASURED,'imu_rpy','imu_gyro','imu_accel','dropped_samples'}
        if set(row)!=required or row['schema']!=SCHEMA or row['acceptance']!='unknown' or row['dropped_samples']!=0:raise ValueError('schema')
        if row['joint_indices']!=list(range(29)) or row['joint_names']!=list(JOINT_NAMES):raise ValueError('joint_order')
        if row['provenance'].get('kind')!='measured' or set(row['clock'])!={'source','domain'}:raise ValueError('metadata')
        for key in MEASURED:_vector(row,key)
        for key in ('imu_rpy','imu_gyro','imu_accel'):_vector(row,key,3)
        if type(row['sequence']) is not int or type(row['state_receive_ns']) is not int or type(row['state_tick']) is not int:raise ValueError('integer')
        if row['has_command']:
            for key in COMMAND:_vector(row,key)
            if any(type(row[k]) is not int for k in ('command_receive_ns','command_age_ns','command_crc')):raise ValueError('command_time')
            if row['command_receive_ns']>row['state_receive_ns'] or row['command_age_ns']!=row['state_receive_ns']-row['command_receive_ns']:raise ValueError('command_time')
        elif any(row[k] is not None for k in (*COMMAND,'command_receive_ns','command_age_ns','command_crc')):raise ValueError('missing_command_contract')
        if prior:
            if row['session']!=prior['session'] or row['sequence']!=prior['sequence']+1 or row['state_receive_ns']<=prior['state_receive_ns'] or row['state_tick']<prior['state_tick']:raise ValueError('sequence_or_clock')
            if row['has_command'] and prior['has_command'] and row['command_receive_ns']==prior['command_receive_ns'] and any(row[k]!=prior[k] for k in COMMAND):raise ValueError('conflicting_command')
        prior=row
    return rows


def inspect(path):
    rows=read(path);commanded=sum(r['has_command'] for r in rows)
    repeated_ticks=sum(rows[i]['state_tick']==rows[i-1]['state_tick'] for i in range(1,len(rows)))
    return {'schema':'g1.sysid.readonly-dds.inspection.v1','file_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
      'session':rows[0]['session'],'samples':len(rows),'commanded_samples':commanded,
      'repeated_state_ticks':repeated_ticks,
      'duration_s':(rows[-1]['state_receive_ns']-rows[0]['state_receive_ns'])*1e-9,
      'fit_ready':commanded==len(rows) and commanded>=30,'acceptance':'unknown','recommended_hardware_gains':None}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture');args=p.parse_args();print(json.dumps(inspect(args.capture),indent=2))
