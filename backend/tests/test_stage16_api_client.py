import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples" / "api"
GENERATED_CLIENT = ROOT / "packages" / "meteolens-api-client" / "src" / "generated.ts"


def test_generated_client_metadata_includes_stage16_operations() -> None:
    generated = GENERATED_CLIENT.read_text(encoding="utf-8")

    assert "/api/v1/export/station/{station_id}/observations.csv" in generated
    assert "/api/v1/export/station/{station_id}/observations.json" in generated
    assert "/api/v1/export/warnings.geojson" in generated
    assert "/api/v1/export/map-state.json" in generated
    assert "/api/v1/status/freshness" in generated
    assert "/api/v1/location/summary" in generated


def test_api_examples_do_not_call_imgw_directly() -> None:
    for path in EXAMPLES_DIR.glob("*.mjs"):
        text = path.read_text(encoding="utf-8")
        assert "danepubliczne.imgw.pl" not in text


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_api_examples_have_valid_javascript_syntax() -> None:
    for path in EXAMPLES_DIR.glob("*.mjs"):
        subprocess.run(["node", "--check", str(path)], check=True)
