"""Satellite change, infrastructure exposure, and road-access scenarios."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
from rasterio.features import shapes
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union

from cdse import catalog_scenes, pick_pair, radar_scene, token
from osm_history import osm_features

ATTRIBUTION = (
    "Contains modified Copernicus Sentinel data 2026.\n"
    "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus "
    "Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European "
    "Union and ESA; all rights reserved.\n© OpenStreetMap contributors."
)
def change_masks(pre, post, strict_db=3.0, possible_db=2.0):
    if pre.shape != post.shape or pre.shape[0] != 4:
        raise ValueError("Radar images must align and have VV, VH, shadow and data bands.")
    valid = (pre[3] > 0) & (post[3] > 0) & (pre[2] == 0) & (post[2] == 0)
    vv = 10 * np.log10(np.maximum(post[0], 1e-8) / np.maximum(pre[0], 1e-8))
    vh = 10 * np.log10(np.maximum(post[1], 1e-8) / np.maximum(pre[1], 1e-8))
    # Both darker open water and brighter rough debris are candidate change.
    possible = valid & ((vv <= -possible_db) | ((vv >= possible_db) & (vh >= possible_db)))
    strict = valid & ((vv <= -strict_db) | ((vv >= strict_db) & (vh >= strict_db)))
    return strict, possible, valid


def mask_geometry(mask, transform):
    polygons = [shape(geometry) for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=transform)
                if value == 1]
    return unary_union(polygons) if polygons else shape({"type": "GeometryCollection", "geometries": []})


def meters(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    return 6371000 * 2 * math.asin(math.sqrt(math.sin((lat2-lat1)/2)**2
           + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2))


def feature_id(feature):
    return str(feature.get("properties", {}).get("@osmId", feature.get("id", "unknown")))


def feature_point(feature):
    return shape(feature["geometry"]).representative_point()


def snap(point, nodes, max_m=1000):
    # ponytail: linear nearest-node scan; spatial index if AOIs exceed a valley.
    if not nodes:
        return None
    target = (point.x, point.y)
    node = min(nodes, key=lambda candidate: meters(candidate, target))
    return node if meters(node, target) <= max_m else None


def road_graph(roads, flood_geometry):
    graph = nx.Graph()
    affected_ids = set()
    bridge_ids = set()
    affected_length = 0.0
    for feature in roads:
        geometry = shape(feature["geometry"])
        lines = [geometry] if geometry.geom_type == "LineString" else list(getattr(geometry, "geoms", []))
        identifier = feature_id(feature)
        bridge = feature.get("properties", {}).get("bridge") not in (None, "no")
        for line in lines:
            if line.geom_type != "LineString":
                continue
            coords = list(line.coords)
            for a, b in zip(coords, coords[1:]):
                a, b = tuple(a[:2]), tuple(b[:2])
                if a == b:
                    continue
                segment = LineString([a, b])
                affected = not flood_geometry.is_empty and flood_geometry.intersects(segment)
                length = meters(a, b)
                existing = graph.get_edge_data(a, b)
                graph.add_edge(a, b, feature_id=(existing["feature_id"] if existing and existing["affected"]
                                                  else identifier),
                               affected=affected or bool(existing and existing["affected"]),
                               length_m=length, bridge=bridge or bool(existing and existing["bridge"]))
                if affected:
                    affected_ids.add(identifier)
                    if not existing or not existing["affected"]:
                        affected_length += length * (segment.intersection(flood_geometry).length / segment.length)
                    if bridge:
                        bridge_ids.add(identifier)
    return graph, affected_ids, bridge_ids, affected_length


def access_analysis(graph, places, hospitals, blocked_edges):
    open_graph = graph.copy()
    open_graph.remove_edges_from(blocked_edges)
    nodes = list(graph.nodes)
    destinations = [f for f in places if f.get("properties", {}).get("place") in ("town", "city")]
    destinations += hospitals
    sources = {node for feature in destinations if (node := snap(feature_point(feature), nodes)) is not None}
    if not sources:
        return [], []
    before = nx.multi_source_dijkstra_path_length(graph, sources, weight="length_m")
    after = nx.multi_source_dijkstra_path_length(open_graph, sources, weight="length_m")
    settlements = []
    cutoff = []
    for feature in places:
        if feature.get("properties", {}).get("place") not in ("village", "hamlet"):
            continue
        node = snap(feature_point(feature), nodes)
        if node is None or node not in before:
            continue
        record = {"id": feature_id(feature), "name": feature.get("properties", {}).get("name", "Unnamed"),
                  "point": [feature_point(feature).x, feature_point(feature).y], "node": node,
                  "before_m": round(before[node]), "after_m": round(after[node]) if node in after else None}
        settlements.append(record)
        if node not in after:
            cutoff.append(record)
    return settlements, cutoff


def crossing_scenarios(graph, places, hospitals, max_results=10):
    blocked = {(a, b) for a, b, attr in graph.edges(data=True) if attr["affected"]}
    _, baseline = access_analysis(graph, places, hospitals, blocked)
    open_graph = graph.copy()
    open_graph.remove_edges_from(blocked)
    components = {node: index for index, group in enumerate(nx.connected_components(open_graph)) for node in group}
    nodes = list(graph.nodes)
    destinations = [f for f in places if f.get("properties", {}).get("place") in ("town", "city")] + hospitals
    served = {components[node] for feature in destinations
              if (node := snap(feature_point(feature), nodes)) is not None}
    lost_by_component = {}
    for item in baseline:
        lost_by_component.setdefault(components[item["node"]], []).append(item["id"])
    ranked = []
    for edge in blocked:
        left, right = components[edge[0]], components[edge[1]]
        if left == right or (left in served) == (right in served):
            continue
        restored = lost_by_component.get(right if left in served else left, [])
        if restored:
            attr = graph.edges[edge]
            ranked.append({"edge": edge, "feature_id": attr["feature_id"],
                           "restored": len(restored), "settlement_ids": sorted(restored),
                           "bridge": attr["bridge"]})
    return sorted(ranked, key=lambda item: (-item["restored"], item["feature_id"]))[:max_results]


def analyze(pre, post, transform, osm, strict_db=3.0, possible_db=2.0):
    strict, possible, valid = change_masks(pre, post, strict_db, possible_db)
    strict_geom, possible_geom = mask_geometry(strict, transform), mask_geometry(possible, transform)
    graph, road_ids, bridge_ids, road_m = road_graph(osm["roads"], strict_geom)
    destinations = osm["hospitals"] + [f for f in osm["places"]
                                       if f.get("properties", {}).get("place") in ("town", "city")]
    nodes = list(graph.nodes)
    access_available = any(snap(feature_point(f), nodes) is not None for f in destinations)
    if access_available:
        blocked = {(a, b) for a, b, attr in graph.edges(data=True) if attr["affected"]}
        settlements, cutoff = access_analysis(graph, osm["places"], osm["hospitals"], blocked)
        scenarios = crossing_scenarios(graph, osm["places"], osm["hospitals"])
    else:
        settlements, cutoff, scenarios = [], [], []
    buildings = [f for f in osm["buildings"] if strict_geom.intersects(shape(f["geometry"]))]
    # WGS84 pixel area varies with latitude; sum each row's spherical cell area.
    lat_edges = transform.f + np.arange(strict.shape[0] + 1) * transform.e
    row_km2 = (6371.0**2 * abs(math.radians(transform.a))
               * abs(np.diff(np.sin(np.radians(lat_edges)))))
    flood_km2 = float(strict.sum(axis=1) @ row_km2)
    return {"strict_geometry": mapping(strict_geom), "possible_geometry": mapping(possible_geom),
            "valid_fraction": float(valid.mean()), "flood_km2": round(flood_km2, 2),
            "buildings": buildings,
            "affected_roads": [f for f in osm["roads"] if feature_id(f) in road_ids],
            "affected_road_ids": sorted(road_ids), "affected_bridge_ids": sorted(bridge_ids),
            "affected_road_km": round(road_m / 1000, 2), "settlements": settlements,
            "cutoff": cutoff, "access_available": access_available, "scenarios": scenarios}, graph


def run(bbox, flood_date):
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Enter a valid west, south, east, north bounding box.")
    if east - west > 0.5 or north - south > 0.5:
        raise ValueError("Keep the first prototype area within 0.5° by 0.5°.")
    auth = token()
    before_scene, after_scene = pick_pair(catalog_scenes(bbox, flood_date, auth), flood_date)
    pre, transform = radar_scene(before_scene, bbox, auth)
    post, post_transform = radar_scene(after_scene, bbox, auth)
    if not np.allclose(tuple(transform), tuple(post_transform)):
        raise ValueError("Before and after image grids do not align.")
    result, graph = analyze(pre, post, transform, osm_features(bbox, flood_date))
    result["scenes"] = {"before": before_scene.product_id, "after": after_scene.product_id,
                        "relative_orbit": before_scene.relative_orbit}
    return result, graph, (pre, post)
