#!/usr/bin/env python
"""Sync the docs with the latest oryxflow / oryxeval releases.

Copies both sibling CHANGELOG.md files into _external/ (the committed snapshots the
Cloudflare build uses), and rewrites the oryxflow pin in docs/requirements-cloudflare.txt
to the newest released version in oryxflow's changelog. Then prints what changed and what
to do next. Run it after a release has landed on PyPI.

Usage:
    python scripts/sync_release.py [--src-root DIR]   # default: $ORYX_SRC_ROOT, else ..
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_docs import EXTERNAL_REPOS, newest_released_version  # noqa: E402  (reused, not copied)

REQ_FILE = "docs/requirements-cloudflare.txt"
_PIN_RE = re.compile(r"^oryxflow==\S+[ \t]*$", re.MULTILINE)


def rewrite_pin(text: str, version: str):
    """Return (new_text, changed) with the `oryxflow==X` line set to `version`."""
    if not _PIN_RE.search(text):
        sys.exit(f"ERROR: no 'oryxflow==<version>' line in {REQ_FILE}.")
    new = _PIN_RE.sub(f"oryxflow=={version}", text, count=1)
    return new, new != text


def sync(src_root: Path, repo_root: Path = ROOT) -> dict:
    """Copy changelogs and re-pin; return {repo: newest version, 'changed': [paths]}."""
    src_root, repo_root = Path(src_root), Path(repo_root)
    missing = [r for r in EXTERNAL_REPOS if not (src_root / r / "CHANGELOG.md").is_file()]
    if missing:
        sys.exit(f"ERROR: cannot find CHANGELOG.md for {', '.join(missing)} under {src_root}. "
                 "Pass --src-root DIR or set ORYX_SRC_ROOT.")
    changed, report = [], {}
    for repo in EXTERNAL_REPOS:
        src = src_root / repo / "CHANGELOG.md"
        dest = repo_root / "_external" / repo / "CHANGELOG.md"
        if not dest.is_file() or dest.read_bytes() != src.read_bytes():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            changed.append(f"_external/{repo}/CHANGELOG.md")
        report[repo] = newest_released_version(dest)
    req = repo_root / REQ_FILE
    new, did = rewrite_pin(req.read_text(encoding="utf-8"), report["oryxflow"])
    if did:
        req.write_text(new, encoding="utf-8")
        changed.append(REQ_FILE)
    report["changed"] = changed
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-root", type=Path, default=Path(os.environ.get("ORYX_SRC_ROOT", "..")))
    args = ap.parse_args()
    src_root = args.src_root if args.src_root.is_absolute() else ROOT / args.src_root
    r = sync(src_root)
    print(f"oryxflow {r['oryxflow']} / oryxeval {r['oryxeval']}")
    print("changed: " + (", ".join(r["changed"]) or "nothing (already in sync)"))
    if r["changed"]:
        print("next: python scripts/build_docs.py (full build with doc tests), "
              "commit, then push main (the push redeploys the site via Cloudflare).")


if __name__ == "__main__":
    main()
