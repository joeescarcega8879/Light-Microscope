import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from src.inspection.engine import Roi
from src.inspection.imageio import write_image
from src.inspection.reference import ReferenceStore
from src.presenters.part_inspection_presenter import PartInspectionPresenter
from src.views.part_inspection_view import PartInspectionView
from src.views.roi_canvas import RoiCanvas
from test_inspection_engine import make_part, shift


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _pump(app, cond, timeout=10.0):
    import time
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    return cond()


def test_roi_canvas_draw_and_remove(app):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent
    c = RoiCanvas()
    c.resize(400, 300)
    c.set_image(make_part(300, 400))
    c.set_mode("ignore")

    def mouse(kind, pos, button=Qt.MouseButton.LeftButton):
        e = QMouseEvent(kind, QPointF(*pos), QPointF(*pos), button, button, Qt.KeyboardModifier.NoModifier)
        {QEvent.Type.MouseButtonPress: c.mousePressEvent, QEvent.Type.MouseMove: c.mouseMoveEvent,
         QEvent.Type.MouseButtonRelease: c.mouseReleaseEvent}[kind](e)

    mouse(QEvent.Type.MouseButtonPress, (100, 100))
    mouse(QEvent.Type.MouseMove, (200, 180))
    mouse(QEvent.Type.MouseButtonRelease, (200, 180))
    rois = c.rois()
    assert len(rois) == 1 and rois[0].mode == "ignore"
    # canvas 400x300 shows a 400x300 image 1:1 -> drag (100,100)-(200,180)
    r = rois[0]
    assert (r.x, r.y, r.w, r.h) == pytest.approx((100 / 400, 100 / 300, 100 / 400, 80 / 300))

    mouse(QEvent.Type.MouseButtonPress, (150, 140), Qt.MouseButton.RightButton)
    assert c.rois() == []


def test_full_flow_create_reference_run_batch_and_preview(app, tmp_path, monkeypatch):
    good = make_part()
    gp = tmp_path / "good.png"
    write_image(gp, good)
    src = tmp_path / "in"
    src.mkdir()
    write_image(src / "ok.png", shift(good, 6, 3, 2))
    bad = good.copy()
    cv2.circle(bad, (150, 240), 14, (0, 0, 0), -1)
    write_image(src / "bad.png", shift(bad, 5, -4, -2))

    store = ReferenceStore(tmp_path / "refs")
    store.create("demo", [good])
    view = PartInspectionView()
    pres = PartInspectionPresenter(view, store)
    assert view.cmbReference.currentText() == "demo"
    assert pres._ref is not None and len(pres._ref_images) == 1

    view.set_input_dir(str(src))
    view.set_output_dir(str(tmp_path / "out"))
    pres._run()
    assert _pump(app, lambda: pres._worker is None and len(pres._items) == 2)
    assert "1 OK" in view.lblSummary.text() and "1 NG" in view.lblSummary.text()
    assert view.table.rowCount() == 2
    assert view.btnOpenResults.isEnabled()

    view.cmbFilter.setCurrentText("NG")
    assert view.table.rowCount() == 1 and view.table.item(0, 0).text() == "bad.png"
    view.table.selectRow(0)
    assert view.lblPreview.pixmap() is not None and not view.lblPreview.pixmap().isNull()
    assert "NG" in view.lblReasons.text()
    assert (tmp_path / "out" / "NG" / "bad_diff.png").exists()


def test_settings_roundtrip_through_view(app, tmp_path):
    store = ReferenceStore(tmp_path / "refs")
    store.create("p", [make_part()])
    view = PartInspectionView()
    pres = PartInspectionPresenter(view, store)
    view.spnThreshold.setValue(60)
    view.spnMaxDefects.setValue(3)
    view.set_rois([Roi(0.1, 0.1, 0.3, 0.3, "ignore")])
    pres._save_settings()
    loaded = store.load("p")
    assert loaded.params.threshold == 60 and loaded.params.max_defects == 3
    assert loaded.rois[0].mode == "ignore"
