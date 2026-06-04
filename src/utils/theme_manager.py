import os
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self, css_dir: str, parent=None):
        super().__init__(parent)
        self._css_dir = css_dir
        self._themes: dict[str, str] = {}
        self._current_theme: str | None = None
        self._scan_themes()

    def _scan_themes(self):
        self._themes.clear()
        if not os.path.isdir(self._css_dir):
            return
        for filename in sorted(os.listdir(self._css_dir)):
            if filename.endswith(".qss"):
                name = filename[:-4]
                path = os.path.join(self._css_dir, filename)
                try:
                    with open(path) as f:
                        self._themes[name] = f.read()
                except OSError:
                    pass

    def theme_names(self) -> list[str]:
        return list(self._themes.keys())

    def current_theme(self) -> str | None:
        return self._current_theme

    def apply_theme(self, name: str) -> bool:
        qss = self._themes.get(name)
        if qss is None:
            return False
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        self._current_theme = name
        self.theme_changed.emit(name)
        return True
