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

    def test_catalog_pagination_and_product_validation(self):
        start = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        good = product("S1A", start, 248)
        good["id"] += "_COG.SAFE"
        bad = product("S1A", start, 248)
        bad["id"] = bad["id"].replace("1SDV", "1SDH")
        pages = [json.dumps({"features": [good, bad], "context": {"next": 100}}).encode(),
                 json.dumps({"features": [good], "context": {}}).encode()]
        with patch.object(cdse, "_post", side_effect=[ValueError("STAC unavailable"), *pages]) as post:
            scenes = cdse.catalog_scenes([84.5, 27.5, 85, 28], date(2026, 8, 20), "token")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(post.call_args_list[0].args[0], cdse.STAC)
        self.assertNotIn("filter", post.call_args_list[1].args[1])
        self.assertEqual(post.call_args_list[2].args[1]["next"], 100)

    def test_public_stac_catalog_avoids_slow_authenticated_catalog(self):
        start = datetime(2026, 8, 10, 10, tzinfo=timezone.utc)
        item = product("S1A", start, 248)
        item["id"] += "_COG"
        data = json.dumps({"features": [item], "links": []}).encode()
        with patch.object(cdse, "_post", return_value=data) as post:
            scenes = cdse.catalog_scenes([84.5, 27.5, 85, 28], date(2026, 8, 20), "token")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[0], cdse.STAC)

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

    def test_radar_request_has_bounded_wait(self):
        scene = cdse.scene_from_item(product("S1A", datetime(2026, 8, 10, 10, tzinfo=timezone.utc), 248))
        with patch.object(cdse, "_post", side_effect=ValueError("Copernicus API timed out")) as post:
            with self.assertRaisesRegex(ValueError, "timed out"):
                cdse.radar_scene(scene, [84.5, 27.5, 85, 28], "token", width=64)
        self.assertEqual(post.call_args.kwargs["timeout"], 45)

    def test_sentinel2_pair_returns_aligned_six_band_dates(self):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin

        with MemoryFile() as mem:
            with mem.open(driver="GTiff", width=64, height=64, count=6, dtype="float32",
                          crs="EPSG:4326", transform=from_origin(85, 28, 0.01, 0.01)) as raster:
                bands = np.ones((6, 64, 64), dtype="float32")
                bands[4] = 4
                raster.write(bands)
            tiff = mem.read()
        pre_catalog = {"features": [{"properties": {"datetime": "2026-08-12T05:00:00Z",
                                                 "eo:cloud_cover": 90}}]}
        post_catalog = {"features": [{"properties": {"datetime": "2026-08-27T05:00:00Z",
                                                  "eo:cloud_cover": 78}}]}
        responses = [json.dumps(pre_catalog).encode(), json.dumps(post_catalog).encode(),
                     tiff, tiff]
        with patch.object(cdse, "_post", side_effect=responses) as post:
            pre, after, transform, pre_time, after_time = cdse.sentinel2_pair(
                [85.32, 28.15, 85.35, 28.19], date(2026, 8, 26), "token", width=64)
        self.assertEqual(pre.shape, (6, 64, 64))
        self.assertTrue(np.array_equal(pre, after))
        self.assertEqual(pre_time.date(), date(2026, 8, 12))
        self.assertEqual(after_time.date(), date(2026, 8, 27))
        self.assertEqual(post.call_args_list[2].args[1]["input"]["data"][0]["dataFilter"]["timeRange"]["from"],
                         "2026-08-12T05:00:00Z")
        self.assertEqual(post.call_args_list[3].args[1]["evalscript"], cdse.S2_EVALSCRIPT)
        self.assertEqual(len(post.call_args_list), 4)  # two catalog + two Process calls

    def test_sentinel2_search_uses_aoi_clear_coverage_over_tile_cloud_score(self):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin

        def image(scl):
            with MemoryFile() as mem:
                with mem.open(driver="GTiff", width=64, height=64, count=6, dtype="float32",
                              crs="EPSG:4326", transform=from_origin(85, 28, 0.01, 0.01)) as raster:
                    bands = np.ones((6, 64, 64), dtype="float32")
                    bands[4] = scl
                    raster.write(bands)
                return mem.read()

        clear, cloudy = image(4), image(8)
        before = {"features": [{"properties": {"datetime": "2026-08-12T05:00:00Z", "eo:cloud_cover": 10}},
                               {"properties": {"datetime": "2026-08-24T05:00:00Z", "eo:cloud_cover": 80}}]}
        after = {"features": [{"properties": {"datetime": "2026-08-27T05:00:00Z", "eo:cloud_cover": 78}},
                              {"properties": {"datetime": "2026-08-30T05:00:00Z", "eo:cloud_cover": 5}}]}

        def respond(url, payload, **_kwargs):
            if url.endswith("/catalog/v1/search"):
                return json.dumps(before if payload["datetime"].startswith("2026-07") else after).encode()
            day = payload["input"]["data"][0]["dataFilter"]["timeRange"]["from"][:10]
            return clear if day in {"2026-08-24", "2026-08-27"} else cloudy

        with patch.object(cdse, "_post", side_effect=respond) as post:
            _pre, _post, _transform, pre_time, post_time = cdse.sentinel2_pair(
                [85.32, 28.15, 85.35, 28.19], date(2026, 8, 26), "token", width=64)
        self.assertEqual((pre_time.date(), post_time.date()), (date(2026, 8, 24), date(2026, 8, 27)))
        self.assertLessEqual(sum(call.args[0].endswith("/process/v1") for call in post.call_args_list), 4)

    def test_sentinel2_process_failure_keeps_api_cause_and_short_timeout(self):
        before = {"features": [{"properties": {"datetime": "2026-08-12T05:00:00Z", "eo:cloud_cover": 10}}]}
        after = {"features": [{"properties": {"datetime": "2026-08-27T05:00:00Z", "eo:cloud_cover": 78}}]}
        calls = []

        def respond(url, payload, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/catalog/v1/search"):
                return json.dumps(before if payload["datetime"].startswith("2026-07") else after).encode()
            raise ValueError("Copernicus API HTTP 429: rate limit exceeded")

        with patch.object(cdse, "_post", side_effect=respond):
            with self.assertRaisesRegex(ValueError, "2026-08-12.*HTTP 429"):
                cdse.sentinel2_pair([85.32, 28.15, 85.35, 28.19], date(2026, 8, 26), "token", width=64)
        self.assertEqual(sum(url.endswith("/process/v1") for url, _ in calls), 1)
        self.assertLessEqual(calls[-1][1]["timeout"], 20)

    def test_sentinel2_retries_one_transient_transport_failure(self):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin

        with MemoryFile() as mem:
            with mem.open(driver="GTiff", width=64, height=64, count=6, dtype="float32",
                          crs="EPSG:4326", transform=from_origin(85, 28, 0.01, 0.01)) as raster:
                bands = np.ones((6, 64, 64), dtype="float32")
                bands[4] = 4
                raster.write(bands)
            tiff = mem.read()
        catalog = lambda day: json.dumps({"features": [{"properties": {
            "datetime": f"2026-08-{day}T05:00:00Z", "eo:cloud_cover": 10}}]}).encode()
        responses = [catalog("12"), catalog("27"),
                     ValueError("Copernicus API unavailable: TLS handshake timed out"), tiff, tiff]
        with patch.object(cdse, "_post", side_effect=responses) as post:
            cdse.sentinel2_pair([85.32, 28.15, 85.35, 28.19], date(2026, 8, 26), "token", width=64)
        self.assertEqual(sum(call.args[0].endswith("/process/v1") for call in post.call_args_list), 3)

    def test_sentinel2_tries_another_date_after_transport_failure(self):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin

        with MemoryFile() as mem:
            with mem.open(driver="GTiff", width=64, height=64, count=6, dtype="float32",
                          crs="EPSG:4326", transform=from_origin(85, 28, 0.01, 0.01)) as raster:
                bands = np.ones((6, 64, 64), dtype="float32")
                bands[4] = 4
                raster.write(bands)
            tiff = mem.read()
        before = {"features": [{"properties": {"datetime": "2026-08-24T05:00:00Z", "eo:cloud_cover": 10}},
                               {"properties": {"datetime": "2026-08-12T05:00:00Z", "eo:cloud_cover": 20}}]}
        after = {"features": [{"properties": {"datetime": "2026-08-27T05:00:00Z", "eo:cloud_cover": 10}}]}
        attempts = []

        def respond(url, payload, **_kwargs):
            if url.endswith("/catalog/v1/search"):
                return json.dumps(before if payload["datetime"].startswith("2026-07") else after).encode()
            day = payload["input"]["data"][0]["dataFilter"]["timeRange"]["from"][:10]
            attempts.append(day)
            if day == "2026-08-24":
                raise ValueError("Copernicus API unavailable: TLS handshake timed out")
            return tiff

        with patch.object(cdse, "_post", side_effect=respond):
            _pre, _post, _transform, pre_time, post_time = cdse.sentinel2_pair(
                [85.32, 28.15, 85.35, 28.19], date(2026, 8, 26), "token", width=64)
        self.assertEqual((pre_time.date(), post_time.date()), (date(2026, 8, 12), date(2026, 8, 27)))
        self.assertEqual(attempts.count("2026-08-24"), 2)

    def test_socket_timeout_is_a_catchable_optical_error(self):
        with patch.object(cdse, "urlopen", side_effect=TimeoutError("The read operation timed out")):
            with self.assertRaisesRegex(ValueError, "timed out after 20s"):
                cdse._post("https://example.invalid", {}, timeout=20)

    def test_default_copernicus_request_fails_fast(self):
        with patch.object(cdse, "urlopen", side_effect=TimeoutError("The read operation timed out")) as open_url:
            with self.assertRaisesRegex(ValueError, "timed out after 15s"):
                cdse._post("https://example.invalid", {})
        self.assertEqual(open_url.call_args.kwargs["timeout"], 15)


if __name__ == "__main__":
    unittest.main()
