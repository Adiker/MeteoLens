from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ATTRIBUTION = "Źródło danych: IMGW-PIB."
PROCESSED_NOTICE = "Dane IMGW-PIB zostały przetworzone przez MeteoLens."


class SourceMetadata(BaseModel):
    provider: Literal["IMGW-PIB"] = "IMGW-PIB"
    source_key: str
    url: str
    retrieved_at: datetime
    attribution: str = ATTRIBUTION
    processed_notice: str = PROCESSED_NOTICE


class Observation(BaseModel):
    metric: str
    value: float | str | None
    unit: str | None
    observed_at: datetime | None
    raw_field: str
    missing: bool = False


class Station(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["station"] = "station"
    id: str
    source_id: str
    source_key: str
    station_type: Literal["synop", "hydro", "meteo"]
    name: str
    lat: float | None = None
    lon: float | None = None
    region: str | None = None
    watercourse: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    source: SourceMetadata
    raw: dict[str, object]


class WarningArea(BaseModel):
    area_type: Literal["teryt", "basin", "province"]
    code: str
    label: str | None = None
    region: str | None = None


class Warning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["warning"] = "warning"
    id: str
    source_id: str
    source_key: str
    warning_type: Literal["meteo", "hydro"]
    event: str
    level: int | None
    probability: int | None
    valid_from: datetime | None
    valid_to: datetime | None
    published_at: datetime | None
    office: str | None
    content: str | None
    comment: str | None
    areas: list[WarningArea] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    source: SourceMetadata
    raw: dict[str, object]


class ProductManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["product_manifest"] = "product_manifest"
    id: str
    source_id: str
    source_key: Literal["product"] = "product"
    description: str
    url: str
    missing_fields: list[str] = Field(default_factory=list)
    source: SourceMetadata
    raw: dict[str, object]


NormalizedRecord = Station | Warning | ProductManifest

