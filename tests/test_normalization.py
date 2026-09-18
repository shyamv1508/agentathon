from stage1.normalization import parse_number, parse_date

def test_qualified_number():
    assert parse_number("<5") == (5.0, "<")
    assert parse_number("12,4") == (12.4, None)

def test_unknown_number():
    assert parse_number("ND")[1] == "unknown"

def test_dates():
    assert str(parse_date("31-Jan-2026")) == "2026-01-31"
