import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from streamlit.testing.v1 import AppTest


EMPTY_GEOMETRY = {"type": "GeometryCollection", "geometries": []}


class AppTests(unittest.TestCase):
    def test_failed_rerun_keeps_and_labels_previous_result(self):
        result = {
            "scenes": {"before": "PRE", "after": "POST", "relative_orbit": 85},
            "optical_dates": None, "optical_error": "clouds", "evidence_mode": "radar-only",
            "flood_km2": 1.25, "buildings": [], "affected_road_km": 0,
            "affected_bridge_ids": [],
            "cutoff": [{"id": "village/1", "name": "Village", "point": [85.325, 28.155]}],
            "access_available": True,
            "valid_fraction": 0.8, "optical_clear_fraction": None,
            "scenarios": [{"feature_id": "way/1", "restored": 1,
                           "edge": ((85.32, 28.15), (85.33, 28.16))}],
            "possible_geometry": EMPTY_GEOMETRY,
            "strict_geometry": {"type": "Polygon", "coordinates": [[[85.32, 28.15], [85.33, 28.15],
                                                                   [85.33, 28.16], [85.32, 28.15]]]},
            "affected_roads": [{"type": "Feature", "properties": {}, "geometry": {
                "type": "LineString", "coordinates": [[85.32, 28.15], [85.33, 28.16]]}}],
            "settlements": [{"id": "village/1", "name": "Village", "point": [85.325, 28.155]}],
        }
        image = np.ones((4, 2, 2), dtype="float32")
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30)
        with patch("valleylink.run", side_effect=[(result, None, (image, image)),
                                                   ValueError("Copernicus timed out"),
                                                   TypeError("run() got an unexpected keyword argument 'previous'")]) as run_analysis, \
             patch("streamlit.pydeck_chart") as map_chart:
            app.run()
            app.button[0].click().run()
            self.assertEqual(len(app.metric), 5)
            map_json = map_chart.call_args.args[0].to_json()
            for layer in ("GeoJsonLayer", "ScatterplotLayer", "PathLayer"):
                self.assertIn(layer, map_json)
            self.assertEqual(map_chart.call_args.kwargs["height"], 580)
            app.button[0].click().run()
            self.assertIs(run_analysis.call_args.kwargs["previous"][0], result)
            self.assertIs(run_analysis.call_args.kwargs["previous"][1][0], image)
            self.assertEqual(len(app.metric), 5)
            self.assertEqual(app.session_state["analysis"], result)
            self.assertTrue(any("previous successful analysis" in warning.value for warning in app.warning))
            self.assertIn("Copernicus timed out", app.error[0].value)
            fresh_run = Mock(return_value=(result, None, (image, image)))
            with patch("importlib.reload", return_value=SimpleNamespace(run=fresh_run)) as reload_module:
                app.button[0].click().run()
            reload_module.assert_called_once()
            self.assertIs(fresh_run.call_args.kwargs["previous"][0], result)
            self.assertEqual(len(app.error), 0)


if __name__ == "__main__":
    unittest.main()
