"""Batch inspection: run a folder of part images against a reference set."""
from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .engine import inspect_against_references
from .imageio import list_images, read_image, write_image
from .reference import ReferenceSet


@dataclass
class BatchItem:
    path: Path
    verdict: str            # "OK" | "NG" | "ERROR"
    defects: int = 0
    defect_area_pct: float = 0.0
    reference_index: int = 0
    reasons: str = ""
    error: str = ""


@dataclass
class BatchSummary:
    items: list[BatchItem] = field(default_factory=list)
    output_dir: Optional[Path] = None
    cancelled: bool = False

    def count(self, verdict: str) -> int:
        return sum(1 for i in self.items if i.verdict == verdict)

    @property
    def ok(self) -> int:
        return self.count("OK")

    @property
    def ng(self) -> int:
        return self.count("NG")

    @property
    def errors(self) -> int:
        return self.count("ERROR")


def _unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    n = 2
    while True:
        cand = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
        if not cand.exists():
            return cand
        n += 1


def run_batch(folder, ref: ReferenceSet, output_dir=None, copy_ok: bool = False,
              progress: Optional[Callable[[int, int, BatchItem], None]] = None,
              cancel: Optional[Callable[[], bool]] = None) -> BatchSummary:
    """Inspect every image in `folder`. NG parts are copied to `<output>/NG/` together
    with an annotated diff overlay; a `results.csv` is written to `<output>/`."""
    references = ref.load_images()
    if not references:
        raise ValueError(f"Reference '{ref.name}' has no readable images.")
    files = list_images(folder)
    out = Path(output_dir) if output_dir else None
    ng_dir = ok_dir = None
    if out:
        ng_dir = out / "NG"
        ng_dir.mkdir(parents=True, exist_ok=True)
        if copy_ok:
            ok_dir = out / "OK"
            ok_dir.mkdir(parents=True, exist_ok=True)

    summary = BatchSummary(output_dir=out)
    total = len(files)
    for i, path in enumerate(files, 1):
        if cancel and cancel():
            summary.cancelled = True
            break
        img = read_image(path)
        if img is None:
            item = BatchItem(path, "ERROR", error="could not read image")
        else:
            try:
                res = inspect_against_references(references, img, ref.params, ref.rois)
                item = BatchItem(path, res.verdict, len(res.defects), round(res.defect_area_pct, 3),
                                 res.reference_index, "; ".join(res.reasons))
                if out and not res.ok:
                    shutil.copy2(path, _unique(ng_dir / path.name))
                    write_image(_unique(ng_dir / f"{path.stem}_diff.png"), res.overlay)
                elif ok_dir is not None:
                    shutil.copy2(path, _unique(ok_dir / path.name))
            except Exception as exc:  # one bad file must not abort the whole batch
                item = BatchItem(path, "ERROR", error=str(exc))
        summary.items.append(item)
        if progress:
            progress(i, total, item)

    if out:
        write_results_csv(out / "results.csv", summary)
    return summary


def write_results_csv(path: Path, summary: BatchSummary):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "verdict", "defects", "defect_area_pct", "reference_index", "reasons", "error"])
        for it in summary.items:
            w.writerow([it.path.name, it.verdict, it.defects, it.defect_area_pct,
                        it.reference_index, it.reasons, it.error])
