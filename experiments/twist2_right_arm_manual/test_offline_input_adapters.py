"""Independent CRC division vectors and local policy artifact/array validation."""
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest
from offline_policy_adapter import ReadVerifiedPolicy,AdaptOutput,EXPECTED_SHA256

ROOT=Path(__file__).resolve().parents[2]


def ReferenceCrc(data):
    # Polynomial long division, independent of the C++ shift-register loop.
    crc=0xffffffff
    polynomial=(1<<32)|0x04c11db7
    for offset in range(0,len(data),4):
        dividend=(crc^int.from_bytes(bytes(data[offset:offset+4]),'little'))<<32
        while dividend.bit_length()>32:
            dividend^=polynomial<<(dividend.bit_length()-33)
        crc=dividend
    return crc


class AdapterTests(unittest.TestCase):
    def test_crc_vectors_bit_flips_and_invalid_lengths(self):
        rng=random.Random(17)
        vectors=[[0]*4,[255]*4,[1,2,3,4]]+[[rng.randrange(256) for _ in range(n*4)] for n in range(1,41)]
        vectors += [[1<<bit,0,0,0] for bit in range(8)]
        inputs=vectors+[[],[1,2,3],[256,0,0,0]]
        result=subprocess.run([str(ROOT/'logs/test_results/test_offline_word_crc.exe')],
            input=''.join(json.dumps(v)+'\n' for v in inputs),text=True,capture_output=True,check=True,timeout=5)
        rows=[json.loads(x) for x in result.stdout.splitlines()]
        self.assertEqual(len(rows),len(inputs))
        for data,row in zip(vectors,rows):
            with self.subTest(bytes=len(data)): self.assertEqual(row['crc'],ReferenceCrc(data))
        for row in rows[-3:]: self.assertTrue(row['error'])

    def test_local_policy_identity_and_mismatch(self):
        source=(ROOT/'references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp').read_text()
        self.assertIn(EXPECTED_SHA256,source)
        model=ROOT/'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt'
        self.assertEqual(len(ReadVerifiedPolicy(model)),model.stat().st_size)
        with tempfile.TemporaryDirectory() as folder:
            bad=Path(folder)/'bad.pt';bad.write_bytes(b'wrong model')
            with self.assertRaises(ValueError): ReadVerifiedPolicy(bad)

    def Adapt(self,output,**kw):
        args=dict(sequence=1,state_sequence=2,created_at=.02,state_received_at=.01,now=.025,maximum_age=.01)
        args.update(kw)
        return AdaptOutput(output,**args)

    def test_output_clip_shape_and_metadata(self):
        row=self.Adapt([[3,-3]+[.5]*27])
        self.assertEqual(row['action'],[2,-2]+[.5]*27)
        for output in ([],[0]*29,[[0]*28],[[0]*30],[[True]*29],[[float('nan')]*29],[[float('inf')]*29],[[1e100]*29]):
            with self.subTest(output=str(output)[:20]),self.assertRaises(ValueError): self.Adapt(output)
        for kw in (dict(sequence=-1),dict(sequence=True),dict(state_sequence=2**64),dict(created_at=.03),dict(now=.1),dict(maximum_age=0)):
            with self.subTest(kw=kw),self.assertRaises(ValueError): self.Adapt([[0]*29],**kw)

if __name__=='__main__': unittest.main()
