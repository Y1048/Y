"""Generate a Mink reach/return reference only. No sockets, SDK, or robot output."""
import csv
import json
import math
import os
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[2]
os.environ['G1_USE_HARDWARE_INITIAL_STATE'] = '0'
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
import run_mink_g1_right_arm_prototype as base
import mink
import numpy as np
from numpy.polynomial import Polynomial
from pd_reach_timing import choose_timing, check_acceleration, MAX_ACCELERATION_RAD_S2


def plan(output):
    output.mkdir(parents=True, exist_ok=False)
    model, metadata = base.LoadMinkModelWithMetadata()
    base._apply_operational_joint_limits(model)
    q0 = base._initial_configuration(model)
    ids = [int(model.jnt_qposadr[base._joint_id(model,n)]) for n in base.g1.RIGHT_ARM_JOINTS]
    all_ids = [int(model.jnt_qposadr[base._joint_id(model,n)]) for n in base.g1.G1_29_JOINTS]
    config = mink.Configuration(model); config.update(q0)
    start = config.get_transform_frame_to_world('right_wrist_yaw_link','body')
    # FK selects a reachable task goal at approximately shoulder height.
    # It does not replace IK: every intermediate task pose is solved below.
    seed = q0.copy(); seed[ids] = np.deg2rad([-50,-22,0,20,0,0,0])
    config.update(seed)
    end = config.get_transform_frame_to_world('right_wrist_yaw_link','body')
    config.update(q0)
    pairs, geom_ids = base._build_collision_pairs(model)
    task = mink.FrameTask('right_wrist_yaw_link','body',1.0,1.0,lm_damping=1e-3)
    dofs = base._right_arm_dof_indices(model)
    constraints = [mink.DofFreezingTask(model,base._frozen_dof_indices(model,dofs))]
    limits = [mink.ConfigurationLimit(model),
              mink.VelocityLimit(model,{n:math.pi/4 for n in base.g1.RIGHT_ARM_JOINTS}),
              mink.CollisionAvoidanceLimit(model,geom_pairs=pairs,
                 minimum_distance_from_collisions=.02,collision_detection_distance=.06)]
    relative_rotation = start.rotation().inverse() @ end.rotation()
    points = [q0[ids].copy()]
    worst_position = worst_rotation = 0.0
    for u in np.linspace(0,1,81)[1:]:
        rotation = start.rotation() @ mink.SO3.exp(relative_rotation.log()*u)
        position = start.translation()*(1-u)+end.translation()*u
        position = position + np.array([.08*math.sin(math.pi*u),0,0])
        goal = base._matrix_to_se3(rotation.as_matrix(),position)
        task.set_target(goal)
        for iteration in range(400):
            pose = config.get_transform_frame_to_world('right_wrist_yaw_link','body')
            pe = np.linalg.norm(goal.translation()-pose.translation())
            re = np.linalg.norm((goal.rotation().inverse()@pose.rotation()).log())
            if pe < .0005 and re < math.radians(.2): break
            velocity = mink.solve_ik(config,[task],.02,base._select_solver(),
                                     limits=limits,constraints=constraints,damping=1e-5)
            config.integrate_inplace(velocity,.02)
        else:
            raise RuntimeError(f'IK did not converge at {u:.3f}: position={pe}, orientation={re}')
        worst_position=max(worst_position,float(pe));worst_rotation=max(worst_rotation,float(re))
        points.append(config.q[ids].copy())
    nodes=np.linspace(0,1,len(points)); points=np.asarray(points)
    design=np.column_stack([nodes**(k+1)*(1-nodes) for k in range(6)])
    linear=points[0]+nodes[:,None]*(points[-1]-points[0])
    coefficients=np.linalg.lstsq(design,points-linear,rcond=None)[0]
    polynomials=[]
    for j in range(7):
        polynomial=Polynomial([points[0,j],points[-1,j]-points[0,j]])
        for k in range(6):
            values=np.zeros(k+3);values[k+1]=coefficients[k,j];values[k+2]=-coefficients[k,j]
            polynomial+=Polynomial(values)
        polynomials.append(polynomial)
    def curve(u,derivative=0):
        return np.column_stack([p.deriv(derivative)(u) for p in polynomials])
    timing,timing_times,timing_u,timing_du,timing_info=choose_timing(polynomials)
    seconds=float(timing_times[-1])
    dense=np.linspace(0,seconds,20001)
    dense_u=timing(dense);dense_du=timing(dense,1);dense_ddu=timing(dense,2)
    dq=curve(dense_u,1)*dense_du[:,None]
    ddq=curve(dense_u,2)*dense_du[:,None]**2+curve(dense_u,1)*dense_ddu[:,None]
    u=timing_u
    path=curve(u)
    min_clearance=math.inf; joint_margin=math.inf; frozen=0.; wrist=[]
    curve_position_error=curve_rotation_error=0.
    lower=np.array([model.jnt_range[base._joint_id(model,n),0] for n in base.g1.RIGHT_ARM_JOINTS])
    upper=np.array([model.jnt_range[base._joint_id(model,n),1] for n in base.g1.RIGHT_ARM_JOINTS])
    for index,arm in enumerate(path):
        q=q0.copy();q[ids]=arm;config.update(q)
        min_clearance=min(min_clearance,base._min_pair_distance(model,config.data,geom_ids))
        joint_margin=min(joint_margin,float(np.min(np.minimum(arm-lower,upper-arm))))
        frozen=max(frozen,float(np.max(np.abs(q[np.setdiff1d(np.arange(len(q)),ids)]-q0[np.setdiff1d(np.arange(len(q)),ids)]))))
        pose=config.get_transform_frame_to_world('right_wrist_yaw_link','body')
        wrist.append(pose.translation().tolist())
        parameter=u[index]
        goal_position=start.translation()*(1-parameter)+end.translation()*parameter+np.array([.08*math.sin(math.pi*parameter),0,0])
        goal_rotation=start.rotation()@mink.SO3.exp(relative_rotation.log()*parameter)
        curve_position_error=max(curve_position_error,float(np.linalg.norm(pose.translation()-goal_position)))
        curve_rotation_error=max(curve_rotation_error,float(np.linalg.norm((goal_rotation.inverse()@pose.rotation()).log())))
    peak_v=float(np.max(np.abs(dq)))
    peak_a=float(np.max(np.abs(ddq)))
    check_acceleration(peak_a)
    passed=curve_position_error<=.005 and curve_rotation_error<=math.radians(1) and min_clearance>=.02 and joint_margin>=0 and frozen==0 and peak_v<=math.pi/4 and math.isfinite(peak_a) and peak_v>=math.radians(44.9)
    with (output/'reach_return.csv').open('x',newline='') as f:
        w=csv.writer(f);w.writerow(['elapsed_s','phase']+[f'q_{i}' for i in range(29)])
        tick=0
        for phase,arms in [('outbound',path),('hold_far',np.repeat(path[-1:],500,axis=0)),
                           ('return',path[-2::-1]),('hold_start',np.repeat(path[:1],500,axis=0))]:
            for arm in arms:
                q=q0.copy();q[ids]=arm;w.writerow([tick/500,phase,*q[all_ids]]);tick+=1
    report=dict(offline_only=True,physical_execution_allowed=False,
        status='SAMPLED_KINEMATIC_CHECKS_PASSED' if passed else 'REVIEW_REQUIRED',
        initial_source='virtual Mink ready pose, NOT live LowState',model=metadata,
        mujoco_version=base.mujoco.__version__,start_wrist=start.translation().tolist(),
        end_wrist=end.translation().tolist(),wrist_displacement=(end.translation()-start.translation()).tolist(),
        right_arm_start_deg=np.rad2deg(points[0]).tolist(),right_arm_end_deg=np.rad2deg(points[-1]).tolist(),
        smoothing_max_position_error_m=curve_position_error,smoothing_max_orientation_error_deg=math.degrees(curve_rotation_error),
        timing_policy='duration selected from path; speed <=45 deg/s; acceleration <=10 rad/s^2',
        max_acceleration_rad_s2=MAX_ACCELERATION_RAD_S2,
        timing=timing_info,
        move_seconds=seconds,peak_speed_deg_s=math.degrees(peak_v),peak_acceleration_rad_s2=peak_a,
        minimum_configured_clearance_m=min_clearance,configured_collision_pairs=len(geom_ids),
        joint_margin_rad=joint_margin,frozen_joint_drift=frozen,
        worst_waypoint_position_error_m=worst_position,worst_waypoint_orientation_error_deg=math.degrees(worst_rotation),
        limits='Sampled model checks only; configured collision pairs, no full-body dynamics or physical safety proof; C++ replay not connected.')
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if passed:
        header=['#pragma once','#include <array>','namespace PdReachReference {',
                f'inline constexpr double move_seconds={seconds:.17g};',
                f'inline constexpr double max_acceleration_rad_s2={MAX_ACCELERATION_RAD_S2:.17g};',
                'inline constexpr std::array<std::array<double,8>,7> coefficients={{']
        for polynomial in polynomials:
            coef=np.pad(polynomial.coef,(0,8-len(polynomial.coef)))
            header.append('  {{'+','.join(f'{v:.17g}' for v in coef)+'}},')
        header.append('}};')
        for name,values in [('timing_u',timing_u),('timing_du',timing_du)]:
            header.append(f'inline constexpr std::array<double,{len(values)}> {name}={{'+','.join(f'{v:.17g}' for v in values)+'};')
        header.append('}')
        (output/'pd_reach_reference.hpp').write_text('\n'.join(header)+'\n')
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();plan(a.output)
