"""Synthetic GRIB1 encoder for parser and rendering tests.

Encodes the narrow GRIB1 subset the app decodes (simple packing, rotated
lat/lon GDS). Test-only; never used against real IMGW data.
"""

import numpy as np


def encode_ibm32(value: float) -> bytes:
    if value == 0.0:
        return b"\x00\x00\x00\x00"
    sign = 0x80 if value < 0 else 0
    value = abs(value)
    exponent = 64
    mantissa = value * (2.0**24)
    while mantissa >= 2.0**24:
        mantissa /= 16.0
        exponent += 1
    while mantissa < 2.0**20 and exponent > 0:
        mantissa *= 16.0
        exponent -= 1
    return bytes((sign | exponent,)) + round(mantissa).to_bytes(3, "big")


def _signed_24(value: float) -> bytes:
    raw = round(abs(value))
    if value < 0:
        raw |= 0x800000
    return raw.to_bytes(3, "big")


def _signed_16(value: int) -> bytes:
    raw = abs(value)
    if value < 0:
        raw |= 0x8000
    return raw.to_bytes(2, "big")


def encode_grib1_message(
    values: np.ndarray,
    *,
    parameter: int = 11,
    level_type: int = 105,
    level: int = 2,
    reference_time: tuple[int, int, int, int, int] = (2026, 7, 4, 0, 0),
    p1_hours: int = 1,
    south_pole: tuple[float, float] = (-40.0, 10.0),
    first: tuple[float, float] = (-2.4, 0.65),
    step: tuple[float, float] = (0.025, 0.025),
    scan: int = 0x40,
    bitmap: np.ndarray | None = None,
    bits_per_value: int = 8,
    decimal_scale: int = 0,
    binary_scale: int = 0,
    reference_value: float = 0.0,
) -> bytes:
    """Encode one GRIB1 message; ``values`` is (nj, ni) with row 0 south."""
    nj, ni = values.shape
    year, month, day, hour, minute = reference_time
    year_of_century = year % 100
    century = year // 100 + 1
    flags = 0x80 | (0x40 if bitmap is not None else 0)

    pds = bytearray(28)
    pds[0:3] = (28).to_bytes(3, "big")
    pds[3] = 2
    pds[7] = flags
    pds[8] = parameter
    pds[9] = level_type
    pds[10:12] = level.to_bytes(2, "big")
    pds[12] = year_of_century
    pds[13] = month
    pds[14] = day
    pds[15] = hour
    pds[16] = minute
    pds[17] = 1  # unit: hours
    pds[18] = p1_hours
    pds[20] = 0  # time range: forecast valid at reference + P1
    pds[24] = century
    pds[26:28] = _signed_16(decimal_scale)

    first_lat, first_lon = first
    dlat, dlon = step
    last_lat = first_lat + dlat * (nj - 1)
    last_lon = first_lon + dlon * (ni - 1)
    if not scan & 0x40:
        first_lat, last_lat = last_lat, first_lat
    gds = bytearray(42)
    gds[0:3] = (42).to_bytes(3, "big")
    gds[4] = 255
    gds[5] = 10  # rotated lat/lon
    gds[6:8] = ni.to_bytes(2, "big")
    gds[8:10] = nj.to_bytes(2, "big")
    gds[10:13] = _signed_24(first_lat * 1000)
    gds[13:16] = _signed_24(first_lon * 1000)
    gds[16] = 0x80  # increments given
    gds[17:20] = _signed_24(last_lat * 1000)
    gds[20:23] = _signed_24(last_lon * 1000)
    gds[23:25] = round(dlon * 1000).to_bytes(2, "big")
    gds[25:27] = round(dlat * 1000).to_bytes(2, "big")
    gds[27] = scan
    gds[32:35] = _signed_24(south_pole[0] * 1000)
    gds[35:38] = _signed_24(south_pole[1] * 1000)

    ordered = values if scan & 0x40 else values[::-1, :]
    flat = ordered.reshape(-1)
    if bitmap is not None:
        ordered_bitmap = bitmap if scan & 0x40 else bitmap[::-1, :]
        bitmap_flat = ordered_bitmap.reshape(-1).astype(bool)
        flat = flat[bitmap_flat]
        bitmap_bits = np.packbits(bitmap_flat.astype(np.uint8))
        unused = (8 - bitmap_flat.size % 8) % 8
        bms = bytearray(6)
        bms[3] = unused
        bms_bytes = bytes(bms) + bitmap_bits.tobytes()
        bms_len = len(bms_bytes)
        bms_final = bms_len.to_bytes(3, "big") + bms_bytes[3:]
    else:
        bms_final = b""

    packed_ints = np.round(
        (flat * (10.0**decimal_scale) - reference_value) / (2.0**binary_scale)
    ).astype(np.int64)
    if packed_ints.min() < 0 or packed_ints.max() >= 2**bits_per_value:
        raise ValueError("values do not fit the requested packing")
    bits = np.zeros((packed_ints.size, bits_per_value), dtype=np.uint8)
    for position in range(bits_per_value):
        bits[:, position] = (packed_ints >> (bits_per_value - 1 - position)) & 1
    data_bits = bits.reshape(-1)
    unused_bits = (8 - data_bits.size % 8) % 8
    data_bytes = np.packbits(data_bits).tobytes()

    bds = bytearray(11)
    bds[3] = unused_bits  # flags 0 (grid point, simple packing)
    bds[4:6] = _signed_16(binary_scale)
    bds[6:10] = encode_ibm32(reference_value)
    bds[10] = bits_per_value
    bds_bytes = bytes(bds) + data_bytes
    bds_final = len(bds_bytes).to_bytes(3, "big") + bds_bytes[3:]

    body = bytes(pds) + bytes(gds) + bms_final + bds_final
    total = 8 + len(body) + 4
    return b"GRIB" + total.to_bytes(3, "big") + bytes((1,)) + body + b"7777"
