"""Offline review of captured SDK CRC-packed hg states; never starts DDS."""
import hashlib,json,math,statistics,struct
from pathlib import Path

def Crc(data):
    crc=0xffffffff
    for word in struct.unpack("<"+"I"*(len(data)//4),data):
        crc^=word
        for _ in range(4):
            crc=((crc<<8)&0xffffffff)^TABLE[crc>>24]
    return crc
TABLE=[]
for value in range(256):
    crc=value<<24
    for _ in range(8):crc=((crc<<1)&0xffffffff)^(0x04c11db7 if crc&0x80000000 else 0)
    TABLE.append(crc)

def Review(path):
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    if rows[0]["representation"]!="sdk_crc_packed_le2092_not_cdr" or rows[-1]["event"]!="end":
        raise ValueError("incomplete capture")
    samples=[x for x in rows if x["event"]=="sample"]
    qs=[];dqs=[];rpy=[];temps=[];buttons=set();modes=set();faults=set();ticks=[];invalid=0;nonfinite=0
    for row in samples:
        b=bytes.fromhex(row["packed_hex"])
        if len(b)!=2092:raise ValueError("length")
        invalid+=Crc(b[:-4])!=struct.unpack_from("<I",b,2088)[0]
        qs.append([struct.unpack_from("<f",b,76+i*56)[0] for i in range(29)])
        dqs.append([struct.unpack_from("<f",b,80+i*56)[0] for i in range(29)])
        rpy.append(struct.unpack_from("<3f",b,56))
        temps.extend(struct.unpack_from("<2h",b,92+i*56) for i in range(29))
        buttons.add(struct.unpack_from("<H",b,2034)[0]);modes.add((b[8],b[9]))
        ticks.append(struct.unpack_from("<I",b,12)[0])
        for i in range(29):
            f=struct.unpack_from("<I",b,108+i*56)[0]
            if f:faults.add((i,f))
        nonfinite+=any(not math.isfinite(v) for v in qs[-1]+dqs[-1]+list(rpy[-1]))
    intervals=[b["received_at_s"]-a["received_at_s"] for a,b in zip(samples,samples[1:])]
    advances=[(b-a)&0xffffffff for a,b in zip(ticks,ticks[1:])]
    return dict(samples=len(samples),end=rows[-1],span_s=samples[-1]["received_at_s"]-samples[0]["received_at_s"],
        sdk_bad_crc=sum(not s["crc_valid"] for s in samples),independent_bad_crc=invalid,
        nonfinite_samples=nonfinite,modes=sorted(modes),buttons=sorted(buttons),motor_faults=sorted(faults),
        maximum_temperature=max(max(t) for t in temps),maximum_abs_dq=max(abs(v) for q in dqs for v in q),
        max_abs_roll_pitch=[max(abs(v[i]) for v in rpy) for i in range(2)],
        median_receipt_gap_ms=statistics.median(intervals)*1000,maximum_receipt_gap_ms=max(intervals)*1000,
        gaps_over_20ms=sum(v>.02 for v in intervals),duplicate_ticks=advances.count(0),
        backward_ticks=sum(v>=0x80000000 for v in advances),tick_advance_min=min(advances),tick_advance_max=max(advances),
        joint_ranges=[dict(index=i,q_min=min(q[i] for q in qs),q_max=max(q[i] for q in qs),
                           max_abs_dq=max(abs(q[i]) for q in dqs)) for i in range(29)],
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical_output=False)

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    result=Review(root/"logs/test_results/twist2_hg_readonly_capture_20260907.jsonl")
    (root/"logs/test_results/twist2_hg_readonly_review_20260907.json").write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!="joint_ranges"},indent=2))
