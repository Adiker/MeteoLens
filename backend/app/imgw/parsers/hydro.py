from typing import Any

from app.imgw.parsers.utils import missing_fields, parse_datetime, parse_float
from app.normalization.models import Observation, SourceMetadata, Station

HYDRO_METRICS = {
    "stan_wody": ("water_level", "cm", "stan_wody_data_pomiaru"),
    "temperatura_wody": ("water_temperature", "°C", "temperatura_wody_data_pomiaru"),
    "przeplyw": ("flow", "m³/s", "przeplyw_data"),
    "zjawisko_lodowe": ("ice_phenomenon", None, "zjawisko_lodowe_data_pomiaru"),
    "zjawisko_zarastania": ("vegetation_phenomenon", None, "zjawisko_zarastania_data_pomiaru"),
}
HYDRO_MISSING_FIELDS = list(HYDRO_METRICS) + [
    timestamp_field for _, _, timestamp_field in HYDRO_METRICS.values()
]


def parse_hydro(payload: Any, source: SourceMetadata) -> tuple[list[Station], list[str]]:
    if not isinstance(payload, list):
        return [], ["Hydro payload is not a list."]

    records: list[Station] = []
    warnings: list[str] = []
    required_fields = ["id_stacji", "stacja", "rzeka", "wojewodztwo", "lon", "lat"]

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Hydro row {index} is not an object.")
            continue

        source_id = str(row.get("id_stacji") or "")
        if not source_id:
            warnings.append(f"Hydro row {index} has no id_stacji.")
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
            for raw_field, (metric, unit, timestamp_field) in HYDRO_METRICS.items()
        ]

        records.append(
            Station(
                id=f"hydro:{source_id}",
                source_id=source_id,
                source_key="hydro",
                station_type="hydro",
                name=str(row.get("stacja") or source_id),
                lat=parse_float(row.get("lat")),
                lon=parse_float(row.get("lon")),
                region=str(row.get("wojewodztwo") or "") or None,
                watercourse=str(row.get("rzeka") or "") or None,
                observations=observations,
                missing_fields=missing_fields(row, required_fields + HYDRO_MISSING_FIELDS),
                source=source,
                raw=row,
            )
        )

    return records, warnings
