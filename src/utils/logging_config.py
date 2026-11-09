import logging
import logging.handlers
from pathlib import Path

APP_DIR = Path.home() / ".light_microscope"
LOG_DIR = APP_DIR / "logs"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure root logging to console + a rotating file. Returns the log file path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "light_microscope.log"

    root = logging.getLogger()
    root.setLevel(level)
    if any(getattr(h, "_lm_handler", False) for h in root.handlers):
        return log_file  # already configured

    formatter = logging.Formatter(_FORMAT)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.setFormatter(formatter)
        handler._lm_handler = True
        root.addHandler(handler)
    return log_file
