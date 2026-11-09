"""Part-inspection engine: align a part image to a golden reference, diff them
robustly, and decide OK / NG. Pure OpenCV/NumPy — no Qt — so it is easy to test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict, fields
from typing import Optional, Sequence

import cv2
import numpy as np

# ── data types ─────────────────────────────────────────────────


@dataclass
class InspectionParams:
    threshold: int = 25            # min gray-level difference to count as changed (1-255)
    blur_ksize: int = 5            # gaussian blur before diff (odd; 0 = off) — kills sensor noise
    morph_kernel: int = 3          # opening kernel to drop isolated speckles (0 = off)
    min_defect_area: int = 30      # px; smaller blobs are ignored
    max_defects: int = 0           # NG if more defects than this
    max_defect_area_pct: float = 100.0  # NG if defect area exceeds this % of the inspected area
    align: bool = True             # register the image onto the reference first
    normalize_lighting: bool = True  # match brightness/contrast to the reference

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InspectionParams":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


@dataclass
class Roi:
    """Rectangle in normalized (0-1) image coordinates."""
    x: float
    y: float
    w: float
    h: float
    mode: str = "include"  # "include" | "ignore"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Roi":
        return cls(float(data["x"]), float(data["y"]), float(data["w"]), float(data["h"]),
                   data.get("mode", "include"))


@dataclass
class Defect:
    x: int
    y: int
    w: int
    h: int
    area: int


@dataclass
class AlignResult:
    image: np.ndarray             # image warped into the reference frame (BGR)
    valid_mask: np.ndarray        # 255 where the warped image has real pixels
    success: bool
    matrix: Optional[np.ndarray]  # 2x3 affine mapping image -> reference, or None
    method: str                   # "orb" | "ecc" | "identity" | "none"
    inliers: int = 0


@dataclass
class InspectionResult:
    ok: bool
    reasons: list[str]
    defects: list[Defect]
    defect_area_px: int
    defect_area_pct: float
    inspected_px: int
    align: AlignResult
    diff: np.ndarray       # grayscale abs difference (uint8)
    mask: np.ndarray       # binary mask of kept defects (uint8 0/255)
    heatmap: np.ndarray    # JET colormap of diff, masked to the inspected area (BGR)
    overlay: np.ndarray    # reference image with defects outlined in red (BGR)
    reference_index: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return "OK" if self.ok else "NG"


# ── helpers ────────────────────────────────────────────────────


def to_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(to_bgr(img), cv2.COLOR_BGR2GRAY)


def build_roi_mask(shape: tuple, rois: Optional[Sequence[Roi]]) -> np.ndarray:
    """255 = inspect. With any 'include' ROI only those areas are inspected;
    'ignore' ROIs are always carved out."""
    h, w = shape[:2]
    rois = list(rois or [])
    includes = [r for r in rois if r.mode == "include"]
    mask = np.zeros((h, w), np.uint8) if includes else np.full((h, w), 255, np.uint8)

    def _rect(r: Roi):
        x0 = int(round(max(0.0, min(1.0, r.x)) * w))
        y0 = int(round(max(0.0, min(1.0, r.y)) * h))
        x1 = int(round(max(0.0, min(1.0, r.x + r.w)) * w))
        y1 = int(round(max(0.0, min(1.0, r.y + r.h)) * h))
        return x0, y0, x1, y1

    for r in includes:
        x0, y0, x1, y1 = _rect(r)
        mask[y0:y1, x0:x1] = 255
    for r in rois:
        if r.mode == "ignore":
            x0, y0, x1, y1 = _rect(r)
            mask[y0:y1, x0:x1] = 0
    return mask


# ── alignment ──────────────────────────────────────────────────

_MAX_SCALE_DEVIATION = 0.25


def _scale_of(M: np.ndarray) -> float:
    return math.sqrt(abs(float(np.linalg.det(M[:, :2]))))


def _is_plausible(M: Optional[np.ndarray]) -> bool:
    if M is None or not np.all(np.isfinite(M)):
        return False
    return abs(_scale_of(M) - 1.0) <= _MAX_SCALE_DEVIATION


def _estimate_orb(gray_ref: np.ndarray, gray_img: np.ndarray):
    orb = cv2.ORB_create(nfeatures=3000)
    kp_r, des_r = orb.detectAndCompute(gray_ref, None)
    kp_i, des_i = orb.detectAndCompute(gray_img, None)
    if des_r is None or des_i is None or len(kp_r) < 10 or len(kp_i) < 10:
        return None, 0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(matcher.match(des_i, des_r), key=lambda m: m.distance)
    matches = matches[: max(10, int(len(matches) * 0.7))]
    if len(matches) < 10:
        return None, 0
    src = np.float32([kp_i[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([kp_r[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None or inl is None:
        return None, 0
    inliers = int(inl.sum())
    if inliers < 10 or not _is_plausible(M):
        return None, inliers
    return M, inliers


def _estimate_ecc(gray_ref: np.ndarray, gray_img: np.ndarray):
    h, w = gray_ref.shape
    s = min(1.0, 640.0 / max(h, w))
    small_r = cv2.resize(gray_ref, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray_ref
    small_i = cv2.resize(gray_img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray_img
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5)
    try:
        _, warp = cv2.findTransformECC(small_r, small_i, warp, cv2.MOTION_EUCLIDEAN, criteria, None, 5)
    except cv2.error:
        return None
    # warp maps reference coords -> image coords (small scale). Convert to full scale, then invert.
    warp = warp.astype(np.float64)
    warp[:, 2] /= s
    M = cv2.invertAffineTransform(warp)
    return M if _is_plausible(M) else None


def align_image(reference: np.ndarray, image: np.ndarray) -> AlignResult:
    """Warp `image` into the frame of `reference` (rotation + translation + small scale)."""
    ref = to_bgr(reference)
    img = to_bgr(image)
    h, w = ref.shape[:2]
    if img.shape[:2] != (h, w):
        img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    full = np.full((h, w), 255, np.uint8)

    gray_ref, gray_img = _gray(ref), _gray(img)
    M, inliers = _estimate_orb(gray_ref, gray_img)
    method = "orb"
    if M is None:
        M = _estimate_ecc(gray_ref, gray_img)
        method, inliers = "ecc", 0
    if M is None:
        return AlignResult(img, full, False, None, "none", 0)

    angle = abs(math.atan2(M[1, 0], M[0, 0]))
    near_identity = (abs(M[0, 2]) < 0.3 and abs(M[1, 2]) < 0.3
                     and angle < 1e-3 and abs(_scale_of(M) - 1.0) < 1e-3)
    if near_identity:
        return AlignResult(img, full, True, M, "identity", inliers)

    aligned = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    valid = cv2.warpAffine(full, M, (w, h), flags=cv2.INTER_NEAREST,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    valid = cv2.erode(valid, np.ones((3, 3), np.uint8), iterations=2)
    return AlignResult(aligned, valid, True, M, method, inliers)


# ── inspection ─────────────────────────────────────────────────


def _match_brightness(gray_img: np.ndarray, gray_ref: np.ndarray, mask: np.ndarray) -> np.ndarray:
    m = mask > 0
    if int(m.sum()) < 100:
        return gray_img
    mi, si = float(gray_img[m].mean()), float(gray_img[m].std())
    mr, sr = float(gray_ref[m].mean()), float(gray_ref[m].std())
    if si < 1e-3:
        return gray_img
    out = (gray_img.astype(np.float32) - mi) * (sr / si) + mr
    return np.clip(out, 0, 255).astype(np.uint8)


def _odd(k: int) -> int:
    return k if k % 2 == 1 else k + 1


def inspect_image(reference: np.ndarray, image: np.ndarray,
                  params: Optional[InspectionParams] = None,
                  rois: Optional[Sequence[Roi]] = None) -> InspectionResult:
    """Compare `image` against `reference` and return an OK/NG result."""
    params = params or InspectionParams()
    ref = to_bgr(reference)
    h, w = ref.shape[:2]

    if params.align:
        al = align_image(ref, image)
    else:
        img = to_bgr(image)
        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        al = AlignResult(img, np.full((h, w), 255, np.uint8), True, None, "none", 0)

    roi_mask = build_roi_mask(ref.shape, rois)
    inspect_mask = cv2.bitwise_and(roi_mask, al.valid_mask)

    gray_ref = _gray(ref)
    gray_img = _gray(al.image)
    if params.normalize_lighting:
        gray_img = _match_brightness(gray_img, gray_ref, inspect_mask)

    if params.blur_ksize and params.blur_ksize > 1:
        k = _odd(params.blur_ksize)
        gray_ref_b = cv2.GaussianBlur(gray_ref, (k, k), 0)
        gray_img_b = cv2.GaussianBlur(gray_img, (k, k), 0)
    else:
        gray_ref_b, gray_img_b = gray_ref, gray_img

    diff = cv2.absdiff(gray_ref_b, gray_img_b)
    _, mask = cv2.threshold(diff, max(0, params.threshold - 1), 255, cv2.THRESH_BINARY)
    mask = cv2.bitwise_and(mask, inspect_mask)

    if params.morph_kernel and params.morph_kernel > 1:
        kernel = np.ones((params.morph_kernel, params.morph_kernel), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    defects: list[Defect] = []
    kept = np.zeros_like(mask)
    for i in range(1, n):
        x, y, bw, bh, area = (int(v) for v in stats[i])
        if area >= params.min_defect_area:
            defects.append(Defect(x, y, bw, bh, area))
            kept[labels == i] = 255
    defects.sort(key=lambda d: d.area, reverse=True)

    inspected_px = int(np.count_nonzero(inspect_mask))
    defect_px = int(sum(d.area for d in defects))
    pct = (defect_px / inspected_px * 100.0) if inspected_px else 0.0

    reasons: list[str] = []
    if len(defects) > params.max_defects:
        reasons.append(f"{len(defects)} defect(s) found (allowed {params.max_defects})")
    if pct > params.max_defect_area_pct:
        reasons.append(f"defect area {pct:.2f}% exceeds {params.max_defect_area_pct:.2f}%")
    ok = not reasons

    warnings: list[str] = []
    if params.align and not al.success:
        # Not fatal: on a fixed fixture the parts may already be aligned. A misplaced part
        # still shows up as defects in the diff and is rejected.
        warnings.append("alignment failed; compared without registration")

    heat = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
    heat[inspect_mask == 0] = (heat[inspect_mask == 0] * 0.25).astype(np.uint8)

    overlay = ref.copy()
    contours, _ = cv2.findContours(kept, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(overlay, contours, -1, (0, 0, 255), 2)
    for d in defects:
        cv2.rectangle(overlay, (d.x - 3, d.y - 3), (d.x + d.w + 3, d.y + d.h + 3), (0, 200, 255), 1)

    return InspectionResult(
        ok=ok, reasons=reasons, defects=defects, defect_area_px=defect_px,
        defect_area_pct=pct, inspected_px=inspected_px, align=al, diff=diff,
        mask=kept, heatmap=heat, overlay=overlay, warnings=warnings,
    )


def inspect_against_references(references: Sequence[np.ndarray], image: np.ndarray,
                               params: Optional[InspectionParams] = None,
                               rois: Optional[Sequence[Roi]] = None) -> InspectionResult:
    """Inspect against several golden references and keep the best match
    (fewest defect pixels). A part that matches ANY good reference passes."""
    if not references:
        raise ValueError("At least one reference image is required.")
    best: Optional[InspectionResult] = None
    for idx, ref in enumerate(references):
        res = inspect_image(ref, image, params, rois)
        res.reference_index = idx
        if best is None or res.defect_area_px < best.defect_area_px:
            best = res
        if best.ok and best.defect_area_px == 0:
            break
    return best
