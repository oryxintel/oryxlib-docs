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
