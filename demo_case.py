"""Load and capture the reproducible live-derived Syapru Besi reference case."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from valleylink import run


CASE_PATH = Path(__file__).with_name("syapru_besi_reference.npz")
CASE_BBOX = (85.318, 28.145, 85.353, 28.192)
CASE_DATE = date(2026, 8, 26)


def load_case(path=CASE_PATH):
    with np.load(path, allow_pickle=False) as case:
        metadata = json.loads(str(case["metadata"]))
        imagery = tuple(case[name] for name in metadata["image_names"])
    return metadata["result"], tuple(metadata["bbox"]), date.fromisoformat(metadata["flood_date"]), imagery, metadata["captured_at"]


def capture_case(path=CASE_PATH):
    result, _, imagery = run(CASE_BBOX, CASE_DATE)
    if not result["optical_dates"] or len(imagery) != 4:
        raise ValueError(f"Optical reference capture failed: {result['optical_error']}")
    image_names = ("radar_before", "radar_after", "optical_before", "optical_after")
    metadata = {"result": result, "bbox": CASE_BBOX, "flood_date": CASE_DATE.isoformat(),
                "captured_at": datetime.now(timezone.utc).isoformat(), "image_names": image_names}
    np.savez_compressed(path, metadata=json.dumps(metadata), **dict(zip(image_names, imagery)))
    return result


if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    result = capture_case()
    print(f"Captured {CASE_PATH.name}: {result['evidence_mode']}, "
          f"{result['optical_clear_fraction']:.0%} clear, "
          f"{result['flood_km2']} km² candidate change")
