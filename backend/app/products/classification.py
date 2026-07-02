from dataclasses import dataclass
from typing import Literal

ProductCategory = Literal[
    "grib_model",
    "radar_composite",
    "radar_site",
    "radar_derivative",
    "other",
]
ProductAvailability = Literal[
    "stable_retrievable",
    "listed_missing",
    "listed_unstable",
    "technically_risky",
    "legally_unreviewed",
]
RenderingStatus = Literal[
    "metadata_only",
    "parser_not_implemented",
    "rendering_not_implemented",
    "unsupported_format",
    "unavailable",
]

RESEARCH_DATE = "2026-07-01"


@dataclass(frozen=True)
class ProductClassification:
    product_id: str
    category: ProductCategory
    availability: ProductAvailability
    format_notes: str
    rendering_status: RenderingStatus
    high_value: bool
    notes: str | None = None


def classify_product_id(product_id: str) -> ProductClassification:
    if product_id.startswith("COSMO_HVD_"):
        return ProductClassification(
            product_id=product_id,
            category="grib_model",
            availability="stable_retrievable",
            format_notes=(
                "GRIB2-like binary files referenced by JSON manifest; "
                "projection and variables undocumented in API."
            ),
            rendering_status="parser_not_implemented",
            high_value=True,
            notes="Detail endpoint returns ~63 forecast lead files per run.",
        )

    if product_id in {"COMPO_SRI.comp.sri", "COMPO_CMAX_250.comp.cmax"}:
        kind = "SRI composite" if "SRI" in product_id else "CMAX composite"
        return ProductClassification(
            product_id=product_id,
            category="radar_composite",
            availability="stable_retrievable",
            format_notes=(
                f"Proprietary {kind} binary plus occasional PNG echo previews in manifest."
            ),
            rendering_status="parser_not_implemented",
            high_value=True,
            notes="Detail endpoint returns thousands of recent frames.",
        )

    if product_id.startswith("COMPO_"):
        return ProductClassification(
            product_id=product_id,
            category="radar_composite",
            availability="listed_missing",
            format_notes=(
                "Listed in public manifest but detail endpoint returned 404 during research."
            ),
            rendering_status="unavailable",
            high_value=True,
            notes="Includes CAPPI, EHT, PAC, and alternate SRI identifiers.",
        )

    if product_id.endswith(".vvp") or product_id.endswith("_200_leads.sri"):
        return ProductClassification(
            product_id=product_id,
            category="radar_site",
            availability="listed_missing",
            format_notes="Per-site radar derivative listed in manifest.",
            rendering_status="unavailable",
            high_value=False,
            notes="Detail endpoint returned 404 during research.",
        )

    if "cappi" in product_id.lower():
        return ProductClassification(
            product_id=product_id,
            category="radar_site",
            availability="listed_missing",
            format_notes="Per-site or composite CAPPI identifier.",
            rendering_status="unavailable",
            high_value=True,
            notes="Detail endpoint returned 404 during research.",
        )

    return ProductClassification(
        product_id=product_id,
        category="other",
        availability="listed_unstable",
        format_notes="Unknown public product type.",
        rendering_status="unsupported_format",
        high_value=False,
    )


def all_researched_missing_ids() -> frozenset[str]:
    return frozenset(
        {
            "brz.vvp",
            "brz_compo_pcz.cappi",
            "gdy.vvp",
            "gdy_200_leads.sri",
            "gsa.vvp",
            "gsa_200_leads.sri",
            "gsa_compo_pcz.cappi",
            "leg.vvp",
            "leg_200_leads.sri",
            "leg_compo_pcz.cappi",
            "pas.vvp",
            "pas_200_leads.sri",
            "pas_compo_pcz.cappi",
            "COMPO_CAPPI.comp.cappi_buf",
            "COMPO_CAPPI.comp.cappi_h5",
            "COMPO_EHT.comp.eht",
            "COMPO_PAC.comp.pac",
            "COMPO_SRI.comp.sri_h5",
            "poz.vvp",
            "poz_200_leads.sri",
            "poz_compo_pcz.cappi",
            "ram.vvp",
            "ram_200_leads.sri",
            "ram_compo_pcz.cappi",
            "rze.vvp",
            "rze_200_leads.sri",
            "rze_compo_pcz.cappi",
            "swi.vvp",
            "swi_200_leads.sri",
            "swi_compo_pcz.cappi",
            "uzr.vvp",
            "uzr_200_leads.sri",
        }
    )
