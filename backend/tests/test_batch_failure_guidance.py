from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAILURE_MARKERS = ("[FAIL]", "[ERROR]", "[BLOCKED]", "[FAULT]")


class BatchFailureGuidanceTest(unittest.TestCase):
    @staticmethod
    def batch_paths() -> list[Path]:
        paths = sorted(PROJECT_ROOT.glob("*.bat"))
        paths.extend(sorted((PROJECT_ROOT / "tools").glob("*.bat")))
        return paths

    def test_each_failure_message_is_followed_by_an_action(self):
        missing_actions: list[str] = []

        for batch_path in self.batch_paths():
            lines = batch_path.read_text(
                encoding="utf-8-sig",
                errors="replace",
            ).splitlines()
            for index, line in enumerate(lines):
                if not any(marker in line for marker in FAILURE_MARKERS):
                    continue
                following_lines = lines[index + 1 : index + 8]
                if not any("[ACTION]" in candidate for candidate in following_lines):
                    relative_path = batch_path.relative_to(PROJECT_ROOT)
                    missing_actions.append(f"{relative_path}:{index + 1}")

        self.assertEqual(
            missing_actions,
            [],
            "Failure messages without nearby [ACTION] guidance: "
            + ", ".join(missing_actions),
        )

    def test_saved_failure_logs_include_an_action(self):
        missing_log_actions: list[str] = []

        for batch_path in self.batch_paths():
            text = batch_path.read_text(encoding="utf-8-sig", errors="replace")
            lowered = text.lower()
            if "result_path" not in lowered:
                continue
            if not any(marker.lower() in lowered for marker in FAILURE_MARKERS):
                continue

            writes_action_to_result = any(
                ">>" in line
                and "result_path" in line.lower()
                and "[action]" in line.lower()
                for line in text.splitlines()
            )
            if not writes_action_to_result:
                missing_log_actions.append(str(batch_path.relative_to(PROJECT_ROOT)))

        self.assertEqual(
            missing_log_actions,
            [],
            "Saved failure logs without [ACTION] guidance: "
            + ", ".join(missing_log_actions),
        )


if __name__ == "__main__":
    unittest.main()
