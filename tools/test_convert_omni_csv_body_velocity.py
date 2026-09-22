import csv
import math
import tempfile
import unittest
from pathlib import Path

from tools.CONVERT_OMNI_CSV_BODY_VELOCITY import convert


class ConvertOmniCsvTests(unittest.TestCase):
    def test_preserves_source_columns_and_adds_body_velocity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "omni.csv"
            theta0 = math.radians(120.)
            theta90 = math.radians(210.)
            rows = [
                {"receive_monotonic_s": "10", "movement_x": math.sin(theta0),
                 "movement_y": math.cos(theta0), "yaw": "350", "note": "first"},
                {"receive_monotonic_s": "10.5", "movement_x": math.sin(theta90),
                 "movement_y": math.cos(theta90), "yaw": "80", "note": "wrapped"},
            ]
            with source.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            output = convert(source)
            with output.open(newline="", encoding="utf-8") as stream:
                converted = list(csv.DictReader(stream))
            self.assertEqual(converted[1]["note"], "wrapped")
            self.assertAlmostEqual(float(converted[1]["time_s"]), .5)
            self.assertAlmostEqual(float(converted[1]["yaw_relative_deg"]), 90.)
            self.assertAlmostEqual(float(converted[1]["vx_forward"]), 1.)
            self.assertAlmostEqual(float(converted[1]["vy_right"]), 0.)
            self.assertAlmostEqual(float(converted[1]["vy_left"]), 0.)


if __name__ == "__main__":
    unittest.main()
