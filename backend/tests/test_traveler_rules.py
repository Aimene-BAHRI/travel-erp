from datetime import date

import pytest

from travelers.rules import (
    parse_td3_mrz,
    passenger_category_code,
    passport_validity,
)


def test_passenger_category_uses_trip_return_date_boundaries():
    returned = date(2026, 9, 15)

    assert passenger_category_code(date(2024, 9, 16), returned) == "INF"
    assert passenger_category_code(date(2024, 9, 15), returned) == "CHD"
    assert passenger_category_code(date(2014, 9, 16), returned) == "CHD"
    assert passenger_category_code(date(2014, 9, 15), returned) == "ADT"


def test_passport_requires_six_calendar_months_after_return():
    returned = date(2026, 9, 15)

    assert passport_validity(date(2027, 3, 15), returned).is_valid
    result = passport_validity(date(2027, 3, 14), returned)
    assert not result.is_valid
    assert result.status == "LESS_THAN_SIX_MONTHS"
    assert result.required_until == date(2027, 3, 15)


def test_td3_mrz_parser_extracts_identity_fields():
    mrz = (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
    )

    parsed = parse_td3_mrz(mrz, reference_date=date(2026, 9, 15))

    assert parsed["passport_number"] == "L898902C3"
    assert parsed["first_name"] == "ANNA"
    assert parsed["middle_name"] == "MARIA"
    assert parsed["last_name"] == "ERIKSSON"
    assert parsed["birth_date"] == date(1974, 8, 12)
    assert parsed["gender"] == "F"


def test_td3_mrz_parser_rejects_ocr_check_digit_errors():
    mrz = (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C36UTO7408123F1204159ZE184226B<<<<<10"
    )

    with pytest.raises(ValueError, match="check digit failed"):
        parse_td3_mrz(mrz, reference_date=date(2026, 9, 15))


def test_td3_mrz_parser_repairs_common_scanner_confusions():
    mrz = (
        r"PK\<DZABENATTALLAHS\<KHADIDJA\<KLLLLLLLLLLLLKLL" "\n"
        r"1773708760DZAB507055F2707141X170<<<<<K<<K<<<"
    )

    parsed = parse_td3_mrz(mrz, reference_date=date(2026, 9, 15))

    assert parsed["passport_number"] == "177370876"
    assert parsed["first_name"] == "KHADIDJA"
    assert parsed["last_name"] == "BENATTALLAHS"
    assert parsed["birth_date"] == date(1985, 7, 5)
    assert parsed["expiry_date"] == date(2027, 7, 14)
    assert parsed["gender"] == "F"
    assert parsed["mrz_warnings"] == ["optional data", "composite"]
