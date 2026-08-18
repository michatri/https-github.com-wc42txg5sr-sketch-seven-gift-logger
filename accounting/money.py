"""Baht amounts stored as integer satang (1 baht = 100 satang)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class MoneyError(ValueError):
    pass


def parse_baht(text: str | None) -> int:
    """Parse a user-entered baht amount into satang."""
    if text is None:
        raise MoneyError("กรุณากรอกจำนวนเงิน")
    cleaned = (
        str(text)
        .replace("฿", "")
        .replace(",", "")
        .replace(" ", "")
        .replace("\u00a0", "")
        .strip()
    )
    if not cleaned:
        raise MoneyError("กรุณากรอกจำนวนเงิน")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise MoneyError("จำนวนเงินไม่ถูกต้อง") from exc
    if value < 0:
        raise MoneyError("จำนวนเงินต้องไม่ติดลบ")
    satang = (value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(satang)


def format_baht(satang: int | None) -> str:
    """Format satang as ฿1,234.56 (Thai-style grouping)."""
    if satang is None:
        satang = 0
    sign = "-" if satang < 0 else ""
    amount = abs(int(satang))
    baht, fraction = divmod(amount, 100)
    grouped = f"{baht:,}"
    return f"{sign}฿{grouped}.{fraction:02d}"


def baht_to_satang(baht: Decimal | int | float | str) -> int:
    return parse_baht(str(baht))
