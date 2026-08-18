"""จำนวนเงินเก็บเป็นสตางค์ (integer) เพื่อไม่ให้ทศนิยมคลาดเคลื่อน."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

THAI_ONES = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
THAI_PLACE = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def baht_to_satang(value) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value * 100
    text = str(value).strip().replace(",", "").replace("บาท", "").replace(" ", "")
    if not text:
        return 0
    amount = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def satang_to_baht(satang: int | None) -> Decimal:
    return (Decimal(satang or 0) / Decimal(100)).quantize(Decimal("0.01"))


def format_baht(satang: int | None) -> str:
    n = satang_to_baht(satang)
    formatted = f"{n:,.2f}"
    return formatted


def _read_six(n: int) -> str:
    if n == 0:
        return ""
    parts = []
    s = f"{n:06d}"
    digits = [int(ch) for ch in s]
    for i, d in enumerate(digits):
        if d == 0:
            continue
        place = 5 - i
        if place == 1:
            if d == 1:
                parts.append("สิบ")
            elif d == 2:
                parts.append("ยี่สิบ")
            else:
                parts.append(THAI_ONES[d] + "สิบ")
        elif place == 0:
            if d == 1 and n % 100 >= 10:
                parts.append("เอ็ด")
            else:
                parts.append(THAI_ONES[d])
        else:
            parts.append(THAI_ONES[d] + THAI_PLACE[place])
    return "".join(parts)


def baht_text(satang: int | None) -> str:
    """แปลงสตางค์เป็นข้อความไทย เช่น 'สองพันแปดร้อยหกสิบห้าบาทถ้วน'."""
    amount = int(satang or 0)
    negative = amount < 0
    amount = abs(amount)
    baht, st = divmod(amount, 100)
    if baht == 0 and st == 0:
        words = "ศูนย์บาทถ้วน"
    else:
        million, rest = divmod(baht, 1_000_000)
        body = ""
        if million:
            body += _read_six(million) + "ล้าน"
        body += _read_six(rest)
        if not body:
            body = "ศูนย์"
        if st == 0:
            words = body + "บาทถ้วน"
        else:
            words = body + "บาท" + (_read_six(st) or "ศูนย์") + "สตางค์"
    if negative:
        words = "ลบ" + words
    return words
