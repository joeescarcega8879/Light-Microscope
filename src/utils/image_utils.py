from enum import Enum

class TypeCapture(Enum):
    Time        = "Time"
    Quantity    = "Quantity"
    General     = "General"

class TypePlatform(Enum):
    Windows     = "Windows"
    Linux       = "Linux"
    MacOS       = "Darwin"