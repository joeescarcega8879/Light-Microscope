import csv

import cv2
import numpy as np
import pytest

from src.inspection.batch import run_batch
from src.inspection.engine import InspectionParams, Roi
from src.inspection.imageio import list_images, read_image, write_image
from src.inspection.reference import ReferenceStore, safe_name
from test_inspection_engine import make_part, shift


@pytest.fixture
def store(tmp_path):
    return ReferenceStore(tmp_path / "refs")


def test_store_roundtrip_with_rois_and_params(store):
    ref = store.create("Part A", [make_part()], InspectionParams(threshold=40),
                       [Roi(0.1, 0.1, 0.5, 0.5, "ignore")])
    assert store.list_names() == ["Part A"]
    loaded = store.load("Part A")
    assert loaded.params.threshold == 40
    assert loaded.rois[0].mode == "ignore"
    assert len(loaded.load_images()) == 1


def test_store_add_remove_image_and_delete(store):
    ref = store.create("p", [make_part()])
    store.add_image(ref, make_part(seed=2))
    assert len(store.load("p").image_paths) == 2
    store.remove_image(ref, 0)
    assert len(store.load("p").image_paths) == 1
    with pytest.raises(ValueError):
        store.remove_image(ref, 0)   # cannot drop the last image
    store.delete("p")
    assert store.list_names() == []


def test_store_rejects_duplicates_and_unsafe_names(store):
    store.create("p", [make_part()])
    with pytest.raises(FileExistsError):
        store.create("p", [make_part()])
    assert "/" not in safe_name("../../etc/passwd") and ".." not in safe_name("../x")
    with pytest.raises(ValueError):
        safe_name("   ")
    with pytest.raises(ValueError):
        store.create("empty", [])


def test_imageio_unicode_path_and_listing(tmp_path):
    p = tmp_path / "pieza_ñ.png"
    assert write_image(p, make_part())
    assert read_image(p) is not None
    (tmp_path / "notes.txt").write_text("x")
    assert [f.name for f in list_images(tmp_path)] == ["pieza_ñ.png"]
    assert read_image(tmp_path / "missing.png") is None


def test_batch_separates_ng_and_writes_report(store, tmp_path):
    good = make_part()
    ref = store.create("p", [good])
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    for i in range(3):                                   # good parts, slightly moved
        write_image(src / f"ok_{i}.png", shift(good, 5 + i, -3, angle=i))
    for i in range(2):                                   # defective parts
        bad = good.copy()
        cv2.circle(bad, (150 + 20 * i, 240), 14, (0, 0, 0), -1)
        write_image(src / f"bad_{i}.png", shift(bad, 6, 4, angle=2))
    (src / "corrupt.png").write_bytes(b"not an image")

    seen = []
    summary = run_batch(src, ref, out, progress=lambda i, n, it: seen.append((i, n)))

    assert (summary.ok, summary.ng, summary.errors) == (3, 2, 1)
    assert seen[-1] == (6, 6)
    assert sorted(p.name for p in (out / "NG").iterdir()) == [
        "bad_0.png", "bad_0_diff.png", "bad_1.png", "bad_1_diff.png"]
    rows = list(csv.DictReader(open(out / "results.csv", encoding="utf-8")))
    assert {r["file"]: r["verdict"] for r in rows}["bad_0.png"] == "NG"
    assert {r["file"]: r["verdict"] for r in rows}["corrupt.png"] == "ERROR"


def test_batch_cancel_stops_early(store, tmp_path):
    ref = store.create("p", [make_part()])
    src = tmp_path / "in"
    src.mkdir()
    for i in range(4):
        write_image(src / f"{i}.png", make_part())
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 2

    summary = run_batch(src, ref, cancel=cancel)
    assert summary.cancelled and len(summary.items) == 2


def test_batch_copy_ok_option(store, tmp_path):
    ref = store.create("p", [make_part()])
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    write_image(src / "a.png", make_part())
    run_batch(src, ref, out, copy_ok=True)
    assert (out / "OK" / "a.png").exists()


# ── recipe export / import ──
def test_export_import_roundtrip(store, tmp_path):
    store.create("A", [make_part(), make_part(seed=2)], InspectionParams(threshold=33),
                 [Roi(0.1, 0.1, 0.2, 0.2, "ignore")])
    z = store.export_zip("A", tmp_path / "A.zip")
    other = ReferenceStore(tmp_path / "elsewhere")
    ref = other.import_zip(z)
    assert ref.name == "A" and len(ref.image_paths) == 2
    assert ref.params.threshold == 33 and ref.rois[0].mode == "ignore"
    with pytest.raises(FileExistsError):
        other.import_zip(z)
    assert other.import_zip(z, "A copy").name == "A copy"


def test_import_rejects_zip_slip_and_foreign_archives(store, tmp_path):
    import json, zipfile
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("reference.json", json.dumps({"images": ["../../escape.png"], "rois": [], "params": {}}))
        zf.writestr("../../escape.png", b"x")
    with pytest.raises(ValueError):
        store.import_zip(evil)
    assert not (tmp_path / "escape.png").exists()
    assert store.list_names() == []

    foreign = tmp_path / "foreign.zip"
    with zipfile.ZipFile(foreign, "w") as zf:
        zf.writestr("hello.txt", "hi")
    with pytest.raises(ValueError):
        store.import_zip(foreign)
