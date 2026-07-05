"""Minimal pure-Python GRIB edition 1 reader.

Scope is deliberately narrow: sequential record scan plus simple-packing
decode of regular grids, which is exactly what the public IMGW-PIB COSMO
files use (see docs/products/PRODUCT_RESEARCH.md). Anything outside that
scope raises Grib1Error instead of guessing.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

GRIB_MAGIC = b"GRIB"

# PDS octet 8 flags.
_FLAG_GDS_PRESENT = 0x80
_FLAG_BMS_PRESENT = 0x40

# GDS data representation types we understand.
GRID_TYPE_LATLON = 0
GRID_TYPE_ROTATED_LATLON = 10

# PDS octet 18 forecast time units (WMO code table 4).
_TIME_UNIT_HOURS = {0: 1 / 60, 1: 1, 2: 24, 10: 3, 11: 6, 12: 12}


class Grib1Error(ValueError):
    """Raised when a GRIB1 message cannot be parsed within supported scope."""


@dataclass(frozen=True)
class Grib1Grid:
    representation_type: int
    ni: int
    nj: int
    lat1: float
    lon1: float
    lat2: float
    lon2: float
    di: float
    dj: float
    scan_i_negative: bool
    scan_j_positive: bool
    south_pole_lat: float | None = None
    south_pole_lon: float | None = None

    @property
    def rotated(self) -> bool:
        return self.representation_type == GRID_TYPE_ROTATED_LATLON


@dataclass(frozen=True)
class Grib1Record:
    offset: int
    length: int
    parameter: int
    level_type: int
    level: int
    reference_time: datetime
    forecast_hours: float | None
    decimal_scale: int
    grid: Grib1Grid | None
    _data: bytes

    @property
    def valid_time(self) -> datetime | None:
        if self.forecast_hours is None:
            return None
        return self.reference_time + timedelta(hours=self.forecast_hours)

    def values(self) -> np.ndarray:
        """Decode the record into a (nj, ni) float array, NaN where masked.

        Rows are normalised so index 0 is the southernmost row and columns
        run west to east, regardless of the scanning mode in the file.
        """
        return _decode_values(self)


def iter_records(data: bytes):
    """Yield Grib1Record headers from a byte buffer without decoding data."""
    pos = 0
    while True:
        pos = data.find(GRIB_MAGIC, pos)
        if pos < 0:
            return
        if len(data) - pos < 8:
            return
        total_length = int.from_bytes(data[pos + 4 : pos + 7], "big")
        edition = data[pos + 7]
        if edition != 1 or total_length < 32 or pos + total_length > len(data):
            pos += 4
            continue
        message = data[pos : pos + total_length]
        if message[-4:] != b"7777":
            pos += 4
            continue
        try:
            yield _parse_message(message, offset=pos)
        except Grib1Error:
            # A malformed record must not hide the rest of the file.
            pass
        pos += total_length


def find_record(
    data: bytes,
    *,
    parameter: int,
    level_type: int,
    level: int,
) -> Grib1Record | None:
    for record in iter_records(data):
        if (
            record.parameter == parameter
            and record.level_type == level_type
            and record.level == level
        ):
            return record
    return None


def _parse_message(message: bytes, *, offset: int) -> Grib1Record:
    pos = 8
    pds = _section(message, pos, "PDS")
    pos += len(pds)

    flags = pds[7]
    parameter = pds[8]
    level_type = pds[9]
    level = int.from_bytes(pds[10:12], "big")
    reference_time = _reference_time(pds)
    forecast_hours = _forecast_hours(pds)
    decimal_scale = _signed_16(pds[26:28])

    grid: Grib1Grid | None = None
    if flags & _FLAG_GDS_PRESENT:
        gds = _section(message, pos, "GDS")
        pos += len(gds)
        grid = _parse_gds(gds)

    return Grib1Record(
        offset=offset,
        length=len(message),
        parameter=parameter,
        level_type=level_type,
        level=level,
        reference_time=reference_time,
        forecast_hours=forecast_hours,
        decimal_scale=decimal_scale,
        grid=grid,
        _data=message,
    )


def _decode_values(record: Grib1Record) -> np.ndarray:
    message = record._data
    pos = 8
    pds = _section(message, pos, "PDS")
    pos += len(pds)
    flags = pds[7]

    if flags & _FLAG_GDS_PRESENT:
        gds = _section(message, pos, "GDS")
        pos += len(gds)

    bitmap: np.ndarray | None = None
    if flags & _FLAG_BMS_PRESENT:
        bms = _section(message, pos, "BMS")
        pos += len(bms)
        bitmap = _parse_bms(bms)

    bds = _section(message, pos, "BDS")
    grid = record.grid
    if grid is None:
        raise Grib1Error("Records without a GDS are not supported.")

    values = _parse_bds(bds, record.decimal_scale, expected=grid.ni * grid.nj, bitmap=bitmap)
    array = values.reshape(grid.nj, grid.ni)
    if grid.scan_i_negative:
        array = array[:, ::-1]
    if not grid.scan_j_positive:
        array = array[::-1, :]
    return array


def _parse_gds(gds: bytes) -> Grib1Grid:
    representation_type = gds[5]
    if representation_type not in (GRID_TYPE_LATLON, GRID_TYPE_ROTATED_LATLON):
        raise Grib1Error(
            f"Unsupported GRIB1 grid representation type {representation_type}."
        )
    ni = int.from_bytes(gds[6:8], "big")
    nj = int.from_bytes(gds[8:10], "big")
    if ni == 0xFFFF or nj == 0xFFFF:
        raise Grib1Error("Quasi-regular GRIB1 grids are not supported.")
    lat1 = _signed_24(gds[10:13]) / 1000.0
    lon1 = _signed_24(gds[13:16]) / 1000.0
    lat2 = _signed_24(gds[17:20]) / 1000.0
    lon2 = _signed_24(gds[20:23]) / 1000.0
    di = int.from_bytes(gds[23:25], "big") / 1000.0
    dj = int.from_bytes(gds[25:27], "big") / 1000.0
    scan = gds[27]

    south_pole_lat: float | None = None
    south_pole_lon: float | None = None
    if representation_type == GRID_TYPE_ROTATED_LATLON:
        if len(gds) < 38:
            raise Grib1Error("Rotated lat/lon GDS is truncated.")
        south_pole_lat = _signed_24(gds[32:35]) / 1000.0
        south_pole_lon = _signed_24(gds[35:38]) / 1000.0

    return Grib1Grid(
        representation_type=representation_type,
        ni=ni,
        nj=nj,
        lat1=lat1,
        lon1=lon1,
        lat2=lat2,
        lon2=lon2,
        di=di,
        dj=dj,
        scan_i_negative=bool(scan & 0x80),
        scan_j_positive=bool(scan & 0x40),
        south_pole_lat=south_pole_lat,
        south_pole_lon=south_pole_lon,
    )


def _parse_bms(bms: bytes) -> np.ndarray:
    unused_bits = bms[3]
    table_reference = int.from_bytes(bms[4:6], "big")
    if table_reference != 0:
        raise Grib1Error("Predefined GRIB1 bitmaps are not supported.")
    bits = np.unpackbits(np.frombuffer(bms[6:], dtype=np.uint8))
    if unused_bits:
        bits = bits[: len(bits) - unused_bits]
    return bits.astype(bool)


def _parse_bds(
    bds: bytes,
    decimal_scale: int,
    *,
    expected: int,
    bitmap: np.ndarray | None,
) -> np.ndarray:
    flags = bds[3] >> 4
    if flags & 0b1100:
        raise Grib1Error("Only grid-point simple packing is supported.")
    unused_bits = bds[3] & 0x0F
    binary_scale = _signed_16(bds[4:6])
    reference_value = _ibm32(bds[6:10])
    bits_per_value = bds[10]

    if bits_per_value == 0:
        packed = np.zeros(expected if bitmap is None else int(bitmap.sum()))
    else:
        bits = np.unpackbits(np.frombuffer(bds[11:], dtype=np.uint8))
        if unused_bits:
            bits = bits[: len(bits) - unused_bits]
        count = len(bits) // bits_per_value
        bits = bits[: count * bits_per_value].reshape(count, bits_per_value)
        weights = 2 ** np.arange(bits_per_value - 1, -1, -1, dtype=np.float64)
        packed = bits.astype(np.float64) @ weights

    values = (reference_value + packed * (2.0**binary_scale)) / (10.0**decimal_scale)

    if bitmap is None:
        if len(values) < expected:
            raise Grib1Error(
                f"GRIB1 record holds {len(values)} values, expected {expected}."
            )
        return values[:expected]

    if len(bitmap) < expected:
        raise Grib1Error("GRIB1 bitmap is shorter than the grid.")
    present = bitmap[:expected]
    if int(present.sum()) > len(values):
        raise Grib1Error("GRIB1 bitmap marks more points than packed values.")
    full = np.full(expected, np.nan)
    full[present] = values[: int(present.sum())]
    return full


def _reference_time(pds: bytes) -> datetime:
    year_of_century = pds[12]
    century = pds[24] if len(pds) > 24 else 21
    year = (century - 1) * 100 + year_of_century
    try:
        return datetime(year, pds[13], pds[14], pds[15], pds[16], tzinfo=UTC)
    except ValueError as exc:
        raise Grib1Error(f"Invalid GRIB1 reference time: {exc}") from exc


def _forecast_hours(pds: bytes) -> float | None:
    unit = pds[17]
    p1 = pds[18]
    p2 = pds[19]
    time_range = pds[20]
    factor = _TIME_UNIT_HOURS.get(unit)
    if factor is None:
        return None
    if time_range == 10:
        return int.from_bytes(bytes((p1, p2)), "big") * factor
    if time_range in (0, 1):
        return p1 * factor
    if time_range in (2, 3, 4, 5):
        return p2 * factor
    return None


def _section(message: bytes, pos: int, name: str) -> bytes:
    if pos + 3 > len(message):
        raise Grib1Error(f"GRIB1 {name} is truncated.")
    length = int.from_bytes(message[pos : pos + 3], "big")
    if length < 3 or pos + length > len(message):
        raise Grib1Error(f"GRIB1 {name} has invalid length {length}.")
    return message[pos : pos + length]


def _signed_16(raw: bytes) -> int:
    value = int.from_bytes(raw, "big")
    if value & 0x8000:
        return -(value & 0x7FFF)
    return value


def _signed_24(raw: bytes) -> int:
    value = int.from_bytes(raw, "big")
    if value & 0x800000:
        return -(value & 0x7FFFFF)
    return value


def _ibm32(raw: bytes) -> float:
    sign = -1.0 if raw[0] & 0x80 else 1.0
    exponent = raw[0] & 0x7F
    mantissa = int.from_bytes(raw[1:4], "big")
    if mantissa == 0:
        return 0.0
    return sign * mantissa * (2.0**-24) * (16.0 ** (exponent - 64))
