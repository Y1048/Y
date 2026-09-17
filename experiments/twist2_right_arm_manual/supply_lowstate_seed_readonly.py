"""Draft approved separately: 30-second state-only SDK subscriber -> simulation seed."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
import time
from capture_hg_readonly import Pack,CRC_SHA,SelectInterface
from lowstate_seed_writer import SeedWriter

def JointNames():
    # Read the existing literal contract without importing MuJoCo or running its module.
    path=Path(__file__).resolve().parents[2]/"MuJoCo_G1_Controller/scripts/g1_right_arm_common.py"
    tree=ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="G1_29_JOINT_NAMES" for t in node.targets):
            names=ast.literal_eval(node.value)
            if len(names)==29 and len(set(names))==29:return names
    raise ValueError("joint names")

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--session",required=True)
    args=p.parse_args()
    if not args.session or not args.session.isascii() or not args.session.replace("-","").isalnum():
        raise ValueError("session")
    root=Path("/mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results").resolve()
    directory=args.directory.resolve()
    if not directory.is_relative_to(root) or directory==root:raise ValueError("Windows output only")
    crc_path=Path("/home/user/unitree_sdk2_python/unitree_sdk2py/utils/crc.py")
    if hashlib.sha256(crc_path.read_bytes()).hexdigest()!=CRC_SHA:raise ValueError("SDK source changed")
    interface=SelectInterface(json.loads(subprocess.check_output(
        ['ip','-j','-4','address','show'],text=True,timeout=5)))
    names=JointNames()
    directory.mkdir(exist_ok=False) # exclusive per-run ownership; never reuse another writer's file
    writer=SeedWriter(directory/"seed.json",args.session,names)
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize,ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    from unitree_sdk2py.utils.crc import CRC
    crc=CRC();subscriber=None;count=0;updates=0;last_write=float("-inf")
    try:
        ChannelFactoryInitialize(0,interface)
        subscriber=ChannelSubscriber("rt/lowstate",LowState_);subscriber.Init()
        start=time.monotonic()
        while time.monotonic()-start<30:
            msg=subscriber.Read(timeout=.1)
            received=time.time();mono=time.monotonic()
            if msg is None:
                writer.invalidate()
                continue
            count+=1
            if crc.Crc(msg)!=msg.crc:raise ValueError("source_crc")
            if mono-last_write>=.02:
                packed=Pack(msg)
                writer.write(packed,received,time.time())
                last_write=mono;updates+=1
        print(f"read-only seed supplier ended: samples={count}, updates={updates}",flush=True)
    finally:
        writer.invalidate()
        if subscriber is not None:subscriber.Close()

if __name__=="__main__":Main()
