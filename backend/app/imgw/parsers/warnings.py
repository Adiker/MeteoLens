from typing import Any

from app.imgw.parsers.utils import missing_fields, parse_datetime, parse_int
from app.normalization.models import SourceMetadata, Warning, WarningArea


def parse_warnings_meteo(payload: Any, source: SourceMetadata) -> tuple[list[Warning], list[str]]:
    if not isinstance(payload, list):
        return [], ["Meteorological warnings payload is not a list."]

    records: list[Warning] = []
    warnings: list[str] = []
    required_fields = [
        "id",
        "nazwa_zdarzenia",
        "stopien",
        "prawdopodobienstwo",
        "obowiazuje_od",
        "obowiazuje_do",
        "opublikowano",
        "teryt",
    ]

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Meteo warning row {index} is not an object.")
            continue

        source_id = str(row.get("id") or "")
        if not source_id:
            warnings.append(f"Meteo warning row {index} has no id.")
            continue

        areas = [
            WarningArea(area_type="teryt", code=str(code), label=str(code))
            for code in row.get("teryt", [])
            if code not in (None, "")
        ]
        records.append(
            Warning(
                id=f"warningsmeteo:{source_id}",
                source_id=source_id,
                source_key="warningsmeteo",
                warning_type="meteo",
                event=str(row.get("nazwa_zdarzenia") or ""),
                level=parse_int(row.get("stopien")),
                probability=parse_int(row.get("prawdopodobienstwo")),
                valid_from=parse_datetime(row.get("obowiazuje_od")),
                valid_to=parse_datetime(row.get("obowiazuje_do")),
                published_at=parse_datetime(row.get("opublikowano")),
                office=str(row.get("biuro") or "") or None,
                content=str(row.get("tresc") or "") or None,
                comment=str(row.get("komentarz") or "") or None,
                areas=areas,
                missing_fields=missing_fields(row, required_fields),
                source=source,
                raw=row,
            )
        )

    return records, warnings


def parse_warnings_hydro(payload: Any, source: SourceMetadata) -> tuple[list[Warning], list[str]]:
    if not isinstance(payload, list):
        return [], ["Hydrological warnings payload is not a list."]

    records: list[Warning] = []
    warnings: list[str] = []
    required_fields = [
        "numer",
        "zdarzenie",
        "stopień",
        "prawdopodobienstwo",
        "data_od",
        "data_do",
        "opublikowano",
        "obszary",
    ]

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Hydro warning row {index} is not an object.")
            continue

        source_id = str(row.get("numer") or f"row-{index}")
        areas: list[WarningArea] = []
        for area in row.get("obszary", []):
            if not isinstance(area, dict):
                continue
            region = str(area.get("wojewodztwo") or "") or None
            label = str(area.get("opis") or "") or None
            basin_codes = area.get("kod_zlewni") or []
            for code in basin_codes:
                areas.append(
                    WarningArea(
                        area_type="basin",
                        code=str(code),
                        label=label,
                        region=region,
                    )
                )
            if not basin_codes and region:
                areas.append(
                    WarningArea(
                        area_type="province",
                        code=region,
                        label=label,
                        region=region,
                    )
                )

        records.append(
            Warning(
                id=f"warningshydro:{source_id}",
                source_id=source_id,
                source_key="warningshydro",
                warning_type="hydro",
                event=str(row.get("zdarzenie") or ""),
                level=parse_int(row.get("stopień")),
                probability=parse_int(row.get("prawdopodobienstwo")),
                valid_from=parse_datetime(row.get("data_od")),
                valid_to=parse_datetime(row.get("data_do")),
                published_at=parse_datetime(row.get("opublikowano")),
                office=str(row.get("biuro") or "") or None,
                content=str(row.get("przebieg") or "") or None,
                comment=str(row.get("komentarz") or "") or None,
                areas=areas,
                missing_fields=missing_fields(row, required_fields),
                source=source,
                raw=row,
            )
        )

    return records, warnings
