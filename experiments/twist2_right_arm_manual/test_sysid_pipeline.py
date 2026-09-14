"""Generated fixtures only; no SDK, network, controller or robot execution."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import sysid_capture as cap
import sysid_model as model


def records(episode='train', seed=1, delay=4, count=320):
    rng=np.random.default_rng(seed)
    u=np.repeat(rng.uniform(-.2,.2,(count//8+1,29)),8,axis=0)[:count]
    q=np.zeros((count,29));dq=np.zeros_like(q)
    for k in range(count-1):
        q[k+1]=.85*q[k]+.12*u[max(0,k-delay)]+.001
        dq[k+1]=(q[k+1]-q[k])/.01
    result=[]
    for k in range(count):
        t=1000000000+k*10000000
        result.append(dict(schema=cap.SCHEMA,session=episode,episode=episode,
             sequence=k,state='active',mode=None,provenance={'kind':'generated','source':'seeded fixture'},
             clock={'domain':'fixture shared','source':'generated monotonic'},
             joint_indices=list(range(29)),joint_names=list(cap.JOINT_NAMES),units=cap.UNITS.copy(),
             acceptance='unknown',dropped_samples=0,target_ns=t,write_begin_ns=t,
             write_end_ns=t+100,state_receive_ns=t,target_q=u[k].tolist(),command_q=u[k].tolist(),
             command_dq=[0.]*29,kp=[40.]*29,kd=[5.]*29,tau_ff=[0.]*29,
             measured_q=q[k].tolist(),measured_dq=dq[k].tolist(),torque_estimate=None,
             imu_rpy=[0.,0.,0.],imu_gyro=[0.,0.,0.],imu_accel=[0.,0.,9.81],
             temperature=None,motor_status=None))
    return result


def save(path, rows):
    logger=cap.Capture(path,capacity=1000)
    for r in rows: assert logger.offer(cap.canonical(r))
    status=logger.close()
    assert status['complete'],status


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def plan(self):
        p=self.root/'plan.json'
        model.create_plan(p,['train'],['validation'],[22,25],list(range(9)),1e-7,1e-6,
                          'generated noiseless fixture only; not real noise')
        return p

    def test_29_order_matches_canonical(self):
        p=Path(__file__).resolve().parents[2]/'hardware/g1_arm_bridge/g1_joint_contract.py'
        spec=importlib.util.spec_from_file_location('contract',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.assertEqual(cap.JOINT_NAMES,m.G1_29_JOINT_NAMES)

    def test_roundtrip_exact_bytes_optional_fields(self):
        rows=records(count=20);p=self.root/'episode.jsonl';save(p,rows)
        self.assertEqual(cap.read_episode(p),rows)
        self.assertEqual(p.read_bytes(),b''.join(cap.canonical(r)+b'\n' for r in rows))

    def test_no_transport_imports(self):
        allowed={'hashlib','json','math','pathlib','queue','threading','argparse','numpy','sysid_capture'}
        for module in (cap,model):
            tree=ast.parse(Path(module.__file__).read_text())
            for n in ast.walk(tree):
                if isinstance(n,ast.Import):
                    self.assertTrue(all(a.name.split('.')[0] in allowed for a in n.names))
                if isinstance(n,ast.ImportFrom): self.assertIn(n.module.split('.')[0],allowed)

    def test_nonfinite_and_missing(self):
        for change in ('nan','missing','order','acceptance'):
            r=records(count=1)[0]
            if change=='nan':r['imu_gyro'][0]=float('nan')
            elif change=='missing':del r['kd']
            elif change=='order':r['joint_names'].reverse()
            else:r['acceptance']='accepted'
            with self.assertRaises(ValueError):cap.validate(r)

    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):cap.decode(b'{"a":1,"a":2}')

    def test_queue_overflow_is_nonthrowing_and_incomplete(self):
        # No worker: deterministic full queue, test actual producer method.
        import queue,threading
        sink=object.__new__(cap.Capture);sink.q=queue.Queue(1)
        sink.closed=threading.Event();sink.failed=threading.Event();sink.offered=sink.dropped=0
        self.assertTrue(sink.offer(b'{}'));self.assertFalse(sink.offer(b'{}'))
        self.assertEqual(sink.dropped,1)

    def test_bad_record_does_not_throw_into_producer(self):
        sink=cap.Capture(self.root/'bad.jsonl')
        self.assertTrue(sink.offer(b'{}'))
        result=sink.close();self.assertFalse(result['complete'])
        with self.assertRaises(ValueError):cap.read_episode(sink.path)

    def test_file_failure_close_does_not_deadlock(self):
        # Parent missing makes worker fail; close only attempts receipt once.
        sink=cap.Capture(self.root/'missing'/'bad.jsonl');sink.offer(b'{}')
        with self.assertRaises(FileNotFoundError):sink.close()
        self.assertFalse(sink.worker.is_alive())

    def test_gap_reverse_and_timestamp(self):
        for key,value in [('sequence',9),('write_begin_ns',0),('dropped_samples',1)]:
            rows=records(count=12);rows[5][key]=value;p=self.root/(key+'.jsonl')
            if key=='write_begin_ns':
                with self.assertRaises(ValueError):cap.validate(rows[5])
            else:
                save(p,rows)
                with self.assertRaises(ValueError):cap.read_episode(p)

    def test_clock_reversal_and_repeated_conflict(self):
        for repeat in (False,True):
            rows=records(count=12)
            rows[5]['state_receive_ns']=rows[4]['state_receive_ns']-(0 if repeat else 1)
            p=self.root/f'clock{repeat}.jsonl';save(p,rows)
            with self.assertRaises(ValueError):cap.read_episode(p)

    def test_known_delay_fit_and_independent_validation(self):
        plan=self.plan() # frozen before even generating validation
        a=self.root/'train.jsonl';save(a,records())
        fit=model.fit(plan,[a])
        for m in fit['models']:
            self.assertEqual(m['delay_samples'],4)
            self.assertAlmostEqual(m['effective_lag_s'],-.01/np.log(.85),places=8)
        b=self.root/'val.jsonl';save(b,records('validation',seed=2))
        result=model.validate_model(plan,fit,[b]);self.assertTrue(result['passed'])
        self.assertFalse(result['hardware_validated']);self.assertIsNone(fit['recommended_hardware_gains'])

    def test_split_overlap_and_plan_overwrite(self):
        with self.assertRaises(ValueError):model.create_plan(self.root/'x',['same'],['same'],[22],[0],.1,.1,'fixture')
        p=self.plan()
        with self.assertRaises(FileExistsError):model.create_plan(p,['train'],['validation'],[22],[0],.1,.1,'fixture')

    def test_relabelled_data_rejected(self):
        p=self.plan();a=self.root/'a.jsonl';save(a,records());m=model.fit(p,[a])
        b=self.root/'b.jsonl';save(b,records('validation'))
        with self.assertRaisesRegex(ValueError,'leakage'):model.validate_model(p,m,[b])

    def test_validation_plan_tampering(self):
        p=self.plan();a=self.root/'a.jsonl';save(a,records());m=model.fit(p,[a])
        x=cap.decode(p.read_bytes());x['q_rmse_rad']=999;p.write_bytes(cap.canonical(x))
        with self.assertRaisesRegex(ValueError,'plan_changed'):model.validate_model(p,m,[])

    def test_hold_data_rejected(self):
        p=self.plan();r=records()
        for x in r:x['command_q']=[0.]*29
        a=self.root/'a.jsonl';save(a,r)
        with self.assertRaisesRegex(ValueError,'excitation'):model.fit(p,[a])

    def test_modified_capture_rejected(self):
        a=self.root/'a.jsonl';save(a,records(count=20));a.write_bytes(a.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'modified'):cap.read_episode(a)

    def test_validation_failure_not_retuned(self):
        p=self.plan();a=self.root/'a.jsonl';save(a,records());m=model.fit(p,[a]);before=cap.digest(m)
        b=self.root/'b.jsonl';save(b,records('validation',seed=2,delay=8))
        self.assertFalse(model.validate_model(p,m,[b])['passed']);self.assertEqual(before,cap.digest(m))

    def test_timing_ambiguity_rejected(self):
        p=self.plan();r=records()
        for x in r:x['state_receive_ns']-=1000
        a=self.root/'a.jsonl';save(a,r)
        with self.assertRaisesRegex(ValueError,'aligned'):model.fit(p,[a])

    def test_existing_runtime_gain_model_preservation(self):
        import subprocess
        root=Path(__file__).resolve().parents[2]
        result=subprocess.run(['git','diff','--exit-code',
            '5de85864988e2c62671dbe7ec6ecc9826dd45ebd','--',
            'tools','hardware','MuJoCo_G1_Controller','references',
            'experiments/twist2_right_arm_manual',
            ':!experiments/twist2_right_arm_manual/sysid_capture.py',
            ':!experiments/twist2_right_arm_manual/sysid_model.py',
            ':!experiments/twist2_right_arm_manual/test_sysid_pipeline.py'],
            cwd=root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_parse_rejects_missing_receipt(self):
        p=self.root/'raw.jsonl';p.write_bytes(cap.canonical(records(count=1)[0])+b'\n')
        with self.assertRaises(FileNotFoundError):cap.read_episode(p)

    def test_hand_edited_overlap_plan_rejected(self):
        p=self.plan();x=cap.decode(p.read_bytes());x['validation']=x['train']
        p.write_bytes(cap.canonical(x))
        with self.assertRaisesRegex(ValueError,'overlap'):model.fit(p,[])


if __name__=='__main__':unittest.main()
