import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from test_real_response_identification import record
from sysid_inspect_legacy import inspect


class LegacyReadinessTests(unittest.TestCase):
    def test_hold_and_gap_reported_without_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'v1.jsonl';z=np.zeros(7)
            rows=[record(i,z,z,z) for i in (0,1,3)]
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            before=p.read_bytes();result=inspect(p)
            self.assertEqual(result['sequence_gaps'],1)
            self.assertIn('no_command_excitation',result['blockers'])
            self.assertEqual(p.read_bytes(),before)
            self.assertFalse(result['fit_ready'])

    def test_motion_does_not_remove_missing_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'v1.jsonl';z=np.zeros(7)
            rows=[record(i,z+i*.01,z,z) for i in range(3)]
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=inspect(p)
            self.assertNotIn('no_command_excitation',result['blockers'])
            self.assertIn('write_begin_not_proven',result['blockers'])
            self.assertFalse(result['fit_ready'])
            self.assertIsNone(result['recommended_hardware_gains'])


if __name__=='__main__':unittest.main()
