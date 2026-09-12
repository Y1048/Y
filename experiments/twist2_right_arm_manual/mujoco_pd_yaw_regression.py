"""Revalidate frozen simultaneous-yaw candidates on known individual-axis profiles.

No new gain search: prior 216 profiles are regression data, NOT fresh holdouts.
Use the unchanged multiaxis core with exactly one excited axis; screen all four
proximal endpoint errors, not only the excited axis. No SDK, DDS or deployment.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
import csv
import json
import platform
import shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
import mujoco_pd_multiaxis_yaw as yaw
import mujoco_pd_perjoint_study as prior
import mujoco_pd_final as final

base, multi, pj, engine = yaw.base, yaw.multi, yaw.pj, yaw.engine
SCHEMA = 'g1.pd.yaw-regression.v1'


def conditions():
    result = []
    groups = (('prior_operating', prior.operating_conditions()),
              ('prior_fresh', prior.fresh_conditions()), ('prior_final', final.conditions()))
    for group, profiles in groups:
        for p, s in profiles:
            scales = tuple(1. if j == p.joint else 0. for j in range(22, 26))
            m = multi.Motion(p.name, scales, p.amplitude_deg, p.speed_deg_s,
                             p.acceleration_deg_s2, p.cycles, p.elbow_offset_deg, p.post_hold_s)
            m.validate(); s.validate()
            result.append((group, m, s))
    return result


def accepted(summary):
    base.require(summary.get('complete') is True and summary.get('simulation_only') is True,
                 'Source is incomplete or not simulation-only')
    base.require(summary.get('hardware_approved') is False and
                 summary.get('hardware_config_modified') is False and
                 summary.get('recommended_hardware_gains') is None, 'Source hardware claim')
    valid = {pj.Gains(**r['candidate']).key for r in summary['ranking']['validation']
             if r['all_pass'] and r['cases'] == 24 and r['passed'] == 24}
    result = []
    for r in summary['ranking']['operating']:
        g = pj.Gains(**r['candidate']); g.validate()
        if r['all_pass'] and r['cases'] == 144 and r['passed'] == 144 and g.key in valid:
            base.require(tuple(g.kp[i] for i in (0, 1, 3)) == (100., 300., 100.) and
                         tuple(g.kd[i] for i in (0, 1, 3)) == (1.4, 4., 1.4),
                         'Unexpected non-yaw gain change')
            result.append(g)
    base.require(len(result) <= 2 and len({g.key for g in result}) == len(result),
                 'Unexpected or duplicate finalists')
    return result


def receipt(source):
    source = Path(source).resolve()
    checked = yaw.audit(source)  # Re-read original 462 records, not just flags.
    s = base.read(source / 'summary.json')
    base.require(checked['passed'] and checked['cases'] == s['actual_runs'], 'Source audit failed')
    meta = [source / n for n in ('manifest.json', 'summary.json', 'screen_selection.json',
                                 'validation_selection.json', 'screen_plan.json',
                                 'operating_plan.json', 'validation_plan.json')]
    value = dict(source_cases=checked['cases'],
                 metadata_sha256={p.name: engine.sha256(p) for p in meta},
                 case_json_sha256={p.name: engine.sha256(p) for p in sorted((source/'cases').glob('*.json'))},
                 source_rows=checked['all29_500hz_rows'])
    return s, value


def plan(vectors):
    return [dict(case_id=f'regression_{i:05d}', phase=group, candidate=base.norm(asdict(g)),
                 motion=base.norm(asdict(m)), scenario=asdict(s))
            for i, (g, (group, m, s)) in enumerate(yaw.itertools.product(vectors, conditions()))]


def dependencies():
    return base.dependencies() + [Path(yaw.__file__), Path(prior.__file__), Path(final.__file__), Path(__file__)]


def summarize(records, jobs, vectors, source_summary, manifest_hash):
    records = sorted(records, key=lambda r: r['case_id'])
    base.require({pj.Gains(**j['candidate']).key for j in jobs} == {g.key for g in vectors},
                 'Candidate set differs')
    for record in records:
        base.require(record.get('simulation_only') is True and record.get('hardware_approved') is False and
                     record.get('hardware_config_modified') is False and record.get('recommended_hardware_gains') is None,
                     'Hardware claim or non-simulation record')
    rows = yaw.ranking(records, jobs)
    old = {pj.Gains(**r['candidate']).key: r for r in source_summary['ranking']['operating']}
    new = {pj.Gains(**r['candidate']).key: r for r in source_summary['ranking']['validation']}
    for row in rows:
        key = pj.Gains(**row['candidate']).key
        base.require(row['cases'] == len(conditions()), 'Incomplete regression coverage')
        simultaneous = max(old[key]['selectable_worst_rmse_rad'], new[key]['selectable_worst_rmse_rad'])
        row['source_simultaneous_passes'] = old[key]['passed'] + new[key]['passed']
        row['combined_384_worst_rmse_rad'] = max(simultaneous, row['selectable_worst_rmse_rad']) if row['all_pass'] else None
    good = {pj.Gains(**r['candidate']).key for r in rows if r['all_pass']}
    selected = next((base.norm(asdict(g)) for g in vectors if g.key in good), None)
    minimum = lambda key: min((v for r in records for v in r['joint_limit_guard'][key] if v is not None), default=None)
    return dict(schema=SCHEMA, complete=True, simulation_only=True, actual_runs=len(records),
                completed=sum(r['completed'] for r in records), eligible=sum(r['eligible'] for r in records),
                phase_counts=dict(sorted(Counter(r['phase'] for r in records).items())), ranking=rows,
                selected_simulation_vector=selected, selection_rule='retain frozen simultaneous operating order after regression passes',
                base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
                exclusions=dict(sorted(Counter(e for r in records if not r['eligible'] for e in r['exclusions']).items())),
                guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
                minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),
                minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
                minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),
                manifest_sha256=manifest_hash, hardware_approved=False, recommended_hardware_gains=None,
                hardware_config_modified=False, global_optimum_proven=False,
                scope='216 known individual-axis conditions per frozen yaw vector; all4 endpoint tests; not a new holdout or hardware proof')


def validate_files(folder, manifest):
    base.require(manifest['source_sha256'] == engine.source_hashes(dependencies()), 'Computational source changed')
    base.require(manifest['quality_policy'] == multi.POLICY, 'Quality policy changed')
    for name, digest in {**manifest['source_sha256'], **manifest['asset_archive_sha256']}.items():
        base.require(engine.sha256(base.safe_path(folder/'frozen_source', name)) == digest, 'Frozen input changed')
        base.require(engine.sha256(base.safe_path(engine.ROOT, name)) == digest, 'Current source/model changed')


def audit(source, folder):
    source, folder = Path(source).resolve(), Path(folder).resolve()
    m, stored = base.read(folder/'manifest.json'), base.read(folder/'summary.json')
    validate_files(folder, m)
    s, source_receipt = receipt(source)
    base.require(source_receipt == base.read(folder/'source_receipt.json'), 'Source changed since candidate freeze')
    base.require(engine.sha256(folder/'source_receipt.json') == m['source_receipt_sha256'], 'Source receipt changed')
    vectors = accepted(s)
    base.require(m['vectors'] == base.norm([asdict(g) for g in vectors]), 'Frozen vectors changed')
    jobs = base.read(folder/'plan.json')
    base.require(jobs == plan(vectors) and engine.sha256(folder/'plan.json') == m['plan_sha256'], 'Plan changed')
    ids = {j['case_id'] for j in jobs}
    base.require({p.stem for p in (folder/'cases').glob('*.json')} == ids, 'Missing/extra case records')
    base.require({p.stem for p in (folder/'full_state').glob('*.npz')} == ids, 'Missing/extra full-state records')
    records, table, margins, samples = [], [], [], 0
    for job in jobs:
        r, a = base.audit_case(folder, job); records.append(r); samples += len(a['time_s'])
        row = {k:r[k] for k in ('case_id', 'phase', 'completed', 'eligible', 'reason')}
        joint = 22 + list(r['motion']['scales']).index(1.)
        row.update(kp=json.dumps(r['candidate']['kp']), kd=json.dumps(r['candidate']['kd']), joint=joint,
                   motion=r['motion']['name'], scenario=r['scenario']['name'], exclusions=';'.join(r['exclusions']),
                   trace_sha256=r['trace_sha256'])
        for key in ('max_proximal_rmse_rad', 'max_proximal_tail_error_rad',
                    'max_right7_tail_rms_speed_rad_s', 'max_right7_tail_p2p_rad',
                    'torque_limited_ratio', 'hard_clipped_ratio'):
            row[key] = r['metrics'][key] if r['metrics'] else None
        row['excited_joint_rmse_rad'] = r['metrics']['proximal_rmse_rad'][joint-22] if r['metrics'] else None
        table.append(row)
        for j in range(29):
            margins.append(dict(case_id=r['case_id'], joint=j,
                **{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad', 'minimum_hard_margin_rad', 'minimum_stopping_slack_rad')}))
    base.require(summarize(records, jobs, vectors, s, engine.sha256(folder/'manifest.json')) == stored, 'Summary differs')
    for name, rows in (('all_cases.csv', table), ('all_joint_margins.csv', margins)):
        with (folder/name).open('w', newline='', encoding='utf-8') as stream:
            w = csv.DictWriter(stream, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    result = dict(schema='g1.pd.yaw-regression.audit.v1', passed=True, source_cases_reaudited=source_receipt['source_cases'],
                  cases=len(records), all29_500hz_rows=samples, all29_margin_records=len(margins),
                  all_cases_sha256=engine.sha256(folder/'all_cases.csv'),
                  source_model_bytes_checked=True, physical_validation=False)
    base.save(folder/'audit.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-yaw', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8: parser.error('workers must be 1..8')
    source, folder = args.source_yaw.resolve(), args.output.resolve()
    base.require(not folder.is_relative_to(source) and not source.is_relative_to(folder), 'Source/output overlap')
    if args.audit_only:
        print(json.dumps(audit(source, folder))); return 0
    base.require(not folder.exists(), 'Output exists; no overwrite')
    s, source_receipt = receipt(source)
    vectors = accepted(s)
    base.require(bool(vectors), 'No fully validated source candidate; no fabricated vector')
    jobs = plan(vectors)
    import mujoco
    _, _, _, _, assets = engine.load_model(engine.MODEL, .001)
    archive = {}
    for name, digest in assets.items():
        p = base.safe_path(engine.MODEL.parent if name.replace('\\','/').startswith('meshes/') else engine.ROOT, name)
        archive[p.relative_to(engine.ROOT).as_posix()] = digest
    base.require(archive == base.read(source/'manifest.json')['asset_archive_sha256'], 'Model differs from yaw source study')
    sources = engine.source_hashes(dependencies())
    folder.mkdir(parents=True, exist_ok=False)
    for name, digest in {**sources, **archive}.items():
        src = base.safe_path(engine.ROOT, name); dest = base.safe_path(folder/'frozen_source', name)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dest)
        base.require(engine.sha256(dest) == digest, 'Input freeze mismatch')
    base.save(folder/'source_receipt.json', source_receipt)
    base.save(folder/'plan.json', jobs)
    base.save(folder/'manifest.json', dict(schema=SCHEMA, simulation_only=True, vectors=base.norm([asdict(g) for g in vectors]),
       plan_sha256=engine.sha256(folder/'plan.json'), source_receipt_sha256=engine.sha256(folder/'source_receipt.json'),
       source_sha256=sources, asset_archive_sha256=archive, quality_policy=multi.POLICY,
       mujoco=mujoco.__version__, numpy=base.np.__version__, python=platform.python_version(), platform=platform.platform(),
       workers=args.workers, hardware_approved=False, source_role='audited yaw experiment; earlier individual conditions reused as regression'))
    records = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=base.expanded.init_worker) as pool:
        for f in as_completed([pool.submit(base.run_case, j, str(folder)) for j in jobs]):
            records.append(f.result())
            if len(records) % 24 == 0 or len(records) == len(jobs):
                progress = dict(complete=False, done=len(records), total=len(jobs), eligible=sum(r['eligible'] for r in records))
                base.save(folder/'progress.json', progress); print(json.dumps(progress), flush=True)
    base.save(folder/'summary.json', summarize(records, jobs, vectors, s, engine.sha256(folder/'manifest.json')))
    checked = audit(source, folder)
    base.save(folder/'progress.json', dict(complete=True, done=len(records), audited=checked['passed']))
    print('REGRESSION_RESULT '+json.dumps({k:v for k,v in base.read(folder/'summary.json').items() if k!='ranking'}), flush=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
