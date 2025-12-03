"""Dump schema using alembic offline mode."""
from __future__ import annotations

from alembic.config import Config
from alembic import command


def main() -> None:
    cfg = Config("alembic.ini")
    command.revision(cfg, autogenerate=True, message="schema snapshot", rev_id=None, sql=True)


if __name__ == "__main__":
    main()
