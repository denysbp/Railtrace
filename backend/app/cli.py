import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.seed import load_seed


def seed(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        inserted = load_seed(db, args.file)
    for table, count in inserted.items():
        print(f"{table}: {count} inserted")


def main() -> None:
    parser = argparse.ArgumentParser(prog="railtrace")
    commands = parser.add_subparsers(dest="command", required=True)

    seed_parser = commands.add_parser("seed", help="Loads the seed (idempotent)")
    seed_parser.add_argument("--file", type=Path, required=True)
    seed_parser.set_defaults(handler=seed)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
