from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi.responses import Response
from fpdf import FPDF

from app.db import display_name, format_report_value, thai_date

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
BURGUNDY = (107, 29, 42)
GOLD = (138, 106, 22)
INK = (43, 33, 24)
MUTED = (110, 98, 86)

CERT_TITLES = {
    "baptism": "ใบรับรองศีลล้างบาป",
    "communion": "ใบรับรองศีลมหาสนิทแรก",
    "confirm": "ใบรับรองศีลกำลัง",
    "marriage": "ใบรับรองศีลสมรส",
    "death": "ใบรับรองมรณกรรม",
    "all": "เอกสารรับรองการรับศีลศักดิ์สิทธิ์",
}

LIST_TITLES = {
    "alpha": "รายชื่อสัตบุรุษเรียงตามอักษร",
    "saint": "รายชื่อสัตบุรุษแยกตามชื่อนักบุญ",
    "gang": "รายชื่อสัตบุรุษแยกตามกลุ่ม/สาย",
    "num": "รายชื่อสัตบุรุษเรียงตามรหัส",
    "family": "รายชื่อสัตบุรุษตามครอบครัว",
    "summary": "สรุปข้อมูลสัตบุรุษ",
}


def t(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def join(*parts: Any) -> str:
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def pdf_response(data: bytes, filename: str) -> Response:
    ascii_name = "catholic-report.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
        },
    )


class ParishPDF(FPDF):
    def __init__(self, parish: dict[str, Any], subtitle: str = "", orientation: str = "P", skip_header: bool = False):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.parish = parish or {}
        self.subtitle = subtitle
        self.skip_header = skip_header
        self.set_auto_page_break(auto=True, margin=18)
        self.add_font("Sarabun", "", str(FONTS / "Sarabun-Regular.ttf"))
        self.add_font("Sarabun", "B", str(FONTS / "Sarabun-Bold.ttf"))
        self.set_text_color(*INK)

    def header(self):
        if self.skip_header:
            return
        self.set_font("Sarabun", "B", 11)
        self.set_text_color(*GOLD)
        self.cell(0, 6, "†", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*BURGUNDY)
        self.set_font("Sarabun", "B", 14)
        self.cell(0, 7, t(self.parish.get("church_th"), "Catholic ID"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Sarabun", "", 10)
        self.set_text_color(*MUTED)
        if self.parish.get("church_en"):
            self.cell(0, 5, str(self.parish["church_en"]), align="C", new_x="LMARGIN", new_y="NEXT")
        if self.parish.get("addr_th"):
            self.multi_cell(0, 5, str(self.parish["addr_th"]), align="C")
        if self.subtitle:
            self.set_text_color(*BURGUNDY)
            self.set_font("Sarabun", "B", 16)
            self.ln(2)
            self.cell(0, 8, self.subtitle, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*GOLD)
        self.set_line_width(0.4)
        y = self.get_y() + 2
        self.line(15, y, 195 if self.w > 150 else self.w - 15, y)
        self.ln(6)
        self.set_text_color(*INK)

    def footer(self):
        self.set_y(-14)
        self.set_font("Sarabun", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"Catholic ID Web  ·  หน้า {self.page_no()} / {{nb}}", align="C")

    def kv(self, label: str, value: Any, w_label: float = 48):
        self.set_x(self.l_margin)
        y = self.get_y()
        usable = self.w - self.l_margin - self.r_margin
        self.set_font("Sarabun", "B", 11)
        self.multi_cell(w_label, 7, label)
        y_label = self.get_y()
        self.set_xy(self.l_margin + w_label, y)
        self.set_font("Sarabun", "", 11)
        self.multi_cell(usable - w_label, 7, t(value))
        self.set_y(max(y_label, self.get_y(), y + 7))

    def signatures(self, left: str = "เจ้าของประวัติ", right: str | None = None):
        right = right or t(self.parish.get("father"), "เจ้าอาวาส")
        self.ln(12)
        y = self.get_y()
        self.set_font("Sarabun", "", 11)
        self.set_xy(20, y)
        self.cell(70, 6, "ลงชื่อ .................................", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_x(20)
        self.cell(70, 6, left, align="C")
        self.set_xy(120, y)
        self.cell(70, 6, "ลงชื่อ .................................", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_x(120)
        self.cell(70, 6, right, align="C")


def _finish(pdf: ParishPDF) -> bytes:
    pdf.alias_nb_pages()
    return bytes(pdf.output())


def certificate_pdf(parish: dict, member: dict, kind: str, issued: str) -> bytes:
    title = CERT_TITLES.get(kind, CERT_TITLES["all"])
    pdf = ParishPDF(parish, title)
    pdf.add_page()
    pdf.set_font("Sarabun", "", 12)
    pdf.multi_cell(0, 8, f"ข้าพเจ้า {t(parish.get('father'), 'เจ้าอาวาส')} ขอรับรองว่า")
    pdf.ln(2)
    pdf.set_font("Sarabun", "B", 18)
    pdf.set_text_color(*BURGUNDY)
    pdf.cell(0, 10, display_name(member), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(4)
    pdf.kv("รหัสประจำตัว", member.get("num"))
    pdf.kv("เพศ / ศาสนา", f"{t(member.get('sex'))} · {t(member.get('religion'))}")
    pdf.kv("วันเกิด", thai_date(member.get("birth_date")))
    pdf.kv("บิดา", join(member.get("papa_st"), member.get("papa_nm")))
    pdf.kv("มารดา", join(member.get("mama_st"), member.get("mama_nm")))
    if kind in ("baptism", "all"):
        pdf.kv(
            "ศีลล้างบาป",
            f"เลขที่ {t(member.get('btsm_no'))} วันที่ {thai_date(member.get('btsm_date')) or '-'} "
            f"ณ {t(member.get('btsm_wat'))} พระสงฆ์ {t(member.get('btsm_priest'))} "
            f"ทูนหัว {join(member.get('btsm_st'), member.get('btsm_parent'))}",
        )
    if kind in ("communion", "all"):
        pdf.kv(
            "ศีลมหาสนิทแรก",
            f"เลขที่ {t(member.get('fm_no'))} วันที่ {thai_date(member.get('fm_date')) or '-'} "
            f"ณ {t(member.get('fm_wat'))} พระสงฆ์ {t(member.get('fm_priest'))}",
        )
    if kind in ("confirm", "all"):
        pdf.kv(
            "ศีลกำลัง",
            f"เลขที่ {t(member.get('cnfm_no'))} วันที่ {thai_date(member.get('cnfm_date')) or '-'} "
            f"ณ {t(member.get('cnfm_wat'))} พระสงฆ์ {t(member.get('cnfm_priest'))} "
            f"ทูนหัว {join(member.get('cnfm_st'), member.get('cnfm_parent'))}",
        )
    if kind in ("marriage", "all"):
        pdf.kv(
            "ศีลสมรส",
            f"เลขที่ {t(member.get('mtmn_no'))} วันที่ {thai_date(member.get('mtmn_date')) or '-'} "
            f"ณ {t(member.get('mtmn_wat'))} คู่สมรส {join(member.get('couple_st'), member.get('couple_nm'))} "
            f"พยาน {t(member.get('mtmn_father'))} / {t(member.get('mtmn_mother'))}",
        )
    if kind == "death":
        pdf.kv(
            "มรณกรรม",
            f"เลขที่ {t(member.get('dead_no'))} วันที่ {thai_date(member.get('dead_date')) or '-'} "
            f"สถานที่ {t(member.get('keep_place'))}",
        )
    pdf.ln(4)
    pdf.set_font("Sarabun", "", 12)
    pdf.cell(0, 8, f"ออกให้ ณ วันที่ {thai_date(issued) or issued}", new_x="LMARGIN", new_y="NEXT")
    pdf.signatures()
    return _finish(pdf)


def id_card_pdf(parish: dict, member: dict, photo_path: Path | None) -> bytes:
    pdf = ParishPDF(parish, "", orientation="L", skip_header=True)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    # Card box
    pdf.set_draw_color(*BURGUNDY)
    pdf.set_line_width(0.8)
    pdf.rect(18, 18, 120, 72)
    pdf.set_xy(22, 22)
    pdf.set_font("Sarabun", "B", 12)
    pdf.set_text_color(*BURGUNDY)
    pdf.cell(80, 6, t(parish.get("church_th")))
    pdf.set_xy(22, 28)
    pdf.set_font("Sarabun", "", 9)
    pdf.set_text_color(*GOLD)
    pdf.cell(80, 5, t(parish.get("church_en"), "Catholic ID Card"))
    if photo_path and photo_path.exists():
        try:
            pdf.image(str(photo_path), x=22, y=36, w=28, h=36)
        except Exception:
            pass
    pdf.set_text_color(*INK)
    pdf.set_xy(54, 36)
    pdf.set_font("Sarabun", "B", 13)
    pdf.cell(80, 7, display_name(member), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(54)
    pdf.set_font("Sarabun", "", 10)
    lines = [
        f"รหัส {t(member.get('num'))}",
        f"เกิด {thai_date(member.get('birth_date')) or '-'} · {t(member.get('sex'))}",
        f"ล้างบาป {thai_date(member.get('btsm_date')) or '-'}",
        join(member.get("address1"), member.get("address2")),
    ]
    for line in lines:
        pdf.set_x(54)
        pdf.cell(80, 5, line[:70], new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(22, 78)
    pdf.set_font("Sarabun", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(110, 5, "บัตรประจำตัวสัตบุรุษ · Catholic ID")
    return _finish(pdf)


def member_record_pdf(parish: dict, member: dict) -> bytes:
    pdf = ParishPDF(parish, "ประวัติสัตบุรุษ")
    pdf.add_page()
    pdf.set_font("Sarabun", "B", 16)
    pdf.set_text_color(*BURGUNDY)
    pdf.cell(0, 9, display_name(member), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    fields = [
        ("รหัส", member.get("num")),
        ("เพศ", member.get("sex")),
        ("ศาสนา", member.get("religion")),
        ("วันเกิด", thai_date(member.get("birth_date"))),
        ("กลุ่ม/สาย", member.get("gang")),
        ("ครอบครัว", member.get("family_no") or member.get("from_family")),
        ("อาชีพ", member.get("occupation")),
        ("ที่อยู่", join(member.get("address1"), member.get("address2"))),
        ("โทร / อีเมล", join(member.get("tel"), member.get("email"))),
        ("วัดที่สังกัด", member.get("go_church")),
        ("บิดา", join(member.get("papa_st"), member.get("papa_nm"))),
        ("มารดา", join(member.get("mama_st"), member.get("mama_nm"))),
        ("ศีลล้างบาป", f"{t(member.get('btsm_no'))} · {thai_date(member.get('btsm_date')) or '-'} · {t(member.get('btsm_wat'))}"),
        ("มหาสนิทแรก", f"{t(member.get('fm_no'))} · {thai_date(member.get('fm_date')) or '-'} · {t(member.get('fm_wat'))}"),
        ("ศีลกำลัง", f"{t(member.get('cnfm_no'))} · {thai_date(member.get('cnfm_date')) or '-'} · {t(member.get('cnfm_wat'))}"),
        ("ศีลสมรส", f"{t(member.get('mtmn_no'))} · {thai_date(member.get('mtmn_date')) or '-'} · {t(member.get('mtmn_wat'))}"),
        ("คู่สมรส", join(member.get("couple_st"), member.get("couple_nm"))),
        ("ย้ายเข้า", f"{thai_date(member.get('date_in')) or '-'} จาก {t(member.get('from_church'))}"),
        ("ย้ายออก", f"{thai_date(member.get('date_out')) or '-'} ไป {t(member.get('to_church'))}"),
        ("มรณกรรม", f"{thai_date(member.get('dead_date')) or '-'} {t(member.get('keep_place'))}"),
    ]
    for label, value in fields:
        pdf.kv(label, value)
    return _finish(pdf)


def list_pdf(parish: dict, items: list[dict], mode: str, stats_data: dict | None = None) -> bytes:
    title = LIST_TITLES.get(mode, LIST_TITLES["alpha"])
    pdf = ParishPDF(parish, title)
    pdf.add_page()
    pdf.set_font("Sarabun", "", 11)
    pdf.cell(0, 7, f"จำนวน {len(items)} รายการ", new_x="LMARGIN", new_y="NEXT")
    if mode == "summary" and stats_data:
        pdf.ln(2)
        for label, key in [
            ("ทั้งหมด", "members"),
            ("สังกัดวัด", "alive"),
            ("ชาย", "male"),
            ("หญิง", "female"),
            ("ครอบครัว", "families"),
            ("กลุ่ม/สาย", "gangs"),
            ("รับศีลล้างบาป", "baptized"),
            ("รับศีลกำลัง", "confirmed"),
            ("รับศีลสมรส", "married"),
            ("มรณกรรม", "deceased"),
        ]:
            pdf.set_font("Sarabun", "B", 11)
            pdf.cell(50, 7, label)
            pdf.set_font("Sarabun", "", 11)
            pdf.cell(0, 7, str(stats_data.get(key, 0)), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
    headers = ["รหัส", "ชื่อนักบุญ", "ชื่อ", "นามสกุล", "กลุ่ม", "ครอบครัว", "วันเกิด"]
    col_w = (32, 28, 24, 28, 16, 22, 24)
    pdf.set_font("Sarabun", "B", 9)
    pdf.set_fill_color(247, 241, 230)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 8, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Sarabun", "", 9)
    for m in items:
        row = [
            t(m.get("num"), ""),
            t(m.get("saint_name"), ""),
            t(m.get("first_name"), ""),
            t(m.get("last_name"), ""),
            t(m.get("gang"), ""),
            t(m.get("family_no") or m.get("from_family"), ""),
            thai_date(m.get("birth_date")) or "",
        ]
        if pdf.get_y() > 270:
            pdf.add_page()
            pdf.set_font("Sarabun", "B", 9)
            for w, h in zip(col_w, headers):
                pdf.cell(w, 8, h, border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("Sarabun", "", 9)
        for w, cell in zip(col_w, row):
            pdf.cell(w, 7, cell[:22], border=1)
        pdf.ln()
    return _finish(pdf)


def marriage_pdf(parish: dict, item: dict) -> bytes:
    pdf = ParishPDF(parish, "เอกสารแจ้งการสมรส")
    pdf.add_page()
    pdf.set_font("Sarabun", "", 11)
    pdf.cell(0, 7, f"Notification of Marriage  เลขที่ {t(item.get('notify_no'))}  ทะเบียนสมรส {t(item.get('marriage_id'))}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.kv("เจ้าบ่าว", f"{t(item.get('groom'))} ({t(item.get('gr_religion'))})")
    pdf.kv("ล้างบาป", f"{thai_date(item.get('gr_bap_date')) or '-'} ณ {t(item.get('gr_bap_place'))} เลขที่ {t(item.get('gr_bap_no'))}")
    pdf.kv("บิดา / มารดา", f"{t(item.get('groom_fr'))} / {t(item.get('groom_mo'))}")
    pdf.kv("เจ้าสาว", f"{t(item.get('bride'))} ({t(item.get('br_religion'))})")
    pdf.kv("ล้างบาป", f"{thai_date(item.get('br_bap_date')) or '-'} ณ {t(item.get('br_bap_place'))} เลขที่ {t(item.get('br_bap_no'))}")
    pdf.kv("บิดา / มารดา", f"{t(item.get('bride_fr'))} / {t(item.get('bride_mo'))}")
    pdf.kv("วันที่สมรส", thai_date(item.get("marriage_date")))
    pdf.kv("พระสงฆ์", item.get("priest"))
    pdf.kv("พยาน", f"{t(item.get('witness1'))} / {t(item.get('witness2'))}")
    pdf.kv("แจ้งไปยัง", item.get("notify_to"))
    pdf.kv("ผู้รับรอง", f"{t(item.get('certify_by'))} วันที่ {thai_date(item.get('certify_date')) or '-'}")
    pdf.signatures(left="พยาน", right=t(parish.get("father"), "เจ้าอาวาส"))
    return _finish(pdf)


def move_pdf(parish: dict, item: dict, member: dict | None) -> bytes:
    pdf = ParishPDF(parish, "เอกสารแจ้งย้ายสัตบุรุษ")
    pdf.add_page()
    name = display_name(member) if member else t(item.get("num"))
    pdf.set_font("Sarabun", "B", 14)
    pdf.cell(0, 8, name, new_x="LMARGIN", new_y="NEXT")
    pdf.kv("รหัส", item.get("num"))
    pdf.kv("ย้ายเข้า", f"{thai_date(item.get('date_in')) or '-'} จากวัด {t(item.get('from_church'))} เลขที่ {t(item.get('move_from_no'))}")
    pdf.kv("เจ้าอาวาสวัดเดิม", item.get("from_fr"))
    pdf.kv("ผู้บันทึกย้ายเข้า", item.get("move_in_by"))
    pdf.kv("ย้ายออก", f"{thai_date(item.get('date_out')) or '-'} ไปวัด {t(item.get('to_church'))} เลขที่ {t(item.get('move_to_no'))}")
    pdf.kv("ผู้รับสังกัด", item.get("receive_in_by"))
    pdf.kv("ผู้บันทึกย้ายออก", item.get("move_out_by"))
    pdf.signatures(left="ผู้เกี่ยวข้อง", right=t(parish.get("father"), "เจ้าอาวาส"))
    return _finish(pdf)


def envelope_pdf(parish: dict, member: dict) -> bytes:
    pdf = ParishPDF(parish, "")
    pdf.add_page()
    pdf.set_font("Sarabun", "", 12)
    pdf.multi_cell(
        0,
        8,
        f"{t(parish.get('sen'), 'เรียน')} {t(parish.get('prefix'), 'คุณ')} {display_name(member)}\n"
        f"จาก {t(parish.get('church_th'))}\n{t(parish.get('addr_th'), '')}",
    )
    pdf.ln(24)
    pdf.set_font("Sarabun", "B", 16)
    pdf.cell(0, 9, f"{t(parish.get('prefix'), 'คุณ')} {display_name(member)}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Sarabun", "", 13)
    pdf.multi_cell(0, 8, f"{t(member.get('address1'), '')}\n{t(member.get('address2'), '')}")
    return _finish(pdf)


def churches_pdf(parish: dict, items: list[dict]) -> bytes:
    pdf = ParishPDF(parish, "รายชื่อวัดคาทอลิกในประเทศไทย")
    pdf.add_page()
    pdf.set_font("Sarabun", "", 11)
    pdf.cell(0, 7, f"จำนวน {len(items)} รายการ", new_x="LMARGIN", new_y="NEXT")
    headers = ["รหัส", "ชื่อวัด", "ชื่อสามัญ", "โทร"]
    col_w = (22, 58, 58, 36)
    pdf.set_font("Sarabun", "B", 9)
    pdf.set_fill_color(247, 241, 230)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 8, h, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Sarabun", "", 8)
    for c in items:
        if pdf.get_y() > 270:
            pdf.add_page()
            pdf.set_font("Sarabun", "B", 9)
            for w, h in zip(col_w, headers):
                pdf.cell(w, 8, h, border=1, fill=True)
            pdf.ln()
            pdf.set_font("Sarabun", "", 8)
        row = [t(c.get("id"), ""), t(c.get("name"), ""), t(c.get("gen_name"), ""), t(c.get("tel"), "")]
        for w, cell in zip(col_w, row):
            pdf.cell(w, 6, cell[:40], border=1)
        pdf.ln()
    return _finish(pdf)


def _draw_design_element(pdf: ParishPDF, el: dict[str, Any], record: dict[str, Any]) -> None:
    x = float(el.get("x") or 15)
    y = float(el.get("y") or 20)
    w = float(el.get("w") or 80)
    h = float(el.get("h") or 8)
    size = int(el.get("size") or 12)
    bold = "B" if el.get("bold") else ""
    align = {"C": "C", "R": "R", "L": "L"}.get(str(el.get("align") or "L"), "L")
    kind = el.get("type") or "field"
    if kind == "line":
        pdf.set_draw_color(*GOLD)
        pdf.set_line_width(max(0.2, h if h < 2 else 0.4))
        pdf.line(x, y, x + max(w, 1), y)
        return
    if kind == "text":
        text = str(el.get("text") or "")
    else:
        value = format_report_value(record, str(el.get("field") or ""))
        label = str(el.get("label") or "")
        text = f"{label}: {value}" if el.get("show_label") and label else value
    pdf.set_xy(x, y)
    pdf.set_font("Sarabun", bold, size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(max(w, 8), max(h, 5), text, align=align)


def design_pdf(parish: dict, title: str, layout: dict[str, Any], records: list[dict[str, Any]]) -> bytes:
    records = records or [{}]
    header = bool(layout.get("header", True))
    orient = "L" if str(layout.get("orientation") or "P").upper().startswith("L") else "P"
    mode = layout.get("mode") or "form"
    pdf = ParishPDF(parish, title if header else "", orientation=orient, skip_header=not header)
    pdf.set_auto_page_break(auto=mode == "list", margin=18)
    elements = layout.get("elements") or []
    columns = layout.get("columns") or []

    if mode == "list":
        pdf.add_page()
        if columns:
            usable = pdf.w - 30
            total_w = sum(float(c.get("w") or 25) for c in columns) or 1
            widths = [usable * float(c.get("w") or 25) / total_w for c in columns]
            pdf.set_font("Sarabun", "B", 9)
            pdf.set_fill_color(247, 241, 230)
            for w, col in zip(widths, columns):
                pdf.cell(w, 8, str(col.get("label") or col.get("field") or ""), border=1, fill=True)
            pdf.ln()
            pdf.set_font("Sarabun", "", 9)
            for rec in records:
                if pdf.get_y() > (pdf.h - 22):
                    pdf.add_page()
                    pdf.set_font("Sarabun", "B", 9)
                    for w, col in zip(widths, columns):
                        pdf.cell(w, 8, str(col.get("label") or col.get("field") or ""), border=1, fill=True)
                    pdf.ln()
                    pdf.set_font("Sarabun", "", 9)
                for w, col in zip(widths, columns):
                    pdf.cell(w, 7, format_report_value(rec, str(col.get("field") or ""))[:40], border=1)
                pdf.ln()
        else:
            pdf.set_font("Sarabun", "", 12)
            pdf.cell(0, 8, "ยังไม่ได้เลือกคอลัมน์ในโหมดรายชื่อ", new_x="LMARGIN", new_y="NEXT")
        return _finish(pdf)

    for rec in records:
        pdf.add_page()
        for el in elements:
            _draw_design_element(pdf, el, rec)
    if not records:
        pdf.add_page()
    return _finish(pdf)
