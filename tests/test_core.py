from datetime import date, datetime, timezone

import numpy as np
from rasterio.transform import from_origin

from cdse import Scene, pick_pair, relative_orbit
from valleylink import analyze, change_masks


def feature(identifier, geometry, **tags):
    return {"type": "Feature", "properties": {"@osmId": identifier, **tags}, "geometry": geometry}


def point(x, y):
    return {"type": "Point", "coordinates": [x, y]}


def line(coords):
    return {"type": "LineString", "coordinates": coords}


def test_orbit_matching_and_change_detection():
    assert relative_orbit("S1C", 200, datetime(2026, 6, 23, tzinfo=timezone.utc)) != relative_orbit(
        "S1C", 200, datetime(2026, 6, 24, tzinfo=timezone.utc))
    scenes = [
        Scene("before", datetime(2026, 8, 20, tzinfo=timezone.utc), datetime(2026, 8, 20, 0, 1, tzinfo=timezone.utc), "S1A", 41, "ASCENDING"),
        Scene("wrong", datetime(2026, 8, 27, tzinfo=timezone.utc), datetime(2026, 8, 27, 0, 1, tzinfo=timezone.utc), "S1A", 42, "ASCENDING"),
        Scene("after", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 1, 0, 1, tzinfo=timezone.utc), "S1A", 41, "ASCENDING"),
    ]
    assert tuple(s.product_id for s in pick_pair(scenes, date(2026, 8, 26))) == ("before", "after")
    pre = np.ones((4, 3, 3), dtype=np.float32)
    post = pre.copy()
    post[0, 1, 1] = 0.1
    pre[2] = post[2] = 0
    strict, possible, valid = change_masks(pre, post)
    assert strict.sum() == possible.sum() == 1
    assert valid.all()


def test_blocked_crossing_restores_one_village():
    pre = np.ones((4, 5, 5), dtype=np.float32)
    post = pre.copy()
    pre[2] = post[2] = 0
    post[0, 2, 2] = 0.1
    transform = from_origin(85.0, 28.05, 0.01, 0.01)
    osm = {
        "roads": [feature("way/1", line([[85.005, 28.025], [85.015, 28.025],
                                          [85.035, 28.025], [85.045, 28.025]]), highway="residential")],
        "buildings": [feature("way/2", {"type": "Polygon", "coordinates": [[
            [85.021, 28.029], [85.022, 28.029], [85.022, 28.028], [85.021, 28.029]]]}, building="yes")],
        "places": [feature("node/1", point(85.005, 28.025), place="town", name="Town"),
                   feature("node/2", point(85.045, 28.025), place="village", name="Village")],
        "hospitals": [],
    }
    result, _ = analyze(pre, post, transform, osm)
    assert len(result["cutoff"]) == 1
    assert result["cutoff"][0]["name"] == "Village"
    assert result["scenarios"][0]["restored"] == 1
    assert len(result["buildings"]) == 1
    assert result["flood_km2"] > 0
