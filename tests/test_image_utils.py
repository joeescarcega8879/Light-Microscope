import numpy as np
import pytest

from src.utils.image_utils import ImageUtils


def _blank(h=60, w=80):
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_diff_identical_images_has_no_changes():
    img = _blank()
    diff, mask, heatmap = ImageUtils.compute_diff(img, img.copy(), threshold=5)
    assert diff.max() == 0
    assert mask.max() == 0
    assert heatmap.shape == img.shape


def test_diff_detects_changed_region():
    a, b = _blank(), _blank()
    b[10:20, 10:20] = 255
    diff, mask, _ = ImageUtils.compute_diff(a, b, threshold=10)
    assert int((mask > 0).sum()) == 100
    assert diff[15, 15] == 255


def test_diff_threshold_filters_small_changes():
    a, b = _blank(), _blank()
    b[:] = 5
    _, mask, _ = ImageUtils.compute_diff(a, b, threshold=10)
    assert mask.max() == 0


def test_diff_shape_mismatch_raises():
    with pytest.raises(ValueError):
        ImageUtils.compute_diff(_blank(60, 80), _blank(40, 40))


def test_draw_contours_does_not_modify_input():
    base = _blank()
    mask = np.zeros((60, 80), dtype=np.uint8)
    mask[10:30, 10:30] = 255
    out = ImageUtils.draw_contours(base, mask)
    assert base.max() == 0
    assert out.max() > 0


def test_detect_contours_min_area_filters_small_blobs():
    img = _blank(100, 100)
    img[10:40, 10:40] = 255   # 900 px blob
    img[60:63, 60:63] = 255   # 9 px blob
    _, contours_all, _ = ImageUtils.detect_contours(img, threshold=127, min_area=0)
    _, contours_big, _ = ImageUtils.detect_contours(img, threshold=127, min_area=100)
    assert len(contours_all) == 2
    assert len(contours_big) == 1
