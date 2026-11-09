"""PDF inspection reports built with Qt's QTextDocument + QPdfWriter (no extra dependencies)."""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QMarginsF, QUrl
from PyQt6.QtGui import QImage, QPageLayout, QPageSize, QPdfWriter, QTextDocument

MAX_TABLE_ROWS = 500
THUMB_WIDTH_PX = 250


def _g(row, key, default=""):
    """Read a key from a sqlite3.Row or dict."""
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _find_overlay(batch, item) -> Optional[Path]:
    out = _g(batch, "output_dir")
    if not out:
        return None
    p = Path(out) / "NG" / f"{Path(_g(item, 'file')).stem}_diff.png"
    return p if p.is_file() else None


def build_report_html(batch, items: list, include_ok: bool = False, max_thumbs: int = 24,
                      company: str = "") -> tuple[str, dict[str, QImage]]:
    """Return (html, {resource_name: QImage}). All dynamic text is HTML-escaped."""
    total, ok, ng, errors = (int(_g(batch, k, 0)) for k in ("total", "ok", "ng", "errors"))
    inspected = ok + ng
    reject = (ng / inspected * 100.0) if inspected else 0.0
    e = lambda v: escape(str(v))  # noqa: E731

    meta = [
        ("Batch", f"#{_g(batch, 'id')}"),
        ("Date", _g(batch, "started_at")),
        ("Reference", _g(batch, "reference")),
        ("Inspector", _g(batch, "username") or "—"),
        ("Folder", _g(batch, "folder")),
    ]
    if int(_g(batch, "cancelled", 0)):
        meta.append(("Note", "Batch was cancelled before finishing"))

    html = [
        "<html><body style='font-family: sans-serif; font-size: 10pt;'>",
        f"<h1>Inspection report</h1>" + (f"<p><b>{e(company)}</b></p>" if company else ""),
        "<table cellpadding='3'>",
        *(f"<tr><td><b>{e(k)}</b></td><td>{e(v)}</td></tr>" for k, v in meta),
        "</table>",
        "<h2>Summary</h2>",
        "<table border='1' cellspacing='0' cellpadding='6' width='100%'><tr>"
        f"<td align='center'><b>{total}</b><br>parts</td>"
        f"<td align='center' style='color:#1f7a3a'><b>{ok}</b><br>OK</td>"
        f"<td align='center' style='color:#c0261f'><b>{ng}</b><br>NG</td>"
        f"<td align='center'><b>{errors}</b><br>errors</td>"
        f"<td align='center'><b>{reject:.1f}%</b><br>reject rate</td></tr></table>",
    ]

    shown = [i for i in items if include_ok or _g(i, "verdict") != "OK"]
    html.append(f"<h2>{'All parts' if include_ok else 'Rejected and failed parts'}</h2>")
    if not shown:
        html.append("<p>No rejected parts in this batch.</p>")
    else:
        html.append("<table border='1' cellspacing='0' cellpadding='4' width='100%'>"
                    "<tr style='background:#e8e8e8'><th>File</th><th>Verdict</th><th>Defects</th>"
                    "<th>Area %</th><th>Details</th></tr>")
        for it in shown[:MAX_TABLE_ROWS]:
            verdict = _g(it, "verdict")
            color = {"OK": "#1f7a3a", "NG": "#c0261f"}.get(verdict, "#a06800")
            detail = _g(it, "reasons") or _g(it, "error")
            html.append(
                f"<tr><td>{e(_g(it, 'file'))}</td>"
                f"<td style='color:{color}'><b>{e(verdict)}</b></td>"
                f"<td align='right'>{e(_g(it, 'defects', 0))}</td>"
                f"<td align='right'>{float(_g(it, 'defect_area_pct', 0)):.2f}</td>"
                f"<td>{e(detail)}</td></tr>")
        html.append("</table>")
        if len(shown) > MAX_TABLE_ROWS:
            html.append(f"<p><i>Showing the first {MAX_TABLE_ROWS} of {len(shown)} rows. "
                        "Export the CSV for the complete list.</i></p>")

    images: dict[str, QImage] = {}
    captions: dict[str, str] = {}
    for it in items:
        if len(images) >= max_thumbs:
            break
        if _g(it, "verdict") != "NG":
            continue
        path = _find_overlay(batch, it)
        if path is None:
            continue
        img = QImage(str(path))
        if img.isNull():
            continue
        name = f"thumb{len(images)}"
        images[name] = img.scaledToWidth(THUMB_WIDTH_PX * 2)
        captions[name] = _g(it, "file")
    if images:
        html.append("<h2>Defect images</h2><table cellspacing='8'>")
        names = list(images)
        for row_start in range(0, len(names), 2):
            html.append("<tr>")
            for n in names[row_start:row_start + 2]:
                html.append(f"<td><img src='{n}' width='{THUMB_WIDTH_PX}'><br><small>{e(captions[n])}</small></td>")
            html.append("</tr>")
        html.append("</table>")
    html.append("</body></html>")
    return "".join(html), images


def write_pdf(path, html: str, images: Optional[dict[str, QImage]] = None) -> Path:
    doc = QTextDocument()
    for name, img in (images or {}).items():
        doc.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(name), img)
    doc.setHtml(html)

    path = Path(path)
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    doc.print(writer)
    return path


def generate_batch_report(path, batch, items: list, include_ok: bool = False, company: str = "") -> Path:
    html, images = build_report_html(batch, items, include_ok=include_ok, company=company)
    return write_pdf(path, html, images)
