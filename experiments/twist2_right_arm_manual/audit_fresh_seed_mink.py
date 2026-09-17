"""Fresh file -> Mink model audit. No sockets, viewer, SDK or robot output."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"backend/tools"))
from verify_feasible_target import BuildPlanner,probe
from g1_lowstate_seed import ReadSeed,ApplySeed
from g1_standard_mink_planner import StandardMinkPlanner
from g1_virtual_center_tasks import virtual_center_velocity_limits
import numpy as np

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed",type=Path,required=True)
    p.add_argument("--session",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    base=probe.base
    with tempfile.TemporaryDirectory() as directory:
        xml=base._prepare_mink_xml(output_path=Path(directory)/"model.xml")
        model=probe.mujoco.MjModel.from_xml_path(str(xml))
    base._apply_operational_joint_limits(model)
    original=base._initial_configuration(model)
    shared=BuildPlanner(model,original,collision_profile="mink-default")
    planner=StandardMinkPlanner(model,*shared.tasks,shared.limits,shared.constraints,
        shared.solver,shared.clearance_m,virtual_center_velocity_limits(),horizon_steps=1)
    result=dict(robot_output=False,actual_vr_engage=False,base_pose_measured=False)
    try:
        deadline=time.monotonic()+40
        while True:
            try:
                seed=ReadSeed(args.seed,args.session,base.g1.G1_29_JOINT_NAMES)
                break
            except FileNotFoundError:
                if time.monotonic()>=deadline:raise TimeoutError("seed_not_received")
                time.sleep(.02)
        result["seed"]=seed
        q=ApplySeed(model,original,seed,base.g1.G1_29_JOINTS)
        ids=[int(model.jnt_qposadr[base._joint_id(model,n)]) for n in base.g1.G1_29_JOINTS]
        unused=[i for i in range(model.nq) if i not in ids]
        result["mapping_max_error_rad"]=float(np.max(np.abs(q[ids]-seed["q"])))
        result["unmapped_qpos_unchanged"]=bool(np.array_equal(q[unused],original[unused]))
        valid,clearance=planner.CheckConfigurationWithClearance(q)
        result.update(configuration_valid=bool(valid),clearance_m=clearance)
        if not valid:raise ValueError("initial_seed_configuration_rejected")
        planner.configuration.update(q)
        goal=planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link","body")
        plan=planner.Plan(q,goal,goal.translation())
        result.update(synthetic_hold_valid=bool(plan.valid),synthetic_hold_status=plan.status,
            synthetic_hold_max_joint_delta_rad=float(np.max(np.abs(plan.next_q[ids]-q[ids]))),
            validation_age_s=time.time()-seed["received_at_unix_s"])
        if not plan.valid or result["synthetic_hold_max_joint_delta_rad"]>.025:
            raise ValueError("synthetic_hold_mismatch")
        if not 0<=result["validation_age_s"]<=.25:raise ValueError("seed_expired_during_audit")
        result["passed"]=True
    except Exception as error:
        result.update(passed=False,error=f"{type(error).__name__}: {error}")
    with args.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
    if not result["passed"]:raise SystemExit(1)

if __name__=="__main__":Main()
