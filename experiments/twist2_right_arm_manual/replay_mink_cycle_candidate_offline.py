"""Real Mink/Ruckig model samples -> local C++ pipe. No transport or SDK.

Run from project root after compiling mink_cycle_candidate_stdio_offline.cpp.
Feedback follows the prior model target; this is NOT a physical G1 simulation.
"""
import json
import subprocess
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
runtime=ROOT/'logs/diagnostics/mujoco_versions/3.12.0'
if not (runtime/'mujoco').is_dir():raise RuntimeError('isolated MuJoCo 3.12.0 missing')
sys.path.insert(0,str(runtime))
import mujoco
if mujoco.__version__!='3.12.0':raise RuntimeError('wrong isolated runtime')
import numpy as np
from replay_upstream_mink import build, base

ROOT = Path(__file__).resolve().parents[2]


def main():
    model, planner, trajectory = build()
    q = base._initial_configuration(model)
    home = q.copy()
    planner.configuration.update(q)
    trajectory.Reset(q)
    all_ids = [int(model.joint(name).qposadr[0]) for name in base.g1.G1_29_JOINTS]
    bounds = model.jnt_range[planner.joint_ids]
    process = subprocess.Popen([str(ROOT/'logs/test_results/mink_cycle_candidate_stdio_offline.exe')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def write(value):
        process.stdin.write(json.dumps(value, allow_nan=False)+'\n');process.stdin.flush()
    write(dict(home=q[all_ids].tolist(), lower=bounds[:,0].tolist(), upper=bounds[:,1].tolist()))
    sequence=0;epoch=0;now=0.;accepted=0;cycles=[];resample_inputs=[]
    def send(event, start, candidate):
        nonlocal sequence,epoch,now,accepted
        sequence+=1;now+=trajectory.dt_s
        valid=trajectory._safe_path(start,candidate)
        packet=dict(schema='g1.mink.cycle.offline.v1',provenance='offline_only',
            profile='right_arm_90_180_a60',session='offline-model-cycle',sequence=sequence,
            epoch=epoch,source_age_s=0.,event=event,joints=candidate[planner.qpos_ids].tolist())
        write(dict(time=now,packet=packet,measured=start[all_ids].tolist(),dq=[0.]*29,
            feedback_received=now,r1=True,stop=False,path_checked=valid))
        result=json.loads(process.stdout.readline())
        assert result['accepted'],result
        np.testing.assert_allclose(result['q'],candidate[all_ids],atol=1e-12)
        epoch=result['epoch'];accepted+=1
        resample_inputs.append(candidate[planner.qpos_ids].tolist())
        return result
    try:
        for release in ('pinch','tracking_disengaged'):
            send('idle',q,q);send('active',q,q)
            planner.configuration.update(q);planner.ResetDetour();trajectory.Reset(q)
            pose=planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link','body')
            goal=base._matrix_to_se3(pose.rotation().as_matrix(),pose.translation()+[.02,0,0])
            for _ in range(180):
                step=trajectory.Track(q,goal);assert step.applied,step.status
                send('active',q,step.q);q=step.q
            trajectory.BeginReturn(q)
            for tick in range(1800):
                step=trajectory.Step(q,home);assert step.applied,step.status
                result=send(release if tick==0 else 'return',q,step.q);q=step.q
                if result['state']=='waiting':break
            assert result['state']=='waiting','return did not settle'
            cycles.append(dict(release=release,return_ticks=tick+1,epoch=epoch))
        send('idle',q,q);result=send('active',q,q)
        assert result['state']=='tracking'
        process.stdin.close();assert process.wait(timeout=5)==0
        # Mathematical resampling fixture has no geometry authority. Validate all
        # generated 500 Hz segments here against the actual model before reporting.
        batch=dict(home=home[all_ids].tolist(),lower=bounds[:,0].tolist(),
                   upper=bounds[:,1].tolist(),samples=resample_inputs+[resample_inputs[-1]]*10)
        replay=subprocess.run([str(ROOT/'logs/test_results/mink_resampler_batch_offline.exe')],
            input=json.dumps(batch,allow_nan=False),text=True,capture_output=True,check=True)
        generated=json.loads(replay.stdout)
        (ROOT/'logs/test_results/mink_resampler_generated_offline.json').write_text(json.dumps(dict(batch=batch,generated=generated)))
        assert generated['offline_only'] and not generated['geometry_checked']
        print(json.dumps(dict(resampled_fixture_samples=len(generated['outputs']),geometry_checked=False)))
        report=dict(offline_only=True,mujoco_version=mujoco.__version__,feedback='ideal_previous_model_target',
            accepted_samples=accepted,cycles=cycles,reengaged=True,publisher_created=False)
        (ROOT/'logs/test_results/mink_cycle_candidate_model_replay.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report))
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        for pipe in (process.stdin,process.stdout,process.stderr):pipe.close()


if __name__=='__main__':main()
