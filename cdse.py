"""Copernicus Data Space Sentinel-1 discovery and terrain-corrected radar retrieval.

The Catalog API chooses products; the Process API returns aligned VV/VH rasters.
Live calls require CDSE_CLIENT_ID and CDSE_CLIENT_SECRET. No damage-map input is used.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://sh.dataspace.copernicus.eu"
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PRODUCT = re.compile(
    r"^(S1[ABCD])_IW_GRDH_1SDV_(\d{8}T\d{6})_(\d{8}T\d{6})_(\d{6})_[0-9A-F]{6}_[0-9A-F]{4}$"
)
EVALSCRIPT = """//VERSION=3
function setup() {
  return {input: ["VV", "VH", "shadowMask", "dataMask"],
          output: {bands: 4, sampleType: "FLOAT32"}};
}
function evaluatePixel(s) { return [s.VV, s.VH, s.shadowMask, s.dataMask]; }
"""
S2_EVALSCRIPT = """//VERSION=3
function setup() {
  return {input: ["B03", "B04", "B08", "B11", "SCL", "dataMask"],
          output: {bands: 6, sampleType: "FLOAT32"}};
}
function evaluatePixel(s) {
  return [s.B03, s.B04, s.B08, s.B11, s.SCL, s.dataMask];
}
"""


@dataclass(frozen=True)
class Scene:
    product_id: str
    timestamp: datetime
    end: datetime
    satellite: str
    relative_orbit: int
    orbit_state: str


def _post(url, payload, *, bearer=None, form=False, timeout=60):
    headers = {"User-Agent": "ValleyLink/0.1",
               "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    data = urlencode(payload).encode() if form else json.dumps(payload).encode()
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read(300).decode("utf-8", "replace")
        raise ValueError(f"Copernicus API HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"Copernicus API unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ValueError(f"Copernicus API timed out after {timeout}s: {exc}") from exc


def token():
    client_id, client_secret = os.getenv("CDSE_CLIENT_ID"), os.getenv("CDSE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET (Sentinel Hub OAuth client).")
    data = json.loads(_post(TOKEN_URL, {"grant_type": "client_credentials",
                                        "client_id": client_id, "client_secret": client_secret}, form=True))
    if not data.get("access_token"):
        raise ValueError("Copernicus token response has no access_token.")
    return data["access_token"]


def relative_orbit(satellite, absolute, timestamp):
    """ESA SentiWiki offsets, including S1C's 24 June 2026 orbit change."""
    offsets = {"S1A": 73, "S1B": 27, "S1D": 42}
    if satellite == "S1C":
        offset = 172 if timestamp.date() < date(2026, 6, 24) else 99
    else:
        offset = offsets[satellite]
    return (absolute - offset) % 175 + 1


def scene_from_item(item):
    properties = item.get("properties", {})
    raw_id = (properties.get("s1:product_identifier") or properties.get("title")
              or item.get("id") or "").removesuffix(".SAFE").removesuffix("_COG")
    match = PRODUCT.fullmatch(raw_id)
    if not match:
        raise ValueError(f"Not a Sentinel-1 IW GRDH dual-VV/VH product: {raw_id}")
    satellite, start, end, absolute = match.groups()
    begin = datetime.strptime(start, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    finish = datetime.strptime(end, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    direction = str(properties.get("sat:orbit_state", "")).upper()
    if direction not in {"ASCENDING", "DESCENDING"} or finish <= begin:
        raise ValueError(f"Invalid orbit direction or acquisition interval: {raw_id}")
    return Scene(raw_id, begin, finish, satellite,
                 relative_orbit(satellite, int(absolute), begin), direction)


def _validate_bbox(bbox):
    if len(bbox) != 4 or not all(math.isfinite(x) for x in bbox):
        raise ValueError("AOI needs four finite WGS84 coordinates: west, south, east, north.")
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid WGS84 AOI bounds; antimeridian-spanning AOIs are unsupported.")


def catalog_scenes(bbox, flood_date, auth, *, window_days=30):
    _validate_bbox(bbox)
    if not isinstance(flood_date, date) or not 1 <= window_days <= 60:
        raise ValueError("Use a date and a search window of 1–60 days.")
    start = datetime.combine(flood_date - timedelta(days=window_days), datetime.min.time(), timezone.utc)
    end = datetime.combine(flood_date + timedelta(days=window_days + 1), datetime.min.time(), timezone.utc)
    payload = {"bbox": list(bbox), "datetime": f"{start.isoformat()}/{end.isoformat()}",
               "collections": ["sentinel-1-grd"], "limit": 100}
    scenes = {}
    for _ in range(50):  # ponytail: cap pages to avoid unbounded catalog traffic; tile by date for huge AOIs.
        result = json.loads(_post(f"{BASE}/catalog/v1/search", payload, bearer=auth))
        for item in result.get("features", []):
            try:
                scene = scene_from_item(item)
                scenes[scene.product_id] = scene
            except ValueError:
                continue
        next_token = result.get("context", {}).get("next")
        if next_token is None:
            return sorted(scenes.values(), key=lambda scene: scene.timestamp)
        payload["next"] = next_token
    raise ValueError("Catalog returned over 50 pages; choose a smaller area or date window.")


def pick_pair(scenes, flood_date, *, max_gap_days=30):
    boundary = datetime.combine(flood_date, datetime.min.time(), timezone.utc)
    before = [s for s in scenes if s.end < boundary]
    after = [s for s in scenes if s.timestamp >= boundary]
    candidates = [(pre, post) for pre in before for post in after
                  if pre.satellite == post.satellite
                  and pre.relative_orbit == post.relative_orbit
                  and pre.orbit_state == post.orbit_state
                  and post.timestamp - pre.timestamp <= timedelta(days=max_gap_days)]
    if not candidates:
        raise ValueError("No pre/post Sentinel-1 IW dual-VV/VH pair on the same satellite, relative orbit and direction.")
    return min(candidates, key=lambda pair: (pair[1].timestamp - pair[0].timestamp,
                                              pair[1].timestamp - boundary))


def process_payload(scene, bbox, *, width=512):
    _validate_bbox(bbox)
    if not 64 <= width <= 2500:
        raise ValueError("Raster width must be 64–2500 pixels.")
    west, south, east, north = bbox
    height = round(width * (north - south) / (east - west)
                   * math.cos(math.radians((south + north) / 2)))
    height = max(64, min(height, 2500))
    # Start at the product's first second, end just beyond its final second.
    # Process API can mosaic adjacent slices from the same pass over a larger AOI.
    timerange = {"from": scene.timestamp.isoformat().replace("+00:00", "Z"),
                 "to": (scene.end + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")}
    return {"input": {"bounds": {"bbox": list(bbox)},
                      "data": [{"type": "sentinel-1-grd",
                                "dataFilter": {"timeRange": timerange, "acquisitionMode": "IW",
                                               "polarization": "DV", "orbitDirection": scene.orbit_state},
                                "processing": {"orthorectify": True, "backCoeff": "GAMMA0_TERRAIN",
                                               "demInstance": "COPERNICUS_30"}}]},
            "output": {"width": width, "height": height,
                       "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
            "evalscript": EVALSCRIPT}


def radar_scene(scene, bbox, auth, *, width=512):
    import numpy as np
    from rasterio.io import MemoryFile

    data = _post(f"{BASE}/process/v1", process_payload(scene, bbox, width=width),
                 bearer=auth, timeout=45)
    try:
        with MemoryFile(data) as mem, mem.open() as raster:
            bands, transform = raster.read(), raster.transform
    except Exception as exc:
        raise ValueError("Copernicus Process API did not return a readable GeoTIFF.") from exc
    if bands.shape[0] != 4 or not np.any(bands[3] > 0):
        raise ValueError("Radar response has no usable four-band VV/VH/shadow/data coverage.")
    return bands, transform


def sentinel2_pair(bbox, flood_date, auth, *, pre_date=None, post_date=None, width=512):
    """Return aligned (pre, post, transform, pre_UTC, post_UTC) optical rasters.

    Six FLOAT32 bands: B03, B04, B08, B11 reflectance, SCL class, dataMask.
    Searches 30 days before and 14 days after the flood; optional dates pin a day.
    """
    import numpy as np
    from rasterio.io import MemoryFile

    _validate_bbox(bbox)
    if not 64 <= width <= 2500:
        raise ValueError("Raster width must be 64–2500 pixels.")
    if (pre_date is not None and pre_date >= flood_date) or (post_date is not None and post_date <= flood_date):
        raise ValueError("Optical dates must bracket the flood date.")
    deadline = time.monotonic() + 60

    west, south, east, north = bbox
    height = max(64, min(2500, round(width * (north - south) / (east - west)
                                      * math.cos(math.radians((south + north) / 2)))))

    def candidates(first_day, last_day):
        begin = datetime.combine(first_day, datetime.min.time(), timezone.utc)
        finish = datetime.combine(last_day + timedelta(days=1), datetime.min.time(), timezone.utc)
        query = {"bbox": list(bbox), "datetime": f"{begin.isoformat()}/{finish.isoformat()}",
                 "collections": ["sentinel-2-l2a"], "limit": 100}
        best_by_day = {}
        for _ in range(10):
            catalog = json.loads(_post(f"{BASE}/catalog/v1/search", query, bearer=auth, timeout=15))
            for item in catalog.get("features", []):
                properties = item.get("properties", {})
                try:
                    timestamp = datetime.fromisoformat(properties["datetime"].replace("Z", "+00:00"))
                    if timestamp.tzinfo is None:
                        continue
                    timestamp = timestamp.astimezone(timezone.utc)
                    cloud_value = properties.get("eo:cloud_cover")
                    cloud = float(cloud_value) if cloud_value is not None else 100.0
                except (KeyError, ValueError, TypeError):
                    continue
                if first_day <= timestamp.date() <= last_day:
                    current = best_by_day.get(timestamp.date())
                    if current is None or cloud < current[0]:
                        best_by_day[timestamp.date()] = (cloud, timestamp)
            next_token = catalog.get("context", {}).get("next")
            if next_token is None:
                break
            query["next"] = next_token
        else:
            raise ValueError("Optical catalog returned too many pages; choose a smaller area.")
        # shortcut: two dates per side keep a live run bounded; widen for batch evaluation.
        selected = sorted(best_by_day.values(), key=lambda entry: (entry[0], -entry[1].timestamp()))[:2]
        return [timestamp for _, timestamp in selected]

    attempted = set()

    def fetch(timestamp):
        attempted.add(timestamp)
        # A narrow interval selects the cataloged overpass, including adjacent tiles.
        timerange = {"from": timestamp.isoformat().replace("+00:00", "Z"),
                     "to": (timestamp + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}
        payload = {"input": {"bounds": {"bbox": list(bbox)},
                             "data": [{"type": "sentinel-2-l2a", "dataFilter": {"timeRange": timerange}}]},
                   "output": {"width": width, "height": height,
                              "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
                   "evalscript": S2_EVALSCRIPT}
        remaining = deadline - time.monotonic()
        if remaining < 1:
            raise ValueError("Sentinel-2 search exceeded its 60-second time budget.")
        data = _post(f"{BASE}/process/v1", payload, bearer=auth, timeout=min(20, remaining))
        try:
            with MemoryFile(data) as mem, mem.open() as raster:
                bands, transform = raster.read(), raster.transform
        except Exception as exc:
            raise ValueError("Copernicus Process API did not return a readable Sentinel-2 GeoTIFF.") from exc
        if bands.shape[0] != 6 or not np.any(bands[5] > 0):
            raise ValueError("Sentinel-2 response has no usable six-band coverage.")
        return bands, transform, timestamp

    pre_times = candidates(pre_date or flood_date - timedelta(days=30),
                           pre_date or flood_date - timedelta(days=1))
    post_times = candidates(post_date or flood_date + timedelta(days=1),
                            post_date or flood_date + timedelta(days=14))
    if not pre_times or not post_times:
        raise ValueError("No Sentinel-2 L2A acquisitions in the requested before/after windows.")
    errors = []

    def usable(times):
        for timestamp in times:
            try:
                return fetch(timestamp)
            except ValueError as exc:
                if str(exc).startswith("Copernicus API") or "time budget" in str(exc):
                    raise ValueError(f"Sentinel-2 {timestamp.date()}: {exc}") from exc
                errors.append(f"{timestamp.date()}: {exc}")
        raise ValueError("No usable Sentinel-2 raster: " + "; ".join(errors))

    pre_images, post_images = [usable(pre_times)], [usable(post_times)]

    def rank():
        pairs = []
        for pre, transform, pre_time in pre_images:
            for post, post_transform, post_time in post_images:
                if pre.shape != post.shape or transform != post_transform:
                    continue
                clear = (np.isin(pre[4], [4, 5, 6]) & np.isin(post[4], [2, 4, 5, 6])
                         & (pre[5] > 0) & (post[5] > 0))
                pairs.append((float(clear.mean()), pre_time, post_time, pre, post, transform))
        if not pairs:
            raise ValueError("Sentinel-2 before and after images do not align.")
        return max(pairs, key=lambda pair: (pair[0], -(pair[2] - pair[1]).total_seconds(), pair[2]))

    best = rank()
    if best[0] < 0.5:
        for times, images in ((pre_times, pre_images), (post_times, post_images)):
            for timestamp in times:
                if timestamp not in attempted:
                    try:
                        images.append(fetch(timestamp))
                    except ValueError as exc:
                        if str(exc).startswith("Copernicus API") or "time budget" in str(exc):
                            raise ValueError(f"Sentinel-2 {timestamp.date()}: {exc}") from exc
                        errors.append(f"{timestamp.date()}: {exc}")
        best = rank()
    coverage, pre_time, post_time, pre, post, transform = best
    if coverage < 0.2:
        detail = f" ({'; '.join(errors)})" if errors else ""
        raise ValueError(f"Best Sentinel-2 pair has only {coverage:.0%} jointly clear coverage{detail}.")
    return pre, post, transform, pre_time, post_time
