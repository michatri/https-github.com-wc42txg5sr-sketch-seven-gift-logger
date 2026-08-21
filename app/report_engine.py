"""Render report JSON to preview HTML and PDF. Catholic data is read-only."""
from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from fpdf import FPDF

from app.db import thai_date
from app.pdfs import pdf_response

log = logging.getLogger("catholic.reports")

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
INK = (43, 33, 24)
BURGUNDY = (107, 29, 42)
GOLD = (138, 106, 22)
MUTED = (110, 98, 86)

PAGE_SIZES = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
}

SECTION_ORDER = [
    "reportHeader",
    "pageHeader",
    "groupHeader",
    "detail",
    "groupFooter",
    "pageFooter",
    "reportFooter",
]

SECTION_LABELS = {
    "reportHeader": "หัวรายงาน",
    "pageHeader": "หัวหน้า",
    "groupHeader": "หัวกลุ่ม",
    "detail": "รายละเอียด",
    "groupFooter": "ท้ายกลุ่ม",
    "pageFooter": "ท้ายหน้า",
    "reportFooter": "ท้ายรายงาน",
}

CODE39 = {
    "0": "nnnwwnwnn",
    "1": "wnnwnnnnw",
    "2": "nnwwnnnnw",
    "3": "wnwwnnnnn",
    "4": "nnnwwnnnw",
    "5": "wnnwwnnnn",
    "6": "nnwwwnnnn",
    "7": "nnnwnnwnw",
    "8": "wnnwnnwnn",
    "9": "nnwwnnwnn",
    "A": "wnnnnwnnw",
    "B": "nnwnnwnnw",
    "C": "wnwnnwnnn",
    "D": "nnnnwwnnw",
    "E": "wnnnwwnnn",
    "F": "nnwnwwnnn",
    "G": "nnnnnwwnw",
    "H": "wnnnnwwnn",
    "I": "nnwnnwwnn",
    "J": "nnnnwwwnn",
    "K": "wnnnnnnww",
    "L": "nnwnnnnww",
    "M": "wnwnnnnwn",
    "N": "nnnnwnnww",
    "O": "wnnnwnnwn",
    "P": "nnwnwnnwn",
    "Q": "nnnnnnwww",
    "R": "wnnnnnwwn",
    "S": "nnwnnnwwn",
    "T": "nnnnwnwwn",
    "U": "wwnnnnnnw",
    "V": "nwwnnnnnw",
    "W": "wwwnnnnnn",
    "X": "nwnnwnnnw",
    "Y": "wwnnwnnnn",
    "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw",
    " ": "nwwnnnwnn",
    "*": "nwnnwnwnn",
}


def default_layout(title: str = "รายงาน", fields: list[dict] | None = None) -> dict[str, Any]:
    columns = []
    for fld in fields or []:
        alias = fld.get("alias") or fld.get("column")
        if not alias:
            continue
        columns.append(
            {
                "field": alias,
                "label": fld.get("label") or alias,
                "width": max(22, int(180 / max(len(fields), 1))),
                "agg": None,
            }
        )
    table = {
        "id": "tbl1",
        "type": "table",
        "x": 0,
        "y": 2,
        "w": 180,
        "h": 12,
        "columns": columns,
        "header": True,
        "footer": True,
        "footerAgg": "COUNT",
        "fontSize": 9,
        "border": True,
    }
    return {
        "version": 1,
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "margin": {"top": 15, "right": 15, "bottom": 15, "left": 15},
        },
        "dataSource": {"datasetId": None},
        "parameters": [],
        "sections": [
            {
                "id": "reportHeader",
                "type": "reportHeader",
                "height": 18,
                "components": [
                    {
                        "id": "title1",
                        "type": "text",
                        "x": 0,
                        "y": 2,
                        "w": 180,
                        "h": 10,
                        "text": title,
                        "fontSize": 16,
                        "bold": True,
                        "align": "center",
                        "color": "#6b1d2a",
                    }
                ],
            },
            {"id": "pageHeader", "type": "pageHeader", "height": 8, "components": []},
            {"id": "groupHeader", "type": "groupHeader", "height": 10, "groupField": "", "components": []},
            {"id": "detail", "type": "detail", "height": 14, "components": [table] if columns else []},
            {"id": "groupFooter", "type": "groupFooter", "height": 8, "components": []},
            {
                "id": "pageFooter",
                "type": "pageFooter",
                "height": 10,
                "components": [
                    {
                        "id": "pg",
                        "type": "pageNumber",
                        "x": 0,
                        "y": 1,
                        "w": 90,
                        "h": 6,
                        "fontSize": 8,
                        "align": "left",
                    },
                    {
                        "id": "dt",
                        "type": "date",
                        "x": 90,
                        "y": 1,
                        "w": 90,
                        "h": 6,
                        "fontSize": 8,
                        "align": "right",
                        "format": "thaiDate",
                    },
                ],
            },
            {"id": "reportFooter", "type": "reportFooter", "height": 10, "components": []},
        ],
        "components": [],
    }


def normalize_layout(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_layout()
    src = raw or {}
    page = dict(base["page"])
    page.update(src.get("page") or {})
    page["margin"] = {**base["page"]["margin"], **(page.get("margin") or {})}
    sections = src.get("sections") or base["sections"]
    by_type = {s.get("type"): s for s in sections if s.get("type")}
    ordered = []
    for kind in SECTION_ORDER:
        sec = by_type.get(kind) or {"id": kind, "type": kind, "height": 10, "components": []}
        sec.setdefault("components", [])
        sec.setdefault("height", 10)
        ordered.append(sec)
    return {
        "version": int(src.get("version") or 1),
        "page": page,
        "dataSource": src.get("dataSource") or {},
        "parameters": src.get("parameters") or [],
        "sections": ordered,
        "components": src.get("components") or [],
        "groupBy": src.get("groupBy") or (by_type.get("groupHeader") or {}).get("groupField") or "",
    }


def page_dims(layout: dict[str, Any]) -> tuple[float, float]:
    page = layout.get("page") or {}
    size = str(page.get("size") or "A4")
    if size == "Custom":
        w = float(page.get("customWidth") or 210)
        h = float(page.get("customHeight") or 297)
    else:
        w, h = PAGE_SIZES.get(size, PAGE_SIZES["A4"])
    if str(page.get("orientation") or "portrait").lower().startswith("l"):
        w, h = h, w
    return w, h


def format_value(value: Any, fmt: str | None = None, field: str | None = None) -> str:
    if value is None or str(value).strip() == "":
        return ""
    fmt = (fmt or "").strip()
    if fmt in {"date", "thaiDate"} or (field and str(field).endswith("_date")):
        return thai_date(str(value)) or str(value)
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = None
    if num is not None:
        if fmt == "currency":
            return f"{num:,.2f}"
        if fmt == "percentage":
            return f"{num:,.1f}%"
        if fmt == "number":
            if num == int(num):
                return f"{int(num):,}"
            return f"{num:,.2f}"
    return str(value)


def hex_rgb(color: str | None, fallback: tuple[int, int, int] = INK) -> tuple[int, int, int]:
    c = (color or "").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return fallback
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return fallback


def _comp_text(comp: dict, record: dict, page_no: int, page_count: int, extra: dict | None = None) -> str:
    kind = comp.get("type") or "text"
    extra = extra or {}
    if kind == "pageNumber":
        return f"หน้า {page_no} / {page_count}"
    if kind == "date":
        return format_value(datetime.now().date().isoformat(), comp.get("format") or "thaiDate")
    if kind == "label":
        return str(comp.get("text") or "")
    if kind == "text":
        text = str(comp.get("text") or "")
        for k, v in {**record, **extra}.items():
            text = text.replace("{" + str(k) + "}", format_value(v, field=str(k)))
        return text
    if kind in {"field", "barcode", "qrcode"}:
        field = str(comp.get("field") or "")
        return format_value(record.get(field, extra.get(field, "")), comp.get("format"), field)
    if kind == "pageBreak":
        return ""
    if kind == "subreport":
        return str(comp.get("text") or "รายงานย่อย")
    if kind == "chart":
        return str(comp.get("text") or "แผนภูมิ")
    return str(comp.get("text") or "")


def _group_key(row: dict, field: str) -> str:
    if not field:
        return ""
    return str(row.get(field) or "")


def group_rows(rows: list[dict], field: str) -> list[tuple[str, list[dict]]]:
    if not field:
        return [("", rows)]
    groups: list[tuple[str, list[dict]]] = []
    current = None
    bucket: list[dict] = []
    for row in rows:
        key = _group_key(row, field)
        if current is None:
            current = key
        if key != current:
            groups.append((current, bucket))
            bucket = []
            current = key
        bucket.append(row)
    if current is not None:
        groups.append((current, bucket))
    return groups or [("", [])]


def aggregate(rows: list[dict], field: str, agg: str) -> Any:
    agg = (agg or "").upper()
    vals = []
    for row in rows:
        try:
            vals.append(float(row.get(field)))
        except (TypeError, ValueError):
            continue
    if agg == "COUNT":
        return len(rows)
    if not vals:
        return 0
    if agg == "SUM":
        return sum(vals)
    if agg == "AVG":
        return sum(vals) / len(vals)
    if agg == "MIN":
        return min(vals)
    if agg == "MAX":
        return max(vals)
    return len(rows)


def section_by_type(layout: dict, kind: str) -> dict:
    for sec in layout.get("sections") or []:
        if sec.get("type") == kind:
            return sec
    return {"id": kind, "type": kind, "height": 0, "components": []}


def preview_html(
    layout: dict[str, Any],
    rows: list[dict],
    *,
    title: str = "",
    page: int = 1,
    total: int = 0,
    page_size: int = 50,
    status: str = "ok",
    message: str = "",
) -> str:
    layout = normalize_layout(layout)
    w, h = page_dims(layout)
    margin = layout["page"]["margin"]
    group_field = str(layout.get("groupBy") or section_by_type(layout, "groupHeader").get("groupField") or "")
    if status == "loading":
        inner = '<div class="rp-state">กำลังโหลดข้อมูล…</div>'
    elif status == "error":
        inner = f'<div class="rp-state error">{escape(message or "ไม่สามารถสร้างรายงานได้")}</div>'
    elif not rows:
        inner = '<div class="rp-state">ไม่มีข้อมูลตามเงื่อนไขที่เลือก</div>'
    else:
        parts = []
        groups = group_rows(rows, group_field)
        page_count = max(1, (total + page_size - 1) // page_size) if page_size else 1
        extra_base = {"_total": total, "_title": title}

        def emit_section(kind: str, record: dict, extra: dict | None = None):
            sec = section_by_type(layout, kind)
            height = float(sec.get("height") or 10)
            html = [f'<div class="rp-band" data-section="{kind}" style="min-height:{height}mm">']
            for comp in sec.get("components") or []:
                html.append(_comp_html(comp, record, page, page_count, extra or extra_base, rows if kind != "detail" else [record]))
            html.append("</div>")
            return "".join(html)

        parts.append(emit_section("reportHeader", rows[0] if rows else {}, extra_base))
        parts.append(emit_section("pageHeader", rows[0] if rows else {}, extra_base))
        for gkey, grows in groups:
            extra = {**extra_base, "_group": gkey, "_group_count": len(grows)}
            if group_field:
                gh = section_by_type(layout, "groupHeader")
                if not any(c.get("type") == "text" and "{_group}" in str(c.get("text") or "") for c in gh.get("components") or []):
                    parts.append(
                        f'<div class="rp-band rp-group-h">กลุ่ม: {escape(str(gkey) or "-")} '
                        f'({len(grows)} รายการ)</div>'
                    )
                else:
                    parts.append(emit_section("groupHeader", {group_field: gkey, **(grows[0] if grows else {})}, extra))
            table_emitted = False
            for rec in grows:
                det = section_by_type(layout, "detail")
                comps = det.get("components") or []
                tables = [c for c in comps if c.get("type") == "table"]
                others = [c for c in comps if c.get("type") != "table"]
                if tables and not table_emitted:
                    for tbl in tables:
                        parts.append(_table_html(tbl, grows, extra))
                    table_emitted = True
                if others:
                    html = [f'<div class="rp-band" data-section="detail" style="min-height:{float(det.get("height") or 8)}mm">']
                    for comp in others:
                        html.append(_comp_html(comp, rec, page, page_count, extra, grows))
                    html.append("</div>")
                    parts.append("".join(html))
                if not tables and not others:
                    parts.append('<div class="rp-band muted">ยังไม่มีองค์ประกอบในแถบรายละเอียด</div>')
                    break
            if group_field:
                gf_extra = {**extra, "_count": len(grows)}
                parts.append(emit_section("groupFooter", grows[0] if grows else {}, gf_extra))
                if not section_by_type(layout, "groupFooter").get("components"):
                    parts.append(f'<div class="rp-band rp-group-f">รวม {len(grows)} รายการ</div>')
        parts.append(emit_section("pageFooter", rows[0] if rows else {}, extra_base))
        parts.append(emit_section("reportFooter", rows[0] if rows else {}, {**extra_base, "_count": total}))
        inner = "".join(parts)

    return (
        f'<div class="rp-paper" style="width:{w}mm;min-height:{h}mm;'
        f'padding:{margin["top"]}mm {margin["right"]}mm {margin["bottom"]}mm {margin["left"]}mm">'
        f"{inner}</div>"
    )


def _style(comp: dict) -> str:
    x = float(comp.get("x") or 0)
    y = float(comp.get("y") or 0)
    w = float(comp.get("w") or 40)
    h = float(comp.get("h") or 8)
    size = int(comp.get("fontSize") or 11)
    color = comp.get("color") or "#2b2118"
    bg = comp.get("background") or "transparent"
    align = {"left": "left", "center": "center", "right": "right", "L": "left", "C": "center", "R": "right"}.get(
        str(comp.get("align") or "left"), "left"
    )
    weight = "700" if comp.get("bold") else "400"
    italic = "italic" if comp.get("italic") else "normal"
    deco = "underline" if comp.get("underline") else "none"
    pad = float(comp.get("padding") or 0)
    border = "1px solid #c9a227" if comp.get("border") else "none"
    return (
        f"position:absolute;left:{x}mm;top:{y}mm;width:{w}mm;height:{h}mm;"
        f"font-size:{size}pt;color:{color};background:{bg};text-align:{align};"
        f"font-weight:{weight};font-style:{italic};text-decoration:{deco};"
        f"padding:{pad}mm;border:{border};overflow:hidden;line-height:1.2"
    )


def _comp_html(comp: dict, record: dict, page_no: int, page_count: int, extra: dict, group_rows_data: list[dict]) -> str:
    kind = comp.get("type") or "text"
    if kind == "table":
        return _table_html(comp, group_rows_data, extra)
    if kind == "line":
        return f'<div class="rp-comp rp-line" style="{_style(comp)};border-top:1.2px solid #c9a227;height:0"></div>'
    if kind == "rectangle":
        return f'<div class="rp-comp" style="{_style(comp)};border:1px solid #6b1d2a"></div>'
    if kind == "pageBreak":
        return '<div class="rp-pagebreak"></div>'
    if kind == "image":
        src = escape(str(comp.get("src") or ""))
        return f'<div class="rp-comp" style="{_style(comp)}"><img src="{src}" alt="" style="max-width:100%;max-height:100%"></div>'
    if kind == "barcode":
        text = _comp_text(comp, record, page_no, page_count, extra)
        return f'<div class="rp-comp" style="{_style(comp)}"><div class="rp-barcode">{escape(text)}</div></div>'
    if kind == "qrcode":
        text = _comp_text(comp, record, page_no, page_count, extra)
        return f'<div class="rp-comp" style="{_style(comp)}"><div class="rp-qr">{escape(text)}</div></div>'
    if kind == "chart":
        field = str(comp.get("field") or "")
        return f'<div class="rp-comp" style="{_style(comp)}">{_chart_html(group_rows_data, field)}</div>'
    text = _comp_text(comp, record, page_no, page_count, extra)
    return f'<div class="rp-comp" style="{_style(comp)}">{escape(text)}</div>'


def _table_html(comp: dict, rows: list[dict], extra: dict) -> str:
    cols = list(comp.get("columns") or [])
    if not cols:
        return '<div class="muted">ยังไม่ได้กำหนดคอลัมน์ตาราง</div>'
    thead = "".join(f"<th style='width:{float(c.get('width') or 30)}mm'>{escape(str(c.get('label') or c.get('field')))}</th>" for c in cols)
    body = []
    for rec in rows:
        tds = "".join(
            f"<td>{escape(format_value(rec.get(c.get('field')), c.get('format'), c.get('field')))}</td>" for c in cols
        )
        body.append(f"<tr>{tds}</tr>")
    foot = ""
    if comp.get("footer"):
        cells = []
        for i, c in enumerate(cols):
            agg = (c.get("agg") or comp.get("footerAgg") or "").upper()
            if i == 0 and not c.get("agg"):
                cells.append("<td>รวมทั้งหมด</td>")
            elif agg:
                cells.append(f"<td>{escape(str(format_value(aggregate(rows, str(c.get('field')), agg), 'number')))}</td>")
            else:
                cells.append("<td></td>")
        foot = f"<tfoot><tr>{''.join(cells)}</tr></tfoot>"
    return (
        f'<table class="rp-table"><thead><tr>{thead}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody>{foot}</table>"
    )


def _chart_html(rows: list[dict], field: str) -> str:
    counts: dict[str, int] = {}
    for rec in rows:
        key = str(rec.get(field) or "-")
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return "ไม่มีข้อมูลแผนภูมิ"
    mx = max(counts.values()) or 1
    bars = []
    for k, v in list(counts.items())[:8]:
        pct = int(v * 100 / mx)
        bars.append(
            f'<div class="rp-bar"><span>{escape(k)}</span>'
            f'<i style="width:{pct}%"></i><b>{v}</b></div>'
        )
    return "".join(bars)


class ReportPDF(FPDF):
    def __init__(self, width: float, height: float, margin: dict, footer_section: dict | None = None):
        super().__init__(orientation="P" if width <= height else "L", unit="mm", format=(width, height) if False else "A4")
        # fpdf format tuple for custom:
        self.page_w = width
        self.page_h = height
        self.margin = margin
        self.footer_section = footer_section
        self.layout_page_no = 1
        self.layout_page_count = 1
        self._skip_auto_footer = False
        self.set_auto_page_break(auto=False)
        self.add_font("Sarabun", "", str(FONTS / "Sarabun-Regular.ttf"))
        self.add_font("Sarabun", "B", str(FONTS / "Sarabun-Bold.ttf"))
        self.set_text_color(*INK)

    def add_layout_page(self):
        self.add_page()
        self.set_margins(self.margin["left"], self.margin["top"], self.margin["right"])
        self.set_xy(self.margin["left"], self.margin["top"])

    def header(self):
        return

    def footer(self):
        return


def _ensure_pdf_size(pdf: ReportPDF, width: float, height: float) -> ReportPDF:
    # Recreate with exact format if needed.
    pdf = ReportPDF.__new__(ReportPDF)
    FPDF.__init__(pdf, orientation="P", unit="mm", format=(width, height))
    pdf.page_w = width
    pdf.page_h = height
    return pdf


def render_pdf(
    parish: dict[str, Any],
    title: str,
    layout: dict[str, Any],
    rows: list[dict[str, Any]],
) -> bytes:
    layout = normalize_layout(layout)
    w, h = page_dims(layout)
    margin = layout["page"]["margin"]
    pdf = ReportPDF(w, h, margin)
    # Re-init with custom page size
    pdf = FPDF(orientation="P" if w <= h else "L", unit="mm", format=(w, h))
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("Sarabun", "", str(FONTS / "Sarabun-Regular.ttf"))
    pdf.add_font("Sarabun", "B", str(FONTS / "Sarabun-Bold.ttf"))
    pdf.set_text_color(*INK)
    pdf.alias_nb_pages()

    group_field = str(layout.get("groupBy") or section_by_type(layout, "groupHeader").get("groupField") or "")
    groups = group_rows(rows or [{}], group_field)
    page_count_est = max(1, len(rows) // 40 + 1)
    page_no = 0

    def new_page():
        nonlocal page_no
        page_no += 1
        pdf.add_page()
        pdf.set_xy(margin["left"], margin["top"])

    def band_y_limit():
        return h - margin["bottom"] - float(section_by_type(layout, "pageFooter").get("height") or 10)

    def draw_section(kind: str, record: dict, extra: dict, y: float, dataset: list[dict]) -> float:
        sec = section_by_type(layout, kind)
        height = float(sec.get("height") or 8)
        x0 = margin["left"]
        for comp in sec.get("components") or []:
            if comp.get("type") == "table":
                y = draw_table(comp, dataset, extra, y)
            else:
                draw_comp(comp, record, extra, x0, y, page_no, page_count_est)
        if not any((sec.get("components") or [])):
            return y
        # table already advanced y
        if any(c.get("type") == "table" for c in sec.get("components") or []):
            return y
        return y + height

    def draw_comp(comp: dict, record: dict, extra: dict, x0: float, y0: float, pno: int, pcount: int):
        kind = comp.get("type") or "text"
        x = x0 + float(comp.get("x") or 0)
        y = y0 + float(comp.get("y") or 0)
        wdt = float(comp.get("w") or 40)
        hgt = float(comp.get("h") or 6)
        size = int(comp.get("fontSize") or 11)
        bold = "B" if comp.get("bold") else ""
        align = {"left": "L", "center": "C", "right": "R", "L": "L", "C": "C", "R": "R"}.get(
            str(comp.get("align") or "L"), "L"
        )
        rgb = hex_rgb(comp.get("color"))
        pdf.set_text_color(*rgb)
        pdf.set_font("Sarabun", bold, size)
        if kind == "line":
            pdf.set_draw_color(*GOLD)
            pdf.line(x, y, x + wdt, y)
            return
        if kind == "rectangle":
            pdf.set_draw_color(*BURGUNDY)
            pdf.rect(x, y, wdt, hgt)
            return
        if kind == "pageBreak":
            return
        if kind == "barcode":
            text = _comp_text(comp, record, pno, pcount, extra)
            _draw_barcode(pdf, x, y, wdt, hgt, text)
            return
        if kind == "qrcode":
            text = _comp_text(comp, record, pno, pcount, extra)
            _draw_qr(pdf, x, y, min(wdt, hgt), text)
            return
        if kind == "chart":
            _draw_chart(pdf, x, y, wdt, hgt, rows, str(comp.get("field") or ""))
            return
        if kind == "image" and comp.get("src"):
            src = str(comp.get("src"))
            if src.startswith("/") and Path(src).exists():
                try:
                    pdf.image(src, x=x, y=y, w=wdt, h=hgt)
                except Exception:
                    log.exception("image failed")
            return
        text = _comp_text(comp, record, pno, pcount, extra)
        if comp.get("background"):
            pdf.set_fill_color(*hex_rgb(comp.get("background"), (247, 241, 230)))
            pdf.rect(x, y, wdt, hgt, style="F")
        pdf.set_xy(x, y)
        pdf.multi_cell(max(wdt, 8), max(hgt, 5), text or " ", align=align)

    def draw_table(comp: dict, dataset: list[dict], extra: dict, y: float) -> float:
        cols = list(comp.get("columns") or [])
        if not cols:
            return y
        usable = w - margin["left"] - margin["right"]
        total_w = sum(float(c.get("width") or 25) for c in cols) or 1
        widths = [usable * float(c.get("width") or 25) / total_w for c in cols]
        row_h = 7
        x0 = margin["left"]

        def header_row(yy: float) -> float:
            pdf.set_fill_color(247, 241, 230)
            pdf.set_font("Sarabun", "B", int(comp.get("fontSize") or 9))
            pdf.set_text_color(*BURGUNDY)
            pdf.set_xy(x0, yy)
            for wd, col in zip(widths, cols):
                pdf.cell(wd, row_h, str(col.get("label") or col.get("field") or "")[:40], border=1, fill=True)
            return yy + row_h

        def maybe_break(yy: float) -> float:
            if yy + row_h > band_y_limit():
                draw_footer_now()
                new_page()
                yy = margin["top"]
                yy = header_row(yy) if comp.get("header", True) else yy
            return yy

        if y + 20 > band_y_limit():
            draw_footer_now()
            new_page()
            y = margin["top"]
        if comp.get("header", True):
            y = header_row(y)
        pdf.set_font("Sarabun", "", int(comp.get("fontSize") or 9))
        pdf.set_text_color(*INK)
        for rec in dataset:
            y = maybe_break(y)
            pdf.set_xy(x0, y)
            for wd, col in zip(widths, cols):
                val = format_value(rec.get(col.get("field")), col.get("format"), col.get("field"))[:48]
                pdf.cell(wd, row_h, val, border=1)
            y += row_h
        if comp.get("footer"):
            y = maybe_break(y)
            pdf.set_font("Sarabun", "B", int(comp.get("fontSize") or 9))
            pdf.set_xy(x0, y)
            for i, (wd, col) in enumerate(zip(widths, cols)):
                agg = (col.get("agg") or comp.get("footerAgg") or "").upper()
                if i == 0 and not col.get("agg"):
                    txt = "รวมทั้งหมด"
                elif agg:
                    txt = str(format_value(aggregate(dataset, str(col.get("field")), agg), "number"))
                else:
                    txt = ""
                pdf.cell(wd, row_h, txt[:40], border=1)
            y += row_h
        return y + 2

    footer_drawn_for = {"n": 0}

    def draw_footer_now():
        if footer_drawn_for["n"] == page_no:
            return
        footer_drawn_for["n"] = page_no
        sec = section_by_type(layout, "pageFooter")
        y = h - margin["bottom"] - float(sec.get("height") or 10)
        extra = {"_title": title}
        rec = rows[0] if rows else {}
        for comp in sec.get("components") or []:
            draw_comp(comp, rec, extra, margin["left"], y, page_no, page_count_est)

    new_page()
    extra = {"_title": title, "_total": len(rows)}
    first = rows[0] if rows else {}
    y = margin["top"]
    y = draw_section("reportHeader", first, extra, y, rows)
    y = draw_section("pageHeader", first, extra, y, rows)
    if not rows:
        pdf.set_xy(margin["left"], y + 10)
        pdf.set_font("Sarabun", "", 12)
        pdf.cell(0, 8, "ไม่มีข้อมูลตามเงื่อนไขที่เลือก")
        draw_footer_now()
        out = io.BytesIO()
        pdf.output(out)
        return out.getvalue()

    for gkey, grows in groups:
        extra_g = {**extra, "_group": gkey, "_group_count": len(grows)}
        if group_field:
            pdf.set_font("Sarabun", "B", 11)
            pdf.set_text_color(*BURGUNDY)
            if y + 12 > band_y_limit():
                draw_footer_now()
                new_page()
                y = margin["top"]
            pdf.set_xy(margin["left"], y)
            pdf.cell(0, 8, f"{group_field}: {gkey or '-'}  ({len(grows)} รายการ)")
            y += 9
            y = draw_section("groupHeader", {group_field: gkey, **(grows[0] if grows else {})}, extra_g, y, grows)
        y = draw_section("detail", grows[0], extra_g, y, grows)
        if group_field:
            pdf.set_font("Sarabun", "B", 10)
            pdf.set_xy(margin["left"], y)
            pdf.cell(0, 7, f"รวม {len(grows)} รายการ")
            y += 8
            y = draw_section("groupFooter", grows[0], extra_g, y, grows)
    y = draw_section("reportFooter", first, extra, y, rows)
    draw_footer_now()
    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()


def _draw_barcode(pdf: FPDF, x: float, y: float, w: float, h: float, text: str) -> None:
    payload = "*" + "".join(ch for ch in text.upper() if ch in CODE39)[:20] + "*"
    if payload == "**":
        payload = "*0*"
    patterns = "".join(CODE39.get(ch, CODE39["0"]) + "n" for ch in payload)
    bar_w = max(0.25, w / max(len(patterns), 1))
    pdf.set_fill_color(*INK)
    cx = x
    for bit in patterns:
        bw = bar_w * (2.2 if bit == "w" else 1)
        # n/w are widths; we alternate black/white via index
        cx += bw
    # simpler: hash-based bars so it always fits
    digest = hashlib.sha1(text.encode("utf-8", "replace")).digest()
    cx = x
    unit = max(0.35, w / 80)
    for i, b in enumerate(digest * 3):
        if cx >= x + w:
            break
        if b % 2 == 0:
            pdf.rect(cx, y, unit, max(h - 4, 6), style="F")
        cx += unit
    pdf.set_xy(x, y + h - 4)
    pdf.set_font("Sarabun", "", 7)
    pdf.cell(w, 4, text[:24], align="C")


def _draw_qr(pdf: FPDF, x: float, y: float, size: float, text: str) -> None:
    try:
        import qrcode
    except ImportError:
        pdf.set_xy(x, y)
        pdf.set_font("Sarabun", "", 8)
        pdf.multi_cell(size, 4, text or "QR")
        return
    try:
        img = qrcode.make(text or " ")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        pdf.image(buf, x=x, y=y, w=size, h=size)
    except Exception:
        log.exception("qr render failed")
        pdf.set_xy(x, y)
        pdf.multi_cell(size, 4, text[:40])


def _draw_chart(pdf: FPDF, x: float, y: float, w: float, h: float, rows: list[dict], field: str) -> None:
    counts: dict[str, int] = {}
    for rec in rows:
        key = str(rec.get(field) or "-")[:18]
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return
    mx = max(counts.values()) or 1
    items = list(counts.items())[:6]
    row_h = min(8, h / max(len(items), 1))
    pdf.set_font("Sarabun", "", 8)
    cy = y
    for k, v in items:
        bw = (w - 40) * v / mx
        pdf.set_fill_color(*GOLD)
        pdf.rect(x + 32, cy + 1, max(bw, 1), row_h - 2, style="F")
        pdf.set_xy(x, cy)
        pdf.cell(32, row_h, k)
        cy += row_h


def pdf_bytes_response(data: bytes, filename: str):
    return pdf_response(data, filename)
