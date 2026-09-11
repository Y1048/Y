"""Offline per-joint PD research. NEVER import a robot SDK, create DDS or deploy gains.

Only joint23 may exceed the legacy Kp100 software search ceiling, up to300 in
this isolated experiment. Original hardware validators, actuator torque/ranges,
all29 inner-limit guards and quality thresholds are NOT modified. This is not
permission to send the candidate through the hardware launcher.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from contextlib import contextmanager
from dataclasses import asdict,dataclass
from pathlib import Path
import json,math
import numpy as np
import mujoco_pd_operating_core as core
import mujoco_pd_operating_study as operating
import mujoco_pd_expand as expanded
from mujoco_pd_expand_audit import safe_path

engine=core.engine
BASE=(100.,1.4)
KP_CAP=(100.,300.,100.,100.)

@dataclass(frozen=True)
class Gains:
    kp:tuple=(100.,100.,100.,100.)
    kd:tuple=(1.4,1.4,1.4,1.4)
    def validate(self):
        if len(self.kp)!=4 or len(self.kd)!=4:raise ValueError('Four proximal joint gains required')
        if not all(math.isfinite(x) and 1<=x<=cap for x,cap in zip(self.kp,KP_CAP)):
            raise ValueError('Offline Kp bounds are100,300,100,100; never a hardware approval')
        if not all(math.isfinite(x) and .1<=x<=20 for x in self.kd):raise ValueError('Kd bounds0.1..20')
    @property
    def key(self):return tuple(self.kp)+tuple(self.kd)

@contextmanager
def scoped_gains(gains):
    """Process-local adapter: restore even on failure; no disk/live config mutation.

The experiment uses separate worker processes. Concurrent threads invoking the
same core while this scope is open are unsupported and deliberately not used.
"""
    gains.validate();old=engine.candidate_gains
    def assign(contract,p,d):
        if (p,d)!=BASE:raise ValueError('Unexpected core adapter sentinel')
        kp,kd=old(contract,p,d)
        kp[22:26]=gains.kp;kd[22:26]=gains.kd
        return kp,kd
    engine.candidate_gains=assign
    try:yield
    finally:engine.candidate_gains=old

def simulate(profile,gains,scenario):
    gains.validate()
    with scoped_gains(gains):r,a=core.simulate(profile,*BASE,scenario)
    del r['kp'];del r['kd'] # Do not mislabel the four different applied gains.
    r['candidate']=asdict(gains)
    r['legacy_hardware_gain_compatible']=all(x<=100 for x in gains.kp)
    r['simulation_cap_extension_joint23']=gains.kp[1]>100
    r['recommended_hardware_gains']=None
    return r,a

def write_case(job,folder):
    g=Gains(**job['candidate']);p=core.Profile(**job['profile']);s=core.Coupled(**job['scenario'])
    r,a=simulate(p,g,s)
    r.update(case_id=job['case_id'],phase=job['phase'])
    folder=Path(folder);dest=folder/'full_state'/(job['case_id']+'.npz')
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Save every29-position/velocity/reference/command/torque stream, failures too.
    np.savez_compressed(dest,**a)
    r.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    expanded.save_json(folder/'cases'/(job['case_id']+'.json'),r)
    return r

def gain_key(r):
    g=Gains(**r['candidate']);g.validate();return g.key

def ranking(records,plan):
    expected={j['case_id']:j for j in plan};seen={r['case_id']:r for r in records}
    if len(expected)!=len(plan) or len(seen)!=len(records) or set(expected)!=set(seen):
        raise ValueError('Incomplete or duplicate per-joint cases')
    for identifier,r in seen.items():
        for field in ('candidate','profile','scenario','phase'):
            if json.dumps(r[field],sort_keys=True)!=json.dumps(expected[identifier][field],sort_keys=True):
                raise ValueError('Recorded candidate/profile differs from plan')
    rows=[]
    for key in sorted({gain_key(r) for r in records}):
        rs=[r for r in records if gain_key(r)==key];good=all(r['eligible'] for r in rs)
        metric=lambda name:max((r['metrics'][name] for r in rs if r['metrics'] and r['metrics'].get(name) is not None),default=None)
        rows.append({'candidate':json.loads(json.dumps(asdict(Gains(key[:4],key[4:])))), 'cases':len(rs),
          'passed':sum(r['eligible'] for r in rs),'all_pass':good,
          'worst_rmse_rad':metric('active_rmse_rad') if good else None,
          'partial_worst_rmse_rad':metric('active_rmse_rad'),
          'worst_tail_error_rad':metric('max_active_tail_error_rad'),
          'worst_tail_speed_rad_s':metric('max_right7_tail_rms_speed_rad_s'),
          'failures':[{'case_id':r['case_id'],'reason':r['reason'],'exclusions':r['exclusions']} for r in rs if not r['eligible']]})
    return sorted(rows,key=lambda x:(not x['all_pass'],x['worst_rmse_rad'] if x['all_pass'] else math.inf,
                                     tuple(x['candidate']['kp']),tuple(x['candidate']['kd'])))

def audit_case(folder,job):
    """Reuse exact operating audit, adapting its scalar gain check only in memory.

The on-disk per-joint record carries actual arrays, never a forged scalar pair.
A fresh full-state recomputation verifies all metrics and guards independently.
"""
    folder=Path(folder);r=json.loads((folder/'cases'/(job['case_id']+'.json')).read_text())
    for field in ('candidate','profile','scenario','phase'):
        if json.dumps(r[field],sort_keys=True)!=json.dumps(job[field],sort_keys=True):raise ValueError('Plan mismatch')
    g=Gains(**r['candidate']);g.validate();p=core.Profile(**r['profile']);s=core.Coupled(**r['scenario'])
    expected_kp,expected_kd=engine.candidate_gains(core.profile_contract(p),*BASE)
    expected_kp[22:26]=g.kp;expected_kd[22:26]=g.kd
    if not np.array_equal(r['gains_kp'],expected_kp) or not np.array_equal(r['gains_kd'],expected_kd):raise ValueError('Applied vector gains changed')
    if r['quality_policy']!=core.POLICY or not r['simulation_only'] or r['hardware_config_modified'] or r['recommended_hardware_gains'] is not None:
        raise ValueError('Policy/hardware claim mismatch')
    if r['legacy_hardware_gain_compatible']!=all(x<=100 for x in g.kp):raise ValueError('Hardware compatibility misreported')
    dest=safe_path(folder,r['trace'])
    if engine.sha256(dest)!=r['trace_sha256']:raise ValueError('Trace hash mismatch')
    with np.load(dest,allow_pickle=False) as z:a={k:z[k] for k in z.files}
    actual=core.evaluate(a,p,r['completed'],r['reason'],r['physics'])
    if any(r[k]!=v for k,v in actual.items()):raise ValueError('Per-joint trace metrics changed')
    requested=expected_kp*(a["cmd"]-a["q"])-expected_kd*a["dq"]
    if not np.allclose(requested,a["requested"],rtol=1e-12,atol=1e-12):raise ValueError("Recorded PD torque equation differs")
    operating.check_guard(r,a)
    # Temporary in-memory scalar adapter for the inherited reference verifier.
    # The recorded result never acquires a false common-gain label.
    with scoped_gains(g):operating.check_reference(dict(r,kp=BASE[0],kd=BASE[1]),a)
    operating.coupled.check_model_evidence({"study_scenario_contract":r["scenario"],
      "coupled_model_evidence":r["model_evidence"],
      "torque_path":{"delay_s":s.delay_s,"lag_s":s.lag_s}})
    return r,a
