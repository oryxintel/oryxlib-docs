#!/usr/bin/env python
"""Stamp git commit dates into the built site: sitemap <lastmod> and JSON-LD dateModified.

MkDocs got these from mkdocs-git-revision-date-localized; Zensical has no equivalent, so
after `zensical build` this maps every docs source file to its page URL and writes the
date of the file's last git commit (`git log -1 --format=%cs`) into

  * site/sitemap.xml: a <lastmod> after each matching <loc>
  * site/<page>/index.html: "dateModified" on the page's JSON-LD article node
    (TechArticle / BlogPosting; the home page's SoftwareApplication)

Files without commits (new, untracked) are skipped, so their pages carry no date.

Usage: python scripts/stamp_lastmod.py [SITE_DIR] [DOCS_DIR]
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent

_FRONT_RE = re.compile(r"^-{3}[ \t]*\r?\n(.*?)\r?\n(?:-{3}|\.{3})[ \t]*\r?\n", re.DOTALL)
_LOC_RE = re.compile(r"([ \t]*)<loc>(.*?)</loc>")
_LD_RE = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.DOTALL)
ARTICLE_TYPES = {"TechArticle", "BlogPosting"}


def slugify(text: str) -> str:
    """Category slug as the MkDocs blog plugin made it: lowercase, runs of non-word -> '-'."""
    return re.sub(r"[^\w]+", "-", str(text).strip().lower()).strip("-")


def _front_matter(md: Path) -> dict:
    m = _FRONT_RE.match(md.read_text(encoding="utf-8-sig"))
    meta = yaml.safe_load(m.group(1)) if m else None
    return meta if isinstance(meta, dict) else {}


def url_for_source(md: Path, docs_dir: Path) -> "str | None":
    """Site-relative URL path of a docs source ('' for the home page), or None if not a page."""
    md, docs_dir = Path(md), Path(docs_dir)
    if md.suffix != ".md":
        return None
    try:
        rel = md.relative_to(docs_dir).as_posix()
    except ValueError:
        return None
    if rel.startswith("blog/posts/"):
        meta = _front_matter(md)
        cats = meta.get("categories") or []
        slug = str(meta.get("slug") or md.stem)
        return f"blog/{slugify(cats[0])}/{slug}/" if cats else f"blog/{slug}/"
    stem = rel[: -len(".md")]
    if stem == "index":
        return ""
    if stem.endswith("/index"):
        return stem[: -len("index")]
    return stem + "/"


def git_date(path: Path, cwd: Path) -> "str | None":
    """YYYY-MM-DD of the last commit touching path, or None when it has no commits."""
    r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                       cwd=cwd, capture_output=True, text=True)
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


class PageDates(dict):
    """{url path: git date} for source pages, plus dates for generated blog pages.

    Generated pages (no source file) are resolved on lookup: the blog index and its
    pagination use the newest post date, category pages (and pagination) the newest in
    that category, year archives (and pagination) the newest post of that year.
    """

    def __init__(self, pages, posts):
        super().__init__(pages)
        self.posts = posts  # [(date, category slugs, year)]

    def _newest(self, pred=lambda p: True):
        ds = [p[0] for p in self.posts if pred(p)]
        return max(ds) if ds else None

    def __missing__(self, url):
        m = re.fullmatch(r"blog/(?:page/\d+/)?", url)
        if m:
            d = self._newest()
        elif (m := re.fullmatch(r"blog/category/([^/]+)/(?:page/\d+/)?", url)):
            d = self._newest(lambda p: m.group(1) in p[1])
        elif (m := re.fullmatch(r"blog/archive/(\d{4})/(?:page/\d+/)?", url)):
            d = self._newest(lambda p: p[2] == m.group(1))
        else:
            d = None
        if d is None:
            raise KeyError(url)
        return d

    def get(self, url, default=None):
        try:
            return self[url]
        except KeyError:
            return default


def dates_by_url(docs_dir: Path) -> PageDates:
    """Git dates by url path for every docs page that has a commit (plus generated blog pages)."""
    docs_dir = Path(docs_dir).resolve()
    out, posts = {}, []
    for md in sorted(docs_dir.rglob("*.md")):
        url = url_for_source(md, docs_dir)
        if url is None:
            continue
        d = git_date(md, docs_dir)
        if not d:
            continue
        out[url] = d
        if md.relative_to(docs_dir).as_posix().startswith("blog/posts/"):
            meta = _front_matter(md)
            cats = {slugify(c) for c in meta.get("categories") or []}
            posts.append((d, cats, str(meta.get("date", ""))[:4]))
    return PageDates(out, posts)


def stamp_lastmod(site: Path, docs_dir: Path) -> int:
    """Add <lastmod> after each sitemap <loc> whose page has a git date; return the count."""
    sitemap = Path(site) / "sitemap.xml"
    dates = dates_by_url(docs_dir)
    n = 0

    def repl(m):
        nonlocal n
        path = urlparse(html.unescape(m.group(2)).strip()).path.lstrip("/")
        d = dates.get(path)
        if not d:
            return m.group(0)
        n += 1
        return f"{m.group(0)}\n{m.group(1)}<lastmod>{d}</lastmod>"

    text = sitemap.read_text(encoding="utf-8")
    sitemap.write_text(_LOC_RE.sub(repl, text), encoding="utf-8")
    return n


def _dump(data) -> str:
    # Keep the block safe inside <script>: escape what Jinja's tojson escapes.
    s = json.dumps(data, indent=2, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _nodes(data):
    items = data if isinstance(data, list) else [data]
    for item in items:
        if isinstance(item, dict):
            yield item
            yield from (n for n in item.get("@graph", []) if isinstance(n, dict))


def stamp_date_modified(site: Path, docs_dir: Path) -> int:
    """Set JSON-LD dateModified on each page that has a git date; return pages stamped."""
    site = Path(site)
    count = 0
    dates = dates_by_url(docs_dir)
    for page in sorted(site.rglob("index.html")):
        url = page.parent.relative_to(site).as_posix()
        url = "" if url == "." else url + "/"
        d = dates.get(url)
        if not d:
            continue
        text = page.read_text(encoding="utf-8")
        hit = False

        def repl(m):
            nonlocal hit
            try:
                data = json.loads(m.group(2))
            except ValueError:
                return m.group(0)
            changed = False
            for node in _nodes(data):
                kinds = node.get("@type")
                kinds = set(kinds if isinstance(kinds, list) else [kinds])
                if kinds & ARTICLE_TYPES or (url == "" and "SoftwareApplication" in kinds):
                    node["dateModified"] = d
                    changed = True
            if not changed:
                return m.group(0)
            hit = True
            return f"{m.group(1)}\n{_dump(data)}\n{m.group(3)}"

        new = _LD_RE.sub(repl, text)
        if hit:
            page.write_text(new, encoding="utf-8", newline="")
            count += 1
    return count


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    site = Path(argv[0]) if argv else ROOT / "site"
    docs = Path(argv[1]) if len(argv) > 1 else ROOT / "docs"
    print(f"stamped <lastmod> on {stamp_lastmod(site, docs)} sitemap entries; "
          f"dateModified on {stamp_date_modified(site, docs)} pages")


if __name__ == "__main__":
    main()
