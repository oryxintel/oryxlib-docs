#!/usr/bin/env python
"""Fetch external sources, regenerate the doc-example tests, run them, build the Zensical site.

One portable entry point used by both the local deploy scripts and CI, so "it built
on my machine" and "it built in the Action" run the exact same steps.

Steps:
  0. Copy the oryxflow and oryxeval changelogs from the sibling checkouts into
     _external/ (the changelog pages include them by snippet). With --offline the
     committed _external/ snapshots are used instead and no sibling is read.
  1. Validate every page's YAML front matter — invalid front matter is not an error in
     MkDocs, it just gets rendered as page text, so the build has to catch it.
  2. Compile the runnable Markdown pages into tests/test_docs_*.py with phmdoctest.
  3. Run those doc tests — they fail if a documented example has rotted (an API was
     renamed, a snippet raises, sklearn dropped a dataset, ...).
  4. Build the static site into ./site with `zensical build`.
  5. SEO check on the built site (scripts/check_seo.py): fails on a missing title, description,
     canonical or Open Graph tag, or a duplicate title/description; warns on length.

Usage:
    python scripts/build_docs.py                # regenerate tests, run them, build
    python scripts/build_docs.py --check        # additionally fail if committed test
                                                #   files are stale (use in CI)
    python scripts/build_docs.py --skip-tests   # just build (fast local preview)
    python scripts/build_docs.py --strict       # zensical build --strict
    python scripts/build_docs.py --src-root DIR # where oryxflow/ and oryxeval/ live
                                                #   (default: $ORYX_SRC_ROOT, else ..)
    python scripts/build_docs.py --offline      # no siblings: committed _external/ snapshots
                                                #   (what Cloudflare runs)
    python scripts/build_docs.py --use-snapshot oryxeval   # snapshot for that repo only (CI)
    python scripts/build_docs.py --regen        # front matter + regenerate tests only,
                                                #   no pytest, no build (pre-commit hook)

Why --regen exists: phmdoctest names each generated test after its code block's SOURCE
LINE (test_code_66), so editing prose ABOVE a block renames the test and makes the
committed file stale — with no behavior change at all. That is pure churn, and easy to
forget before committing, which then fails CI's --check. The pre-commit hook runs this
mode so the regeneration happens automatically. See .pre-commit-config.yaml.
"""
import argparse
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Sibling repos whose CHANGELOG.md the site includes; copied into _external/<repo>/.
EXTERNAL_REPOS = ("oryxflow", "oryxeval")

# Markdown pages that run top-to-bottom and are compiled into pytest files by phmdoctest.
# Add a page here (and mark its runnable code blocks with <!--phmdoctest-share-names-->)
# to have its examples verified on every build. See CLAUDE.md.
TESTED_PAGES = {
    "docs/docs/quickstart.md": "tests/test_docs_quickstart.py",
    "docs/docs/targets.md": "tests/test_docs_targets.py",
    "docs/index.md": "tests/test_docs_index.py",
}


def fetch_sources(src_root: Path, dest: Path, snapshot=()) -> None:
    """Make dest/<repo>/CHANGELOG.md available for every repo in EXTERNAL_REPOS.

    Repos named in `snapshot` are NOT read from src_root: the committed copy already in
    dest is used (it must exist). All others are copied from the sibling checkout.
    """
    src_root, dest = Path(src_root), Path(dest)
    unknown = [r for r in snapshot if r not in EXTERNAL_REPOS]
    if unknown:
        sys.exit(f"ERROR: unknown repo for snapshot mode: {', '.join(unknown)} "
                 f"(known: {', '.join(EXTERNAL_REPOS)}).")
    no_snap = [r for r in snapshot if not (dest / r / "CHANGELOG.md").is_file()]
    if no_snap:
        sys.exit(f"ERROR: no committed snapshot _external/{no_snap[0]}/CHANGELOG.md for "
                 f"{', '.join(no_snap)}. Run scripts/sync_release.py with the sibling "
                 "checkouts present, then commit _external/.")
    live = [r for r in EXTERNAL_REPOS if r not in snapshot]
    missing = [r for r in live if not (src_root / r / "CHANGELOG.md").is_file()]
    if missing:
        sys.exit(
            f"ERROR: cannot find CHANGELOG.md for {', '.join(missing)} under {src_root}.\n"
            "       Check out the sibling repos next to this one, or pass --src-root DIR "
            "(or set ORYX_SRC_ROOT); --use-snapshot REPO uses the committed copy instead."
        )
    for repo in live:
        out = dest / repo
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_root / repo / "CHANGELOG.md", out / "CHANGELOG.md")


def run(cmd):
    print(">>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


# Front matter that isn't valid YAML fails SILENTLY: MkDocs leaves the block in the page
# and renders it as body text, so the build succeeds and ships a page whose first
# paragraph is "title: ... description: ... faq: ...". The usual cause is an unquoted
# value containing ": " (a colon-space starts a nested mapping). Fail the build instead.
YAML_FRONT_MATTER_RE = re.compile(r"^-{3}[ \t]*\r?\n(.*?)\r?\n(?:-{3}|\.{3})[ \t]*\r?\n", re.DOTALL)


def check_front_matter():
    import yaml

    broken = []
    for page in sorted((ROOT / "docs").rglob("*.md")):
        text = page.read_text(encoding="utf-8-sig")
        if not text.startswith("---"):
            continue
        m = YAML_FRONT_MATTER_RE.match(text)
        if not m:
            broken.append((page, "front-matter delimiters not matched (needs a closing --- line)"))
            continue
        try:
            meta = yaml.safe_load(m.group(1))
        except yaml.YAMLError as e:
            broken.append((page, str(e).splitlines()[0]))
            continue
        if not isinstance(meta, dict):
            broken.append((page, f"parsed as {type(meta).__name__}, not a mapping"))

    if broken:
        lines = [f"  {p.relative_to(ROOT).as_posix()}: {why}" for p, why in broken]
        sys.exit(
            "ERROR: invalid YAML front matter - MkDocs would render it as page text.\n"
            + "\n".join(lines)
            + "\n       Quote any value containing a colon, e.g. description: \"a: b\"."
        )


_VERSION_HEADING_RE = re.compile(r"^##[ \t]+\[(\d+)\.(\d+)\.(\d+)\]", re.MULTILINE)


def newest_released_version(changelog: Path) -> str:
    """Highest calver (YY.M.D) in the changelog's `## [version]` headings; skips Unreleased."""
    text = Path(changelog).read_text(encoding="utf-8-sig")
    versions = [tuple(int(g) for g in m.groups()) for m in _VERSION_HEADING_RE.finditer(text)]
    if not versions:
        sys.exit(f"ERROR: no '## [YY.M.D]' release heading found in {changelog}.")
    return ".".join(str(n) for n in max(versions))


def check_installed_version(changelog: Path, installed: str) -> None:
    """Fail when the installed oryxflow is older than the newest release in its changelog.

    The API page documents the installed package, so a stale install would publish an API
    older than the changelog beside it. Compared numerically, not as strings.
    """
    newest = newest_released_version(changelog)
    as_tuple = lambda v: tuple(int(n) for n in v.split(".")[:3])  # noqa: E731
    if as_tuple(installed) < as_tuple(newest):
        sys.exit(
            f"ERROR: installed oryxflow {installed} is older than the newest release {newest} "
            "in its CHANGELOG.md, so the API page would document an older oryxflow.\n"
            "       Reinstall: pip install ../oryxflow (or run scripts/sync_release.py, then\n       pip install -r docs/requirements-cloudflare.txt)"
        )
    print(f"oryxflow installed {installed}; newest changelog release {newest}", flush=True)


def check_blog_excerpts(root: Path = ROOT) -> None:
    """Every blog post needs a <!-- more --> marker (MkDocs blog `post_excerpt: required`).

    Zensical's blog does not enforce it, and a post without the marker would show its
    whole body on the /blog/ index instead of a teaser.
    """
    posts = Path(root) / "docs" / "blog" / "posts"
    bad = [p for p in sorted(posts.glob("*.md"))
           if "<!-- more -->" not in p.read_text(encoding="utf-8-sig")]
    if bad:
        names = "\n".join(f"  {p.name}" for p in bad)
        sys.exit(f"ERROR: blog posts without a <!-- more --> excerpt marker:\n{names}")


def generate(check=False):
    for page, out in TESTED_PAGES.items():
        outp = ROOT / out
        if check:
            fd, tmp = tempfile.mkstemp(suffix=".py")
            os.close(fd)
            run([sys.executable, "-m", "phmdoctest", page, "--outfile", tmp])
            stale = not outp.exists() or not filecmp.cmp(tmp, outp, shallow=False)
            os.unlink(tmp)
            if stale:
                sys.exit(
                    f"ERROR: {out} is out of date with {page}.\n"
                    f"       Run `python scripts/build_docs.py` and commit the result."
                )
        else:
            run([sys.executable, "-m", "phmdoctest", page, "--outfile", str(outp)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if generated test files are stale (CI)")
    ap.add_argument("--skip-tests", action="store_true", help="skip regenerating/running doc tests")
    ap.add_argument("--strict", action="store_true", help="pass --strict to zensical build")
    ap.add_argument("--src-root", type=Path, default=Path(os.environ.get("ORYX_SRC_ROOT", "..")),
                    help="folder holding the oryxflow/ and oryxeval/ checkouts "
                         "(default: $ORYX_SRC_ROOT, else ..)")
    ap.add_argument("--offline", action="store_true",
                    help="do not read sibling checkouts: use the committed _external/ snapshots "
                         "(the Cloudflare build)")
    ap.add_argument("--use-snapshot", action="append", default=[], metavar="REPO",
                    choices=EXTERNAL_REPOS,
                    help="use the committed snapshot for this repo only (repeatable); "
                         "CI uses it for oryxeval, which has no GitHub remote yet")
    ap.add_argument("--regen", action="store_true",
                    help="only validate front matter and regenerate doc tests (pre-commit hook)")
    args = ap.parse_args()

    # Relative --src-root / ORYX_SRC_ROOT resolve against the repo, not the caller's cwd.
    src_root = args.src_root if args.src_root.is_absolute() else (ROOT / args.src_root)

    # Always: a page whose front matter doesn't parse renders it as visible text.
    check_front_matter()
    check_blog_excerpts()

    # Pre-commit path: regenerate and stop. No pytest, no build — the hook has to be
    # fast enough that nobody is tempted to --no-verify past it.
    if args.regen:
        generate(check=False)
        return

    # Build path only: needs the sibling checkouts unless --offline / --use-snapshot.
    snapshot = EXTERNAL_REPOS if args.offline else tuple(args.use_snapshot)
    fetch_sources(src_root, ROOT / "_external", snapshot=snapshot)
    import oryxflow

    check_installed_version(ROOT / "_external" / "oryxflow" / "CHANGELOG.md", oryxflow.__version__)

    if not args.skip_tests:
        generate(check=args.check)
        run([sys.executable, "-m", "pytest", *TESTED_PAGES.values(), "-q"])

    build = [sys.executable, "-m", "zensical", "build"]
    if args.strict:
        build.append("--strict")
    run(build)

    # Crawler-facing metadata: fail on a missing/duplicate title or description (scripts/check_seo.py).
    import check_seo

    seo_errors, seo_warnings = check_seo.check_site(ROOT / "site")
    for w in seo_warnings:
        print(f"WARNING: {w}", flush=True)
    if seo_errors:
        sys.exit("ERROR: SEO check failed:\n  " + "\n  ".join(seo_errors))
    print(f"SEO check OK ({len(seo_warnings)} warning(s))", flush=True)

    # Zensical has no git-revision-date plugin: stamp sitemap <lastmod> and JSON-LD
    # dateModified from git commit dates (see scripts/stamp_lastmod.py).
    import stamp_lastmod

    docs = ROOT / "docs"
    if not stamp_lastmod.ensure_full_history(ROOT):
        print("\nOK (WARNING: dates not stamped): site built to ./site", flush=True)
        return
    n_loc = stamp_lastmod.stamp_lastmod(ROOT / "site", docs)
    n_mod = stamp_lastmod.stamp_date_modified(ROOT / "site", docs)
    print(f"stamped <lastmod> on {n_loc} sitemap entries, dateModified on {n_mod} pages", flush=True)
    print("\nOK: site built to ./site", flush=True)


if __name__ == "__main__":
    main()
