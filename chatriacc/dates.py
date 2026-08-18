"""วันที่และปีบัญชีแบบไทย."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BANGKOK = ZoneInfo("Asia/Bangkok")

THAI_MONTHS = [
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
]

THAI_MONTHS_SHORT = [
    "",
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
]


def today() -> date:
    return datetime.now(BANGKOK).date()


def now_iso() -> str:
    return datetime.now(BANGKOK).replace(microsecond=0).isoformat()


def buddhist_year(year: int) -> int:
    return int(year) + 543


def year_label(year: int) -> str:
    return f"{int(year)} / {buddhist_year(int(year))}"


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)) and 20000 < float(value) < 80000:
        return (datetime(1899, 12, 30) + timedelta(days=int(value))).date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def iso_date(value) -> str:
    d = parse_date(value)
    return d.isoformat() if d else ""


def thai_date(value, short: bool = False) -> str:
    d = parse_date(value)
    if not d:
        return ""
    months = THAI_MONTHS_SHORT if short else THAI_MONTHS
    return f"{d.day} {months[d.month]} {buddhist_year(d.year)}"
