"""Offline artifact/array adapter. Never imports Torch, SDK, DDS or opens sockets."""
import hashlib
import math
from pathlib import Path
import struct

EXPECTED_SHA256='463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015'


def ReadVerifiedPolicy(path):
    # Return the same checked bytes for a future loader; do not re-open the path.
    payload=Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=EXPECTED_SHA256:
        raise ValueError('policy_hash_mismatch')
    return payload


def AdaptOutput(output, *, sequence, state_sequence, created_at, state_received_at, now, maximum_age):
    """Validate raw [1,29] finite output, round to float32 and clip like Policy::infer.

    This validates an array only; it does not prove that a model produced it.
    The C++ wrapper still owns repeated-sequence and state-binding checks.
    """
    for value in (sequence,state_sequence):
        if type(value) is not int or not 0<=value<=2**64-1: raise ValueError('sequence')
    for value in (created_at,state_received_at,now,maximum_age):
        if type(value) not in (int,float) or not math.isfinite(value): raise ValueError('time')
    if maximum_age<=0 or state_received_at<0 or not state_received_at<=created_at<=now or now-created_at>maximum_age:
        raise ValueError('policy_time')
    if not isinstance(output,(list,tuple)) or len(output)!=1 or not isinstance(output[0],(list,tuple)) or len(output[0])!=29:
        raise ValueError('policy_shape')
    action=[]
    for value in output[0]:
        if type(value) not in (int,float) or not math.isfinite(value): raise ValueError('policy_number')
        try: v=struct.unpack('<f',struct.pack('<f',value))[0]
        except (OverflowError,struct.error) as error: raise ValueError('policy_float32') from error
        if not math.isfinite(v): raise ValueError('policy_float32')
        action.append(max(-2.0,min(2.0,v)))
    return dict(action=action,sequence=sequence,state_sequence=state_sequence,created_at=created_at)
