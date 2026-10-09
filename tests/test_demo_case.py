from datetime import date

from demo_case import CASE_BBOX, CASE_DATE, load_case


def test_bundled_case_has_real_optical_provenance_and_aligned_images():
    result, bbox, flood_date, imagery, captured_at = load_case()
    assert bbox == CASE_BBOX
    assert flood_date == CASE_DATE == date(2026, 8, 26)
    assert captured_at.startswith("2026-10-09")
    assert result["evidence_mode"] == "optical"
    assert result["optical_clear_fraction"] >= 0.8
    assert result["scenes"]["before"].startswith("S1")
    assert result["scenes"]["after"].startswith("S1")
    assert len(imagery) == 4
    assert all(image.shape[1:] == imagery[0].shape[1:] for image in imagery)
