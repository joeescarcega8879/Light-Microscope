"""End-to-end checks of the Phase 2 app flow (login, roles, history, users)."""
import cv2
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

import main_application as m
from src.data import auth as auth_mod
from src.data.database import Database
from src.inspection.imageio import write_image
from src.inspection.reference import ReferenceStore
from test_inspection_engine import make_part, shift


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mainapp(app, tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "PBKDF2_ITERATIONS", 1000)
    monkeypatch.setattr(m, "Database", lambda: Database(tmp_path / "app.db"))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    ma = m.MainApplication()
    yield ma
    for name in ("login_view", "main_window", "part_inspection_view", "history_view"):
        v = getattr(ma, name, None)
        if v is not None:
            v.close()
    ma.db.close()


def _login(ma, user, pw, confirm=None):
    v = ma.login_view
    v.lineEditUsername.setText(user)
    v.lineEditPassword.setText(pw)
    if confirm is not None:
        v.lineEditConfirm.setText(confirm)
    v.btnLogin.click()


def test_first_run_creates_admin_then_normal_login(mainapp):
    ma = mainapp
    assert ma.login_view.is_setup_mode() and not ma.login_view.lineEditConfirm.isHidden()

    _login(ma, "boss", "long-password", "different!!")
    assert "do not match" in ma.login_view.lblError.text() and not ma.auth.has_users()
    assert ma.login_view.lineEditPassword.text() == ""          # cleared after a failure

    _login(ma, "boss", "long-password", "long-password")
    assert ma.auth.has_users() and ma.session.user.role == "admin"
    assert ma.main_window.isVisible() and not ma.login_view.isVisible()
    assert "boss (admin)" in ma.main_window.statusBar().currentMessage()
    actions = [r["action"] for r in ma.db.query("SELECT action FROM audit_log ORDER BY id")]
    assert actions[:2] == ["admin_created", "login"]


def test_login_errors_do_not_log_in(mainapp):
    ma = mainapp
    ma.auth.create_user("boss", "long-password", "admin")
    ma.login_presenter.view.set_setup_mode(False)
    _login(ma, "boss", "wrong-password")
    assert ma.login_view.lblError.text() == "Invalid username or password."
    assert ma.session.user is None
    ma.login_view.chkShowPassword.setChecked(True)
    assert ma.login_view.lineEditPassword.echoMode().name == "Normal"


def test_operator_is_locked_out_of_admin_features(mainapp):
    ma = mainapp
    ma.auth.create_user("boss", "long-password", "admin")
    ma.auth.create_user("oper", "long-password", "operator")
    ma.login_presenter.view.set_setup_mode(False)
    _login(ma, "oper", "long-password")
    mw = ma.main_window
    assert mw.btnInspect.isEnabled() and mw.btnHistory.isEnabled()
    assert not mw.btnAiStudio.isEnabled()

    ma.open_part_inspection_view()
    piv = ma.part_inspection_view
    assert not piv.btnNewRef.isEnabled() and not piv.btnSaveSettings.isEnabled()
    assert not piv.canvas.isEnabled() and not piv.spnThreshold.isEnabled()
    assert piv.btnRun.isEnabled()

    ma.open_history_view()
    hv = ma.history_view
    assert not hv.btnPdf.isEnabled() and not hv.btnExportCsv.isEnabled() and not hv.btnDeleteBatch.isEnabled()
    assert not hv.tabs.isTabVisible(hv.tabs.indexOf(hv._audit_tab))


def test_settings_dialog_shows_user_management_only_to_admin(mainapp):
    from PyQt6.QtWidgets import QPushButton
    from src.views.settings_view import SettingsView

    def button_texts(can_manage):
        dialog = SettingsView(["light", "dark"], "light", can_manage_users=can_manage)
        return [b.text() for b in dialog.findChildren(QPushButton)]

    assert "Manage users…" in button_texts(True)
    assert "Manage users…" not in button_texts(False)


def test_batch_run_is_recorded_in_history_and_audit(mainapp, tmp_path):
    ma = mainapp
    ma.auth.create_user("sup", "long-password", "supervisor")
    ma.login_presenter.view.set_setup_mode(False)
    _login(ma, "sup", "long-password")

    good = make_part()
    store = ReferenceStore(tmp_path / "refs")
    store.create("demo", [good])
    src = tmp_path / "in"
    src.mkdir()
    write_image(src / "ok.png", shift(good, 5, 3, 2))
    bad = good.copy()
    cv2.circle(bad, (150, 240), 14, (0, 0, 0), -1)
    write_image(src / "bad.png", bad)

    from src.presenters.part_inspection_presenter import PartInspectionPresenter
    from src.views.part_inspection_view import PartInspectionView
    view = PartInspectionView()
    pres = PartInspectionPresenter(view, store, ma.session, ma.history)
    assert view.btnNewRef.isEnabled()                               # supervisor may edit
    view.set_input_dir(str(src))
    view.set_output_dir(str(tmp_path / "out"))
    pres._run()
    import time
    end = time.time() + 15
    while time.time() < end and pres._worker is not None:
        QApplication.processEvents()
        time.sleep(0.01)

    batch = ma.history.list_batches()[0]
    assert (batch["reference"], batch["username"], batch["ok"], batch["ng"]) == ("demo", "sup", 1, 1)
    assert {r["file"]: r["verdict"] for r in ma.history.batch_items(batch["id"])} == {"ok.png": "OK", "bad.png": "NG"}
    actions = [r["action"] for r in ma.db.query("SELECT action FROM audit_log")]
    assert "batch_started" in actions and "batch_finished" in actions

    # history view reflects it, including the dashboard numbers
    from src.presenters.history_presenter import HistoryPresenter
    from src.views.history_view import HistoryView
    hv = HistoryView()
    hp = HistoryPresenter(hv, ma.history, ma.session)
    assert hv.tblBatches.rowCount() == 1 and hv.tblInspections.rowCount() == 2
    assert hv._kpis["inspected"].text() == "2" and hv._kpis["reject"].text() == "50.0%"
    hv.show_inspections_for_batch(batch["id"])
    hv.cmbVerdict.setCurrentText("NG")
    hp._refresh_inspections()
    assert hv.tblInspections.rowCount() == 1


def test_sign_out_returns_to_login_without_quitting(mainapp):
    ma = mainapp
    ma.auth.create_user("boss", "long-password", "admin")
    ma.login_presenter.view.set_setup_mode(False)
    _login(ma, "boss", "long-password")
    ma.open_history_view()
    ma.main_window.actionSignOut.trigger()
    assert ma.login_view.isVisible() and not ma.main_window.isVisible()
    assert ma.session.user is None and not ma.history_view.isVisible()
    assert not ma.login_view.is_setup_mode()
    assert "logout" in [r["action"] for r in ma.db.query("SELECT action FROM audit_log")]
