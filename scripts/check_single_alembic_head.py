"""Fail CI when the API migration graph has more than one head (context.md §9)."""

from pathlib import Path
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

API_ROOT = Path("services/api")


def main() -> int:
    versions_dir = API_ROOT / "migrations" / "versions"
    if not versions_dir.is_dir() or not any(versions_dir.glob("*.py")):
        return 0
    config = Config(str(API_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_revisions("heads")
    if len(heads) == 1:
        return 0
    labels = ", ".join(revision.revision for revision in heads)
    print(
        f"Expected exactly one Alembic head, found {len(heads)}: {labels}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
