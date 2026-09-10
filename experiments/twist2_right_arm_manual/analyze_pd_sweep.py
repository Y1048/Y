"""Rank the three recorded proximal-Kp segments from one-owner PD sweep."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def rms(xs):
    return math.sqrt(sum(x*x for x in xs)/len(xs))


def analyze(path):
    path=Path(path);groups={40.0:[],48.0:[],56.0:[]};seen=set()
    with path.open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row.get('writer_valid')!='1' or int(row['writer_trial_phase']) not in (2,3,4,5):continue
            seq=int(row['writer_sequence'])
            if seq in seen:continue
            seen.add(seq)
            kp=round(float(row['writer_kp_22']),6)
            if kp not in groups:raise ValueError(f'unexpected proximal Kp {kp}')
            for j in range(22,26):
                if abs(float(row[f'writer_kp_{j}'])-kp)>1e-5 or abs(float(row[f'writer_kd_{j}'])-5)>1e-5:
                    raise ValueError('proximal gain mismatch')
            groups[kp].append(row)
    candidates=[]
    for kp,rows in groups.items():
        if not rows:raise ValueError(f'missing Kp {kp} segment')
        phases={(int(r['writer_trial_cycle']),int(r['writer_trial_phase'])) for r in rows}
        if not all((c,p) in phases for c in range(3) for p in (2,3,4,5)):
            raise ValueError(f'incomplete Kp {kp} trajectory')
        joints=[]
        for j in range(22,29):
            errors=[float(r[f'writer_target_{j}'])-float(r[f'writer_q_{j}']) for r in rows]
            joints.append({'joint':j,'rmse_rad':rms(errors),'peak_abs_error_rad':max(map(abs,errors)),
              'peak_abs_speed_rad_s':max(abs(float(r[f'writer_dq_{j}'])) for r in rows),
              'peak_abs_tau_est_nm':max(abs(float(r[f'writer_tau_est_{j}'])) for r in rows)})
        score=rms([e for r in rows for j in range(22,26)
                   for e in [float(r[f'writer_target_{j}'])-float(r[f'writer_q_{j}'])]])
        candidates.append({'proximal_kp':kp,'proximal_kd':5.0,'samples':len(rows),
                           'proximal_tracking_rmse_rad':score,'joints':joints})
    candidates.sort(key=lambda x:x['proximal_tracking_rmse_rad'])
    return {'schema':'g1.pd.sweep.review.v1','source':str(path.resolve()),
      'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'ranking':candidates,
      'selection_rule':'Lowest proximal RMSE is only eligible if the run completed and torque limiting, oscillation, body attitude, and operator observations are acceptable.',
      'limitation':'Recorded physical comparison, not proof of global optimum or robot safety.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=analyze(a.csv);a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
