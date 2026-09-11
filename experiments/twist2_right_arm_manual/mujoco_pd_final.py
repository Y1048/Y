"""Finalize bounded per-joint PD optimization: simulation review ONLY.

optimize: run the existing per-joint search, then independent final checks.
finalize: reuse an existing fully audited search, without rerunning its dynamics.
verify: independently reread both searches' evidence and the final decision.
No SDK, DDS, live config writes, actuation, automatic deployment or safety waiver.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import json
from pathlib import Path
import shutil

import numpy as np
import mujoco_pd_perjoint as pj
import mujoco_pd_perjoint_study as search

SCHEMA = 'g1.pd.final-review.v1'
JOINTS = (22, 23, 24, 25)
FINAL_POLICY = {
    'all_proximal_tail_error_rad': .02,
    'all_proximal_tail_speed_rad_s': .1,
    'whole_post_hold_last_second': True,
    'require_original_eligibility': True,
    'all_joint_limit_guard_unchanged': True,
}
MAX_FINALISTS = 2


def conditions():
    """Fixed before results: all four axes under six new operating combinations.

The tuple list represents hypothetical model/torque-path variation, not a
measured probability distribution. All candidates see exactly the same cases.
"""
    settings = (
        (1.00, 1.00, .80, .001, .003, .001, 7., 17., -6., 6, 10.),
        (1.20, .75, .30, .002, .005, .0005, 9., 23., 6., 6, 10.),
        (1.40, 1.25, .20, .003, .007, .001, 11., 27., 0., 6, 10.),
        (.80, .65, .10, .002, .004, .0005, 7., 23., 6., 6, 10.),
        (1.10, 1.50, .60, .003, .006, .001, 9., 17., -6., 12, 5.),
        (1.25, .90, .40, .002, .005, .0005, 11., 27., 0., 3, 30.),
    )
    result = []
    for i, (mass, damping, friction, delay, lag, dt, amp, speed, elbow, cycles, hold) in enumerate(settings):
        s = pj.core.Coupled(f'final_{i:02d}', mass, damping, friction, delay, lag, dt)
        s.validate()
        for j in JOINTS:
            p = pj.core.Profile(f'final_{i:02d}_j{j}', joint=j, amplitude_deg=amp,
                                speed_deg_s=speed, elbow_offset_deg=elbow,
                                cycles=cycles, post_hold_s=hold)
            p.validate()
            result.append((p, s))
    return result


def normalize(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def require(test, message):
    if not test:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def accepted_vectors(summary):
    require(summary.get('complete') is True and summary.get('simulation_only') is True,
            'Input search incomplete or not simulation-only')
    require(summary.get('hardware_config_modified') is False and
            summary.get('recommended_hardware_gains') is None, 'Invalid hardware claim')
    ranks = summary.get('ranking', {})
    valid = {pj.Gains(**r['candidate']).key for r in ranks.get('fresh', [])
             if r['all_pass'] and r['cases'] == 48 and r['passed'] == 48}
    result = []
    for r in ranks.get('operating', []):
        g = pj.Gains(**r['candidate']); g.validate()
        if r['all_pass'] and r['cases'] == 144 and r['passed'] == 144 and g.key in valid:
            result.append(g)
    require(len({g.key for g in result}) == len(result), 'Duplicate source finalists')
    # Preserve frozen main-operating minimax order. Do not rerank on final checks.
    return result[:MAX_FINALISTS]


def source_receipt(folder):
    """Audit with current processing code; archived inputs are READ, never executed.

Older completed runs may have an immutable frozen_source because a later
processing-only patch fixed failure-list ordering. Never rewrite that manifest.
"""
    folder = Path(folder).resolve()
    source = folder / 'frozen_source'
    if not source.is_dir():
        source = pj.engine.ROOT
    audited = search.audit(folder, source)
    summary = read(folder / 'summary.json')
    require(audited['passed'] is True and audited['cases'] == summary['actual_runs'],
            'Source audit failed or incomplete')
    files = [folder / 'manifest.json', folder / 'selection.json', folder / 'summary.json',
             folder / 'operating_selection.json', *sorted(folder.glob('*_plan.json'))]
    for optional in ('processing_fix.json', 'summary_before_order_fix.json'):
        if (folder / optional).exists(): files.append(folder / optional)
    return {
        'summary': summary,
        'receipt': {
            'source_metadata_sha256': {p.name: pj.engine.sha256(p) for p in files},
            'case_json_sha256': audited['case_hashes'],
            'cases': audited['cases'], 'all29_500hz_rows': audited['all29_500hz_rows'],
            'all29_margin_records': audited['all29_margin_records'],
            'original_source_model_bytes_checked': audited['source_model_bytes_checked'],
        },
    }


def final_quality(record, arrays):
    """Stricter last-step gate: ALL four proximal joints, not just excited/q22.

Use actual unmodified q/dq and original reference. A quiet biased joint fails.
Any original contact/velocity/limiting/guard rejection remains a rejection.
"""
    p = pj.core.Profile(**record['profile']); p.validate()
    reasons = [] if record['eligible'] else ['original_case_rejected']
    error_max = speed_max = 0.
    mask = arrays['trial_time_s'] >= 0
    windows = [(c, seg, 50) for c in range(p.cycles)
               for seg in ('positive_hold', 'negative_hold', 'ready_hold')]
    if p.post_hold_s >= 1:
        windows.append((p.cycles, 'post_hold', 500))
    else:
        reasons.append('final_post_hold_missing')
    evaluated = 0
    for cycle, segment, count in windows:
        ids = np.flatnonzero(mask & (arrays['cycle'] == cycle) & (arrays['segment'] == segment))
        if len(ids) < count:
            reasons.append('missing_final_window'); continue
        ids = ids[-count:]
        q = arrays['q'][ids, 22:26]; ref = arrays['ref'][ids, 22:26]; dq = arrays['dq'][ids, 22:26]
        if not all(np.isfinite(a).all() for a in (q, ref, dq)):
            raise ValueError('Nonfinite final-gate data')
        error = float(np.max(np.abs(q-ref))); speed = float(np.max(np.abs(dq)))
        error_max = max(error_max, error); speed_max = max(speed_max, speed)
        if error > FINAL_POLICY['all_proximal_tail_error_rad']: reasons.append('all_proximal_tail_error')
        if speed > FINAL_POLICY['all_proximal_tail_speed_rad_s']: reasons.append('all_proximal_tail_speed')
        evaluated += 1
    return {'passes': not reasons, 'rejections': sorted(set(reasons)),
            'windows_expected': len(windows), 'windows_evaluated': evaluated,
            'max_all_proximal_tail_error_rad': error_max if evaluated else None,
            'max_all_proximal_tail_speed_rad_s': speed_max if evaluated else None}


def decision(records, plan, vectors):
    records = sorted(records, key=lambda r: r['case_id'])
    pj.ranking(records, plan)  # reject missing/extra/duplicate or altered cells
    rankings = []
    for g in vectors:
        rs = [r for r in records if pj.gain_key(r) == g.key]
        require(len(rs) == len(conditions()), 'Incomplete final matrix for candidate')
        passes = all(r['final_quality']['passes'] for r in rs)
        def worst(name):
            return max((r['metrics'][name] for r in rs if r['metrics']), default=None)
        rankings.append({'candidate': normalize(asdict(g)), 'cases': len(rs),
                         'original_passes': sum(r['eligible'] for r in rs),
                         'final_passes': sum(r['final_quality']['passes'] for r in rs),
                         'all_pass': passes,
                         'worst_active_rmse_rad': worst('active_rmse_rad') if passes else None,
                         'failures': [{'case_id': r['case_id'], 'reason': r['reason'],
                                       'original_exclusions': r['exclusions'],
                                       'final_exclusions': r['final_quality']['rejections']}
                                      for r in rs if not r['final_quality']['passes']]})
    selected = next((r['candidate'] for r in rankings if r['all_pass']), None)
    caps = [j for j, p, cap in zip(JOINTS, selected['kp'], pj.KP_CAP) if p == cap] if selected else []
    return {'schema': SCHEMA, 'status': 'simulation_candidate_validated' if selected else 'no_final_candidate',
            'complete': True, 'simulation_only': True, 'controller': 'pure_PD_dq_target_zero_tau_ff_zero',
            'joints': list(JOINTS), 'candidate': selected,
            'final_ranking_in_frozen_source_order': rankings,
            'actual_new_simulations': len(records), 'completed': sum(r['completed'] for r in records),
            'original_eligible': sum(r['eligible'] for r in records),
            'final_eligible': sum(r['final_quality']['passes'] for r in records),
            'research_kp_caps': list(pj.KP_CAP), 'kp_at_research_cap_joints': caps,
            'legacy_hardware_gain_compatible': bool(selected and all(v <= 100 for v in selected['kp'])),
            'hardware_approved': False, 'recommended_hardware_gains': None,
            'hardware_config_modified': False, 'global_or_continuous_optimum_proven': False,
            'all_operating_conditions_tested': False,
            'blocking_physical_checks': ['joint23 Kp beyond live100 validator when used',
                'actual servo rates, delay and torque/gain capabilities',
                'simultaneous VR trajectories and free-base TWIST2 balance',
                'measured mechanical limits and braking with payload',
                'sensor noise, backlash and thermal behavior',
                'separately reviewed SDK/ARM binary and ownership transition'],
            'scope': 'fixed pelvis; four independently excited proximal axes; unchanged all29 guard'}


def dependencies():
    # Snapshot source text only. Never execute files from the run's archive.
    names = sorted(p.name for p in Path(__file__).parent.glob('mujoco_pd_*.py')
                   if not p.name.startswith('test_'))
    names += ['joint_limit_guard.py']
    return [Path(__file__).with_name(n) for n in names] + [pj.engine.REFERENCE,
        pj.engine.ROOT/'hardware/g1_arm_bridge/g1_joint_contract.py']


def finalize(study_folder, output, workers=6):
    require(type(workers) is int and 1 <= workers <= 8, 'workers must be1..8')
    source = Path(study_folder).resolve(); output = Path(output).resolve()
    require(not output.exists(), 'Output already exists; no overwrite')
    require(not output.is_relative_to(source), 'Output must be outside source study')
    audited = source_receipt(source); vectors = accepted_vectors(audited['summary'])
    output.mkdir(parents=True, exist_ok=False)
    write_new(output/'source_receipt.json', audited['receipt'])
    plan = search.jobs(vectors, conditions(), 'final')
    _, _, _, _, assets = pj.engine.load_model(pj.engine.MODEL, .001)
    manifest = {'schema': SCHEMA, 'asset_sha256': assets, 'source_receipt_sha256': pj.engine.sha256(output/'source_receipt.json'),
        'source_study_path': str(source), 'source_candidates': [normalize(asdict(g)) for g in vectors],
        'conditions': [normalize({'profile': asdict(p), 'scenario': asdict(s)}) for p,s in conditions()],
        'source_quality_policy': pj.core.POLICY, 'final_quality_policy': FINAL_POLICY,
        'selection_rule': 'first source operating minimax candidate passing every frozen final check',
        'simulation_only': True, 'recommended_hardware_gains': None, 'hardware_config_modified': False,
        'source_sha256': pj.engine.source_hashes(dependencies())}
    write_new(output/'manifest.json', manifest); write_new(output/'plan.json', plan)
    for path in dependencies():
        dest = output/'frozen_source'/path.resolve().relative_to(pj.engine.ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
    records = []
    if plan:
        with ProcessPoolExecutor(max_workers=workers, initializer=pj.expanded.init_worker) as pool:
            futures = [pool.submit(pj.write_case, job, str(output)) for job in plan]
            for future in as_completed(futures):
                r = future.result(); job = next(j for j in plan if j['case_id']==r['case_id'])
                checked, arrays = pj.audit_case(output, job)
                checked['final_quality'] = final_quality(checked, arrays); records.append(checked)
                print('FINAL_VALIDATED_CASE', len(records), '/', len(plan), checked['final_quality']['passes'], flush=True)
    result = decision(records, plan, vectors)
    result.update(manifest_sha256=pj.engine.sha256(output/'manifest.json'))
    write_new(output/'simulation_candidate.json', result)
    report = verify(source, output)
    write_new(output/'verification.json', report)
    return result


def verify(study_folder, output):
    source = Path(study_folder).resolve(); output = Path(output).resolve()
    manifest = read(output/'manifest.json'); stored = read(output/'simulation_candidate.json')
    require(manifest['schema']==SCHEMA and manifest['source_quality_policy']==pj.core.POLICY and
            manifest['final_quality_policy']==FINAL_POLICY, 'Altered final policy')
    require(pj.engine.sha256(output/'manifest.json')==stored['manifest_sha256'], 'Manifest hash differs')
    require(pj.engine.sha256(output/'source_receipt.json')==manifest['source_receipt_sha256'], 'Receipt hash differs')
    audited = source_receipt(source)
    require(audited['receipt']==read(output/'source_receipt.json'), 'Original evidence changed')
    vectors = accepted_vectors(audited['summary'])
    require(manifest['source_candidates']==[normalize(asdict(g)) for g in vectors], 'Frozen finalists differ')
    require(manifest['conditions']==normalize([{'profile':asdict(p),'scenario':asdict(s)} for p,s in conditions()]), 'Frozen conditions differ')
    for name, digest in manifest['source_sha256'].items():
        require(pj.engine.sha256(pj.safe_path(output/'frozen_source', name))==digest, 'Archived source mismatch')
        require(pj.engine.sha256(pj.safe_path(pj.engine.ROOT, name))==digest, 'Verifier source differs; use recorded code revision')
    model_root = pj.engine.MODEL.parent
    for name, digest in manifest['asset_sha256'].items():
        root = model_root if name.replace('\\','/').startswith('meshes/') else pj.engine.ROOT
        require(pj.engine.sha256(pj.safe_path(root, name))==digest, 'Current model/mesh differs')
    plan = search.jobs(vectors, conditions(), 'final')
    require(read(output/'plan.json')==normalize(plan), 'Final plan differs')
    require({p.stem for p in (output/'cases').glob('*.json')}=={j['case_id'] for j in plan}, 'Missing/extra final case')
    records=[]; hashes={}; rows=0
    for job in plan:
        r, arrays = pj.audit_case(output, job)
        r['final_quality'] = final_quality(r, arrays); records.append(r)
        hashes[r['case_id']] = pj.engine.sha256(output/'cases'/(r['case_id']+'.json'))
        rows += len(arrays['time_s'])
    expected = decision(records, plan, vectors); expected['manifest_sha256'] = stored['manifest_sha256']
    require(stored==expected, 'Final decision or hardware status differs')
    report = {'schema':'g1.pd.final-audit.v1', 'passed':True, 'simulation_only':True,
        'input_cases_reaudited':audited['receipt']['cases'], 'new_cases_reaudited':len(records),
        'new_all29_500hz_rows':rows, 'case_json_sha256':hashes,
        'simulation_candidate_sha256':pj.engine.sha256(output/'simulation_candidate.json'),
        'hardware_approved':False, 'recommended_hardware_gains':None}
    if (output/'verification.json').exists():
        require(read(output/'verification.json')==report, 'Stored verification differs')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('optimize','finalize','verify'))
    parser.add_argument('--study', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8: parser.error('workers must be1..8')
    if args.mode!='optimize' and args.study is None: parser.error('--study required')
    if args.mode=='optimize' and args.study is not None: parser.error('optimize creates its own study')
    if args.mode=='optimize':
        require(not args.output.exists(), 'Optimization root already exists')
        args.output.mkdir(parents=True, exist_ok=False)
        source = args.output/'search'
        search.main(['--output',str(source),'--workers',str(args.workers)])
        result = finalize(source, args.output/'final', args.workers)
    elif args.mode=='finalize':
        result = finalize(args.study, args.output, args.workers)
    else:
        result = verify(args.study, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if args.mode=='verify' or result['candidate'] is not None else 2


if __name__=='__main__':
    raise SystemExit(main())
