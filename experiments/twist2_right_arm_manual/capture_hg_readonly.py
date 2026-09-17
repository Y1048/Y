"""Draft: subscribe to rt/lowstate for 10 seconds; no command publisher or mode change."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time

FORMAT="<2I2B2xI"+"13fh2x"+"B3x4f2hf7I"*35+"40B5I"
CRC_SHA="b95a530423f72c5acc96811f75677699cb3a185b6327353e7c44b355a425a20e"

def SelectInterface(interfaces):
    matches=[item['ifname'] for item in interfaces
        if item.get('operstate')=='UP' and 'LOWER_UP' in item.get('flags',[])
        and any(addr.get('local')=='192.168.123.99' and addr.get('prefixlen')==24
                for addr in item.get('addr_info',[]))]
    if len(matches)!=1:raise ValueError('exactly one active G1 192.168.123.99/24 interface required')
    return matches[0]
def Pack(state):
    values=[*state.version,state.mode_pr,state.mode_machine,state.tick,
        *state.imu_state.quaternion,*state.imu_state.gyroscope,
        *state.imu_state.accelerometer,*state.imu_state.rpy,state.imu_state.temperature]
    if len(state.motor_state)!=35:raise ValueError("motor count")
    for m in state.motor_state:
        values.extend([m.mode,m.q,m.dq,m.ddq,m.tau_est,*m.temperature,m.vol,
                       *m.sensor,m.motorstate,*m.reserve])
    values.extend([*state.wireless_remote,*state.reserve,state.crc])
    return struct.pack(FORMAT,*values)

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--seconds",type=float,default=10)
    p.add_argument("--sample-limit",type=int,default=6000)
    args=p.parse_args()
    if not 0<args.seconds<=30 or not 1<=args.sample_limit<=36000:
        p.error("seconds must be within (0,30], sample-limit within [1,36000]")
    root=Path("/mnt/c/Users/user/Desktop/G1_Teleop_Project/logs/test_results").resolve()
    destination=args.output.resolve()
    if not destination.is_relative_to(root) or destination==root:raise ValueError("Windows output only")
    crc_source=Path("/home/user/unitree_sdk2_python/unitree_sdk2py/utils/crc.py")
    if hashlib.sha256(crc_source.read_bytes()).hexdigest()!=CRC_SHA:raise ValueError("SDK CRC source changed")
    interface=SelectInterface(json.loads(subprocess.check_output(
        ['ip','-j','-4','address','show'],text=True,timeout=5)))
    # Imports and DDS initialization occur only on explicitly approved live execution.
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize,ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
    from unitree_sdk2py.utils.crc import CRC
    crc=CRC()
    subscriber=None
    with destination.open("x",encoding="utf-8") as log:
        log.write(json.dumps(dict(event="metadata",schema="twist2.hg.capture.v1",
            representation="sdk_crc_packed_le2092_not_cdr",interface=interface,
            topic="rt/lowstate",seconds=args.seconds,sample_limit=args.sample_limit,crc_source_sha256=CRC_SHA,
            publisher_created=False,hardware_output_authorized=False))+"\n")
        log.flush()
        try:
            ChannelFactoryInitialize(0,interface)
            subscriber=ChannelSubscriber("rt/lowstate",LowState_)
            subscriber.Init()
            start=time.monotonic();count=0;bad=0
            while time.monotonic()-start<args.seconds and count<args.sample_limit:
                msg=subscriber.Read(timeout=.1)
                received=time.monotonic()
                if msg is None:continue
                packed=Pack(msg)
                valid=crc.Crc(msg)==msg.crc
                count+=1;bad+=not valid
                log.write(json.dumps(dict(event="sample",sequence=count,
                    received_at_s=received,elapsed_s=received-start,
                    robot_tick=msg.tick,crc_valid=valid,packed_hex=packed.hex()))+"\n")
            log.write(json.dumps(dict(event="end",samples=count,bad_crc=bad,
                elapsed_s=time.monotonic()-start))+"\n")
            print(json.dumps(dict(samples=count,bad_crc=bad,output=str(destination))))
        finally:
            if subscriber is not None:subscriber.Close()

if __name__=="__main__":Main()
