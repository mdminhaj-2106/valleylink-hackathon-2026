"""Offline contract checks for CDSE integration; no live credentials or API calls."""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import cdse


def product(satellite, start, absolute, direction="ASCENDING"):
    end = start + timedelta(seconds=25)
    identifier = (f"{satellite}_IW_GRDH_1SDV_{start:%Y%m%dT%H%M%S}_"
                  f"{end:%Y%m%dT%H%M%S}_{absolute:06d}_ABCDEF_1234")
    return {"id": identifier, "properties": {"sat:orbit_state": direction}}


class CdseTests(unittest.TestCase):
    def test_s1c_offset_transition_and_same_orbit_pair(self):
        old = datetime(2026, 6, 23, 10, tzinfo=timezone.utc)
        new = datetime(2026, 6, 25, 10, tzinfo=timezone.utc)
        self.assertEqual(cdse.relative_orbit("S1C", 172, old), 1)
        self.assertEqual(cdse.relative_orbit("S1C", 99, new), 1)
        pre = cdse.scene_from_item(product("S1C", datetime(2026, 8, 10, 10, tzinfo=timezone.utc), 274))
        post = cdse.scene_from_item(product("S1C", datetime(2026, 8, 22, 10, tzinfo=timezone.utc), 449))
        wrong = cdse.scene_from_item(product("S1A", datetime(2026, 8, 22, 8, tzinfo=timezone.utc), 249))
        self.assertEqual(cdse.pick_pair([pre, wrong, post], date(2026, 8, 20)), (pre, post))
        self.assertEqual(pre.relative_orbit, post.relative_orbit)

    def test_catalog_pagination_filters_and_product_validation(self):
        start = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        good = product("S1A", start, 248)
        bad = product("S1A", start, 248)
        bad["id"] = bad["id"].replace("1SDV", "1SDH")
        pages = [json.dumps({"features": [good, bad], "context": {"next": 100}}).encode(),
                 json.dumps({"features": [good], "context": {}}).encode()]
        with patch.object(cdse, "_post", side_effect=pages) as post:
            scenes = cdse.catalog_scenes([84.5, 27.5, 85, 28], date(2026, 8, 20), "token")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(post.call_args_list[0].args[1]["filter"],
                         "sar:instrument_mode='IW' and s1:polarization='DV'")
        self.assertEqual(post.call_args_list[1].args[1]["next"], 100)

    def test_process_request_pins_acquisition_and_terrain_options(self):
        scene = cdse.scene_from_item(product("S1A", datetime(2026, 8, 10, 10, tzinfo=timezone.utc), 248))
        payload = cdse.process_payload(scene, [84.5, 27.5, 85, 28])
        image = payload["input"]["data"][0]
        self.assertEqual(image["dataFilter"]["timeRange"],
                         {"from": "2026-08-10T10:00:00Z", "to": "2026-08-10T10:00:26Z"})
        self.assertEqual(image["processing"]["backCoeff"], "GAMMA0_TERRAIN")
        self.assertTrue(image["processing"]["orthorectify"])
        self.assertIn("shadowMask", payload["evalscript"])
        with self.assertRaisesRegex(ValueError, "Invalid WGS84"):
            cdse.process_payload(scene, [85, 28, 84, 27])


if __name__ == "__main__":
    unittest.main()
