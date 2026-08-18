import pytest

from chatriacc.dates import parse_date, thai_date, year_label
from chatriacc.money import baht_text, baht_to_satang, format_baht


def test_baht_to_satang_rounds_half_up():
    assert baht_to_satang("5838.25") == 583825
    assert baht_to_satang(2865) == 286500
    assert baht_to_satang("1,400.00") == 140000


def test_format_baht():
    assert format_baht(286500) == "2,865.00"


def test_baht_text_integer():
    assert baht_text(0) == "ศูนย์บาทถ้วน"
    assert baht_text(100) == "หนึ่งบาทถ้วน"
    assert baht_text(1100) == "สิบเอ็ดบาทถ้วน"
    assert baht_text(2100) == "ยี่สิบเอ็ดบาทถ้วน"
    assert baht_text(286500) == "สองพันแปดร้อยหกสิบห้าบาทถ้วน"


def test_baht_text_satang():
    assert baht_text(123882) == "หนึ่งพันสองร้อยสามสิบแปดบาทแปดสิบสองสตางค์"


def test_excel_serial_and_thai_date():
    d = parse_date(45658)
    assert d.isoformat() == "2025-01-01"
    assert "2568" in thai_date(d)
    assert year_label(2025) == "2025 / 2568"
