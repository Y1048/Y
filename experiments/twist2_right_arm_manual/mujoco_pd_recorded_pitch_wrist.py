"""Offline coordinate search for shoulder pitch22 and wrist pitch27.

Keep the recorded-input causal20ms pipeline, original-goal score, and all guards.
Only this process-local research adapter extends pitch22's Kp bound to160;
all original gain validators and files are unchanged. No robot SDK/DDS/network.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_key] = '1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict
import csv
import json
import math
from pathlib import Path
import platform
import shutil
import numpy as np
import mujoco_pd_recorded_roll_yaw as previous
from mujoco_pd_expand_audit import safe_path

ramp, independent, multi, base = previous.ramp, previous.independent, previous.multi, previous.base
pj, engine = ramp.pj, ramp.engine
norm, read, save, require = base.norm, base.read, base.save, base.require
SCHEMA = 'g1.pd.recorded-pitch-wrist.v1'
PITCH_KP = (80., 100., 120., 140., 160.)
PITCH_KD = (1., 1.4, 2.)
WRIST_KP = (15., 20., 30., 40.)
WRIST_KD = (.6, 1., 1.4)
RESEARCH_CAP = (160., 300., 100., 100.)
PHASES = ('pitch', 'wrist', 'validation', 'regression')
MIN_FREE_BYTES = 2_000_000_000
_ACTIVE_SCOPE = False
EXTRA_SCENARIOS = (
    multi.core.Coupled('pitch_wrist_mix_a', 1.1, .7, .2, .006, .006, .001),
    multi.core.Coupled('pitch_wrist_mix_b', .85, 1.5, .1, .001, .010, .0005),
)
POLICY = dict(
    simulation_only=True, hardware_approved=False, recommended_hardware_gains=None,
    hardware_config_modified=False, global_optimum_proven=False,
    requires_command_prefilter=True, pd_only_optimum_proven=False,
    command_filter=dict(ramp.core.COMMAND_FILTER),
    objective='minimize worst original-goal all7 RMSE subject to all validation and regression gates',
    research_kp_cap=list(RESEARCH_CAP), wrist_pitch_kp_cap=40.,
    live_kp_cap_unchanged=100., synthetic_regression_prefilter=False,
    data_scope='one previously observed outgoing-target recording; not measured robot response',
)


def specification(pitch_kp=100., pitch_kd=1.4, wrist_kp=20., wrist_kd=1.):
    value = dict(candidate=dict(kp=[pitch_kp, 300., 64., 100.], kd=[pitch_kd, 3., 1.2, 1.4]),
                 wrist_pitch=dict(kp=wrist_kp, kd=wrist_kd))
    validate(value)
    return norm(value)


def validate(value):
    require(set(value) == {'candidate', 'wrist_pitch'}, 'Unexpected gain specification fields')
    g, w = value['candidate'], value['wrist_pitch']
    require(set(g) == {'kp', 'kd'} and set(w) == {'kp', 'kd'}, 'Unexpected gain fields')
    require(len(g['kp']) == len(g['kd']) == 4, 'Four proximal gains required')
    values = list(g['kp']) + list(g['kd']) + [w['kp'], w['kd']]
    require(all(type(x) in (int, float) and math.isfinite(x) for x in values), 'Finite nonboolean gains required')
    require(all(1 <= x <= cap for x, cap in zip(g['kp'], RESEARCH_CAP)), 'Research Kp bounds')
    require(all(.1 <= x <= 20 for x in g['kd']), 'Research Kd bounds')
    require(g['kp'][1:] == [300., 64., 100.] and g['kd'][1:] == [3., 1.2, 1.4], 'Only pitch22 and wrist27 may change')
    require(1 <= w['kp'] <= 40 and .1 <= w['kd'] <= 2, 'Research wrist27 bounds')


def spec_of(value):
    result = {k: norm(value[k]) for k in ('candidate', 'wrist_pitch')}
    validate(result)
    return result


def identity(value):
    x = spec_of(value)
    return tuple(x['candidate']['kp'] + x['candidate']['kd'] + [x['wrist_pitch']['kp'], x['wrist_pitch']['kd']])


@contextmanager
def research_scope(value):
    """Single-thread, process-local adapter. Restore even after failed simulation/audit."""
    global _ACTIVE_SCOPE
    value = spec_of(value)
    require(not _ACTIVE_SCOPE and pj.KP_CAP == (100., 300., 100., 100.), 'Nested or unexpected research scope')
    original_cap, original_assign = pj.KP_CAP, engine.candidate_gains
    def assign(contract, kp, kd):
        require((kp, kd) == pj.BASE, 'Unexpected adapter sentinel')
        p, d = original_assign(contract, kp, kd)
        p[27], d[27] = value['wrist_pitch']['kp'], value['wrist_pitch']['kd']
        return p, d
    _ACTIVE_SCOPE = True
    pj.KP_CAP, engine.candidate_gains = RESEARCH_CAP, assign
    try:
        yield
    finally:
        pj.KP_CAP, engine.candidate_gains = original_cap, original_assign
        _ACTIVE_SCOPE = False


def deduplicate(values):
    result, seen = [], set()
    for value in values:
        key = identity(value)
        if key not in seen:
            result.append(spec_of(value)); seen.add(key)
    return result


def recorded_plan(stage, vectors, conditions):
    return [dict(case_id=f'{stage}_{i:04d}', stage=stage, kind='recorded', **spec_of(g),
                 episode=0, clock=c, scenario=asdict(s))
            for i, (g, (c, s)) in enumerate((g, cs) for g in vectors for cs in conditions)]


def rank(records, plan):
    expected = {j['case_id']: j for j in plan}
    seen = {r['case_id']: r for r in records}
    require(len(expected) == len(plan) and len(seen) == len(records) and set(expected) == set(seen), 'Missing/duplicate cases')
    for r in records:
        require(all(norm(r[k]) == norm(v) for k, v in expected[r['case_id']].items()), 'Plan identity changed')
        require(r['simulation_only'] is True and r['hardware_approved'] is False and
                r['hardware_config_modified'] is False and r['recommended_hardware_gains'] is None, 'Hardware claim')
    ranked = []
    for g in deduplicate(plan):
        rs = sorted((r for r in records if identity(r) == identity(g)), key=lambda r: r['case_id'])
        passed = bool(rs) and all(r['eligible'] for r in rs)
        scores = [r['metrics'].get('max_right7_recorded_rmse_rad', r['metrics'].get('max_proximal_rmse_rad'))
                  for r in rs if r['metrics']]
        worst = max((x for x in scores if x is not None), default=None)
        ranked.append(dict(**g, cases=len(rs), passed=sum(r['eligible'] for r in rs), all_pass=passed,
                           worst_rmse_rad=worst if passed else None, partial_worst_rmse_rad=worst,
                           failures=[dict(case_id=r['case_id'], reason=r['reason'], exclusions=r['exclusions'])
                                     for r in rs if not r['eligible']]))
    return sorted(ranked, key=lambda r: (not r['all_pass'], r['worst_rmse_rad'] if r['all_pass'] else math.inf, identity(r)))


def passing(records, plan, count=None):
    values = [spec_of(r) for r in rank(records, plan) if r['all_pass']]
    return values if count is None else values[:count]


def phase_plan(stage, records, plans, smoke=False):
    require(stage in PHASES, 'Unknown phase')
    conditions = previous.screen_conditions()
    if smoke:
        conditions = conditions[:1]
    if stage == 'pitch':
        vv = [specification(p, d) for p in PITCH_KP for d in PITCH_KD]
        return recorded_plan(stage, [specification(), specification(120., 1.4)] if smoke else vv, conditions)
    pitch = passing([r for r in records if r['stage'] == 'pitch'], plans['pitch'], 1)
    if stage == 'wrist':
        if not pitch:
            return []
        p = pitch[0]['candidate']
        vv = [specification(p['kp'][0], p['kd'][0], wp, wd) for wp in WRIST_KP for wd in WRIST_KD]
        return recorded_plan(stage, [specification(p['kp'][0], p['kd'][0], 30., 1.)] if smoke else vv, conditions)
    wrist = passing([r for r in records if r['stage'] == 'wrist'], plans['wrist'], 2)
    if stage == 'validation':
        vv = deduplicate(wrist + pitch + [specification()])
        cc = [(c, s) for c in ramp.CLOCKS for s in tuple(ramp.SCENARIOS) + EXTRA_SCENARIOS]
        return recorded_plan(stage, vv[:1] if smoke else vv, cc[:1] if smoke else cc)
    survivors = passing([r for r in records if r['stage'] == 'validation'], plans['validation'])
    jobs = []
    for g in survivors:
        for j in previous.regression_plan([g['candidate']]):
            j = dict(j, case_id=f'regression_{len(jobs):04d}', wrist_pitch=g['wrist_pitch'])
            jobs.append(j)
    return jobs[:1] if smoke else jobs


def run_case(job, folder):
    folder = Path(folder); g = spec_of(job)
    require(shutil.disk_usage(folder).free > MIN_FREE_BYTES, 'Storage reserve reached; preserve incomplete study')
    with research_scope(g):
        if job['kind'] == 'recorded':
            r = ramp.run_case(job, folder)
        elif job['kind'] == 'independent':
            r = independent.run_case(job, folder)
        elif job['kind'] == 'single':
            r, arrays = multi.simulate(multi.Motion(**job['motion']), pj.Gains(**job['candidate']), multi.core.Coupled(**job['scenario']))
            r.update(case_id=job['case_id'], phase=job['phase'])
            dest = folder/'full_state'/(job['case_id'] + '.npz')
            dest.parent.mkdir(parents=True, exist_ok=True)
            require(not dest.exists(), 'Trace already exists')
            np.savez_compressed(dest, **arrays)
            r.update(trace=dest.relative_to(folder).as_posix(), trace_sha256=engine.sha256(dest))
        else:
            raise ValueError('Unknown case kind')
    r.update(stage=job['stage'], kind=job['kind'], wrist_pitch=g['wrist_pitch'], research_kp_cap=list(RESEARCH_CAP))
    save(folder/'cases'/(r['case_id'] + '.json'), r)
    return r


def checked_case(folder, job, capture):
    stored = read(Path(folder)/'cases'/(job['case_id'] + '.json'))
    require(all(norm(stored[k]) == norm(v) for k, v in job.items()), 'Case specification changed')
    require(stored['research_kp_cap'] == list(RESEARCH_CAP), 'Research bound changed')
    with research_scope(job):
        if job['kind'] == 'recorded':
            return ramp.audit_case(folder, job, capture)
        if job['kind'] == 'independent':
            return independent.audit_case(folder, job)
        if job['kind'] == 'single':
            return base.audit_case(folder, job)
        raise ValueError('Unknown audit kind')


def summary(records, plans, manifest_hash, smoke=False):
    rankings = {s: rank([r for r in records if r['stage'] == s], plans[s]) for s in PHASES}
    survivors = {identity(r) for r in rankings['regression'] if r['all_pass']}
    winner = next((spec_of(r) for r in rankings['validation'] if r['all_pass'] and identity(r) in survivors), None)
    minimum = lambda k: min((v for r in records for v in r['joint_limit_guard'][k] if v is not None), default=None)
    return dict(schema=SCHEMA, complete=True, smoke=smoke, **POLICY,
                actual_runs=len(records), completed=sum(r['completed'] for r in records), eligible=sum(r['eligible'] for r in records),
                stage_counts={s: len(plans[s]) for s in PHASES}, ranking=rankings,
                selected_filtered_pipeline_spec=None if smoke else winner,
                base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
                guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
                minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'), minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
                minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),
                simulated_seconds=math.fsum(r['final_time_s'] for r in sorted(records, key=lambda r: r['case_id'])),
                manifest_sha256=manifest_hash, regression_scope='14 known synthetic checks per survivor; no inherited old passes')


def dependencies():
    return list(dict.fromkeys(previous.dependencies() + [Path(previous.__file__), Path(__file__)]))


def audit(folder):
    folder = Path(folder); manifest = read(folder/'manifest.json')
    require(manifest['schema'] == SCHEMA and manifest['policy'] == POLICY and type(manifest['smoke']) is bool, 'Manifest policy')
    require(manifest['grid'] == norm(dict(pitch_kp=PITCH_KP, pitch_kd=PITCH_KD, wrist_kp=WRIST_KP, wrist_kd=WRIST_KD)), 'Grid changed')
    require(manifest['extra_scenarios'] == norm([asdict(s) for s in EXTRA_SCENARIOS]), 'Extra scenarios changed')
    require(engine.source_hashes(dependencies()) == manifest['source_sha256'], 'Calculation sources changed')
    for name, digest in {**manifest['source_sha256'], **manifest['asset_archive_sha256']}.items():
        require(engine.sha256(safe_path(folder/'frozen_source', name)) == digest, 'Archived source/model changed')
    raw = folder/'inputs/recording.jsonl'
    require(engine.sha256(raw) == manifest['recording_sha256'], 'Raw recording changed')
    captures, _ = ramp.recording.extract(raw)
    require(len(captures) == 1 and captures[0].metadata() == manifest['capture'], 'Recording identity changed')
    capture, frozen = captures[0], ramp.load_capture(folder, 0)
    for name in ('joints', 'send_time_s', 'sample_time_s', 'events', 'sequence'):
        require(np.array_equal(getattr(capture, name), getattr(frozen, name)), 'Normalized input changed')
    records, plans, table, margins, rows = [], {}, [], [], 0
    for stage in PHASES:
        plan = phase_plan(stage, records, plans, manifest['smoke'])
        require(read(folder/'plans'/(stage+'.json')) == plan, 'Plan/selection changed')
        plans[stage] = plan
        for job in plan:
            r, arrays = checked_case(folder, job, capture); records.append(r); rows += len(arrays['time_s'])
            m = r['metrics']
            table.append(dict(case_id=r['case_id'], stage=stage, kind=r['kind'], kp=json.dumps(r['candidate']['kp']), kd=json.dumps(r['candidate']['kd']),
                              wrist_kp=r['wrist_pitch']['kp'], wrist_kd=r['wrist_pitch']['kd'], clock=r.get('clock', ''), scenario=r['scenario']['name'],
                              completed=r['completed'], eligible=r['eligible'], reason=r['reason'], exclusions=';'.join(r['exclusions']),
                              samples=len(arrays['time_s']), max_rmse_rad=m.get('max_right7_recorded_rmse_rad', m.get('max_proximal_rmse_rad')) if m else None,
                              peak_upper_speed_rad_s=r['physics']['peak_upper_speed_rad_s'], trace_sha256=r['trace_sha256']))
            for j in range(29):
                margins.append(dict(case_id=r['case_id'], joint=j, **{k: r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad', 'minimum_hard_margin_rad', 'minimum_stopping_slack_rad')}))
    ids = {j['case_id'] for p in plans.values() for j in p}
    for sub, ext in (('cases', '*.json'), ('full_state', '*.npz')):
        require({p.stem for p in (folder/sub).glob(ext)} == ids, 'Missing/extra results')
    require(summary(records, plans, engine.sha256(folder/'manifest.json'), manifest['smoke']) == read(folder/'summary.json'), 'Summary changed')
    for name, values in (('all_cases.csv', table), ('all_joint_margins.csv', margins)):
        with (folder/name).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
    result = dict(passed=True, cases=len(records), all29_500hz_rows=rows, all29_margin_records=len(margins),
                  all_cases_sha256=engine.sha256(folder/'all_cases.csv'), source_and_recording_checked=True,
                  physical_validation=False, scope='sampled all29 traces, original goals, PD/limiter, filter, guards and selection; not continuous physics reconstruction')
    save(folder/'audit.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', type=Path); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4); parser.add_argument('--smoke', action='store_true'); parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 4:
        parser.error('workers must be1..4')
    folder = args.output.resolve()
    if args.audit_only:
        print(json.dumps(audit(folder))); return 0
    require(not folder.exists(), 'Output exists; never overwrite')
    require(args.recording is not None and args.recording.is_file(), 'Explicit existing recording required')
    require(not args.recording.resolve().is_relative_to(folder), 'Nested input refused')
    require(shutil.disk_usage(folder.parent if folder.parent.exists() else Path.cwd()).free > (MIN_FREE_BYTES + (200_000_000 if args.smoke else 2_500_000_000)), 'Insufficient storage reserve')
    captures, info = ramp.recording.extract(args.recording)
    require(len(captures) == 1, 'Exactly one qualified episode required')
    for s in EXTRA_SCENARIOS: s.validate()
    import mujoco
    _, _, _, _, assets = engine.load_model(engine.MODEL, .001); archive = {}
    for name, digest in assets.items():
        source = safe_path(engine.MODEL.parent if name.replace(chr(92), '/').startswith('meshes/') else engine.ROOT, name)
        require(engine.sha256(source) == digest, 'Asset changed'); archive[source.relative_to(engine.ROOT).as_posix()] = digest
    sources = engine.source_hashes(dependencies())
    folder.mkdir(parents=True, exist_ok=False); (folder/'inputs').mkdir()
    shutil.copyfile(args.recording, folder/'inputs/recording.jsonl')
    require(engine.sha256(folder/'inputs/recording.jsonl') == info['source_sha256'], 'Recording changed during freeze')
    ramp.write_capture(folder, 0, captures[0])
    for name, digest in {**sources, **archive}.items():
        source, dest = safe_path(engine.ROOT, name), safe_path(folder/'frozen_source', name)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dest)
        require(engine.sha256(dest) == digest, 'Source archive mismatch')
    manifest = dict(schema=SCHEMA, policy=POLICY, smoke=args.smoke, source_sha256=sources, asset_archive_sha256=archive,
                    recording_sha256=info['source_sha256'], capture=captures[0].metadata(), input_name=args.recording.name,
                    grid=norm(dict(pitch_kp=PITCH_KP, pitch_kd=PITCH_KD, wrist_kp=WRIST_KP, wrist_kd=WRIST_KD)),
                    extra_scenarios=norm([asdict(s) for s in EXTRA_SCENARIOS]),
                    mujoco=mujoco.__version__, numpy=np.__version__, python=platform.python_version(), platform=platform.platform(), workers=args.workers)
    save(folder/'manifest.json', manifest); records, plans = [], {}
    with ProcessPoolExecutor(max_workers=args.workers, initializer=base.expanded.init_worker) as pool:
        for stage in PHASES:
            plan = phase_plan(stage, records, plans, args.smoke); plans[stage] = plan; save(folder/'plans'/(stage+'.json'), plan)
            futures = [pool.submit(run_case, j, str(folder)) for j in plan]
            for future in as_completed(futures):
                r = future.result(); records.append(r)
                done = sum(x['stage'] == stage for x in records)
                progress = dict(complete=False, stage=stage, done=done, total=len(plan), actual_runs=len(records))
                save(folder/'progress.json', progress)
                if done % 4 == 0 or done == len(plan): print(json.dumps(progress), flush=True)
            print('PHASE_RANK ' + json.dumps(dict(stage=stage, top=rank([r for r in records if r['stage'] == stage], plan)[:4])), flush=True)
    result = summary(records, plans, engine.sha256(folder/'manifest.json'), args.smoke)
    save(folder/'summary.json', result)
    checked = audit(folder); save(folder/'progress.json', dict(complete=True, cases=len(records), audited=checked['passed']))
    print('STUDY_COMPLETE ' + json.dumps(dict(cases=len(records), eligible=result['eligible'], selected=result['selected_filtered_pipeline_spec'])), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
