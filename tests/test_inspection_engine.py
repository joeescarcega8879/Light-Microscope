import cv2
import numpy as np
import pytest

from src.inspection.engine import (
    InspectionParams, Roi, align_image, build_roi_mask,
    inspect_against_references, inspect_image,
)


def make_part(h=360, w=480, seed=1):
    """Textured synthetic 'part' on a plain background, rich enough for feature matching."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 200, np.uint8)
    cv2.rectangle(img, (90, 70), (390, 290), (60, 60, 60), -1)
    cv2.circle(img, (240, 180), 55, (180, 180, 180), -1)
    for _ in range(60):
        x, y = int(rng.integers(100, 380)), int(rng.integers(80, 280))
        cv2.circle(img, (x, y), int(rng.integers(2, 6)), tuple(int(v) for v in rng.integers(0, 255, 3)), -1)
    cv2.line(img, (100, 80), (380, 280), (20, 20, 220), 2)
    return img


def shift(img, dx, dy, angle=0.0):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def test_identical_image_is_ok():
    ref = make_part()
    res = inspect_image(ref, ref.copy())
    assert res.ok and res.verdict == "OK"
    assert res.defects == []


def test_translated_and_rotated_good_part_is_ok_with_alignment():
    ref = make_part()
    moved = shift(ref, 14, -9, angle=4.0)
    assert not inspect_image(ref, moved, InspectionParams(align=False)).ok   # sanity: misaligned fails
    res = inspect_image(ref, moved)
    assert res.align.success and res.align.method in {"orb", "ecc"}
    assert res.ok, res.reasons


def test_defect_is_detected_and_located_after_alignment():
    ref = make_part()
    bad = ref.copy()
    cv2.circle(bad, (150, 240), 12, (0, 0, 0), -1)
    moved = shift(bad, 10, 6, angle=-3.0)
    res = inspect_image(ref, moved)
    assert not res.ok
    assert len(res.defects) >= 1
    d = res.defects[0]
    assert abs((d.x + d.w / 2) - 150) < 15 and abs((d.y + d.h / 2) - 240) < 15


def test_different_size_image_does_not_raise():
    ref = make_part()
    small = cv2.resize(ref, (240, 180))
    res = inspect_image(ref, small)
    assert res.diff.shape == ref.shape[:2]


def test_lighting_change_does_not_cause_ng():
    ref = make_part()
    darker = cv2.convertScaleAbs(ref, alpha=0.8, beta=-10)
    assert inspect_image(ref, darker, InspectionParams(normalize_lighting=True)).ok


def test_noise_is_tolerated():
    ref = make_part()
    rng = np.random.default_rng(0)
    noisy = np.clip(ref.astype(np.int16) + rng.normal(0, 6, ref.shape), 0, 255).astype(np.uint8)
    assert inspect_image(ref, noisy).ok


def test_min_defect_area_and_max_defects_control_verdict():
    ref = make_part()
    bad = ref.copy()
    cv2.circle(bad, (150, 240), 6, (0, 0, 0), -1)
    assert not inspect_image(ref, bad, InspectionParams(align=False)).ok
    assert inspect_image(ref, bad, InspectionParams(align=False, min_defect_area=5000)).ok
    assert inspect_image(ref, bad, InspectionParams(align=False, max_defects=5)).ok


def test_ignore_roi_hides_defect_and_include_roi_restricts():
    ref = make_part()
    bad = ref.copy()
    cv2.circle(bad, (150, 240), 12, (0, 0, 0), -1)
    p = InspectionParams(align=False)
    ignore = [Roi(100 / 480, 200 / 360, 100 / 480, 80 / 360, "ignore")]
    assert inspect_image(ref, bad, p, ignore).ok
    include_elsewhere = [Roi(0.7, 0.0, 0.3, 0.3, "include")]
    assert inspect_image(ref, bad, p, include_elsewhere).ok
    include_here = [Roi(0.2, 0.5, 0.3, 0.4, "include")]
    assert not inspect_image(ref, bad, p, include_here).ok


def test_roi_mask_semantics():
    shape = (100, 100, 3)
    assert build_roi_mask(shape, None).min() == 255
    m = build_roi_mask(shape, [Roi(0, 0, 0.5, 0.5, "include")])
    assert m[10, 10] == 255 and m[90, 90] == 0
    m = build_roi_mask(shape, [Roi(0, 0, 0.5, 0.5, "ignore")])
    assert m[10, 10] == 0 and m[90, 90] == 255


def test_multiple_references_pass_if_any_matches():
    ref_a = make_part(seed=1)
    ref_b = ref_a.copy()
    cv2.circle(ref_b, (300, 120), 15, (0, 0, 255), -1)   # a legitimate variant
    part = ref_b.copy()
    p = InspectionParams(align=False)
    assert not inspect_image(ref_a, part, p).ok
    res = inspect_against_references([ref_a, ref_b], part, p)
    assert res.ok and res.reference_index == 1


def test_align_handles_grayscale_and_bgra_inputs():
    ref = make_part()
    gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    bgra = cv2.cvtColor(ref, cv2.COLOR_BGR2BGRA)
    assert inspect_image(ref, gray).diff.shape == ref.shape[:2]
    assert inspect_image(bgra, ref).ok


def test_params_roundtrip_ignores_unknown_keys():
    p = InspectionParams(threshold=40, max_defects=2)
    d = p.to_dict()
    d["something_new"] = 1
    assert InspectionParams.from_dict(d) == p


def test_no_references_raises():
    with pytest.raises(ValueError):
        inspect_against_references([], make_part())
