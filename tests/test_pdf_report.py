import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from src.inspection.imageio import write_image
from src.utils.pdf_report import build_report_html, generate_batch_report


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _batch(tmp_path, **kw):
    b = {"id": 7, "started_at": "2026-11-09 10:00:00", "reference": "Part <A>", "username": "oper",
         "folder": "/data", "output_dir": str(tmp_path), "total": 3, "ok": 1, "ng": 1, "errors": 1,
         "cancelled": 0}
    b.update(kw)
    return b


ITEMS = [
    {"file": "good.png", "verdict": "OK", "defects": 0, "defect_area_pct": 0.0, "reasons": "", "error": ""},
    {"file": "bad<script>.png", "verdict": "NG", "defects": 2, "defect_area_pct": 1.5,
     "reasons": "2 defect(s) found (allowed 0)", "error": ""},
    {"file": "broken.png", "verdict": "ERROR", "defects": 0, "defect_area_pct": 0.0, "reasons": "",
     "error": "could not read image"},
]


def test_html_escapes_untrusted_text_and_lists_only_problems(app, tmp_path):
    html, _ = build_report_html(_batch(tmp_path), ITEMS)
    assert "<script>" not in html and "bad&lt;script&gt;.png" in html
    assert "Part &lt;A&gt;" in html
    assert "good.png" not in html            # OK parts are summarised, not listed
    assert "50.0%" in html                   # 1 NG of 2 inspected; the error is not in the yield
    assert "good.png" in build_report_html(_batch(tmp_path), ITEMS, include_ok=True)[0]


def test_thumbnails_only_for_ng_with_existing_overlay(app, tmp_path):
    ng = tmp_path / "NG"
    ng.mkdir()
    write_image(ng / "bad<script>_diff.png", np.full((60, 80, 3), 127, np.uint8))
    html, images = build_report_html(_batch(tmp_path), ITEMS)
    assert list(images) == ["thumb0"] and "src='thumb0'" in html
    assert build_report_html(_batch(tmp_path, output_dir=None), ITEMS)[1] == {}


def test_pdf_file_is_written(app, tmp_path):
    ng = tmp_path / "NG"
    ng.mkdir()
    write_image(ng / "bad<script>_diff.png", np.full((60, 80, 3), 127, np.uint8))
    out = generate_batch_report(tmp_path / "r.pdf", _batch(tmp_path), ITEMS)
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1500


def test_empty_batch_report(app, tmp_path):
    b = _batch(tmp_path, total=0, ok=0, ng=0, errors=0)
    out = generate_batch_report(tmp_path / "e.pdf", b, [])
    assert out.read_bytes().startswith(b"%PDF")


def test_long_report_paginates_at_readable_scale(app, tmp_path):
    """Regression: QPdfWriter is 1200 dpi; a wrong layout scale squeezed everything onto one tiny page."""
    import re
    items = [{"file": f"part_{i:03d}.png", "verdict": "NG", "defects": 1, "defect_area_pct": 0.5,
              "reasons": "1 defect(s) found (allowed 0)", "error": ""} for i in range(150)]
    out = generate_batch_report(tmp_path / "long.pdf", _batch(tmp_path, total=150, ng=150, ok=0, errors=0), items)
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", out.read_bytes()))
    assert pages >= 3
