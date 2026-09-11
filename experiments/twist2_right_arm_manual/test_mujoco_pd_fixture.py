"""Regression for artificial root contacts introduced by fixing a free base."""
from pathlib import Path
import importlib.util
import os
import unittest
import xml.etree.ElementTree as ET

import numpy as np

from mujoco_pd_fixture import ROOT_PARENT_PAIRS, preserve_root_parent_filter


class FixtureXmlTest(unittest.TestCase):
    def tree(self):
        tree = ET.fromstring('<mujoco><worldbody><body name="pelvis"/></worldbody></mujoco>')
        pelvis = tree.find('./worldbody/body')
        for _, child in ROOT_PARENT_PAIRS:
            ET.SubElement(ET.SubElement(pelvis, 'body', name=child), 'joint')
        return tree, pelvis

    def test_exact_parent_pairs_and_idempotence(self):
        tree, pelvis = self.tree()
        preserve_root_parent_filter(tree, pelvis)
        preserve_root_parent_filter(tree, pelvis)
        self.assertEqual([(e.get('body1'), e.get('body2')) for e in tree.findall('./contact/exclude')],
                         list(ROOT_PARENT_PAIRS))

    def test_changed_source_topology_refused(self):
        tree, pelvis = self.tree()
        ET.SubElement(pelvis, 'body', name='unexpected_child')
        with self.assertRaises(ValueError):
            preserve_root_parent_filter(tree, pelvis)

    def test_disabled_parent_filter_and_explicit_pairs_refused(self):
        for kind in ('flag', 'pair'):
            tree, pelvis = self.tree()
            if kind == 'flag':
                ET.SubElement(ET.SubElement(tree, 'option'), 'flag', filterparent='disable')
            else:
                ET.SubElement(ET.SubElement(tree, 'contact'), 'pair', geom1='x', geom2='y')
            with self.assertRaises(ValueError):
                preserve_root_parent_filter(tree, pelvis)


@unittest.skipUnless(importlib.util.find_spec('mujoco'), 'MuJoCo required for fixture dynamics')
class FixtureDynamicsTest(unittest.TestCase):
    def xml(self):
        from mujoco_pd_sweep import MODEL
        tree = ET.fromstring(MODEL.read_text())
        tree.find('compiler').set('meshdir', str(MODEL.parent / 'meshes'))
        return tree

    def data_at_ready(self, model):
        import mujoco
        from mujoco_pd_sweep import JOINTS, load_contract
        data = mujoco.MjData(model)
        ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in JOINTS]
        data.qpos[model.jnt_qposadr[ids]] = load_contract().baseline
        mujoco.mj_forward(model, data)
        return data

    def pairs(self, model, data):
        import mujoco
        return {frozenset(mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY,
                                            int(model.geom_bodyid[int(g)]))
                           for g in c.geom) for c in data.contact if c.efc_address >= 0}

    def test_free_source_and_fixed_fixture_collision_filter_match(self):
        import mujoco
        from mujoco_pd_sweep import MODEL, load_model
        source = mujoco.MjModel.from_xml_string(ET.tostring(self.xml(), encoding='unicode'))
        source_data = self.data_at_ready(source)
        tree = self.xml()
        pelvis = tree.find('./worldbody/body')
        pelvis.remove(pelvis.find("joint[@type='free']"))
        broken = mujoco.MjModel.from_xml_string(ET.tostring(tree, encoding='unicode'))
        broken_data = self.data_at_ready(broken)
        fixed, *_ = load_model(MODEL, .001)
        fixed_data = self.data_at_ready(fixed)
        self.assertEqual(self.pairs(source, source_data), set())
        self.assertEqual(self.pairs(broken, broken_data),
                         {frozenset(pair) for pair in ROOT_PARENT_PAIRS[:2]})
        self.assertEqual(self.pairs(fixed, fixed_data), self.pairs(source, source_data))
        self.assertEqual(fixed.nexclude, 3)
        np.testing.assert_array_equal(source.geom_contype, fixed.geom_contype)
        np.testing.assert_array_equal(source.geom_conaffinity, fixed.geom_conaffinity)

    def test_nonadjacent_obstacle_contact_is_not_disabled(self):
        import mujoco
        tree = self.xml()
        pelvis = tree.find('./worldbody/body')
        preserve_root_parent_filter(tree, pelvis)
        pelvis.remove(pelvis.find("joint[@type='free']"))
        model = mujoco.MjModel.from_xml_string(ET.tostring(tree, encoding='unicode'))
        data = self.data_at_ready(model)
        wrist = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'right_wrist_yaw_link')
        position = ' '.join(map(str, data.xpos[wrist]))
        ET.SubElement(tree.find('worldbody'), 'geom', name='offline_test_obstacle',
                      type='sphere', size='.04', pos=position)
        model = mujoco.MjModel.from_xml_string(ET.tostring(tree, encoding='unicode'))
        data = self.data_at_ready(model)
        self.assertTrue(any('world' in pair and any(n.startswith('right_wrist') for n in pair)
                            for pair in self.pairs(model, data)))

    def test_complete_candidate_is_contact_free_and_eligible(self):
        from mujoco_pd_sweep import MODEL, load_model, load_contract, run_candidate
        model, qadr, vadr, motors, _ = load_model(MODEL, .001)
        result, _ = run_candidate(model, qadr, vadr, motors, load_contract(), 40, 5)
        self.assertTrue(result['completed'], result)
        self.assertEqual(result['metrics']['contact_sample_ratio'], 0)
        self.assertTrue(result['eligible'], result)


if __name__ == '__main__':
    if os.environ.get('G1_REQUIRE_MUJOCO') == '1' and not importlib.util.find_spec('mujoco'):
        raise SystemExit('MuJoCo required; no skipped fixture validation')
    unittest.main()
