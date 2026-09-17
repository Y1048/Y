"""Strict opt-in 29-joint simulation seed. No robot IO or SDK imports."""
import json
import math
import os
from pathlib import Path
import struct
import time

def ReadSeedBytes(path):
    """Allow atomic replacement while Windows holds the old file open."""
    if os.name!="nt":
        with open(path,"rb") as stream:return stream.read(16385)
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                     wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype=wintypes.HANDLE
    # GENERIC_READ; FILE_SHARE_READ | WRITE | DELETE; OPEN_EXISTING.
    handle=create(str(Path(path).resolve()),0x80000000,7,None,3,0x80,None)
    if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE]
        close(handle)
        raise
    with os.fdopen(fd,"rb") as stream:return stream.read(16385)

def ReadSeed(path, session, joint_names, now=None):
    if not isinstance(session,str) or not session.strip():raise ValueError("seed_session_required")
    def Unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError("duplicate_seed_key")
            result[key]=value
        return result
    data=ReadSeedBytes(path)
    if len(data)>16384:raise ValueError("seed_size")
    seed=json.loads(data,object_pairs_hook=Unique)
    if seed.get("schema")!="g1.mink.lowstate_seed.v1" or seed.get("session_id")!=session:
        raise ValueError("seed_schema_or_session")
    if seed.get("joint_names")!=list(joint_names):raise ValueError("seed_joint_order")
    if seed.get("representation")!="sdk_crc_packed_le2092_b95a5304":raise ValueError("seed_representation")
    received=seed.get("received_at_unix_s")
    now=time.time() if now is None else now
    if type(received) not in (int,float) or not math.isfinite(received) or not math.isfinite(now) or not 0<=now-received<=.25:
        raise ValueError("seed_stale_or_future")
    raw=bytes.fromhex(seed["packed_hex"])
    if len(raw)!=2092:raise ValueError("seed_byte_count")
    crc=0xffffffff
    for word in struct.unpack("<522I",raw[:-4]):
        crc^=word
        for _ in range(32):crc=((crc<<1)&0xffffffff)^(0x04c11db7 if crc&0x80000000 else 0)
    if crc!=struct.unpack_from("<I",raw,2088)[0]:raise ValueError("seed_crc")
    if raw[8:10]!=bytes((0,5)):raise ValueError("seed_mode")
    q=[struct.unpack_from("<f",raw,76+i*56)[0] for i in range(29)]
    dq=[struct.unpack_from("<f",raw,80+i*56)[0] for i in range(29)]
    if any(not math.isfinite(x) for x in q+dq):
        raise ValueError("seed_position_or_velocity: nonfinite q/dq")
    fastest=max(range(29),key=lambda i:abs(dq[i]))
    if abs(dq[fastest])>.1:
        raise ValueError(f"seed_position_or_velocity: joint={fastest}, dq={dq[fastest]:.9g}, limit=0.1")
    for i in range(29):
        if max(struct.unpack_from("<2h",raw,92+i*56))>75 or struct.unpack_from("<I",raw,108+i*56)[0]:
            raise ValueError("seed_motor_health")
    rpy=struct.unpack_from("<3f",raw,56)
    if not all(math.isfinite(x) for x in rpy) or max(map(abs,rpy[:2]))>.15:raise ValueError("seed_attitude")
    return dict(q=q,session_id=session,received_at_unix_s=received,
                robot_tick=struct.unpack_from("<I",raw,12)[0])

def ApplySeed(model, initial_q, seed, joint_names):
    import mujoco
    candidate=initial_q.copy()
    for name,value in zip(joint_names,seed["q"],strict=True):
        j=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,name)
        if j<0 or model.jnt_type[j] not in (mujoco.mjtJoint.mjJNT_HINGE,mujoco.mjtJoint.mjJNT_SLIDE):
            raise ValueError("seed_joint_mapping")
        if model.jnt_limited[j] and not model.jnt_range[j,0]<=value<=model.jnt_range[j,1]:
            raise ValueError("seed_joint_limit")
        candidate[int(model.jnt_qposadr[j])]=value
    return candidate
