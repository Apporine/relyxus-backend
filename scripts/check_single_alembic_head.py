"""Fail CI when the API migration graph has more than one head (context.md §9)."""

import re
import sys
from pathlib import Path

API_ROOT = Path("services/api")
VERSIONS_DIR = API_ROOT / "migrations" / "versions"
_REVISION = re.compile(r'^revision\s*:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)
_DOWN = re.compile(r'^down_revision\s*:\s*str\s*\|\s*None\s*=\s*(?:"([^"]+)"|None)', re.MULTILINE)


def _load_graph() -> tuple[dict[str, str | None], list[Path]]:
    files = sorted(VERSIONS_DIR.glob("*.py"))
    revisions: dict[str, str | None] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        revision_match = _REVISION.search(text)
        if revision_match is None:
            continue
        revision = revision_match.group(1)
        down_match = _DOWN.search(text)
        down_revision = None if down_match is None else down_match.group(1)
        revisions[revision] = down_revision
    return revisions, files


def main() -> int:
    if not VERSIONS_DIR.is_dir() or not any(VERSIONS_DIR.glob("*.py")):
        return 0
    revisions, files = _load_graph()
    if not revisions:
        sys.stderr.write("Migration version files exist but no revision IDs were parsed.\n")
        return 1
    referenced = {down for down in revisions.values() if down is not None}
    heads = [rev for rev in revisions if rev not in referenced]
    if len(heads) == 1:
        return 0
    sys.stderr.write(
        f"Expected exactly one Alembic head, found {len(heads)}: {', '.join(sorted(heads))}\n"
    )
    sys.stderr.write(f"Parsed {len(revisions)} revisions from {len(files)} files.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
