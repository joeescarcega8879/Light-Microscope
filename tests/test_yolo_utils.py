import cv2
import numpy as np
import yaml

from src.utils.yolo_utils import YoloUtils


def test_labels_roundtrip(tmp_path):
    path = str(tmp_path / "a.txt")
    labels = [(0, [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]),
              (2, [(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4)])]
    YoloUtils.save_labels(labels, path)
    loaded = YoloUtils.load_labels(path)
    assert [c for c, _ in loaded] == [0, 2]
    assert loaded[1][1][2] == (0.4, 0.4)


def test_load_labels_missing_file_returns_empty(tmp_path):
    assert YoloUtils.load_labels(str(tmp_path / "nope.txt")) == []


def test_load_labels_skips_malformed_lines(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("0 0.1 0.1\n1 0.1 0.1 0.9 0.1 0.5 0.9\n")
    assert [c for c, _ in YoloUtils.load_labels(str(path))] == [1]


def test_class_names_roundtrip(tmp_path):
    assert YoloUtils.load_class_names(str(tmp_path)) == []
    YoloUtils.save_class_names(["screw", "washer"], str(tmp_path))
    assert YoloUtils.load_class_names(str(tmp_path)) == ["screw", "washer"]


def test_prepare_dataset_splits_and_writes_yaml(tmp_path):
    for i in range(5):
        cv2.imwrite(str(tmp_path / f"img{i}.png"), np.zeros((8, 8, 3), np.uint8))
        YoloUtils.save_labels([(0, [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)])], str(tmp_path / f"img{i}.txt"))
    cv2.imwrite(str(tmp_path / "unlabeled.png"), np.zeros((8, 8, 3), np.uint8))

    yaml_path = YoloUtils.prepare_dataset(str(tmp_path), ["part"], val_split=0.2)

    data = yaml.safe_load(open(yaml_path))
    assert data["nc"] == 1 and data["names"] == ["part"]
    root = tmp_path / "yolo_dataset"
    n_train = len(list((root / "images" / "train").iterdir()))
    n_val = len(list((root / "images" / "val").iterdir()))
    assert (n_train, n_val) == (4, 1)  # unlabeled image excluded


def test_prepare_dataset_without_annotations_raises(tmp_path):
    import pytest
    cv2.imwrite(str(tmp_path / "x.png"), np.zeros((8, 8, 3), np.uint8))
    with pytest.raises(ValueError):
        YoloUtils.prepare_dataset(str(tmp_path), ["part"])
