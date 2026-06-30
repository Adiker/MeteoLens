from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["v1"])


class SourceDescriptor(BaseModel):
    key: str
    title: str
    url: str
    parser_status: str
    cache_status: str
    notes: str | None = None


class SourcesResponse(BaseModel):
    retrieved_at: datetime
    sources: list[SourceDescriptor]


@router.get("/sources", response_model=SourcesResponse)
def list_sources() -> SourcesResponse:
    base_url = str(get_settings().imgw_base_url).rstrip("/")
    planned_sources = [
        SourceDescriptor(
            key="synop",
            title="Aktualne dane synoptyczne",
            url=f"{base_url}/api/data/synop",
            parser_status="planned",
            cache_status="not_configured",
            notes="Current endpoint does not include coordinates.",
        ),
        SourceDescriptor(
            key="hydro",
            title="Aktualne dane hydrologiczne",
            url=f"{base_url}/api/data/hydro",
            parser_status="planned",
            cache_status="not_configured",
        ),
        SourceDescriptor(
            key="meteo",
            title="Aktualne dane meteorologiczne",
            url=f"{base_url}/api/data/meteo",
            parser_status="planned",
            cache_status="not_configured",
        ),
        SourceDescriptor(
            key="warningsmeteo",
            title="Ostrzeżenia meteorologiczne",
            url=f"{base_url}/api/data/warningsmeteo",
            parser_status="planned",
            cache_status="not_configured",
            notes="Requires TERYT geometry for polygons.",
        ),
        SourceDescriptor(
            key="warningshydro",
            title="Ostrzeżenia hydrologiczne",
            url=f"{base_url}/api/data/warningshydro",
            parser_status="planned",
            cache_status="not_configured",
            notes="Requires basin geometry for polygons.",
        ),
        SourceDescriptor(
            key="product",
            title="Produkty plikowe IMGW-PIB",
            url=f"{base_url}/api/data/product",
            parser_status="risky",
            cache_status="not_configured",
            notes="GRIB/radar products are post-MVP research items.",
        ),
    ]
    return SourcesResponse(retrieved_at=datetime.now(UTC), sources=planned_sources)

