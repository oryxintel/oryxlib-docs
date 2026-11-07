"""Tests for scripts/stamp_lastmod.py, on a tiny git repo built in tmp_path."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "stamp_lastmod", Path(__file__).resolve().parent.parent / "scripts" / "stamp_lastmod.py"
)
sl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sl)

BASE = "https://example.test"


def _git(repo, *args, date=None):
    env = dict(os.environ)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00+0000"
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True, env=env)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_docs_page_url(tmp_path):
    docs = tmp_path / "docs"
    assert sl.url_for_source(docs / "docs" / "quickstart.md", docs) == "docs/quickstart/"


def test_index_page_url(tmp_path):
    docs = tmp_path / "docs"
    assert sl.url_for_source(docs / "docs" / "index.md", docs) == "docs/"
    assert sl.url_for_source(docs / "index.md", docs) == ""
    assert sl.url_for_source(docs / "blog" / "index.md", docs) == "blog/"


def test_blog_post_url_uses_first_category_slug(tmp_path):
    docs = tmp_path / "docs"
    post = docs / "blog" / "posts" / "some-file.md"
    _write(post, "---\ndate: 2026-01-01\nslug: my-slug\ncategories:\n  - LLM evals\n  - Other\n---\nbody\n")
    assert sl.url_for_source(post, docs) == "blog/llm-evals/my-slug/"


@pytest.fixture
def site_repo(tmp_path):
    docs = tmp_path / "docs"
    _git(tmp_path, "init", "-q")
    _write(docs / "docs" / "a.md", "# a\n")
    _write(docs / "docs" / "uncommitted.md", "# u\n")
    _git(tmp_path, "add", "docs/docs/a.md")
    _git(tmp_path, "commit", "-q", "-m", "a", date="2025-03-04")
    site = tmp_path / "site"
    _write(site / "sitemap.xml",
           '<?xml version="1.0"?>\n<urlset>\n'
           f'    <url>\n         <loc>{BASE}&#x2f;docs&#x2f;a&#x2f;</loc>\n    </url>\n'
           f'    <url>\n         <loc>{BASE}/docs/other/</loc>\n    </url>\n'
           f'    <url>\n         <loc>{BASE}/docs/uncommitted/</loc>\n    </url>\n'
           '</urlset>\n')
    return docs, site


def test_stamps_matching_locs_only(site_repo):
    docs, site = site_repo
    assert sl.stamp_lastmod(site, docs) == 1
    text = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert text.count("<lastmod>") == 1
    assert "<lastmod>2025-03-04</lastmod>" in text
    assert text.index("<lastmod>") < text.index("/docs/other/")


def _page(site, rel, nodes):
    body = json.dumps(nodes, indent=2)
    html = f'<html><head><script type="application/ld+json">\n{body}\n</script></head><body>x</body></html>'
    _write(site / rel / "index.html", html)
    return html


def test_date_modified_set_on_article_json_ld(site_repo):
    docs, site = site_repo
    _page(site, "docs/a", {"@context": "https://schema.org", "@type": "TechArticle", "headline": "A <b>"})
    before = (site / "docs/a/index.html").read_text(encoding="utf-8")
    assert sl.stamp_date_modified(site, docs) == 1
    after = (site / "docs/a/index.html").read_text(encoding="utf-8")
    block = after.split('ld+json">')[1].split("</script>")[0]
    assert json.loads(block)["dateModified"] == "2025-03-04"
    assert "<b>" not in block  # still escaped inside the script block
    assert after.replace(block, "") == before.replace(before.split('ld+json">')[1].split("</script>")[0], "")


def test_date_modified_skips_pages_without_git_date(site_repo):
    docs, site = site_repo
    html = _page(site, "docs/uncommitted", {"@type": "TechArticle", "headline": "U"})
    assert sl.stamp_date_modified(site, docs) == 0
    assert (site / "docs/uncommitted/index.html").read_text(encoding="utf-8") == html
