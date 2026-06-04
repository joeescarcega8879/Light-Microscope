from ..utils.theme_manager import ThemeManager


class SettingsPresenter:
    def __init__(self, view, theme_manager: ThemeManager):
        self.view = view
        self._theme_manager = theme_manager
        self._connect_signals()

    def _connect_signals(self):
        self.view.theme_selected.connect(self._on_theme_selected)

    def _on_theme_selected(self, theme_name: str):
        self._theme_manager.apply_theme(theme_name)
