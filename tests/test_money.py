from accounting.money import MoneyError, format_baht, parse_baht
import pytest


def test_parse_baht_plain():
    assert parse_baht("1234.56") == 123456


def test_parse_baht_with_comma_and_symbol():
    assert parse_baht("฿1,250.00") == 125000


def test_parse_baht_rounds_half_up():
    assert parse_baht("10.005") == 1001


def test_parse_baht_rejects_negative():
    with pytest.raises(MoneyError):
        parse_baht("-1")


def test_parse_baht_rejects_blank():
    with pytest.raises(MoneyError):
        parse_baht("  ")


def test_format_baht():
    assert format_baht(123456) == "฿1,234.56"
    assert format_baht(-50) == "-฿0.50"
    assert format_baht(None) == "฿0.00"
