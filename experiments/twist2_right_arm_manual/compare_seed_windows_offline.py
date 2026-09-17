"""Exploratory saved-data comparison only. Not an arming or seed consumer."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from review_hg_capture_offline import Review

def Metrics(times,q,dq):
    if len(times)<2 or q.shape!=dq.shape or q.shape!=(len(times),29):raise ValueError("shape")
    if not all(np.isfinite(x).all() for x in (times,q,dq)):raise ValueError("nonfinite")
    gaps=np.diff(times)
    if np.any(gaps<=0) or np.max(gaps)>.02:raise ValueError("receipt_gap")
    absolute=np.abs(dq)
    return dict(peak=float(absolute.max()),p99=float(np.quantile(absolute,.99,axis=0,method="higher").max()),
        fraction=float((absolute>.1).mean(axis=0).max()),q_range=float(np.ptp(q,axis=0).max()))

def Main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args();health=Review(args.source)
    if health["sdk_bad_crc"] or health["independent_bad_crc"] or health["nonfinite_samples"] or health["motor_faults"]:
        raise ValueError("capture_health")
    samples=[r for r in map(json.loads,args.source.read_text().splitlines()) if r["event"]=="sample"]
    t=np.array([r["received_at_s"] for r in samples]);raw=[bytes.fromhex(r["packed_hex"]) for r in samples]
    q=np.array([[struct.unpack_from("<f",b,76+i*56)[0] for i in range(29)] for b in raw])
    dq=np.array([[struct.unpack_from("<f",b,80+i*56)[0] for i in range(29)] for b in raw])
    rows=[]
    for duration in (.2,.5,1.):
        windows=[];invalid=0
        for end in np.arange(t[0]+duration,t[-1],.1):
            lo=np.searchsorted(t,end-duration);hi=np.searchsorted(t,end,side="right")
            if hi-lo<2 or t[hi-1]-t[lo]<duration-.02:
                invalid+=1;continue
            try:windows.append(Metrics(t[lo:hi],q[lo:hi],dq[lo:hi]))
            except ValueError:invalid+=1
        for bound in (.005,.01):
            passes=lambda m:m["peak"]<=.2 and m["p99"]<=.1 and m["fraction"]<=.01 and m["q_range"]<=bound
            rows.append(dict(window_s=duration,q_range_limit_rad=bound,valid_windows=len(windows),invalid_windows=invalid,
                strict_all_samples_below_point1=sum(m["peak"]<=.1 for m in windows),
                exploratory_pass=sum(passes(m) for m in windows),
                relaxed_windows=sum(passes(m) and m["peak"]>.1 for m in windows)))
    result=dict(offline_only=True,runtime_changed=False,source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        exploratory_limits=dict(peak=.2,p99=.1,exceed_fraction=.01,receipt_gap_s=.02),
        warning="Illustrative candidates, not validated safety limits. Overlapping windows are not independent trials. No runtime acceptance recommendation.",rows=rows)
    with args.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=="__main__":Main()
