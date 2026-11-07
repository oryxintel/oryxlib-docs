#!/usr/bin/env python
"""Build-time SEO check on the built site (stdlib only).

    python scripts/check_seo.py [SITE_DIR]

Checks every indexable page in SITE_DIR (every .html file except 404.html, pages with a
robots noindex, and meta-refresh redirect stubs).

Errors (exit 1, the build fails):
  * a page is missing <title>, a meta description, a canonical link, og:title,
    og:description or og:url
  * two indexable pages share a title, or share a description

Warnings (printed, never fail):
  * a description is shorter than 120 or longer than 160 characters (search results cut
    descriptions around 155-160)
  * a title is longer than 65 characters
"""
from __future__ import annotations

import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DESC_MIN, DESC_MAX, TITLE_MAX = 120, 160, 65
REQUIRED = ("title", "description", "canonical", "og:title", "og:description", "og:url")
NOT_INDEXED = ("404.html",)


class _Head(HTMLParser):
    """Collects the SEO-relevant head tags of one page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, str] = {}
        self.noindex = False
        self.redirect = False
        self._in_title = False
        self._title: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "")
            if name in ("description", "og:title", "og:description", "og:url"):
                self.fields.setdefault(name, content.strip())
            elif name == "robots" and "noindex" in content.lower():
                self.noindex = True
            if a.get("http-equiv", "").lower() == "refresh":
                self.redirect = True
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.fields.setdefault("canonical", a.get("href", "").strip())

    def handle_data(self, data):
        if self._in_title:
            self._title.append(data)

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.fields.setdefault("title", "".join(self._title).strip())


def _parse(path: Path) -> _Head:
    head = _Head()
    head.feed(path.read_text(encoding="utf-8", errors="replace"))
    head.close()
    return head


def check_site(site: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the built site; no errors means the check passes."""
    site = Path(site)
    errors: list[str] = []
    warnings: list[str] = []
    titles: dict[str, list[str]] = defaultdict(list)
    descs: dict[str, list[str]] = defaultdict(list)

    for path in sorted(site.rglob("*.html")):
        rel = path.relative_to(site).as_posix()
        if rel in NOT_INDEXED:
            continue
        head = _parse(path)
        if head.noindex or head.redirect:
            continue
        for key in REQUIRED:
            if not head.fields.get(key):
                errors.append(f"{rel}: missing {key}")
        title, desc = head.fields.get("title"), head.fields.get("description")
        if title:
            titles[title].append(rel)
            if len(title) > TITLE_MAX:
                warnings.append(f"{rel}: title is {len(title)} chars (over {TITLE_MAX}): {title!r}")
        if desc:
            descs[desc].append(rel)
            if not DESC_MIN <= len(desc) <= DESC_MAX:
                warnings.append(f"{rel}: description is {len(desc)} chars (want {DESC_MIN}-{DESC_MAX})")

    for kind, groups in (("title", titles), ("description", descs)):
        for text, pages in sorted(groups.items()):
            if len(pages) > 1:
                shown = ", ".join(pages[:6]) + (f" (+{len(pages) - 6} more)" if len(pages) > 6 else "")
                errors.append(f"duplicate {kind} on {len(pages)} pages ({shown}): {text[:80]!r}")
    return errors, warnings


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    site = Path(argv[0]) if argv else ROOT / "site"
    errors, warnings = check_site(site)
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"SEO check: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
