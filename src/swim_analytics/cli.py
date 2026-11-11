import argparse
import os
import sys
from getpass import getpass
from math import isfinite
from pathlib import Path

from .connectors.base import ActivitySource
from .connectors.fit import LocalFitSource, pool_message_counts
from .connectors.garmin import load_garmin_source
from .connectors.personal import PersonalApiError, PersonalGarminSource
from .overview import show_overview
from .progress import show_progress
from .storage import archive, archived_activity_ids, archived_payloads, preserve


def ingest(source: ActivitySource, source_name: str, root: Path) -> int:
    imported = 0
    with archive(root) as db:
        for activity in source.activities():
            counts = pool_message_counts(activity.payload)
            added = preserve(db, source_name, activity)
            imported += added
            status = "Imported" if added else "Already archived"
            inventory = ", ".join(f"{kind}={count}" for kind, count in counts.items())
            print(f"{status} ({inventory})")

    return imported


def _configured_key() -> str | None:
    name = "GARMIN_PERSONAL_API_KEY"
    if key := os.environ.get(name, "").strip():
        return key

    path = Path(".env")
    if not path.is_file():
        return None
    if path.stat().st_mode & 0o077:
        raise PersonalApiError("Set .env permissions to owner-only with chmod 600 .env.")
    for line in path.read_text(encoding="utf-8").splitlines():
        variable, separator, value = line.partition("=")
        if separator and variable.strip() == name:
            return value.strip() or None
    return None


def main() -> int:
    default_root = Path.home() / ".local" / "share" / "swim-analytics"
    parser = argparse.ArgumentParser(prog="swim-analytics")
    parser.add_argument(
        "--data-dir", type=Path,
        default=os.environ.get("SWIM_ANALYTICS_HOME") or default_root,
        help="Private archive directory (default: ~/.local/share/swim-analytics)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("import-fit", help="Import original pool-swim FIT files offline")
    fit.add_argument("paths", type=Path, nargs="+")
    commands.add_parser("analyze", help="Show local swimming volume and raw pace by stroke")
    progress = commands.add_parser("progress", help="Show monthly length time and SWOLF")
    progress.add_argument("--pool-m", type=float, default=25.0, help="Pool size in meters (default: 25)")
    progress.add_argument("--raw", action="store_true", help="Include quarantined lengths")
    sync = commands.add_parser("sync-garmin", help="Download pool swims from Garmin")
    provider = sync.add_mutually_exclusive_group()
    provider.add_argument("--connector", help="Run an installed Garmin connector")
    provider.add_argument(
        "--activity-id", type=int, action="append",
        help="Download an activity ID using Garmin Personal API (repeatable)",
    )
    args = parser.parse_args()

    try:
        if args.command == "analyze":
            show_overview(archived_payloads(args.data_dir))
        elif args.command == "progress":
            if not isfinite(args.pool_m) or args.pool_m <= 0:
                progress.error("--pool-m must be a positive finite number.")
            show_progress(archived_payloads(args.data_dir), args.pool_m, raw=args.raw)
        elif args.command == "import-fit":
            ingest(LocalFitSource(tuple(args.paths)), "local-fit", args.data_dir)
        elif not args.connector:
            ids = tuple(dict.fromkeys(args.activity_id or ()))
            if any(not 0 < item <= 2**63 - 1 for item in ids):
                sync.error("--activity-id must be a positive 64-bit integer.")
            key = _configured_key()
            if key is None:
                if not sys.stdin.isatty():
                    sync.error("Set GARMIN_PERSONAL_API_KEY in .env or run in an interactive terminal.")
                key = getpass("Garmin Personal API key: ")
            if not key.strip() or any(char.isspace() for char in key.strip()):
                sync.error("Enter a valid Garmin Personal API key.")
            source_name = "garmin:personal"
            known = frozenset() if ids else archived_activity_ids(args.data_dir, source_name)
            source = PersonalGarminSource(key.strip(), ids or None, known)
            imported = ingest(source, source_name, args.data_dir)
            if not ids:
                print(f"Garmin sync complete. New FIT files archived: {imported}.")
        else:
            ingest(
                load_garmin_source(args.connector), f"garmin:{args.connector}", args.data_dir
            )
    except PersonalApiError as exc:
        parser.exit(1, f"Garmin import failed. {exc}\n")
    except (ValueError, RuntimeError, OSError, EOFError):
        # Adapters can include private paths or credentials in exception strings.
        parser.exit(1, "Import failed. Check the FIT extra, inputs, connector and storage permissions.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
