"""Tiny dependency-free RGBA PNG writer with iTXt metadata chunks."""

import struct
import zlib

import numpy as np


def write_rgba_png(pixels: np.ndarray, *, texts: dict[str, str] | None = None) -> bytes:
    """Encode an (H, W, 4) uint8 array as a PNG byte string.

    ``texts`` entries become iTXt chunks (UTF-8 safe), used to embed the
    IMGW-PIB attribution and processed-data notice in every rendered image.
    """
    if pixels.ndim != 3 or pixels.shape[2] != 4 or pixels.dtype != np.uint8:
        raise ValueError("write_rgba_png expects an (H, W, 4) uint8 array.")
    height, width = pixels.shape[:2]

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(height))

    chunks = [_chunk(b"IHDR", header)]
    for keyword, text in (texts or {}).items():
        payload = (
            keyword.encode("latin-1", "replace")[:79]
            + b"\x00\x00\x00\x00\x00"
            + text.encode("utf-8")
        )
        chunks.append(_chunk(b"iTXt", payload))
    chunks.append(_chunk(b"IDAT", zlib.compress(raw, 6)))
    chunks.append(_chunk(b"IEND", b""))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )
