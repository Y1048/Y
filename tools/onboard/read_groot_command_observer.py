"""Fail-closed reader for observation CSV; no SDK, network, or motor control."""
import csv
import math
from pathlib import Path

JOINT_NAMES = tuple(side+'_'+joint for side in ('left','right')
    for joint in ('hip_pitch','hip_roll','hip_yaw','knee','ankle_pitch','ankle_roll')) + (
    'waist_yaw','waist_roll','waist_pitch') + tuple(side+'_'+joint for side in ('left','right')
    for joint in ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow','wrist_roll','wrist_pitch','wrist_yaw'))
META = ('writer_sequence,input_sequence,target_created_ns,input_observed_ns,state_received_ns,'
        'write_begin_ns,write_end_ns,input_source_timestamp,input_valid,arms_specified,arms_active,'
        'state_available,safe_stand,damping,dropped_total,invalid_total,nonmonotonic_total,gap_total').split(',')
ARRAYS = ('target_q','sent_q','sent_dq','kp','kd','tau_ff','measured_q','measured_dq','tau_est')
FIELDS = META + ['received_q'+str(i) for i in range(15,29)] + [key+str(i) for i in range(29) for key in ARRAYS]

def read_log(path):
    with Path(path).open(encoding='utf-8') as f:
        metadata=f.readline().rstrip()
        if not metadata.startswith('# schema=groot.command.observation.v1; clock=G1 std::chrono::steady_clock ns;'):
            raise ValueError('schema/clock')
        lines=f.readlines()
        footers=[line.strip() for line in lines if line.startswith('# final ')]
        if len(footers)!=1: raise ValueError('unsealed or incomplete observation log')
        if not lines or lines[-1].strip()!=footers[0]: raise ValueError('footer must be last')
        if footers[0]!='# final dropped=0 invalid=0 errors=0':
            raise ValueError('final logging errors/loss')
        reader=csv.DictReader(line for line in lines if not line.startswith('#'))
        if reader.fieldnames != FIELDS: raise ValueError('joint order or missing columns')
        result=[]
        last_seq=last_time=0
        for row in reader:
            if None in row or any(v is None or v=='' for v in row.values()): raise ValueError('missing/extra sample fields')
            try:
                parsed={key:(int(value) if key in META and key!='input_source_timestamp' else float(value)) for key,value in row.items()}
            except (ValueError,OverflowError) as e: raise ValueError('numeric sample') from e
            if any(not math.isfinite(v) for v in parsed.values()): raise ValueError('nonfinite')
            for key in ('input_valid','arms_specified','arms_active','state_available','safe_stand','damping'):
                if parsed[key] not in (0,1): raise ValueError('boolean')
            for key in META:
                if parsed[key]<0: raise ValueError('negative metadata')
            seq=parsed['writer_sequence']; begin=parsed['write_begin_ns']
            if seq<=last_seq or begin<=last_time: raise ValueError('nonmonotonic writer')
            if parsed['write_end_ns']<begin or parsed['target_created_ns']>begin: raise ValueError('timestamp ordering')
            if not parsed['state_available'] or not parsed['state_received_ns']:
                raise ValueError('unavailable measured state')
            if parsed['state_received_ns']>begin: raise ValueError('future measured state')
            # Never silently fit through missing producer samples or lost rows.
            if any(parsed[k] for k in ('dropped_total','invalid_total','nonmonotonic_total','gap_total')) or (last_seq and seq!=last_seq+1):
                raise ValueError('sample loss/gap')
            last_seq=seq; last_time=begin; result.append(parsed)
        if not result: raise ValueError('no samples')
        return result
