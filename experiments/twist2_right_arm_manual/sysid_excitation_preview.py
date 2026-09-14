"""Expand an offline excitation plan to a review CSV; never execute commands."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from sysid_capture import decode
from sysid_excitation_plan import PLAN_SCHEMA, RIGHT_ARM


SCHEMA = "g1.sysid.excitation-preview.v1"


def _smooth(u): return u**3 * (10.0 + u * (-15.0 + 6.0*u))
def _speed(u): return 30.0 * u*u * (1.0-u)**2
def _acceleration(u): return 60.0 * u * (1.0-u) * (1.0-2.0*u)


def expand(plan):
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("plan_schema")
    if plan.get("command_capable") is not False or plan.get("execution_authorized") is not False:
        raise ValueError("plan_must_be_nonexecuting")
    dt = plan.get("sample_period_s")
    if type(dt) not in (int, float) or not math.isfinite(dt) or dt <= 0:
        raise ValueError("sample_period_s")
    result = {}
    for episode_name in ("training", "validation"):
        episode = plan.get("episodes", {}).get(episode_name)
        if not isinstance(episode, dict) or not isinstance(episode.get("segments"), list):
            raise ValueError("episode")
        rows=[]; time_s=0.0; offsets=[0.0]*7
        for segment_index, segment in enumerate(episode["segments"]):
            duration=segment.get("duration_s")
            if type(duration) not in (int,float) or not math.isfinite(duration) or duration <= 0:
                raise ValueError("segment_duration")
            steps=max(1,round(duration/dt))
            if abs(steps*dt-duration)>1e-10: raise ValueError("segment_not_on_sample_grid")
            if segment.get("kind")=="hold":
                joint=segment.get("joint_index")
                if joint is not None:
                    if joint not in RIGHT_ARM: raise ValueError("hold_joint")
                    offsets[joint-22]=float(segment["offset_rad"])
                for step in range(steps):
                    rows.append((time_s+step*dt,segment_index,joint,offsets.copy(),0.0,0.0))
            elif segment.get("kind")=="quintic_move":
                joint=segment.get("joint_index")
                if joint not in RIGHT_ARM: raise ValueError("move_joint")
                local=joint-22;start=float(segment["start_offset_rad"]);end=float(segment["end_offset_rad"])
                if abs(offsets[local]-start)>1e-12: raise ValueError("segment_discontinuity")
                delta=end-start
                for step in range(steps):
                    u=step/steps; q=start+delta*_smooth(u)
                    current=offsets.copy();current[local]=q
                    rows.append((time_s+step*dt,segment_index,joint,current,
                                 delta/duration*_speed(u),delta/duration**2*_acceleration(u)))
                offsets[local]=end
            else: raise ValueError("segment_kind")
            time_s += duration
        rows.append((time_s,len(episode["segments"]),None,offsets.copy(),0.0,0.0))
        if any(abs(x)>1e-12 for x in offsets): raise ValueError("episode_does_not_return_to_zero")
        result[episode_name]=rows
    return result


def write(plan_path, output_directory):
    plan_path=Path(plan_path);output_directory=Path(output_directory)
    if output_directory.exists(): raise FileExistsError(output_directory)
    plan=decode(plan_path.read_bytes());episodes=expand(plan);output_directory.mkdir()
    hashes={};counts={};peaks={}
    for name,rows in episodes.items():
        path=output_directory/f"{name}.csv"
        with path.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.writer(stream);writer.writerow(["time_s","segment","active_joint",*[f"offset_{j}_rad" for j in RIGHT_ARM],"active_velocity_rad_s","active_acceleration_rad_s2"])
            for t,segment,joint,offsets,velocity,acceleration in rows:
                writer.writerow([t,segment,"" if joint is None else joint,*offsets,velocity,acceleration])
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest();counts[name]=len(rows)
        peaks[name]={"velocity_abs_max_rad_s":max(abs(x[4]) for x in rows),
                     "acceleration_abs_max_rad_s2":max(abs(x[5]) for x in rows),
                     "duration_s":rows[-1][0]}
    summary={"schema":SCHEMA,"plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
             "csv_sha256":hashes,"samples":counts,"peaks":peaks,
             "command_capable":False,"physical_execution_authorized":False,
             "recommended_hardware_gains":None}
    (output_directory/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("plan",type=Path)
    parser.add_argument("--output-directory",type=Path,required=True);args=parser.parse_args(argv)
    print(json.dumps(write(args.plan,args.output_directory),indent=2))


if __name__=="__main__":main()
