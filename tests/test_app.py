import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from streamlit.testing.v1 import AppTest


EMPTY_GEOMETRY = {"type": "GeometryCollection", "geometries": []}


class AppTests(unittest.TestCase):
    def test_failed_rerun_keeps_and_labels_previous_result(self):
        result = {
            "scenes": {"before": "PRE", "after": "POST", "relative_orbit": 85},
            "optical_dates": None, "optical_error": "clouds", "evidence_mode": "radar-only",
            "flood_km2": 1.25, "buildings": [], "affected_road_km": 0,
            "affected_bridge_ids": [], "cutoff": [], "access_available": True,
            "valid_fraction": 0.8, "optical_clear_fraction": None, "scenarios": [],
            "possible_geometry": EMPTY_GEOMETRY, "strict_geometry": EMPTY_GEOMETRY,
            "affected_roads": [], "settlements": [],
        }
        image = np.ones((4, 2, 2), dtype="float32")
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30)
        with patch("valleylink.run", side_effect=[(result, None, (image, image)),
                                                   ValueError("Copernicus timed out")]), \
             patch("streamlit.components.v1.html") as embed:
            app.run()
            app.button[0].click().run()
            self.assertEqual(len(app.metric), 5)
            self.assertIn("<script", embed.call_args.args[0])
            self.assertNotIn("<iframe", embed.call_args.args[0])
            app.button[0].click().run()
        self.assertEqual(len(app.metric), 5)
        self.assertEqual(app.session_state["analysis"], result)
        self.assertTrue(any("previous successful analysis" in warning.value for warning in app.warning))
        self.assertIn("Copernicus timed out", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
