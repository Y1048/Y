"""Offline replay of recorded IK blocks; no viewer, sockets or SDK."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
import numpy as np
import mujoco
import mink

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))
import run_mink_g1_right_arm_prototype as base
from g1_standard_mink_planner import StandardMinkPlanner
from g1_mink_trajectory import StatefulMinkTrajectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines()]
    with tempfile.TemporaryDirectory() as directory:
        path = base._prepare_mink_xml(output_path=Path(directory)/"model.xml")
        model = mujoco.MjModel.from_xml_path(str(path))
    base._apply_operational_joint_limits(model)
    pairs, _ = base._build_collision_pairs(model)
    constraints = [mink.DofFreezingTask(model=model, dof_indices=base._frozen_dof_indices(model, base._right_arm_dof_indices(model)))]
    results = []
    for reserve in (0., .0005):
        record = {"reserve_m": reserve, "snapshots": []}
        for row in rows:
            minimum = row["required_clearance_m"]
            speeds = dict(zip(base.g1.RIGHT_ARM_JOINTS, row["velocity_limits"]))
            limits = [mink.ConfigurationLimit(model=model), mink.VelocityLimit(model, speeds),
                      mink.CollisionAvoidanceLimit(model=model, geom_pairs=pairs,
                        minimum_distance_from_collisions=minimum+reserve,
                        collision_detection_distance=.04, gain=base.COLLISION_GAIN, broadphase=True)]
            planner = StandardMinkPlanner(model,None,None,None,None,limits,constraints,base._select_solver(),minimum,speeds)
            q = np.array(row["current_q"])
            position = np.array(row["goal_position"])
            goal = base._matrix_to_se3(np.array(row["goal_rotation"]), position)
            plan = planner.Plan(q,goal,position_target=position)
            record["snapshots"].append({"steps":plan.accepted_steps,"status":plan.status})
        # Last recorded blocked pose, 500 ticks with the real shaping layer.
        trajectory = StatefulMinkTrajectory(planner,planner.qpos_ids,row["velocity_limits"],row["acceleration_limits"],[1.28]*7,base.DT)
        origin=q.copy(); min_clearance=planner.GetClearance(q); holds=0
        configuration=mink.Configuration(model);configuration.update(q)
        start_error=float(np.linalg.norm(configuration.get_transform_frame_to_world("right_wrist_yaw_link","body").translation()-position))
        for _ in range(500):
            plan=planner.Plan(q,goal,position_target=position)
            if plan.accepted_steps:
                step=trajectory.Step(q,plan.target_q)
                q=step.q
                holds+=not step.applied
            else:
                trajectory.Reset(q);holds+=1
            min_clearance=min(min_clearance,planner.GetClearance(q))
        configuration.update(q)
        final_error=float(np.linalg.norm(configuration.get_transform_frame_to_world("right_wrist_yaw_link","body").translation()-position))
        record.update(rollout_ticks=500,holds=int(holds),minimum_clearance_m=min_clearance,
                      target_position_error_start_m=start_error,target_position_error_final_m=final_error,
                      maximum_joint_change_rad=float(np.max(np.abs(q-origin))))
        results.append(record)
    args.output.write_text(json.dumps(results,indent=2),encoding="utf-8")
    for record in results:
        summary={k:v for k,v in record.items() if k!="snapshots"}
        summary["blocked_snapshots"]=sum(x["steps"]==0 for x in record["snapshots"])
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
