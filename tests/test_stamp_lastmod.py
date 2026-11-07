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


def test_generated_blog_pages_use_newest_post_date(tmp_path):
    docs = tmp_path / "docs"
    _git(tmp_path, "init", "-q")
    _write(docs / "blog" / "index.md", "# Blog\n")
    _write(docs / "blog" / "posts" / "p1.md", "---\ndate: 2025-01-01\nslug: one\ncategories:\n  - Alpha\n---\nx\n")
    _write(docs / "blog" / "posts" / "p2.md", "---\ndate: 2026-02-02\nslug: two\ncategories:\n  - Beta Cat\n---\nx\n")
    _git(tmp_path, "add", "docs/blog/index.md", "docs/blog/posts/p1.md")
    _git(tmp_path, "commit", "-q", "-m", "1", date="2025-05-05")
    _git(tmp_path, "add", "docs/blog/posts/p2.md")
    _git(tmp_path, "commit", "-q", "-m", "2", date="2026-06-06")
    d = sl.dates_by_url(docs)
    assert d["blog/category/alpha/"] == "2025-05-05"
    assert d["blog/category/alpha/page/2/"] == "2025-05-05"
    assert d["blog/category/beta-cat/"] == "2026-06-06"
    assert d["blog/page/2/"] == "2026-06-06"
    assert d["blog/archive/2025/"] == "2025-05-05"
    assert d["blog/archive/2026/page/3/"] == "2026-06-06"


def test_string_categories_is_one_category(tmp_path):
    docs = tmp_path / "docs"
    post = docs / "blog" / "posts" / "p.md"
    _write(post, "---\ndate: 2026-01-01\nslug: s\ncategories: LLM evals\n---\nbody\n")
    assert sl.url_for_source(post, docs) == "blog/llm-evals/s/"


def test_shallow_clone_without_unshallow_is_skipped(tmp_path, capsys):
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    _write(origin / "docs" / "a.md", "one\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "1", date="2020-01-01")
    _write(origin / "docs" / "a.md", "two\n")
    _git(origin, "commit", "-qam", "2", date="2021-01-01")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(clone)], check=True)
    assert sl.is_shallow(clone)
    # make unshallowing impossible: the remote disappears
    _git(clone, "remote", "set-url", "origin", (tmp_path / "gone").as_uri())
    assert sl.ensure_full_history(clone) is False
    assert "WARNING" in capsys.readouterr().out
    site = tmp_path / "site"
    _write(site / "sitemap.xml", f"<urlset><url><loc>{BASE}/a/</loc></url></urlset>")
    before = (site / "sitemap.xml").read_text()
    sl.main([str(site), str(clone / "docs")])
    assert (site / "sitemap.xml").read_text() == before


def test_shallow_clone_is_unshallowed_when_possible(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    _write(origin / "docs" / "a.md", "one\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "1", date="2020-01-01")
    _write(origin / "other.txt", "x\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "2", date="2021-01-01")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(clone)], check=True)
    assert sl.ensure_full_history(clone) is True
    assert sl.git_date(clone / "docs" / "a.md", clone) == "2020-01-01"


def test_article_modified_time_meta_added_after_og_type(site_repo):
    docs, site = site_repo
    head = '<meta property="og:type" content="article"><meta property="og:title" content="A">'
    _write(site / "docs/a/index.html", f"<html><head>{head}</head><body>x</body></html>")
    _write(site / "docs/other/index.html",
           '<html><head><meta property="og:type" content="website"></head><body>x</body></html>')
    assert sl.stamp_date_modified(site, docs) == 1
    after = (site / "docs/a/index.html").read_text(encoding="utf-8")
    assert after.count('property="article:modified_time"') == 1
    assert 'content="2025-03-04"' in after.split("article:modified_time")[1]
    assert after.index("og:type") < after.index("article:modified_time") < after.index("og:title")
    # idempotent, and listing pages (og:type website) are left alone
    assert sl.stamp_date_modified(site, docs) == 0
    assert (site / "docs/a/index.html").read_text(encoding="utf-8").count("article:modified_time") == 1
    assert "article:modified_time" not in (site / "docs/other/index.html").read_text(encoding="utf-8")


def test_redirect_stub_dropped_from_sitemap(site_repo):
    docs, site = site_repo
    _write(docs / "docs" / "alias.md", "---\ntemplate: redirect.html\n---\nstub\n")
    text = (site / "sitemap.xml").read_text(encoding="utf-8").replace(
        "</urlset>", f"    <url>\n         <loc>{BASE}/docs/alias/</loc>\n    </url>\n</urlset>")
    (site / "sitemap.xml").write_text(text, encoding="utf-8")
    assert sl.redirect_stub_urls(docs) == {"docs/alias/"}
    sl.stamp_lastmod(site, docs)
    out = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "/docs/alias/" not in out
    assert "/docs/other/" in out and out.count("<url>") == 3 and out.rstrip().endswith("</urlset>")
