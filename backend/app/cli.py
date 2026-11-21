import argparse
import sys
from collections import Counter
from pathlib import Path

from app.db.session import SessionLocal
from app.models import QuarantineReason
from app.services.rebuild import rebuild_read_models
from app.services.replay import replay_quarantine
from app.services.seed import load_seed


def seed(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        inserted = load_seed(db, args.file)
    for table, count in inserted.items():
        print(f"{table}: {count} inserted")


def replay(args: argparse.Namespace) -> None:
    reason = QuarantineReason(args.reason)
    results = replay_quarantine(reason, dry_run=args.dry_run)
    prefix = "[dry-run] " if args.dry_run else ""
    for r in results:
        after = f"{r.status.value}/{r.reason.value}" if r.reason else r.status.value
        print(f"{prefix}report {r.report_id}: {reason.value} -> {after}")
    summary = Counter(r.reason.value if r.reason else r.status.value for r in results)
    verb = "would change" if args.dry_run else "changed"
    print(f"{prefix}{len(results)} report(s) checked, {sum(r.changed for r in results)} {verb}: {dict(summary)}")


def rebuild(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        counts = rebuild_read_models(db)
    print(f"rebuilt read models from {counts['reports']} report(s): {counts['measurements']} measurement(s)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="railtrace")
    commands = parser.add_subparsers(dest="command", required=True)

    seed_parser = commands.add_parser("seed", help="Loads the seed (idempotent)")
    seed_parser.add_argument("--file", type=Path, required=True)
    seed_parser.set_defaults(handler=seed)

    replay_parser = commands.add_parser("replay-quarantine", help="Checks quarantined reports again (R8)")
    replay_parser.add_argument("--reason", required=True, choices=[r.value for r in QuarantineReason])
    replay_parser.add_argument("--dry-run", action="store_true", help="Only prints, changes nothing")
    replay_parser.set_defaults(handler=replay)

    rebuild_parser = commands.add_parser("rebuild-read-models", help="Rebuilds all read models from the raw reports (A4)")
    rebuild_parser.set_defaults(handler=rebuild)

    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
