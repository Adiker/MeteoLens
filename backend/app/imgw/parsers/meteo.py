from typing import Any

from app.imgw.parsers.utils import missing_fields, parse_datetime, parse_float
from app.normalization.models import Observation, SourceMetadata, Station

METEO_METRICS = {
    "temperatura_gruntu": ("ground_temperature", "°C", "temperatura_gruntu_data"),
    "temperatura_powietrza": ("air_temperature", "°C", "temperatura_powietrza_data"),
    "wiatr_kierunek": ("wind_direction", "°", "wiatr_kierunek_data"),
    "wiatr_srednia_predkosc": ("wind_average_speed", "m/s", "wiatr_srednia_predkosc_data"),
    "wiatr_predkosc_maksymalna": ("wind_max_speed", "m/s", "wiatr_predkosc_maksymalna_data"),
    "wilgotnosc_wzgledna": ("relative_humidity", "%", "wilgotnosc_wzgledna_data"),
    "wiatr_poryw_10min": ("wind_gust_10min", "m/s", "wiatr_poryw_10min_data"),
    "opad_10min": ("precipitation_10min", "mm", "opad_10min_data"),
}
METEO_MISSING_FIELDS = list(METEO_METRICS) + [
    timestamp_field for _, _, timestamp_field in METEO_METRICS.values()
]


def parse_meteo(payload: Any, source: SourceMetadata) -> tuple[list[Station], list[str]]:
    if not isinstance(payload, list):
        return [], ["Meteo payload is not a list."]

    records: list[Station] = []
    warnings: list[str] = []
    required_fields = ["kod_stacji", "nazwa_stacji", "lon", "lat"]

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Meteo row {index} is not an object.")
            continue

        source_id = str(row.get("kod_stacji") or "")
        if not source_id:
            warnings.append(f"Meteo row {index} has no kod_stacji.")
            continue

        observations = [
            Observation(
                metric=metric,
                value=parse_float(row.get(raw_field)),
                unit=unit,
                observed_at=parse_datetime(row.get(timestamp_field)),
                raw_field=raw_field,
                missing=row.get(raw_field) in (None, ""),
            )
            for raw_field, (metric, unit, timestamp_field) in METEO_METRICS.items()
        ]

        records.append(
            Station(
                id=f"meteo:{source_id}",
                source_id=source_id,
                source_key="meteo",
                station_type="meteo",
                name=str(row.get("nazwa_stacji") or source_id),
                lat=parse_float(row.get("lat")),
                lon=parse_float(row.get("lon")),
                observations=observations,
                missing_fields=missing_fields(row, required_fields + METEO_MISSING_FIELDS),
                source=source,
                raw=row,
            )
        )

    return records, warnings
