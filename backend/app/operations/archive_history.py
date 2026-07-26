"""Inspect or remove explicitly selected MeteoLens archive history."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta

from app.db.repository import ObservationRepository


def cleanup_archive_history(
    *,
    archive_kind: str,
    observed_from: date,
    observed_to: date,
    confirm: bool = False,
) -> dict[str, object]:
    if observed_from > observed_to:
        raise ValueError("--from must not be later than --to")
    count = ObservationRepository().cleanup_archive_range(
        archive_kind=archive_kind,
        observed_from=datetime.combine(observed_from, datetime.min.time(), tzinfo=UTC),
        observed_to_exclusive=datetime.combine(
            observed_to + timedelta(days=1),
            datetime.min.time(),
            tzinfo=UTC,
        ),
        confirm=confirm,
    )
    return {
        "archive_kind": archive_kind,
        "observed_from": observed_from.isoformat(),
        "observed_to": observed_to.isoformat(),
        "matching_observations": count,
        "deleted": count if confirm else 0,
        "dry_run": not confirm,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("prune",),
        help="Count matching rows, or remove them only when --confirm is supplied.",
    )
    parser.add_argument(
        "--archive-kind",
        choices=("hydro_daily", "synop_daily"),
        required=True,
    )
    parser.add_argument("--from", dest="observed_from", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="observed_to", type=date.fromisoformat, required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    result = cleanup_archive_history(
        archive_kind=args.archive_kind,
        observed_from=args.observed_from,
        observed_to=args.observed_to,
        confirm=args.confirm,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
