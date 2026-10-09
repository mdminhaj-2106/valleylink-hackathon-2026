from datetime import date, datetime, timezone
from unittest.mock import patch

import numpy as np
import networkx as nx
from rasterio.transform import from_bounds, from_origin
from shapely.geometry import Polygon, shape

from cdse import Scene, pick_pair, relative_orbit
from valleylink import access_analysis, analyze, change_masks, optical_change, road_graph, run


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


def test_same_area_rerun_reuses_radar_images_when_optical_is_unavailable():
    bbox = (85.318, 28.145, 85.353, 28.192)
    image = np.ones((4, 2, 2), dtype="float32")
    scenes = {"before": "PRE", "after": "POST", "relative_orbit": 85}
    with patch("valleylink.token", return_value="token"), \
         patch("valleylink.catalog_scenes") as catalog, \
         patch("valleylink.radar_scene") as radar, \
         patch("valleylink.sentinel2_pair", side_effect=ValueError("optical timeout")), \
         patch("valleylink.osm_features", return_value={}), \
         patch("valleylink.analyze", return_value=({}, None)) as analyze_images:
        result, graph, imagery = run(bbox, date(2026, 8, 26),
                                    previous=({"scenes": scenes}, (image, image)))
    catalog.assert_not_called()
    radar.assert_not_called()
    assert analyze_images.call_args.args[2] == from_bounds(*bbox, 2, 2)
    assert result["scenes"] == scenes
    assert result["optical_error"] == "optical timeout"
    assert imagery[0] is image and imagery[1] is image


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


def test_optical_change_excludes_clouds_and_detects_vegetation_loss():
    pre = np.zeros((6, 2, 2), dtype=np.float32)
    post = np.zeros_like(pre)
    pre[1], pre[2] = 0.1, 0.5  # healthy vegetation: red, NIR
    post[1], post[2] = 0.3, 0.2  # new bare or disturbed surface
    pre[4] = post[4] = 4  # usable land pixels
    pre[5] = post[5] = 1
    post[4, 0, 1] = 9  # cloud, despite apparent index change
    change, valid = optical_change(pre, post)
    assert change.tolist() == [[True, False], [True, True]]
    assert not valid[0, 1]


def test_boundary_touch_does_not_close_road():
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    road = feature("way/1", line([[-1, 0], [0, 0], [0, -1]]), highway="primary")
    graph, road_ids, bridge_ids, length = road_graph([road], polygon)
    assert road_ids == bridge_ids == set()
    assert length == 0
    assert all(not attrs["affected"] for _, _, attrs in graph.edges(data=True))


def test_affected_road_map_uses_only_exposed_length():
    pre = np.ones((4, 3, 3), dtype=np.float32)
    post = pre.copy()
    pre[2] = post[2] = 0
    post[0, 1, 1] = 0.1
    osm = {"roads": [feature("way/7", line([[0, 1.5], [3, 1.5]]), highway="primary")],
           "buildings": [], "places": [], "hospitals": []}
    result, _ = analyze(pre, post, from_origin(0, 3, 1, 1), osm)
    assert result["affected_road_ids"] == ["way/7"]
    assert result["affected_roads"][0]["properties"]["@osmId"] == "way/7"
    assert shape(result["affected_roads"][0]["geometry"]).bounds == (1, 1.5, 2, 1.5)


def test_overlapping_osm_ways_preserve_blockage_and_count_length_once():
    roads = [feature("way/1", line([[0, 0], [2, 0]]), highway="primary"),
             feature("way/2", line([[2, 0], [0, 0]]), highway="primary", bridge="yes")]
    graph, roads_hit, bridges_hit, length = road_graph(roads, Polygon([(0.5, -1), (1.5, -1),
                                                                        (1.5, 1), (0.5, 1)]))
    assert roads_hit == {"way/1", "way/2"}
    assert bridges_hit == {"way/2"}
    assert graph.edges[(0, 0), (2, 0)]["affected"]
    assert graph.edges[(0, 0), (2, 0)]["bridge"]
    assert graph.edges[(0, 0), (2, 0)]["feature_id"] == "way/2"
    assert 100_000 < length < 120_000  # one degree, not twice


def test_alternative_destination_means_not_cut_off():
    graph = nx.Graph()
    graph.add_edge((0, 0), (1, 0), length_m=1)
    graph.add_edge((1, 0), (2, 0), length_m=5)
    places = [feature("town/1", point(0, 0), place="town"),
              feature("village/1", point(1, 0), place="village")]
    hospitals = [feature("hospital/1", point(2, 0), amenity="hospital")]
    settlements, cutoff = access_analysis(graph, places, hospitals, {((0, 0), (1, 0))})
    assert cutoff == []
    assert settlements[0]["before_m"] == 1
    assert settlements[0]["after_m"] == 5
