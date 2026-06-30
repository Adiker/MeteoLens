from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

SOURCE_TIMEZONE = ZoneInfo("Europe/Warsaw")


def missing_fields(row: dict[str, object], fields: list[str]) -> list[str]:
    return [field for field in fields if row.get(field) in (None, "")]


def parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(Decimal(str(value).replace(",", ".")))
    except (InvalidOperation, ValueError):
        return None


def parse_int(value: object) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=SOURCE_TIMEZONE)
        except ValueError:
            continue
    return None


def parse_synop_datetime(date_value: object, hour_value: object) -> datetime | None:
    if date_value in (None, "") or hour_value in (None, ""):
        return None
    try:
        hour = int(str(hour_value))
        return datetime.strptime(str(date_value), "%Y-%m-%d").replace(
            hour=hour,
            tzinfo=SOURCE_TIMEZONE,
        )
    except ValueError:
        return None

