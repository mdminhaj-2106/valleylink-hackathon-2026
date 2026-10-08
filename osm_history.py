"""Pre-event OpenStreetMap snapshots from the ohsome API v2 GeoParquet endpoint."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pyarrow.parquet as parquet
from shapely.geometry import box, mapping, shape
from shapely.wkb import loads as load_wkb


URL = "https://api.heigit.org/ohsome-api/v2-rc/extraction/features.parquet"
# ponytail: fixed ~20 km coordinate buffer; use distance-aware expansion if sparse regions need wider searches.
CONTEXT_DEGREES = 0.2
FILTERS = {
    "roads": ("type:way and highway in (motorway, motorway_link, trunk, trunk_link, "
              "primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, "
              "unclassified, residential, living_street, service, track) and geometry:line"),
    "buildings": "building=* and building!=no and geometry:polygon",
    "places": "(place=village or place=hamlet or place=town or place=city) and (geometry:point or geometry:polygon)",
    "hospitals": "(amenity=hospital or healthcare=hospital) and (geometry:point or geometry:polygon)",
}


def parse_features(data):
    """Convert the documented ohsome v2 GeoParquet schema to GeoJSON features."""
    table = parquet.read_table(BytesIO(data), columns=["osm_type", "osm_id", "tags", "geom"])
    features = []
    for row in table.to_pylist():
        if row["geom"] is None:
            continue
        tags = dict(row["tags"] or {})
        features.append({
            "type": "Feature",
            "properties": {"@osmId": f"{row['osm_type']}/{row['osm_id']}", **tags},
            "geometry": mapping(load_wkb(row["geom"])),
        })
    return features


def fetch_parquet(body, api_key):
    import json

    request = Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": api_key,
        "Content-Type": "application/json",
        "User-Agent": "ValleyLink-hackathon/0.1",
    })
    try:
        with urlopen(request, timeout=240) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read(300).decode("utf-8", "replace")
        raise ValueError(f"ohsome returned HTTP {exc.code}: {detail}") from exc


def osm_features(bbox, flood_date: date, *, api_key=None, fetch=fetch_parquet):
    """Extract a UTC midnight snapshot one day before the flood date.

    This conservative cutoff excludes edits after an early local-time event.
    """
    api_key = api_key or os.getenv("OHSOME_API_KEY")
    if not api_key:
        raise ValueError("Set OHSOME_API_KEY for historical OpenStreetMap extraction.")
    if not isinstance(flood_date, date) or isinstance(flood_date, datetime):
        raise ValueError("flood_date must be a date.")
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid WGS84 bounding box.")
    context = [max(-180, west - CONTEXT_DEGREES), max(-90, south - CONTEXT_DEGREES),
               min(180, east + CONTEXT_DEGREES), min(90, north + CONTEXT_DEGREES)]
    timestamp = datetime.combine(flood_date - timedelta(days=1), time.min,
                                 tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    result = {name: parse_features(fetch({"aoi": list(bbox) if name == "buildings" else context,
                                          "time": timestamp, "filter": tag_filter,
                                          "clip": False}, api_key))
              for name, tag_filter in FILTERS.items()}
    selected = box(*bbox)
    result["places"] = [feature for feature in result["places"]
                        if feature["properties"].get("place") in ("town", "city")
                        or shape(feature["geometry"]).intersects(selected)]
    return result
