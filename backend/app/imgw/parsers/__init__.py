from typing import Any

from pydantic import BaseModel

from app.normalization.models import NormalizedRecord, SourceMetadata

from .hydro import parse_hydro
from .meteo import parse_meteo
from .product import parse_product_manifest
from .synop import parse_synop
from .warnings import parse_warnings_hydro, parse_warnings_meteo


class ParseResult(BaseModel):
    source_key: str
    records: list[NormalizedRecord]
    warnings: list[str] = []


def parse_source(source_key: str, payload: Any, source: SourceMetadata) -> ParseResult:
    parser = {
        "synop": parse_synop,
        "hydro": parse_hydro,
        "meteo": parse_meteo,
        "warningsmeteo": parse_warnings_meteo,
        "warningshydro": parse_warnings_hydro,
        "product": parse_product_manifest,
    }.get(source_key)

    if parser is None:
        return ParseResult(
            source_key=source_key,
            records=[],
            warnings=[f"No parser registered for source {source_key!r}."],
        )

    records, warnings = parser(payload, source)
    return ParseResult(source_key=source_key, records=records, warnings=warnings)

