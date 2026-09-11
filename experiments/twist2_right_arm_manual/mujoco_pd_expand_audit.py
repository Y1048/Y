"""Read-only audit of expanded PD simulation artifacts; no MuJoCo or hardware import.

Recompute joint22 metrics from every compressed 500 Hz trace, including failures.
Native Windows manifest separators are accepted on Linux. Optional --source-root
checks EXACT original checkout bytes, so a differently normalized checkout can fail.
The seven-joint aggregate metrics and physics-rate counters are recorded observations,
not independently reconstructed from the joint22-only trace.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

METRICS=('reference_rmse_joint22_rad','command_rmse_joint22_rad',
 'peak_reference_error_joint22_rad','peak_hold_overshoot_joint22_rad',
 'peak_speed_joint22_rad_s','peak_torque_joint22_nm','rms_torque_joint22_nm',
 'torque_target_limit_arm_sample_ratio','hard_clip_arm_sample_ratio',
 'slew_exceeded_arm_sample_ratio','contact_sample_ratio')
SEGMENTS={'out','positive_hold','cross','negative_hold','return','ready_hold'}

def require(value,message):
    if not value: raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def safe_path(folder,name):
    root=Path(folder).resolve()
    target=(root/name.replace('\\','/')).resolve()
    require(target.is_relative_to(root),'Artifact path escapes its root')
    return target

def metric_values(v):
    error=v['ref_22']-v['q_22']; cmd=v['cmd_22']-v['q_22']
    holds=np.isin(v['phase'],(3,5))
    return dict(zip(METRICS,(
      float(np.sqrt(np.mean(error**2))),float(np.sqrt(np.mean(cmd**2))),
      float(np.max(np.abs(error))),float(max(0.,np.max(v['direction'][holds]*(v['q_22'][holds]-v['ref_22'][holds])))) if holds.any() else 0.,
      float(np.max(np.abs(v['dq_22']))),float(np.max(np.abs(v['actual_tau_22']))),
      float(np.sqrt(np.mean(v['actual_tau_22']**2))),float(np.mean(v['torque_target_limited_arm'])),
      float(np.mean(v['hard_clipped_arm'])),float(np.mean(v['slew_exceeded_arm'])),float(np.mean(v['contacts']>0)))))

def check_case(folder,path):
    r=read(path); label=path.name
    require(r['simulation_only'] is True and r['hardware_config_modified'] is False,label+': hardware flags')
    require(r['case_id']==path.stem,label+': case identity')
    trace=safe_path(folder,r['trace_npz'])
    require(sha(trace)==r['trace_sha256'],label+': trace hash')
    with np.load(trace,allow_pickle=False) as archive:
        cols=archive['columns'].tolist(); values=archive['values']; segments=archive['segment']
        require(values.shape==(r['trace_rows'],len(cols)) and len(segments)==len(values),label+': shape')
        require(len(cols)==len(set(cols)) and np.isfinite(values).all(),label+': columns or finite values')
        v={c:values[:,i] for i,c in enumerate(cols)}
        require(np.allclose(np.diff(v['time_s']),.002,rtol=0,atol=1e-10),label+': 500Hz continuity')
        require(np.allclose(v['time_s']-3.,v['trial_time_s'],rtol=0,atol=1e-10),label+': warmup clock')
        mask=v['trial_time_s']>=0; trial={c:x[mask] for c,x in v.items()}; seg=segments[mask]
        require(int(mask.sum())==r['samples'],label+': trial sample count')
        require(np.array_equal(np.array(r['gains_kp'])[22:26],[r['kp_proximal']]*4),label+': Kp fields')
        require(np.array_equal(np.array(r['gains_kd'])[22:26],[r['kd_proximal']]*4),label+': Kd fields')
        metrics=metric_values(trial) if mask.any() else None
        require((metrics is None)==(r['metrics'] is None),label+': absent metrics')
        if metrics:
            for k,value in metrics.items():
                require(math.isclose(value,r['metrics'][k],rel_tol=1e-11,abs_tol=1e-12),label+': '+k)
            for h in r['metrics']['endpoint_holds']:
                ids=(trial['cycle']==h['cycle']) & (seg==h['segment']) & np.isin(trial['phase'],(3,5))
                require(ids.any(),label+': missing hold')
                q=trial['q_22'][ids]; ref=trial['ref_22'][ids]; dq=trial['dq_22'][ids]; t=trial['time_s'][ids]
                good=(np.abs(q-ref)<=.02)&(np.abs(dq)<=.1)
                suffix=np.logical_and.accumulate(good[::-1])[::-1]; idx=np.flatnonzero(suffix)
                settling=None if not len(idx) else float(t[idx[0]]-t[0])
                require(settling==h['settling_time_s'],label+': settling')
                require(math.isclose(float(q[-1]-ref[-1]),h['terminal_error_rad'],abs_tol=1e-12),label+': terminal hold')
        if r['completed']:
            require(r['reason']=='',label+': completed with error')
            require(r['samples']==7633 and set(trial['cycle'])=={0,1,2},label+': complete cycle count')
            for cycle in (0,1,2):
                require(SEGMENTS<=set(seg[trial['cycle']==cycle]),label+': missing cycle segment')
        counters=r['physics_observation']
        require(counters['trial_physics_steps']>=r['samples'],label+': full-rate count')
        expected=bool(r['completed'] and metrics and metrics['contact_sample_ratio']==0
          and metrics['torque_target_limit_arm_sample_ratio']<=.05
          and metrics['hard_clip_arm_sample_ratio']<=.05 and counters['trial_contact_steps']==0)
        require(r['eligible']==expected,label+': eligibility')
        nominal_q=trial['q_22'].copy() if r['scenario'][0]=='nominal' else None
    return r,metrics,nominal_q

def audit(folder,source_root=None):
    folder=Path(folder).resolve(); summary=read(folder/'summary.json'); manifest=read(folder/'manifest.json')
    require(summary['complete'] is True and summary['simulation_only'] is True,'Incomplete/non-simulation summary')
    require(summary['recommended_hardware_gains'] is None and summary['hardware_config_modified'] is False,'Hardware recommendation present')
    require(sha(folder/'manifest.json')==summary['manifest_sha256'],'Manifest hash mismatch')
    if source_root:
        root=Path(source_root)
        for name,digest in manifest['source_sha256'].items():
            require(sha(safe_path(root,name))==digest,'Source changed: '+name)
        model_base=root/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in manifest['asset_sha256'].items():
            base=model_base if name.replace('\\','/').startswith('meshes/') else root
            require(sha(safe_path(base,name))==digest,'Model/mesh changed: '+name)
    records=[]; nominal={}; inventory={}
    for path in sorted((folder/'cases').glob('*.json')):
        r,m,q=check_case(folder,path);records.append((r,m))
        identity=(r['kp_proximal'],r['kd_proximal'],r['scenario'][0])
        require(identity not in inventory,'Duplicate pair/scenario')
        inventory[identity]=r['trace_sha256']
        if q is not None:nominal[identity[:2]]=q
    require(len(records)==summary['count'],'Case count differs')
    require(sum(r['completed'] for r,_ in records)==summary['completed_count'],'Completed count differs')
    require(sum(r['eligible'] for r,_ in records)==summary['eligible_count'],'Eligible count differs')
    if 'nominal_ranking' in summary:
        ordered=sorted((r for r,_ in records if r['scenario'][0]=='nominal' and r['eligible']),
          key=lambda r:(r['metrics']['reference_rmse_joint22_rad'],r['kp_proximal'],r['kd_proximal']))
        require([r['case_id'] for r in ordered]==[r['case_id'] for r in summary['nominal_ranking']],'Nominal ranking differs')
    ranking=summary.get('robust_ranking',summary.get('ranking',[]))
    for rank in ranking:
        selected=[r for r,_ in records if [r['kp_proximal'],r['kd_proximal']]==rank['pair']]
        require(len(selected)==rank['required'],'Missing stress cases for '+str(rank['pair']))
        require(sum(r['eligible'] for r in selected)==rank['eligible_count'],'Stress eligible count differs')
        worst=max(r['metrics']['reference_rmse_joint22_rad'] for r in selected if r['metrics'])
        require(math.isclose(worst,rank['worst_rmse'],abs_tol=1e-12),'Worst-case error differs')
    files={str(p.relative_to(folder)).replace('\\','/'):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    fingerprint=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'folder':str(folder),'count':len(records),'completed':summary['completed_count'],
      'eligible':summary['eligible_count'],'rejected':len(records)-summary['eligible_count'],
      'trace_metric_checks':sum(m is not None for _,m in records)*len(METRICS),
      'manifest_sha256':summary['manifest_sha256'],'summary_sha256':sha(folder/'summary.json'),
      'source_bytes_checked':bool(source_root),'files':files,'file_inventory_sha256':fingerprint},records,nominal

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders',nargs=2,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-root',type=Path)
    args=parser.parse_args(argv)
    dest=args.output.resolve();require(not dest.exists(),'Output already exists')
    require(not any(dest.is_relative_to(p.resolve()) for p in args.folders),'Audit output must be outside source results')
    reports=[];rows=[];nominals=[]
    for folder in args.folders:
        report,records,nominal=audit(folder,args.source_root);reports.append(report);nominals.append(nominal)
        for r,m in records:
            row={'dataset':folder.name,'case_id':r['case_id'],'stage':r['stage'],
              'kp':r['kp_proximal'],'kd':r['kd_proximal'],'scenario':r['scenario'][0],
              'completed':r['completed'],'eligible':r['eligible'],'reason':r['reason'],
              'exclusions':';'.join(r['exclusion_reasons']),'samples':r['samples'],
              'scenario_parameters':json.dumps(r.get('actuator_scenario',r['scenario']),sort_keys=True),
              'trace_sha256':r['trace_sha256']}
            row.update({k:m[k] if m else None for k in METRICS});rows.append(row)
    matched=sorted(set(nominals[0])&set(nominals[1]))
    for pair in matched:require(np.array_equal(nominals[0][pair],nominals[1][pair]),'Nominal q22 parity fails: '+str(pair))
    dest.mkdir(parents=True,exist_ok=False)
    with (dest/'all_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'schema':'g1.pd.expanded.audit.v1','simulation_only':True,'passed':True,
      'total':sum(r['count'] for r in reports),'completed':sum(r['completed'] for r in reports),
      'eligible':sum(r['eligible'] for r in reports),'rejected':sum(r['rejected'] for r in reports),
      'exact_cross_study_nominal_q22_pairs':matched,'runs':reports,'all_cases_csv_sha256':sha(dest/'all_cases.csv'),
      'auditor_sha256':sha(Path(__file__)),'scope':'joint22 trace metrics; other joints aggregate only; full-rate counters not independently reconstructed',
      'recommended_hardware_gains':None,'hardware_config_modified':False}
    (dest/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
