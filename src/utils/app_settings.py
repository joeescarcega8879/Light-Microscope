from PyQt6.QtCore import QSettings

ORGANIZATION = "LightMicroscope"
APPLICATION = "LightMicroscope"


def settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def get_theme(default: str = "light") -> str:
    return str(settings().value("ui/theme", default))


def set_theme(name: str):
    settings().setValue("ui/theme", name)


def get_last_dir(key: str = "default") -> str:
    return str(settings().value(f"paths/{key}", ""))


def set_last_dir(path: str, key: str = "default"):
    settings().setValue(f"paths/{key}", path)
