"""Tests for the pure helpers in scripts/sync_release.py (tmp_path only; no siblings read)."""
import importlib.util
import sys
from pathlib import Path

import pytest

_scripts = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_scripts))
_spec = importlib.util.spec_from_file_location("sync_release", _scripts / "sync_release.py")
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)

REQ = "-r requirements-docs.txt\n# pinned\noryxflow==26.7.21\n"


def test_rewrite_pin_changes_version():
    new, changed = sr.rewrite_pin(REQ, "26.11.6")
    assert changed and "oryxflow==26.11.6" in new and "26.7.21" not in new
    assert new.startswith("-r requirements-docs.txt\n# pinned\n")


def test_rewrite_pin_unchanged():
    new, changed = sr.rewrite_pin(REQ, "26.7.21")
    assert not changed and new == REQ


def test_rewrite_pin_requires_existing_pin():
    with pytest.raises(SystemExit):
        sr.rewrite_pin("-r requirements-docs.txt\n", "26.11.6")


def test_uses_build_docs_parser():
    # reused, not duplicated
    assert sr.newest_released_version.__module__.endswith("build_docs")


def _src(root: Path, text="# Changelog\n\n## [26.11.6] - x\n"):
    for repo in ("oryxflow", "oryxeval"):
        (root / repo).mkdir(parents=True)
        (root / repo / "CHANGELOG.md").write_text(text, encoding="utf-8")


def test_sync_copies_and_pins(tmp_path):
    src, repo = tmp_path / "src", tmp_path / "repo"
    _src(src)
    (repo / "docs").mkdir(parents=True)
    req = repo / "docs" / "requirements-cloudflare.txt"
    req.write_text(REQ, encoding="utf-8")
    report = sr.sync(src, repo)
    assert (repo / "_external" / "oryxeval" / "CHANGELOG.md").is_file()
    assert "oryxflow==26.11.6" in req.read_text(encoding="utf-8")
    assert report["oryxflow"] == "26.11.6" and report["oryxeval"] == "26.11.6"
    assert any("requirements-cloudflare" in c for c in report["changed"])
    # second run: nothing changed
    assert sr.sync(src, repo)["changed"] == []


def test_sync_names_missing_sibling(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "requirements-cloudflare.txt").write_text(REQ, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        sr.sync(tmp_path / "none", tmp_path)
    assert "oryxflow" in str(exc.value)


def test_sibling_warnings():
    assert sr.sibling_warnings("main", "", "oryxflow") == []
    assert sr.sibling_warnings(None, None, "oryxflow") == []
    w = sr.sibling_warnings("feature", " M CHANGELOG.md", "oryxeval")
    assert len(w) == 2 and "feature" in w[0] and "uncommitted" in w[1]


def test_pypi_warning():
    out = "oryxflow (26.11.6)"+chr(10)+"Available versions: 26.11.6, 26.7.21"+chr(10)
    assert sr.pypi_warning("26.11.6", out) is None
    assert "not on PyPI" in sr.pypi_warning("26.12.1", out)
    assert sr.pypi_warning("26.12.1", None) is None
    assert sr.pypi_warning("26.12.1", "garbage") is None
