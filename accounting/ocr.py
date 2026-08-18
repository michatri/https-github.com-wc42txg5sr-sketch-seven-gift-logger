"""Parse Thai bank transfer / payment slip OCR text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from accounting.money import MoneyError, parse_baht

THAI_MONTHS = {
    "มกราคม": 1,
    "ม.ค.": 1,
    "ม.ค": 1,
    "กุมภาพันธ์": 2,
    "ก.พ.": 2,
    "ก.พ": 2,
    "มีนาคม": 3,
    "มี.ค.": 3,
    "มี.ค": 3,
    "เมษายน": 4,
    "เม.ย.": 4,
    "เม.ย": 4,
    "พฤษภาคม": 5,
    "พ.ค.": 5,
    "พ.ค": 5,
    "มิถุนายน": 6,
    "มิ.ย.": 6,
    "มิ.ย": 6,
    "กรกฎาคม": 7,
    "ก.ค.": 7,
    "ก.ค": 7,
    "สิงหาคม": 8,
    "ส.ค.": 8,
    "ส.ค": 8,
    "กันยายน": 9,
    "ก.ย.": 9,
    "ก.ย": 9,
    "ตุลาคม": 10,
    "ต.ค.": 10,
    "ต.ค": 10,
    "พฤศจิกายน": 11,
    "พ.ย.": 11,
    "พ.ย": 11,
    "ธันวาคม": 12,
    "ธ.ค.": 12,
    "ธ.ค": 12,
}

BANKS = [
    ("กสิกรไทย", ("กสิกร", "kbank", "k plus", "kplus", "kasikorn")),
    ("ไทยพาณิชย์", ("ไทยพาณิชย์", "scb", "scbeasy")),
    ("กรุงไทย", ("กรุงไทย", "krungthai", "ktb", "เป๋าตัง")),
    ("กรุงเทพ", ("กรุงเทพ", "bbl", "bangkok bank")),
    ("กรุงศรี", ("กรุงศรี", "krungsri", "baya", "ayuthaya")),
    ("ทหารไทยธนชาต", ("ทหารไทย", "ธนชาต", "ttb", "tmb")),
    ("ออมสิน", ("ออมสิน", "gsb")),
    ("ธกส.", ("ธกส", "baac")),
    ("พร้อมเพย์", ("พร้อมเพย์", "promptpay", "prompt pay")),
]

INCOME_HINTS = (
    "เงินเข้า",
    "รับโอน",
    "ได้รับ",
    "โอนเข้า",
    "รับเงิน",
    "incoming",
    "received",
    "deposit",
    "เติมเงิน",
    "เครดิต",
)
EXPENSE_HINTS = (
    "โอนเงิน",
    "โอนออก",
    "ชำระ",
    "จ่าย",
    "payment",
    "transfer",
    "ค่าธรรมเนียม",
    "บิล",
    "สำเร็จ",
)


@dataclass
class SlipGuess:
    amount_satang: int | None = None
    txn_date: str | None = None
    kind: str = "expense"
    bank_name: str = ""
    reference: str = ""
    description: str = ""
    notes: list[str] = field(default_factory=list)


def parse_bank_slip_text(text: str) -> SlipGuess:
    guess = SlipGuess()
    if not text or not text.strip():
        guess.notes.append("อ่านข้อความจากรูปไม่ได้ กรุณากรอกเอง")
        return guess

    normalized = text.replace("\u00a0", " ")
    lowered = normalized.lower()

    guess.bank_name = _detect_bank(lowered)
    guess.amount_satang = _detect_amount(normalized)
    guess.txn_date = _detect_date(normalized) or date.today().isoformat()
    guess.kind = _detect_kind(lowered)
    guess.reference = _detect_reference(normalized)
    parts = [guess.bank_name or "สลิปธนาคาร"]
    if guess.reference:
        parts.append(f"อ้างอิง {guess.reference}")
    guess.description = " · ".join(parts)
    if guess.amount_satang:
        guess.notes.append("ดึงจำนวนเงินจากสลิปแล้ว กรุณาตรวจก่อนบันทึก")
    else:
        guess.notes.append("ไม่พบจำนวนเงินชัดเจน กรุณากรอกเอง")
    return guess


def _detect_bank(lowered: str) -> str:
    for name, needles in BANKS:
        if any(needle in lowered for needle in needles):
            return name
    return ""


def _detect_kind(lowered: str) -> str:
    if any(hint in lowered for hint in INCOME_HINTS):
        return "income"
    if any(hint in lowered for hint in EXPENSE_HINTS):
        return "expense"
    return "expense"


def _detect_reference(text: str) -> str:
    patterns = [
        r"(?:เลขที่อ้างอิง|อ้างอิง|ref(?:erence)?(?: no\.?)?)\s*[:#]?\s*([A-Za-z0-9\-]+)",
        r"(?:txn(?:\s*id)?|transaction id)\s*[:#]?\s*([A-Za-z0-9\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _to_ad_year(year: int) -> int:
    if year >= 2400:
        return year - 543
    return year


def _detect_date(text: str) -> str | None:
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if match:
        day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if year < 100:
            year += 2500 if year >= 50 else 2000
        year = _to_ad_year(year)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass

    month_alt = "|".join(re.escape(name) for name in sorted(THAI_MONTHS, key=len, reverse=True))
    match = re.search(rf"(\d{{1,2}})\s+({month_alt})\s+(\d{{4}})", text)
    if match:
        day = int(match.group(1))
        month = THAI_MONTHS[match.group(2)]
        year = _to_ad_year(int(match.group(3)))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    return None


def _detect_amount(text: str) -> int | None:
    labeled = re.findall(
        r"(?:จำนวนเงิน|จำนวน|ยอด(?:เงิน)?|amount|total|thb|บาท)\s*[:\-]?[\s฿]*([0-9][0-9,]*(?:\.\d{1,2})?)",
        text,
        flags=re.IGNORECASE,
    )
    candidates = list(labeled)
    candidates.extend(re.findall(r"฿\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text))
    if not candidates:
        candidates = re.findall(r"\b([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d{2})|[0-9]+\.\d{2})\b", text)

    best = None
    for raw in candidates:
        try:
            satang = parse_baht(raw)
        except MoneyError:
            continue
        if satang <= 0 or satang > 10_000_000_000:
            continue
        if best is None or satang > best:
            best = satang
    return best
