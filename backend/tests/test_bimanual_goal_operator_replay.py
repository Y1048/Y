"""Continuous recorded Quest input / model-state regression, no robot IO.

The compact fixture contains all 618 scheduled display requests from the
operator session which exposed the stale geometric branch. It does NOT contain
measured robot tracking, and it is not evidence of physical goal reachability.
Wall-clock deadlines are tested separately: this test uses the same bounded
numerical work on every machine so CPU scheduling cannot decide acceptance.
"""
import gzip
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import mink
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_goal_preview as preview
from g1_bimanual_sim import BimanualSimulation


class OperatorGoalReplayTests(unittest.TestCase):
    def test_entire_operator_sequence_does_not_retain_dominated_branch(self):
        path = Path(__file__).parent / 'fixtures/geometric_goal_operator_20261008.json.gz'
        fixture = json.loads(gzip.decompress(path.read_bytes()))
        self.assertEqual(fixture['schema'], 'g1.bimanual.geometric.operator_fixture.v1')
        self.assertFalse(fixture['hardware_validation'])
        self.assertEqual(len(fixture['frames']), 618)
        source = BimanualSimulation()
        private = BimanualSimulation()
        self.assertEqual(preview._contract_digest(source), fixture['model_contract_sha256'])
        self.assertEqual(list(source.names), fixture['joint_names'])
        self.assertEqual(source.qids.tolist(), fixture['qpos_ids'])
        errors = []
        with patch.object(preview, 'SOLVE_BUDGET_S', None), \
                patch.object(preview, '_WORKER_NATIVE', preview._snapshot_objects(private)), \
                patch.object(preview, '_WORKER_GEOMETRIC_CACHE', None):
            for frame in fixture['frames']:
                q = np.asarray(frame['q'])
                source.config.update(q)
                source.base_rotation = np.asarray(frame['base_rotation'])
                for side, policy in source.motion.items():
                    for name, value in frame['motion'][side].items():
                        setattr(policy, name, np.asarray(value) if isinstance(value, list) else value)
                goals = {side: mink.SE3.from_rotation_and_translation(
                    mink.SO3(np.asarray(pose['wxyz'])), np.asarray(pose['position']))
                    for side, pose in frame['goals'].items()}
                stream = io.BytesIO()
                preview._SnapshotWriter(stream, {id(v): k for k, v in
                                        preview._snapshot_objects(source).items()}).dump(source)
                result = preview._rollout(stream.getvalue(), q.copy(), goals,
                                          frame['generation'], tuple(frame['context']),
                                          frame['source_time'], frame['sequence'])
                self.assertTrue(result['valid'], (frame['row'], result))
                np.testing.assert_array_equal(source.config.q, q)
                self.assertLessEqual(result['iterations'], 64)
                self.assertGreaterEqual(result['minimum_clearance_m'], source.clearance_m)
                arm_q = preview._WORKER_GEOMETRIC_CACHE['arm_q']
                self.assertTrue(np.isfinite(arm_q).all())
                self.assertTrue(np.all(arm_q >= source.ranges[:, 0] - 1e-9))
                self.assertTrue(np.all(arm_q <= source.ranges[:, 1] + 1e-9))
                witness = q.copy()
                witness[source.qids] = arm_q
                self.assertGreaterEqual(source.clearance(witness), source.clearance_m)
                errors.append(result['position_error_m'])
                if frame['row'] == 5771:
                    # Original continuous cache: 178/65 mm. Same-target reference
                    # recovery can achieve <60 mm on BOTH arms, within bounds.
                    self.assertLess(max(result['position_error_m']), .060)
        values = np.asarray(errors)
        # Fixed before evaluating this deterministic replay. Upper bounds are
        # the old matched-run median/p95, not a claim of near-zero residual.
        self.assertTrue(np.all(np.median(values, axis=0) < [.0335, .0407]))
        self.assertTrue(np.all(np.percentile(values, 95, axis=0) < [.1665, .2023]))


if __name__ == '__main__':
    unittest.main()
