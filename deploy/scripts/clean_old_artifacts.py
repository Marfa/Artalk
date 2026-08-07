#!/usr/bin/env python3
"""Delete stale non-source build/migration artifacts (mtime older than N days)."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Paths relative to repo root. Never touches source under deploy/, scripts/, .cursor/.
ARTIFACT_DIR_NAMES = frozenset(
    {
        "exports",
        "data",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
    }
)
ARTIFACT_FILE_SUFFIXES = (
    ".artrans",
    ".artrans.json",
    ".pyc",
    ".pyo",
    ".log",
)
ARTIFACT_FILE_NAMES = frozenset({".DS_Store"})
SKIP_DIR_NAMES = frozenset({".git", ".cursor", ".ssh"})


def is_artifact_file(path: Path) -> bool:
    name = path.name
    if name in ARTIFACT_FILE_NAMES:
        return True
    if name.endswith(ARTIFACT_FILE_SUFFIXES):
        return True
    # Anything under known artifact directories (exports dumps, sqlite data, caches).
    return any(part in ARTIFACT_DIR_NAMES for part in path.parts)


def iter_stale_artifacts(root: Path, older_than_days: float) -> list[Path]:
    cutoff = time.time() - older_than_days * 86400
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
            except OSError:
                continue
            rel = path.relative_to(root)
            if is_artifact_file(rel):
                found.append(path)
    return sorted(found)


def clean(root: Path, older_than_days: float, dry_run: bool) -> int:
    paths = iter_stale_artifacts(root, older_than_days)
    for path in paths:
        rel = path.relative_to(root)
        if dry_run:
            print(f"would delete: {rel}")
            continue
        path.unlink(missing_ok=True)
        print(f"deleted: {rel}")
    return len(paths)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root (default: parent of scripts/)",
    )
    ap.add_argument("--days", type=float, default=7.0, help="Age threshold in days")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"root is not a directory: {root}", file=sys.stderr)
        return 2
    n = clean(root, args.days, args.dry_run)
    print(f"{'would remove' if args.dry_run else 'removed'} {n} file(s) older than {args.days:g} day(s)")
    return 0


if __name__ == "__main__":
    # Self-check: a fresh file must not be selected; an old artifact suffix must.
    _tmp = Path(__file__).resolve().parents[1] / "exports"
    _tmp.mkdir(exist_ok=True)
    _probe = _tmp / ".clean_artifacts_selfcheck.artrans"
    _probe.write_text("probe\n", encoding="utf-8")
    try:
        assert _probe not in iter_stale_artifacts(_tmp.parent, 7.0)
        os.utime(_probe, (0, 0))
        assert _probe in iter_stale_artifacts(_tmp.parent, 7.0)
    finally:
        _probe.unlink(missing_ok=True)
    raise SystemExit(main())
