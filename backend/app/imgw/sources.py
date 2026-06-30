from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    title: str
    path: str
    parser_status: str
    default_ttl_seconds: int
    notes: str | None = None

    def url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}{self.path}"


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        key="synop",
        title="Aktualne dane synoptyczne",
        path="/api/data/synop",
        parser_status="implemented",
        default_ttl_seconds=600,
        notes="Current endpoint does not include coordinates.",
    ),
    SourceDefinition(
        key="hydro",
        title="Aktualne dane hydrologiczne",
        path="/api/data/hydro",
        parser_status="implemented",
        default_ttl_seconds=600,
    ),
    SourceDefinition(
        key="meteo",
        title="Aktualne dane meteorologiczne",
        path="/api/data/meteo",
        parser_status="implemented",
        default_ttl_seconds=600,
    ),
    SourceDefinition(
        key="warningsmeteo",
        title="Ostrzeżenia meteorologiczne",
        path="/api/data/warningsmeteo",
        parser_status="implemented",
        default_ttl_seconds=300,
        notes="Requires TERYT geometry for polygons.",
    ),
    SourceDefinition(
        key="warningshydro",
        title="Ostrzeżenia hydrologiczne",
        path="/api/data/warningshydro",
        parser_status="implemented",
        default_ttl_seconds=300,
        notes="Requires basin geometry for polygons.",
    ),
    SourceDefinition(
        key="product",
        title="Produkty plikowe IMGW-PIB",
        path="/api/data/product",
        parser_status="implemented_manifest_only",
        default_ttl_seconds=3600,
        notes="GRIB/radar file parsing remains post-MVP work.",
    ),
)

SOURCE_BY_KEY = {source.key: source for source in SOURCE_DEFINITIONS}

