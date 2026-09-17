from __future__ import annotations

import sys
import ast
import tempfile
import unittest
from pathlib import Path

import mujoco


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import g1_right_arm_common as g1  # noqa: E402


INSPECTION_GEOMS = (
    "inspection_demo_target_marker",
    "inspection_panel",
    "inspection_tool_tip",
    "inspection_tool_grip",
    "inspection_tool_probe",
)


class MujocoInspectionSceneVisibilityTest(unittest.TestCase):
    def test_backend_tests_always_choose_an_explicit_model_output(self):
        for source in Path(__file__).parent.glob("test_*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ("make_demo_xml", "_prepare_mink_xml")):
                    self.assertTrue(any(k.arg == "output_path" and not (
                        isinstance(k.value, ast.Constant) and k.value.value is None)
                        for k in node.keywords), f"Shared model writer: {source.name}:{node.lineno}")

    def _alphas(self, show_inspection_scene: bool) -> dict[str, float]:
        with tempfile.TemporaryDirectory() as directory:
            path = g1.make_demo_xml(
                "control", show_inspection_scene=show_inspection_scene,
                output_path=Path(directory) / "model.xml",
            )
            model = mujoco.MjModel.from_xml_path(str(path))
        return {
            name: float(model.geom(name).rgba[3])
            for name in INSPECTION_GEOMS
        }

    def test_inspection_scene_is_hidden_by_default(self) -> None:
        alphas = self._alphas(show_inspection_scene=False)
        self.assertTrue(all(alpha == 0.0 for alpha in alphas.values()))

    def test_inspection_scene_can_be_enabled_without_recreating_bodies(self) -> None:
        alphas = self._alphas(show_inspection_scene=True)
        self.assertTrue(all(alpha > 0.0 for alpha in alphas.values()))

    def test_isolated_generation_does_not_touch_shared_model(self):
        import run_mink_g1_right_arm_prototype as base

        before = g1.DEMO_XML.read_bytes() if g1.DEMO_XML.exists() else None
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mink.xml"
            self.assertEqual(base._prepare_mink_xml(output_path=path), path)
            model = mujoco.MjModel.from_xml_path(str(path))
            self.assertGreater(model.nq, 0)
            self.assertGreaterEqual(model.geom(base.RIGHT_HAND_COLLISION_NAME).id, 0)
        after = g1.DEMO_XML.read_bytes() if g1.DEMO_XML.exists() else None
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
