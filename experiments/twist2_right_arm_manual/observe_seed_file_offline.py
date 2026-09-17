"""Windows file-only freshness observer. Does not start VR, sockets or DDS."""
import argparse
import json
from pathlib import Path
import time
from lowstate_seed_writer import ReadSeed
from supply_lowstate_seed_readonly import JointNames

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed",type=Path,required=True)
    p.add_argument("--session",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    names=JointNames();start=time.monotonic();seen=set();errors=[];ages=[];first=None
    while time.monotonic()-start<35:
        try:
            seed=ReadSeed(args.seed,args.session,names)
            if seed["received_at_unix_s"] not in seen:
                seen.add(seed["received_at_unix_s"]);ages.append(time.time()-seed["received_at_unix_s"])
                if first is None:first=seed
        except FileNotFoundError:pass
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors.append(f"{type(error).__name__}: {error}")
        time.sleep(.02)
    result=dict(validated_updates=len(seen),errors=errors,maximum_age_s=max(ages) if ages else None,
                first=first,seed_present_at_end=args.seed.exists(),robot_output=False)
    with args.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
    if not seen or errors:raise SystemExit(1)

if __name__=="__main__":Main()
