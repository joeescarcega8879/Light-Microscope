from src.utils.platform_utils import default_torch_device


def test_default_torch_device_is_valid():
    assert default_torch_device() in {"cpu", "cuda", "mps"}
