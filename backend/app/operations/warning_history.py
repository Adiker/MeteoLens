"""Inspect or remove complete, closed MeteoLens warning histories."""

from __future__ import annotations

import argparse
import json
from datetime import date

from app.services.warning_history import prune_warning_histories


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("prune",),
        help="Count matching histories, or remove them only with --confirm.",
    )
    parser.add_argument("--before", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--source-key",
        choices=("warningsmeteo", "warningshydro"),
    )
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    result = prune_warning_histories(
        before=args.before,
        source_key=args.source_key,
        confirm=args.confirm,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
