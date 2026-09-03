from __future__ import annotations

import sys
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
    def _alphas(self, show_inspection_scene: bool) -> dict[str, float]:
        g1.make_demo_xml(
            "control",
            show_inspection_scene=show_inspection_scene,
        )
        model = mujoco.MjModel.from_xml_path(str(g1.DEMO_XML))
        return {
            name: float(model.geom(name).rgba[3])
            for name in INSPECTION_GEOMS
        }

    def test_inspection_scene_is_hidden_by_default(self) -> None:
        alphas = self._alphas(show_inspection_scene=False)
        self.assertTrue(all(alpha == 0.0 for alpha in alphas.values()))

    def test_inspection_scene_can_be_enabled_without_recreating_bodies(self) -> None:
        try:
            alphas = self._alphas(show_inspection_scene=True)
            self.assertTrue(all(alpha > 0.0 for alpha in alphas.values()))
        finally:
            g1.make_demo_xml("control", show_inspection_scene=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
