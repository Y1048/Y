"""Read-only summary for an incomplete native PD run."""
import argparse,csv,hashlib,json,math
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def analyze(folder):
 folder=Path(folder);result=json.loads((folder/'result.json').read_text());run=json.loads((folder/'run.json').read_text())
 if sha(folder/'policy.csv')!=result['csv_sha256'] or sha(folder/'run.json')!=result['run_sha256']:raise ValueError('provenance hash mismatch')
 rows=list(csv.DictReader((folder/'policy.csv').open(newline='',encoding='utf-8-sig')));seen=set();valid=[]
 for r in rows:
  if r['writer_valid']!='1':continue
  seq=int(r['writer_sequence'])
  if seq in seen:continue
  seen.add(seq);valid.append(r)
 trial=[r for r in valid if int(r['writer_trial_phase']) in (1,2,3,4,5)]
 if not trial:raise ValueError('no PD samples')
 def err(r,j):return float(r[f'writer_target_{j}'])-float(r[f'writer_q_{j}'])
 worst=max(((abs(err(r,j)),r,j) for r in trial for j in range(22,29)),key=lambda x:x[0])
 first,last=trial[0],trial[-1]
 return {'schema':'g1.pd.abort.review.v1','source':str(folder.resolve()),'csv_sha256':result['csv_sha256'],
  'rows':len(rows),'unique_writer_rows':len(valid),'termination_reason':result['reason'],'completed_reach':result['completed_reach'],
  'candidates_observed':sorted({float(r['writer_kp_22']) for r in trial}),
  'last_elapsed_s':float(last['elapsed_s']),'last_phase':last['phase'],
  'worst_sampled_error':{'joint':worst[2],'abs_rad':worst[0],'elapsed_s':float(worst[1]['elapsed_s']),
   'q_rad':float(worst[1][f'writer_q_{worst[2]}']),'target_rad':float(worst[1][f'writer_target_{worst[2]}'])},
  'trial_pitch':{'start_rad':float(first['pitch_rad']),'end_rad':float(last['pitch_rad']),
   'min_rad':min(float(r['pitch_rad']) for r in trial),'max_rad':max(float(r['pitch_rad']) for r in trial)},
  'trial_roll_abs_max_rad':max(abs(float(r['roll_rad'])) for r in trial),
  'peak_measured_arm_speed_rad_s':max(abs(float(r[f'writer_dq_{j}'])) for r in trial for j in range(22,29)),
  'peak_arm_tau_est_nm':max(abs(float(r[f'writer_tau_est_{j}'])) for r in trial for j in range(22,29)),
  'interpretation':'The 50-Hz log ends below the 0.25-rad writer trip because the safety check runs at 500 Hz. Joint 22 dominates sampled tracking error. IMU sign alone does not establish fall direction.',
  'physical_safety_validated':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();x=analyze(a.folder);a.output.write_text(json.dumps(x,indent=2),encoding='utf-8');print(json.dumps(x,indent=2))
