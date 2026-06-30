from typing import Any

from app.imgw.parsers.utils import missing_fields, parse_float, parse_synop_datetime
from app.normalization.models import Observation, SourceMetadata, Station

SYNOP_METRICS = {
    "temperatura": ("temperature", "°C"),
    "predkosc_wiatru": ("wind_speed", "m/s"),
    "kierunek_wiatru": ("wind_direction", "°"),
    "wilgotnosc_wzgledna": ("relative_humidity", "%"),
    "suma_opadu": ("precipitation_sum", "mm"),
    "cisnienie": ("pressure", "hPa"),
}


def parse_synop(payload: Any, source: SourceMetadata) -> tuple[list[Station], list[str]]:
    if not isinstance(payload, list):
        return [], ["Synop payload is not a list."]

    records: list[Station] = []
    warnings: list[str] = []
    required_fields = ["id_stacji", "stacja", "data_pomiaru", "godzina_pomiaru"]

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Synop row {index} is not an object.")
            continue

        source_id = str(row.get("id_stacji") or "")
        if not source_id:
            warnings.append(f"Synop row {index} has no id_stacji.")
            continue

        observed_at = parse_synop_datetime(row.get("data_pomiaru"), row.get("godzina_pomiaru"))
        observations = [
            Observation(
                metric=metric,
                value=parse_float(row.get(raw_field)),
                unit=unit,
                observed_at=observed_at,
                raw_field=raw_field,
                missing=row.get(raw_field) in (None, ""),
            )
            for raw_field, (metric, unit) in SYNOP_METRICS.items()
        ]
        row_missing = missing_fields(row, required_fields + list(SYNOP_METRICS))
        row_missing.extend(["lat", "lon"])

        records.append(
            Station(
                id=f"synop:{source_id}",
                source_id=source_id,
                source_key="synop",
                station_type="synop",
                name=str(row.get("stacja") or source_id),
                observations=observations,
                missing_fields=sorted(set(row_missing)),
                source=source,
                raw=row,
            )
        )

    return records, warnings

