import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Never let tests read or write the real user QSettings."""
    from PyQt6.QtCore import QSettings
    from src.utils import app_settings

    ini = str(tmp_path / "settings.ini")
    monkeypatch.setattr(app_settings, "settings", lambda: QSettings(ini, QSettings.Format.IniFormat))
