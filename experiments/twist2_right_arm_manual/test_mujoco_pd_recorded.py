"""Offline parser/dynamics/evidence tests. Generated input is a TEST FIXTURE,
not an actual operator recording and never counted as the formal experiment.
"""
from __future__ import annotations
import copy,json,math,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco_pd_recording as recording
import mujoco_pd_recorded_core as core
import mujoco_pd_recorded_study as study


def fixture_rows():
    q=core.engine.load_contract().baseline[22:].copy();rows=[]
    for i in range(98):
        x=q.copy();event='idle' if i in (0,97) else ('active' if i<=70 else ('pinch' if i==71 else 'return'))
        if event=='active':
            offset=.03*math.sin(math.pi*i/70)**2;x[0]+=offset;x[5]-=offset
        packet=dict(schema='g1.mink.cycle.live.v1',command_provenance='live_mink',profile='yesterday',
            session='unit-test-fixture-not-live',sequence=i+1,epoch=int(i>=72),sample_time_s=i*.02,
            source_age_s=0.,event=event,joints=x.tolist(),clearance_m=.04)
        rows.append(dict(kind='send_attempt',time=100+i*.02,packet=packet))
    return rows


def dump(path,rows):path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')

def capture():
    with tempfile.TemporaryDirectory() as f:
        p=Path(f)/'fixture.jsonl';dump(p,fixture_rows());cs,info=recording.extract(p)
        if len(cs)!=1:raise RuntimeError(info)
        return cs[0]


class ParserTest(unittest.TestCase):
    def check_rows(self,rows):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'fixture.jsonl';dump(p,rows);return recording.extract(p)
    def test_complete_source_identity_without_measured_claim(self):
        c=capture();m=c.metadata();self.assertTrue(m['simulation_only']);self.assertFalse(m['measured_robot_response']);self.assertFalse(m['delivery_verified']);self.assertEqual(m['samples'],98)
    def test_duplicate_json_and_nonfinite_rejected(self):
        for value in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
            with self.assertRaises(ValueError):recording.strict_json(value)
    def test_boolean_number_rejected(self):
        rows=fixture_rows();rows[1]['packet']['joints'][0]=True
        with self.assertRaisesRegex(ValueError,'packet_joints'):self.check_rows(rows)
    def test_missing_idle_end_not_promoted(self):
        cs,info=self.check_rows(fixture_rows()[:-1]);self.assertEqual(cs,[]);self.assertEqual(info['exclusions'][0]['reason'],'episode_no_idle_end')
    def test_missing_return_not_promoted(self):
        rows=fixture_rows();rows[72]['packet']['event']='active';cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_nonreturned_endpoint_rejected(self):
        rows=fixture_rows();rows[-1]['packet']['joints'][0]+=.02;cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_sequence_gap_rejected(self):
        rows=fixture_rows();rows[20]['packet']['sequence']+=1;cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_epoch_transition_rejected(self):
        rows=fixture_rows();rows[80]['packet']['epoch']=9;cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_session_or_profile_switch_rejected(self):
        for k,v in (('session','another'),('profile','today')):
            rows=fixture_rows();rows[40]['packet'][k]=v;cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_stale_age_and_false_clearance_rejected(self):
        for k,v in (('source_age_s',.251),('clearance_m',.001)):
            rows=fixture_rows();rows[25]['packet'][k]=v;cs,info=self.check_rows(rows);self.assertEqual(cs,[])
    def test_clocks_gaps_and_reversal_rejected(self):
        c=capture()
        for clock,offset in (('send_time_s',-.1),('sample_time_s',.1)):
            x=getattr(c,clock).copy();x[30]+=offset
            with self.assertRaises(ValueError):replace(c,**{clock:x}).validate()
    def test_equal_logger_times_keep_order_and_latest_target(self):
        c=capture();t=c.send_time_s.copy();t[20]=t[19];r=replace(c,send_time_s=t);r.validate();self.assertEqual(r.at(t[19]),20)
    def test_zero_order_hold_not_interpolation(self):
        c=capture();self.assertEqual(c.at(.021,'sample'),1);self.assertEqual(c.at(100),97)
        with self.assertRaises(ValueError):c.at(-1)
        with self.assertRaises(ValueError):c.at(0,'invented')
    def test_secrets_and_synthetic_provenance_refused(self):
        rows=fixture_rows();rows[2]['packet']['relay_token']='test-only'
        with self.assertRaises(ValueError):self.check_rows(rows)
        rows=fixture_rows();rows[2]['packet']['simulation_only']=True
        with self.assertRaises(ValueError):self.check_rows(rows)
    def test_empty_file_has_no_episodes(self):
        cs,info=self.check_rows([]);self.assertEqual(cs,[])
        with self.assertRaises(ValueError):study.jobs(cs)


class WriterPlanTest(unittest.TestCase):
    def test_yesterday_exact_existing_writer(self):
        c=core.engine.load_contract();rng=np.random.default_rng(17)
        for _ in range(100):
            q=c.baseline+rng.uniform(-.02,.02,29);dq=rng.normal(0,.05,29);ref=c.baseline+rng.uniform(-.05,.05,29)
            x=core.writer_target(ref,c.baseline,q,dq,c.kp,c.kd,c,'yesterday')
            y=core.engine.writer_target(ref,c.baseline,q,dq,c.kp,c.kd,c)
            for a,b in zip(x,y):np.testing.assert_array_equal(a,b)
    def test_today_profile_rates_not_old_wrist_rate(self):
        c=core.engine.load_contract();q=c.baseline;ref=q.copy();ref[22:]+=.05
        p=np.full(29,40.);d=np.full(29,3.)
        cmd,limited,_=core.writer_target(ref,q,q,np.zeros(29),p,d,c,'today')
        np.testing.assert_allclose((cmd-q)[22:26],math.pi/2*.002,atol=1e-12)
        np.testing.assert_allclose((cmd-q)[26:],math.pi*.002,atol=1e-12)
        self.assertFalse(limited.any())
        source=Path(__file__).with_name('twist2_mink_cycle_trial.cpp').read_text()
        self.assertIn('joint<26?1.57079632679F:3.14159265359F',source)
    def test_24_frozen_cells(self):
        plan=study.jobs([capture()]);self.assertEqual(len(plan),24)
        self.assertEqual(len({j['case_id'] for j in plan}),24)
        for yaw in (64.,72.):self.assertEqual(sum(j['candidate']['kp'][2]==yaw for j in plan),12)
    def test_existing_output_and_invalid_workers_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):study.main(['--output',d])
            with self.assertRaises(SystemExit):study.main(['--output',d,'--workers','7'])
    def test_no_live_bounds_relaxed(self):
        text=Path(__file__).with_name('pd_gain_options.hpp').read_text().replace(' ','')
        self.assertIn('value>(p?100.F:20.F)',text)
        self.assertFalse(all(x<=100 for x in study.VECTORS[0].kp))


class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=capture();cls.r,cls.a=core.simulate(cls.c,study.VECTORS[1],study.SCENARIOS[0],'sample')
    def test_actual_dynamics_seven_goals(self):
        self.assertTrue(self.r['completed']);self.assertTrue(self.r['eligible'],self.r['exclusions'])
        self.assertGreater(np.ptp(self.a['q'][:,27]),.005);self.assertEqual(self.r['gains_kp'][24],72)
    def test_q_not_projected_to_goal(self):self.assertGreater(np.max(np.abs(self.a['q']-self.a['ref'])),1e-5)
    def test_pd_equation_and_original_source_targets(self):
        a=self.a;kp=np.array(self.r['gains_kp']);kd=np.array(self.r['gains_kd'])
        np.testing.assert_allclose(a['requested'],kp*(a['cmd']-a['q'])-kd*a['dq'],atol=1e-12,rtol=1e-12)
        mask=a['source_index']>=0;np.testing.assert_array_equal(a['ref'][mask,22:],self.c.joints[a['source_index'][mask]])
    def test_final_wrist_bias_refused(self):
        a={k:v.copy() for k,v in self.a.items()};a['q'][-500:,28]+=.04
        score=core.evaluate(a,self.c,'sample',True,'',self.r['physics']);self.assertFalse(score['eligible'])
    def test_final_wrist_speed_refused(self):
        a={k:v.copy() for k,v in self.a.items()};a['dq'][-100:,26]=.2
        self.assertFalse(core.evaluate(a,self.c,'sample',True,'',self.r['physics'])['eligible'])
    def test_partial_failure_cannot_use_last_available_second(self):
        self.assertFalse(core.evaluate(self.a,self.c,'sample',False,'stop',self.r['physics'])['eligible'])
    def test_contact_and_clock_gap_refused(self):
        physics=dict(self.r['physics'],contact_steps=1)
        self.assertFalse(core.evaluate(self.a,self.c,'sample',True,'',physics)['eligible'])
        a={k:v.copy() for k,v in self.a.items()};a['time_s'][10]+=.01
        with self.assertRaises(ValueError):core.evaluate(a,self.c,'sample',True,'',self.r['physics'])
    def test_nonfinite_other_joint_refused(self):
        a={k:v.copy() for k,v in self.a.items()};a['q'][2,0]=np.nan
        with self.assertRaises(ValueError):core.evaluate(a,self.c,'sample',True,'',self.r['physics'])
    def test_all29_final_step_guard(self):
        study.check_guard(self.r,self.a)
        r=copy.deepcopy(self.r);r['joint_limit_guard']['observations']-=1
        with self.assertRaises(ValueError):study.check_guard(r,self.a)
    def test_reference_outside_corridor_refused_before_integration(self):
        q=self.c.joints.copy();q[20,5]=9.;c=replace(self.c,joints=q)
        r,a=core.simulate(c,study.VECTORS[1],study.SCENARIOS[0]);self.assertFalse(r['eligible']);self.assertEqual(r['physics']['steps'],0)
    def test_warmup_matches_existing_dynamics(self):
        motion=core.sync.Motion('parity',post_hold_s=2.)
        r,a=core.sync.simulate(motion,study.VECTORS[1],study.SCENARIOS[0])
        for k in ('q','dq','ref','cmd','requested','actual_tau'):
            np.testing.assert_array_equal(self.a[k][:1500],a[k][:1500])


class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.raw=cls.root/'fixture.jsonl'
        dump(cls.raw,fixture_rows());cls.out=cls.root/'result'
        study.main(['--recording',str(cls.raw),'--output',str(cls.out),'--smoke','--workers','1'])
        cls.caps,_=recording.extract(cls.raw);cls.plan=study.read(cls.out/'plan.json')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_real_smoke_audit(self):
        self.assertTrue(study.audit(self.out)['passed']);self.assertIsNone(study.read(self.out/'summary.json')['selected_simulation_vector'])
    def mutate(self,name,mutator):
        p=self.out/name;old=p.read_bytes()
        try:
            value=json.loads(old);mutator(value);p.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_manifest_hardware_claim_refused(self):self.mutate('manifest.json',lambda d:d.update(hardware_approved=True))
    def test_summary_score_tamper(self):self.mutate('summary.json',lambda d:d['ranking'][0].update(worst_right7_rmse_rad=0.))
    def test_record_gain_tamper(self):self.mutate('cases/case_0000.json',lambda d:d['gains_kp'].__setitem__(24,73.))
    def test_record_input_identity_tamper(self):self.mutate('cases/case_0000.json',lambda d:d['recording'].update(first_line=8))
    def test_missing_cell_refused(self):
        p=self.out/'cases/case_0000.json';old=p.read_bytes();p.unlink()
        try:
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_raw_recording_hash_checked(self):
        p=self.out/'inputs/recording.jsonl';old=p.read_bytes();p.write_bytes(old+b'\n')
        try:
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_normalized_trace_corruption_refused(self):
        p=self.out/'inputs/episode_00.npz';old=p.read_bytes()
        try:
            with np.load(p) as z:fields={k:z[k] for k in z.files}
            fields['joints'][2,0]+=.001;np.savez_compressed(p,**fields)
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_data_trace_hash_checked(self):
        p=self.out/'full_state/case_0000.npz';old=p.read_bytes();p.write_bytes(old+b'x')
        try:
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_no_winner_after_one_failure(self):
        records=[study.read(self.out/'cases'/(j['case_id']+'.json')) for j in self.plan]
        for r in records:r.update(eligible=False,exclusions=['test'])
        s=study.summarize(records,self.plan,'x',False);self.assertIsNone(s['selected_simulation_vector'])
    def test_parallel_order_deterministic(self):
        records=[study.read(self.out/'cases'/(j['case_id']+'.json')) for j in self.plan]
        self.assertEqual(study.summarize(records,self.plan,'x'),study.summarize(list(reversed(records)),self.plan,'x'))


if __name__=='__main__':unittest.main()
