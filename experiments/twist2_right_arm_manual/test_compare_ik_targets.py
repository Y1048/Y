import copy
import json
import tempfile
import unittest
from pathlib import Path
from compare_ik_targets import compare,load


def fixture():
    return dict(schema='g1.ik.target_trace.v1',input_sha256='fixture',model_sha256='model',
        stage='limited_target',ik_version='fixture-v1',initial_q_rad=[0]*29,
        right_lower_rad=[-2]*7,right_upper_rad=[2]*7,
        samples=[dict(input_index=i,elapsed_s=t,q_rad=[0]*29) for i,t in enumerate((0,.1,.3,.6))])


class ComparisonTests(unittest.TestCase):
    def test_identity(self):
        a=fixture();r=compare(a,a,'fixture',.7,.174533,.05)
        self.assertFalse(any(j['review_required'] for j in r['joints']))
    def test_nonuniform_time_derivatives(self):
        a=fixture();b=copy.deepcopy(a)
        for row in b['samples']:row['q_rad'][22]=.2*row['elapsed_s']
        r=compare(a,b,'fixture',.7,.174533,.05)['joints'][0]
        self.assertAlmostEqual(r['after']['peak_speed_rad_s'],.2)
        self.assertAlmostEqual(r['after']['peak_acceleration_rad_s2'],0)
        self.assertTrue(r['review_required'])
    def test_jump_and_limit(self):
        a=fixture();b=copy.deepcopy(a);b['samples'][2]['q_rad'][22]=3
        j=compare(a,b,'fixture',.7,.174533,.05)['joints'][0]
        self.assertLess(j['after']['minimum_limit_margin_rad'],0)
        self.assertTrue(j['after']['violations'])
    def test_context_alignment(self):
        a=fixture()
        for key in ('model_sha256','stage','input_sha256'):
            b=copy.deepcopy(a);b[key]='different'
            with self.assertRaises(ValueError):compare(a,b,'fixture',.7,.174533,.05)
        b=copy.deepcopy(a);b['samples'][1]['elapsed_s']+=.01
        with self.assertRaises(ValueError):compare(a,b,'fixture',.7,.174533,.05)
        with self.assertRaises(ValueError):compare(a,a,'wrong',.7,.174533,.05)
    def test_load_rejects_invalid_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'trace.json'
            for kind in range(3):
                a=fixture()
                if kind==0:a['samples'][1]['elapsed_s']=0
                if kind==1:a['samples'][1]['q_rad'][22]=float('nan')
                if kind==2:a['samples'][1]['input_index']=0
                p.write_text(json.dumps(a))
                with self.assertRaises(ValueError):load(p)


if __name__=='__main__':unittest.main()
