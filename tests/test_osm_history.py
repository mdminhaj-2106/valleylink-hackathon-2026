import unittest
from datetime import date
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import LineString

from osm_history import FILTERS, osm_features, parse_features


def sample_parquet():
    table = pa.table({
        "osm_type": ["way", "way"],
        "osm_id": [42, 43],
        "tags": pa.array([[('highway', 'primary'), ('bridge', 'yes')], []],
                         type=pa.map_(pa.string(), pa.string())),
        "geom": [LineString([(85, 28), (85.1, 28)]).wkb, None],
    })
    buffer = BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


class HistoricalOSMTest(unittest.TestCase):
    def test_parses_documented_geoparquet_columns(self):
        features = parse_features(sample_parquet())
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["properties"],
                         {"@osmId": "way/42", "highway": "primary", "bridge": "yes"})
        self.assertEqual(features[0]["geometry"]["type"], "LineString")

    def test_all_requests_use_same_pre_event_snapshot(self):
        calls = []

        def fetch(body, key):
            calls.append((body, key))
            return sample_parquet()

        output = osm_features((84, 27, 86, 29), date(2026, 8, 15),
                              api_key="example-key", fetch=fetch)
        self.assertEqual(set(output), set(FILTERS))
        self.assertEqual(len(calls), len(FILTERS))
        for body, key in calls:
            self.assertEqual(body["time"], "2026-08-14T00:00:00Z")
            self.assertEqual(body["aoi"], [84, 27, 86, 29] if body["filter"] == FILTERS["buildings"]
                             else [83.8, 26.8, 86.2, 29.2])
            self.assertIs(body["clip"], False)
            self.assertEqual(key, "example-key")

    def test_context_destinations_do_not_expand_assessed_villages(self):
        def response(points):
            table = pa.table({
                "osm_type": ["node"] * len(points),
                "osm_id": list(range(len(points))),
                "tags": pa.array([[('place', tag)] for tag, _ in points],
                                 type=pa.map_(pa.string(), pa.string())),
                "geom": [location.wkb for _, location in points],
            })
            buffer = BytesIO()
            pq.write_table(table, buffer)
            return buffer.getvalue()

        from shapely.geometry import Point

        places = response([("town", Point(85.25, 28.05)),
                           ("village", Point(85.02, 28.02)),
                           ("village", Point(85.25, 28.05))])

        def fetch(body, _key):
            return places if body["filter"] == FILTERS["places"] else sample_parquet()

        output = osm_features((85, 28, 85.1, 28.1), date(2026, 8, 15),
                              api_key="key", fetch=fetch)
        self.assertEqual([f["properties"]["place"] for f in output["places"]],
                         ["town", "village"])

    def test_rejects_invalid_bbox(self):
        with self.assertRaises(ValueError):
            osm_features((86, 27, 84, 29), date(2026, 8, 15), api_key="key")

    def test_roads_limit_to_vehicle_capable_classes(self):
        road_filter = FILTERS["roads"]
        for road_class in ("primary", "residential", "service", "track"):
            self.assertIn(road_class, road_filter)
        for foot_class in ("footway", "path", "steps", "pedestrian"):
            self.assertNotIn(foot_class, road_filter)


if __name__ == "__main__":
    unittest.main()
