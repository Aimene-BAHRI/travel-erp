import calendar
from dataclasses import dataclass
from datetime import date


def age_on_date(birth_date: date, reference_date: date) -> int:
    return (
        reference_date.year
        - birth_date.year
        - ((reference_date.month, reference_date.day) < (birth_date.month, birth_date.day))
    )


def passenger_category_code(birth_date: date, return_date: date) -> str:
    age = age_on_date(birth_date, return_date)
    if age < 2:
        return "INF"
    if age < 12:
        return "CHD"
    return "ADT"


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class PassportValidity:
    status: str
    required_until: date
    is_valid: bool


def passport_validity(expiry_date: date | None, return_date: date) -> PassportValidity:
    required_until = add_calendar_months(return_date, 6)
    if expiry_date is None:
        return PassportValidity("MISSING", required_until, False)
    if expiry_date < return_date:
        return PassportValidity("EXPIRED", required_until, False)
    if expiry_date < required_until:
        return PassportValidity("LESS_THAN_SIX_MONTHS", required_until, False)
    return PassportValidity("VALID", required_until, True)


def _mrz_date(value: str, *, birth: bool, reference_year: int) -> date:
    if len(value) != 6 or not value.isdigit():
        raise ValueError("MRZ date must use YYMMDD format.")
    year = int(value[:2])
    century = 1900 if birth and year > reference_year % 100 else 2000
    return date(century + year, int(value[2:4]), int(value[4:6]))


def _mrz_check_digit(value: str) -> str:
    weights = (7, 3, 1)
    total = 0
    for index, character in enumerate(value):
        if character.isdigit():
            numeric = int(character)
        elif "A" <= character <= "Z":
            numeric = ord(character) - ord("A") + 10
        elif character == "<":
            numeric = 0
        else:
            raise ValueError("MRZ contains an unsupported character.")
        total += numeric * weights[index % 3]
    return str(total % 10)


_OCR_DIGIT_CORRECTIONS = {
    "B": "8",
    "D": "0",
    "G": "6",
    "I": "1",
    "L": "1",
    "O": "0",
    "Q": "0",
    "S": "5",
    "T": "7",
    "Z": "2",
}


def _normalize_td3_ocr(lines: list[str]) -> tuple[str, str]:
    line1, line2 = lines[0][:44], lines[1][:44]

    # Some scanners insert a false K/L before the document-type filler:
    # PK<DZA... -> P<DZA...
    if line1.startswith("P") and line1[2:3] == "<" and line1[3:6].isalpha():
        line1 = (line1[0] + line1[2:] + "<")[:44]

    names = line1[5:]
    if "<<" not in names:
        separator = names.find("<")
        if separator >= 0:
            names = (names[:separator] + "<<" + names[separator + 1 :])[:39]
    if "<<" in names:
        surname, given = names.split("<<", 1)
        filler = given.find("<")
        if filler >= 0 and set(given[filler:]) <= {"<", "K", "L"}:
            given = given[:filler] + "<" * (len(given) - filler)
        names = f"{surname}<<{given}"[:39]
    line1 = (line1[:5] + names).ljust(44, "<")[:44]

    chars = list(line2)
    for start, end in ((9, 10), (13, 20), (21, 28)):
        for index in range(start, end):
            chars[index] = _OCR_DIGIT_CORRECTIONS.get(chars[index], chars[index])
    optional = "".join(chars[28:42])
    filler = optional.find("<")
    if filler >= 0 and set(optional[filler:]) <= {"<", "K", "L"}:
        optional = optional[:filler] + "<" * (len(optional) - filler)
        chars[28:42] = optional
    return line1, "".join(chars)


def _validate_td3_check_digits(line2: str) -> list[str]:
    core_checks = [
        (line2[:9], line2[9], "passport number"),
        (line2[13:19], line2[19], "birth date"),
        (line2[21:27], line2[27], "expiry date"),
    ]
    failed = [
        name
        for value, expected, name in core_checks
        if _mrz_check_digit(value) != expected
    ]
    if failed:
        raise ValueError(f"MRZ check digit failed for: {', '.join(failed)}.")
    warnings = []
    optional_value = line2[28:42]
    optional_expected = line2[42]
    if optional_value.replace("<", "") and _mrz_check_digit(optional_value) != optional_expected:
        warnings.append("optional data")
    composite_value = line2[:10] + line2[13:20] + line2[21:43]
    if _mrz_check_digit(composite_value) != line2[43]:
        warnings.append("composite")
    return warnings


def parse_td3_mrz(mrz: str, *, reference_date: date) -> dict:
    lines = [
        line.strip().replace(" ", "").replace("\\", "").upper()
        for line in mrz.splitlines()
        if line.strip()
    ]
    if len(lines) != 2 or any(len(line) < 44 for line in lines):
        raise ValueError("Enter the two 44-character passport MRZ lines.")
    line1, line2 = _normalize_td3_ocr(lines)
    if not line1.startswith("P"):
        raise ValueError("The MRZ is not a TD3 passport document.")
    warnings = _validate_td3_check_digits(line2)
    names = line1[5:].split("<<", 1)
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
    given_parts = given.split()
    return {
        "passport_number": line2[:9].replace("<", ""),
        "first_name": given_parts[0] if given_parts else "",
        "middle_name": " ".join(given_parts[1:]),
        "last_name": surname,
        "birth_date": _mrz_date(line2[13:19], birth=True, reference_year=reference_date.year),
        "gender": line2[20] if line2[20] in {"M", "F"} else "X",
        "expiry_date": _mrz_date(line2[21:27], birth=False, reference_year=reference_date.year),
        "nationality_code": line2[10:13].replace("<", ""),
        "issuing_country_code": line1[2:5].replace("<", ""),
        "mrz": f"{line1}\n{line2}",
        "mrz_warnings": warnings,
    }
