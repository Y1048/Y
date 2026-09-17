"""Offline velocity distributions; does not change seed or control thresholds."""
import argparse
import json
import math
from pathlib import Path
import struct
from review_hg_capture_offline import Review

def TriggerWindow(times,velocities):
    """Describe +/-1s around first threshold crossing; retain raw capture separately."""
    trigger=next((i for i,v in enumerate(velocities) if any(abs(x)>.1 for x in v)),None)
    if trigger is None:return None
    t=times[trigger]
    selected=[i for i,x in enumerate(times) if t-1<=x<=t+1]
    return dict(trigger_sequence=trigger+1,trigger_received_at_s=t,
        joint_velocities=[dict(index=i,dq=v) for i,v in enumerate(velocities[trigger]) if abs(v)>.1],
        first_sequence=selected[0]+1,last_sequence=selected[-1]+1,
        pre_span_s=t-times[selected[0]],post_span_s=times[selected[-1]]-t,
        max_gap_s=max((times[b]-times[a] for a,b in zip(selected,selected[1:])),default=0))

def JointStats(times,positions,velocities,threshold=.1):
    if not times or not len(times)==len(positions)==len(velocities):raise ValueError("length")
    if any(not math.isfinite(x) for x in times+positions+velocities):raise ValueError("nonfinite")
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError("receipt_order")
    above=[abs(v)>threshold for v in velocities]
    spans=[];start=None
    for i,flag in enumerate(above):
        if start is not None and (not flag or times[i]-times[i-1]>.02):
            spans.append(times[i-1]-times[start]);start=None
        if flag and start is None:start=i
    if start is not None:spans.append(times[-1]-times[start])
    ordered=sorted(abs(v) for v in velocities)
    return dict(max_abs_dq=max(ordered),p99_abs_dq=ordered[math.ceil(.99*len(ordered))-1],
        exceed_samples=sum(above),exceed_fraction=sum(above)/len(above),
        sampled_exceed_runs=len(spans),longest_sampled_exceed_span_s=max(spans,default=0),
        q_range_rad=max(positions)-min(positions),q_net_change_rad=positions[-1]-positions[0])

def Main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args();health=Review(args.source)
    if health["independent_bad_crc"] or health["sdk_bad_crc"] or health["nonfinite_samples"]:
        raise ValueError("invalid_capture")
    rows=[json.loads(x) for x in args.source.read_text().splitlines()]
    samples=[x for x in rows if x["event"]=="sample"]
    times=[s["received_at_s"] for s in samples];raw=[bytes.fromhex(s["packed_hex"]) for s in samples]
    joints=[]
    for i in range(29):
        q=[struct.unpack_from("<f",b,76+i*56)[0] for b in raw]
        dq=[struct.unpack_from("<f",b,80+i*56)[0] for b in raw]
        joints.append(dict(index=i,**JointStats(times,q,dq)))
    velocities=[[struct.unpack_from("<f",b,80+i*56)[0] for i in range(29)] for b in raw]
    result=dict(health=health,joints=joints,trigger_window=TriggerWindow(times,velocities),threshold_changed=False,
        note="Runs are observed sample spans; gaps over 20ms break runs. No interpolation or cause attribution.")
    with args.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(samples=health["samples"],span_s=health["span_s"],
        maximum_gap_ms=health["maximum_receipt_gap_ms"],top=sorted(joints,key=lambda j:j["max_abs_dq"],reverse=True)[:5]),indent=2))

if __name__=="__main__":Main()
