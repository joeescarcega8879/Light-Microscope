from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


def open_folder(path: str) -> bool:
    """Open a folder in the OS file manager (Linux, Windows, macOS)."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def default_torch_device() -> str:
    """'cuda' if available, 'mps' on Apple Silicon, otherwise 'cpu'."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"
