"""Robust PD refinement under mandatory all29 joint-limit screening.

Offline only. Reuse the existing torque dynamics, reference and refusal rules.
Freeze the search and holdout plans before starting; do not deploy any gain.
"""
from __future__ import annotations
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from dataclasses import asdict, dataclass
import itertools
import json
import math
from pathlib import Path
import platform
import time
import numpy as np
import mujoco_pd_expand as expanded
import mujoco_pd_motor_stress as motor
import mujoco_pd_sweep as engine
from mujoco_pd_expand_audit import check_case, safe_path
from mujoco_pd_limit_replay import verify_guard_result

KP_VALUES = (72, 80, 88, 96, 100)
KD_VALUES = (.6, .7, .8, .9, 1., 1.2, 1.5, 2.)
CONTROLS = ((40., 5.), (56., 3.), (100., .1), (100., 3.))
FINALIST_CONTROLS = ((40., 5.), (56., 3.), (80., 1.), (100., 1.), (100., 2.))
FINALIST_COUNT = 6


@dataclass(frozen=True)
class Scenario:
    family: str
    parameters: tuple

    @property
    def identity(self) -> str:
        return self.family + '/' + self.parameters[0]

    @property
    def timestep(self) -> float:
        return float(self.parameters[1] if self.family == 'model' else self.parameters[4])

    def validate(self) -> None:
        if self.family not in ('model', 'motor') or len(self.parameters) != 5:
            raise ValueError('Unknown offline scenario shape')
        if not isinstance(self.parameters[0], str) or not self.parameters[0]:
            raise ValueError('Missing scenario name')
        if not all(math.isfinite(float(v)) for v in self.parameters[1:]):
            raise ValueError('Non-finite scenario parameter')
        dt = self.timestep
        if not 0 < dt <= .002 or not math.isclose(.002/dt, round(.002/dt), abs_tol=1e-9):
            raise ValueError('Physics timestep must divide writer period')
        if self.family == 'motor':
            _, friction, delay, lag, _ = self.parameters
            if not 0 <= friction <= 2:
                raise ValueError('Friction factor outside study range')
            motor.TorquePath(dt, delay, lag)
        else:
            _, _, mass, damping, friction_add = self.parameters
            if not .5 <= mass <= 1.5 or not .25 <= damping <= 2 or not 0 <= friction_add <= .25:
                raise ValueError('Model perturbation outside explicit study bounds')


CALIBRATION = tuple(Scenario('motor', tuple(s)) for s in motor.SCENARIOS) + tuple(
    Scenario('model', tuple(s)) for s in expanded.SCENARIOS if s[0] not in ('nominal', 'dt_half'))
# Prespecified combined/intermediate conditions NOT used to select the finalists.
# These are hypothetical stress assumptions, not identified real G1 uncertainty.
HOLDOUT = (
    Scenario('motor', ('hold_f0125_d3_l3', .125, .003, .003, .001)),
    Scenario('motor', ('hold_f000_d3_l3', 0., .003, .003, .001)),
    Scenario('motor', ('hold_f050_d6_l2', .5, .006, .002, .001)),
    Scenario('motor', ('hold_f025_d2_l8', .25, .002, .008, .001)),
    Scenario('motor', ('hold_f000_d1_l8', 0., .001, .008, .001)),
    Scenario('model', ('hold_mass110_damp075_f005', .001, 1.1, .75, .05)),
    Scenario('model', ('hold_mass140_damp125_f015', .001, 1.4, 1.25, .15)),
    Scenario('model', ('hold_mass060_damp075', .001, .6, .75, 0.)),
)


def pair_of(record: dict) -> tuple[float, float]:
    return float(record['kp_proximal']), float(record['kd_proximal'])


def gain_pairs() -> list[tuple[float, float]]:
    return sorted(set(itertools.product(KP_VALUES, KD_VALUES)) | set(CONTROLS))


def rank_pairs(records: list[dict], pairs, scenarios, phase: str) -> list[dict]:
    """All conditions must pass before worst-case RMSE is a selectable score."""
    required = {s.identity for s in scenarios}
    index = {}
    for r in records:
        if r['study_phase'] != phase:
            continue
        identity = (pair_of(r), r['study_scenario'])
        if identity in index:
            raise ValueError('Duplicate pair/scenario evidence')
        index[identity] = r
    result = []
    for pair in pairs:
        cases = [index[(tuple(pair), name)] for name in sorted(required) if (tuple(pair), name) in index]
        complete = len(cases) == len(required)
        eligible = complete and all(r['eligible'] for r in cases)
        rmses = [r['metrics']['reference_rmse_joint22_rad'] for r in cases if r['metrics']]
        result.append({
            'pair': list(pair), 'conditions_observed': len(cases), 'conditions_required': len(required),
            'all_conditions_present': complete, 'all_conditions_eligible': eligible,
            'eligible_count': sum(r['eligible'] for r in cases),
            'selectable_worst_rmse_rad': max(rmses) if eligible else None,
            'partial_worst_rmse_rad': max(rmses) if rmses else None,
            'mean_rmse_rad': float(np.mean(rmses)) if eligible else None,
            'max_hold_overshoot_rad': max(r['metrics']['peak_hold_overshoot_joint22_rad'] for r in cases) if eligible else None,
            'max_joint22_torque_nm': max(r['metrics']['peak_torque_joint22_nm'] for r in cases) if eligible else None,
            'minimum_soft_margin_rad': min(min(r['joint_limit_guard']['minimum_soft_margin_rad']) for r in cases) if eligible else None,
            'failures': [{'scenario': r['study_scenario'], 'reason': r['reason'],
                          'exclusions': r['exclusion_reasons']} for r in cases if not r['eligible']],
        })
    return sorted(result, key=lambda r: (not r['all_conditions_eligible'],
                  r['selectable_worst_rmse_rad'] if r['all_conditions_eligible'] else math.inf, *r['pair']))


def choose_finalists(ranking, pairs) -> list[tuple[float, float]]:
    selected = {tuple(r['pair']) for r in ranking if r['all_conditions_eligible']}
    ordered = [tuple(r['pair']) for r in ranking if tuple(r['pair']) in selected][:FINALIST_COUNT]
    return sorted(set(ordered) | (set(FINALIST_CONTROLS) & set(map(tuple, pairs))))


def make_jobs(pairs, scenarios, phase, folder):
    return [(float(p), float(d), asdict(s), str(folder), f'{phase}_{i:05d}', phase)
            for i, ((p, d), s) in enumerate(itertools.product(pairs, scenarios))]


def run_case(job):
    kp, kd, raw_scenario, folder, identifier, phase = job
    s = Scenario(raw_scenario['family'], tuple(raw_scenario['parameters']))
    s.validate()
    if s.family == 'motor':
        result = motor.simulate((kp, kd, s.parameters, folder, identifier))
    else:
        result = expanded.simulate((kp, kd, s.parameters, folder, identifier, 'robust_refine'))
    verify_guard_result(result)
    result.update(study_phase=phase, study_scenario=s.identity,
                  study_scenario_contract=asdict(s))
    expanded.save_json(Path(folder)/'cases'/(identifier+'.json'), result)
    return result


def run_jobs(pool, jobs, results, folder):
    futures = {pool.submit(run_case, job): job[4] for job in jobs}
    for future in as_completed(futures):
        r = future.result()  # infrastructure failures must not become valid simulations
        results.append(r)
        if len(results) % 25 == 0:
            print('ROBUST_REFINEMENT', len(results), r['study_phase'], flush=True)
            expanded.save_json(folder/'progress.json', {'complete': False, 'cases': len(results), 'phase': r['study_phase']})


def build_summary(records, manifest, selection, manifest_sha):
    pairs = [tuple(x) for x in manifest['gain_pairs']]
    calibration = [Scenario(x['family'], tuple(x['parameters'])) for x in manifest['calibration']]
    holdout = [Scenario(x['family'], tuple(x['parameters'])) for x in manifest['holdout']]
    training_rank = rank_pairs(records, pairs, calibration, 'calibration')
    expected_finalists = choose_finalists(training_rank, pairs)
    if expected_finalists != [tuple(x) for x in selection['pairs']]:
        raise ValueError('Frozen finalist selection does not match calibration-only rule')
    valid_rank = rank_pairs(records, expected_finalists, holdout, 'holdout')
    expected = len(pairs)*len(calibration) + len(expected_finalists)*len(holdout)
    if len(records) != expected or not all(x['all_conditions_present'] for x in training_rank+valid_rank):
        raise ValueError('Incomplete prescribed plan: do not publish optimization success')
    approved_holdouts = {tuple(r['pair']) for r in valid_rank if r['all_conditions_eligible']}
    # Keep calibration order. Holdout is reported separately, not used to retune.
    survivors = [r['pair'] for r in training_rank if r['all_conditions_eligible'] and tuple(r['pair']) in approved_holdouts]
    events = [r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event'] is not None]
    observed_soft = [v for r in records for v in r['joint_limit_guard']['minimum_soft_margin_rad'] if v is not None]
    observed_hard = [v for r in records for v in r['joint_limit_guard']['minimum_hard_margin_rad'] if v is not None]
    return {'schema': 'g1.pd.robust-refinement.summary.v1', 'complete': True,
        'simulation_only': True, 'total_cases': expected, 'unique_gain_pairs': len(pairs),
        'calibration_cases': len(pairs)*len(calibration), 'holdout_cases': len(expected_finalists)*len(holdout),
        'completed': sum(r['completed'] for r in records), 'eligible': sum(r['eligible'] for r in records),
        'rejected': sum(not r['eligible'] for r in records),
        'rejection_reasons': dict(Counter(r['reason'] for r in records if not r['eligible'])),
        'guard_event_reasons': dict(Counter(e['reason'] for e in events)),
        'minimum_observed_soft_margin_rad': min(observed_soft), 'minimum_observed_model_hard_margin_rad': min(observed_hard),
        'calibration_ranking': training_rank, 'holdout_ranking': valid_rank,
        'calibration_order_survivors': survivors, 'manifest_sha256': manifest_sha,
        'selection_rule': 'eligible in every calibration condition; minimize worst original-reference RMSE; freeze finalists before holdout',
        'global_or_local_optimum_proven': False, 'recommended_hardware_gains': None,
        'hardware_config_modified': False,
        'limitations': ['fixed pelvis; joint22 excitation only; gains grouped22..25',
          'hypothetical uncertainty, not calibrated G1 latency/braking', 'finite grid with Kp100 ceiling',
          'timestep changes ideal motor PD evaluation rate', 'no IK/cost tuning, live VR or physical validation']}


def verify_artifacts(folder: Path, source_root: Path | None = None):
    """Reload every saved trace and guard witness; regenerate ranking from evidence."""
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    selection = json.loads((folder/'selection.json').read_text(encoding='utf-8'))
    stored = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    if engine.sha256(folder/'manifest.json') != stored['manifest_sha256']:
        raise ValueError('Manifest identity changed')
    if source_root:
        for name, digest in manifest['source_sha256'].items():
            if engine.sha256(safe_path(source_root, name)) != digest:
                raise ValueError('Source identity changed: '+name)
        model_root = source_root/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name, digest in manifest['asset_sha256'].items():
            base = model_root if name.replace('\\', '/').startswith('meshes/') else source_root
            if engine.sha256(safe_path(base, name)) != digest:
                raise ValueError('Model identity changed: '+name)
    expected_jobs = json.loads((folder/'calibration_plan.json').read_text()) + json.loads((folder/'holdout_plan.json').read_text())
    planned = {job[4]: job for job in expected_jobs}
    if len(planned) != len(expected_jobs):
        raise ValueError('Duplicate plan case ids')
    results, case_hashes = [], {}
    phase_records, joint_rows = [], []
    for path in sorted((folder/'cases').glob('*.json')):
        r, metrics, _ = check_case(folder, path)
        verify_guard_result(r)
        job = planned.get(r['case_id'])
        if job is None or pair_of(r) != (job[0], job[1]) or r['study_phase'] != job[5] or r['study_scenario_contract'] != job[2]:
            raise ValueError('Case differs from the frozen plan: '+path.name)
        if r['study_scenario'] != job[2]['family']+'/'+job[2]['parameters'][0]:
            raise ValueError('Scenario identity mismatch')
        results.append(r); case_hashes[r['case_id']] = engine.sha256(path)
        row = {'phase': r['study_phase'], 'case_id': r['case_id'], 'kp': r['kp_proximal'], 'kd': r['kd_proximal'],
               'scenario': r['study_scenario'], 'completed': r['completed'], 'eligible': r['eligible'],
               'reason': r['reason'], 'samples': r['samples'], 'trace_sha256': r['trace_sha256']}
        from mujoco_pd_expand_audit import METRICS
        row.update({k: metrics[k] if metrics else None for k in METRICS})
        phase_records.append(row)
        guard = r['joint_limit_guard']
        for j in range(29):
            joint_rows.append({'case_id': r['case_id'], 'joint': j, 'eligible': r['eligible'],
                 'soft_margin_rad': guard['minimum_soft_margin_rad'][j], 'model_hard_margin_rad': guard['minimum_hard_margin_rad'][j],
                 'stopping_slack_rad': guard['minimum_stopping_slack_rad'][j]})
    regenerated = build_summary(results, manifest, selection, engine.sha256(folder/'manifest.json'))
    if regenerated != stored:
        raise ValueError('Stored summary or ranking differs from reconstructed evidence')
    frozen_hashes = selection['calibration_case_json_sha256']
    observed_hashes = {r['case_id']: case_hashes[r['case_id']] for r in results if r['study_phase']=='calibration'}
    if frozen_hashes != observed_hashes:
        raise ValueError('Calibration records changed after finalist freeze')
    for filename, rows in (('all_cases.csv', phase_records), ('all_joint_margins.csv', joint_rows)):
        with (folder/filename).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    audit = {'schema': 'g1.pd.robust-refinement.audit.v1', 'passed': True, 'simulation_only': True,
        'cases': len(results), 'all_joint_records': len(joint_rows), 'source_and_asset_bytes_checked': bool(source_root),
        'case_json_sha256': case_hashes, 'manifest_sha256': engine.sha256(folder/'manifest.json'),
        'summary_sha256': engine.sha256(folder/'summary.json'), 'selection_sha256': engine.sha256(folder/'selection.json'),
        'all_cases_csv_sha256': engine.sha256(folder/'all_cases.csv'),
        'all_joint_margins_csv_sha256': engine.sha256(folder/'all_joint_margins.csv'),
        'scope': 'full q22 trace metrics and all29 extrema/witness coverage; not full all29 trajectory reconstruction',
        'physical_validation': False}
    expanded.save_json(folder/'audit.json', audit)
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--smoke', action='store_true', help='Two pairs and two conditions per phase; not the full study')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error('workers must be 1..8')
    folder = args.output.resolve()
    if args.audit_only:
        print(json.dumps({k:v for k,v in verify_artifacts(folder).items() if k!='case_json_sha256'})); return 0
    pairs = [(56.,3.), (100.,1.)] if args.smoke else gain_pairs()
    calibration = CALIBRATION[:2] if args.smoke else CALIBRATION
    holdout = HOLDOUT[:2] if args.smoke else HOLDOUT
    for s in calibration + holdout: s.validate()
    if len({s.identity for s in calibration+holdout}) != len(calibration)+len(holdout):
        raise ValueError('Overlapping calibration/holdout scenario identities')
    contract = engine.load_contract()
    for pair in pairs: engine.candidate_gains(contract, *pair)
    import mujoco
    model, qa, _, _, assets = engine.load_model(engine.MODEL, .001)
    dependencies = ['mujoco_pd_robust_refine.py','mujoco_pd_sweep.py','mujoco_pd_expand.py','mujoco_pd_motor_stress.py',
      'mujoco_pd_contract.py','mujoco_pd_fixture.py','joint_limit_guard.py','mujoco_pd_limit_replay.py',
      'mujoco_pd_expand_audit.py','pd_small_signal_trial.hpp']
    manifest = {'schema':'g1.pd.robust-refinement.run.v1', 'simulation_only':True, 'full_study':not args.smoke,
        'gain_pairs':pairs, 'calibration':[asdict(s) for s in calibration], 'holdout':[asdict(s) for s in holdout],
        'finalist_top_count':FINALIST_COUNT, 'fixed_comparison_controls':FINALIST_CONTROLS,
        'created_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'mujoco':mujoco.__version__, 'numpy':np.__version__, 'python':platform.python_version(), 'platform':platform.platform(),
        'source_sha256':engine.source_hashes([Path(__file__).with_name(n) for n in dependencies]+[engine.REFERENCE]),
        'asset_sha256':assets, 'joint_limit_envelope':engine.JointLimitEnvelope.from_model(model,qa,contract).manifest(),
        'recommended_hardware_gains':None, 'hardware_config_modified':False}
    folder.mkdir(parents=True, exist_ok=False)
    expanded.save_json(folder/'manifest.json', manifest)
    # Reload JSON-normalized tuples so the subsequent auditor compares exact shapes.
    manifest = json.loads((folder/'manifest.json').read_text())
    results = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=expanded.init_worker) as pool:
        jobs = make_jobs(pairs, calibration, 'calibration', folder)
        expanded.save_json(folder/'calibration_plan.json', jobs)
        run_jobs(pool, jobs, results, folder)
        ranking = rank_pairs(results, pairs, calibration, 'calibration')
        finalists = choose_finalists(ranking, pairs)
        selection = {'pairs':finalists, 'basis':'calibration only; no holdout outcomes inspected',
            'calibration_case_json_sha256':{r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in sorted(results,key=lambda r:r['case_id'])}}
        expanded.save_json(folder/'selection.json', selection)
        print('FROZEN_FINALISTS',json.dumps(finalists),flush=True)
        jobs = make_jobs(finalists, holdout, 'holdout', folder)
        expanded.save_json(folder/'holdout_plan.json', jobs)
        run_jobs(pool,jobs,results,folder)
    selection = json.loads((folder/'selection.json').read_text())
    summary = build_summary(results,manifest,selection,engine.sha256(folder/'manifest.json'))
    expanded.save_json(folder/'summary.json',summary)
    audit = verify_artifacts(folder,engine.ROOT)
    expanded.save_json(folder/'progress.json',{'complete':True,'cases':len(results),'audited':audit['passed']})
    print('REFINEMENT_RESULT '+json.dumps({k:v for k,v in summary.items() if k not in ('calibration_ranking','holdout_ranking')}),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
