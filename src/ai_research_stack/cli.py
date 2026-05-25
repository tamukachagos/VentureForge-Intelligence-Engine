from __future__ import annotations

import argparse

from ai_research_stack.config import load_settings
from ai_research_stack.postgres import PostgresRepository


def init_db() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    PostgresRepository(settings.database_url).initialize_schema()


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-research-stack")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init-db")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()


if __name__ == "__main__":
    main()

