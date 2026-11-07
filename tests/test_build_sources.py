"""Tests for fetch_sources in scripts/build_docs.py, on tiny source trees in tmp_path."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "build_docs", Path(__file__).resolve().parent.parent / "scripts" / "build_docs.py"
)
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)


def _make_src(root: Path, repos=("oryxflow", "oryxeval")):
    for repo in repos:
        (root / repo).mkdir(parents=True)
        (root / repo / "CHANGELOG.md").write_text(f"# Changelog\n{repo} notes\n", encoding="utf-8")


def test_fetch_copies_both_changelogs(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "_external"
    _make_src(src)
    bd.fetch_sources(src, dest)
    for repo in ("oryxflow", "oryxeval"):
        copied = dest / repo / "CHANGELOG.md"
        assert copied.read_text(encoding="utf-8") == f"# Changelog\n{repo} notes\n"


def test_fetch_names_missing_repo(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "_external"
    _make_src(src, repos=("oryxflow",))
    with pytest.raises(SystemExit) as exc:
        bd.fetch_sources(src, dest)
    assert "oryxeval" in str(exc.value)


def test_blog_excerpt_marker_required(tmp_path):
    posts = tmp_path / "docs" / "blog" / "posts"
    posts.mkdir(parents=True)
    (posts / "ok.md").write_text("---\ntitle: a\n---\nIntro\n<!-- more -->\nBody\n", encoding="utf-8")
    bd.check_blog_excerpts(tmp_path)  # no error
    (posts / "bad.md").write_text("---\ntitle: b\n---\nNo marker\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        bd.check_blog_excerpts(tmp_path)
    assert "bad.md" in str(exc.value) and "ok.md" not in str(exc.value)


CHANGELOG = """# Changelog

## [Unreleased]
- x

## [26.11.6] - 2026-11-06
- y

## [26.9.30] - 2026-09-30
"""


def _changelog(tmp_path, text=CHANGELOG):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_newest_released_version_skips_unreleased(tmp_path):
    assert bd.newest_released_version(_changelog(tmp_path)) == "26.11.6"


def test_stale_install_fails_naming_oryxflow(tmp_path):
    with pytest.raises(SystemExit) as exc:
        bd.check_installed_version(_changelog(tmp_path), "26.11.5")
    assert "oryxflow" in str(exc.value) and "26.11.6" in str(exc.value)


def test_numeric_not_string_version_compare(tmp_path):
    with pytest.raises(SystemExit):
        bd.check_installed_version(_changelog(tmp_path), "26.9.30")


def test_current_or_newer_install_ok(tmp_path):
    bd.check_installed_version(_changelog(tmp_path), "26.11.6")
    bd.check_installed_version(_changelog(tmp_path), "26.12.1")


# --- snapshot / offline mode -------------------------------------------------------------

def _make_snapshots(dest: Path, repos=("oryxflow", "oryxeval")):
    for repo in repos:
        (dest / repo).mkdir(parents=True, exist_ok=True)
        (dest / repo / "CHANGELOG.md").write_text("snap\n", encoding="utf-8")


def test_snapshot_repo_is_not_fetched_from_siblings(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "_external"
    _make_src(src, repos=("oryxflow",))  # oryxeval absent
    _make_snapshots(dest)
    bd.fetch_sources(src, dest, snapshot=("oryxeval",))
    assert (dest / "oryxflow" / "CHANGELOG.md").read_text(encoding="utf-8").startswith("# Changelog")
    assert (dest / "oryxeval" / "CHANGELOG.md").read_text(encoding="utf-8") == "snap\n"


def test_offline_never_reads_siblings(tmp_path):
    dest = tmp_path / "_external"
    _make_snapshots(dest)
    bd.fetch_sources(tmp_path / "does-not-exist", dest, snapshot=bd.EXTERNAL_REPOS)
    assert (dest / "oryxflow" / "CHANGELOG.md").read_text(encoding="utf-8") == "snap\n"


def test_missing_snapshot_fails_clearly(tmp_path):
    dest = tmp_path / "_external"
    _make_snapshots(dest, repos=("oryxflow",))
    with pytest.raises(SystemExit) as exc:
        bd.fetch_sources(tmp_path, dest, snapshot=bd.EXTERNAL_REPOS)
    assert "oryxeval" in str(exc.value) and "snapshot" in str(exc.value)


def test_unknown_snapshot_repo_rejected(tmp_path):
    with pytest.raises(SystemExit):
        bd.fetch_sources(tmp_path, tmp_path / "_external", snapshot=("nope",))
