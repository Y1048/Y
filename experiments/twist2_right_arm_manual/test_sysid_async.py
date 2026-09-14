"""Generated Euler oracle only; never connects to hardware."""
import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import sysid_async_model as async_model
import sysid_model as model
import sysid_capture as cap
from test_sysid_pipeline import records, save


def fixture(episode, seed, delay=.02):
    rows=records(episode,seed,count=320)
    u=np.array([r['command_q'] for r in rows])
    # Independent fine-step Euler integration, 10 us, sampled asynchronously.
    dt=.00001; q=np.zeros(29); snapshots={}; wanted={}
    for k in range(len(rows)):
        tick=k*1000+300+(k%3)*20
        wanted[tick]=k
    for tick in range(max(wanted)+1):
        index=max(0,min(len(u)-1,int(np.floor((tick*dt-delay+1e-12)/.01))))
        dq=(.8*u[index]+.003-q)/.08
        if tick in wanted:snapshots[wanted[tick]]=(q.copy(),dq.copy(),tick)
        q=q+dt*dq
    for k,r in enumerate(rows):
        q,dq,tick=snapshots[k]
        r['state_receive_ns']=1000000000+tick*10000
        r['measured_q']=q.tolist();r['measured_dq']=dq.tolist()
    return rows


class AsyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        base=self.root/'base.json'
        model.create_plan(base,['train'],['validation'],[22],[0],.001,.02,
                          'fixed generated Euler oracle tolerances, not sensor noise')
        self.plan=self.root/'plan.json'
        async_model.freeze(self.plan,cap.decode(base.read_bytes()),[.01,.02,.03],[.06,.08,.1])
        self.train=self.root/'train.jsonl';save(self.train,fixture('train',1))
    def tearDown(self):self.temp.cleanup()

    def test_delay_lag_and_heldout(self):
        m=async_model.fit(self.plan,[self.train]);f=m['models'][0]
        self.assertEqual(f['delay_s'],.02);self.assertEqual(f['lag_s'],.08)
        self.assertAlmostEqual(f['gain'],.8,places=3)
        v=self.root/'v.jsonl';save(v,fixture('validation',2))
        result=async_model.validate(self.plan,m,[v])
        self.assertTrue(result['passed'],result)
        self.assertIsNone(result['recommended_hardware_gains'])

    def test_failure_does_not_retune(self):
        m=async_model.fit(self.plan,[self.train]);before=cap.digest(m)
        v=self.root/'v.jsonl';save(v,fixture('validation',2,delay=.06))
        self.assertFalse(async_model.validate(self.plan,m,[v])['passed'])
        self.assertEqual(before,cap.digest(m))

    def test_leakage_rejected(self):
        m=async_model.fit(self.plan,[self.train]);r=fixture('validation',1)
        v=self.root/'v.jsonl';save(v,r)
        with self.assertRaisesRegex(ValueError,'leakage'):async_model.validate(self.plan,m,[v])

    def test_changed_plan_rejected(self):
        m=async_model.fit(self.plan,[self.train]);p=cap.decode(self.plan.read_bytes())
        p['q_rmse_rad']=100;self.plan.write_bytes(cap.canonical(p))
        with self.assertRaisesRegex(ValueError,'plan_changed'):async_model.validate(self.plan,m,[])

    def test_missing_prehistory(self):
        e=async_model.episodes([self.train],['train'],async_model._plan(self.plan))[0]
        with self.assertRaisesRegex(ValueError,'prehistory'):async_model.basis(e,22,.02,.08,0)

    def test_nonfinite_grid(self):
        with self.assertRaises(ValueError):async_model.freeze(self.root/'bad',{},[float('nan')],[.1])

    def test_repeated_state_deduplicated(self):
        r=fixture('train',1)
        for k in range(1,len(r),7):
            for field in ('state_receive_ns','measured_q','measured_dq'):r[k][field]=copy.deepcopy(r[k-1][field])
        p=self.root/'repeat.jsonl';save(p,r)
        m=async_model.fit(self.plan,[p]);self.assertEqual(m['models'][0]['delay_s'],.02)

    def test_gap_rejected(self):
        r=fixture('train',1)
        for row in r[100:]:
            for key in ('target_ns','write_begin_ns','write_end_ns','state_receive_ns'):row[key]+=100000000
        p=self.root/'gap.jsonl';save(p,r)
        with self.assertRaisesRegex(ValueError,'time_gap'):async_model.fit(self.plan,[p])

    def test_empty_model_rejected(self):
        m=async_model.fit(self.plan,[self.train]);m['models']=[]
        with self.assertRaisesRegex(ValueError,'coverage'):async_model.validate(self.plan,m,[])


if __name__=='__main__':unittest.main()
