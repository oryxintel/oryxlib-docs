"""Compare two built static sites for functional parity (stdlib only).

Used to prove the Zensical build matches the MkDocs baseline: same pages,
same SEO / structured data, same anchors, same assets.

    python scripts/compare_sites.py OLD NEW [--allow FILE]

Exit code 1 when any problem is found. ``--allow`` names a file with one entry per line
(``#`` comments and blank lines ignored). Every entry accepts one specific difference:

* ``<site-relative path>`` (bare path): that file may be present only in NEW (an added page
  or asset), or present only in OLD when it is a non-page file (a generator replaced it).
  A page (.html) missing from NEW is never allowed.
* ``description:<page path>``: that page's meta description may differ.
* ``title:<page path>``: that page's <title> may differ (every other common page must have an equal title).
* ``sitemap-loc:<url>``: that <loc> may be present only in NEW's sitemap.
* ``llms-url:<url>``: that URL may be present only in NEW's llms.txt.
* ``llms-sections``: llms.txt section headings may differ (a deliberate restructure).
* ``edit-link-prefix:<old>=><new>``: an "Edit this page" href starting with <old> in OLD
  may appear as the same href with <old> replaced by <new> in NEW (the edit link's
  host/repo moved; the file path part must be unchanged).

Anything else missing from NEW (pages, sitemap URLs, llms URLs, headings, ...) is a problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

# Files that must be byte-identical (rule 3).
EXACT_FILES = ("_redirects", "_headers", "robots.txt")

# Paths the theme/generator emits itself; not compared as "non-page files" (rule 7).
GENERATOR_INTERNAL = (
    "search/",
    "assets/javascripts/",
    "assets/stylesheets/",
    "assets/images/",
    "sitemap.xml.gz",
)

# Non-page files already covered by a dedicated rule (3, 5), skipped in rule 7.
_DEDICATED = set(EXACT_FILES) | {"sitemap.xml"}

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
MAX_LISTED = 10


class _PageInfo(HTMLParser):
    """Collects everything the comparison rules need from one HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonical = None
        self.description = None
        self.title = None
        self._in_title = False
        self.heading_ids: list[str] = []
        self.ld_types: Counter = Counter()
        self.assets: set[str] = set()  # basenames of extra.css/js and font preloads
        self.edit_hrefs: set[str] = set()
        self._in_ld = False
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "link":
            rel = a.get("rel", "").lower().split()
            href = a.get("href", "")
            if "canonical" in rel and self.canonical is None:
                self.canonical = href
            if "preload" in rel and a.get("as", "").lower() == "font" and href:
                self.assets.add(_basename(href))
            self._maybe_extra(href)
        elif tag == "title" and self.title is None:
            self._in_title = True
            self.title = ""
        elif tag == "script":
            self._maybe_extra(a.get("src", ""))
            if a.get("type", "").lower() == "application/ld+json":
                self._in_ld = True
                self._ld_buf = []
        elif tag == "meta":
            if a.get("name", "").lower() == "description" and self.description is None:
                self.description = a.get("content", "")
        elif tag in HEADINGS:
            if a.get("id"):
                self.heading_ids.append(a["id"])
        elif tag == "a":
            classes = a.get("class", "").split()
            if a.get("title", "") == "Edit this page" or "md-content__button" in classes:
                self.edit_hrefs.add(a.get("href", ""))

    def _maybe_extra(self, url):
        name = _basename(url)
        if re.fullmatch(r"extra\.(css|js)", name):
            self.assets.add(name)

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        if self._in_ld:
            self._ld_buf.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self._collect_ld("".join(self._ld_buf))

    def _collect_ld(self, raw):
        try:
            data = json.loads(raw)
        except ValueError:
            return
        nodes = data if isinstance(data, list) else [data]
        for item in nodes:
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                nodes = nodes + item["@graph"]
        for item in nodes:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            for name in t if isinstance(t, list) else [t]:
                if name:
                    self.ld_types[str(name)] += 1


def _basename(url: str) -> str:
    return url.split("#")[0].split("?")[0].rstrip("/").rsplit("/", 1)[-1]


def _parse(path: Path) -> _PageInfo:
    info = _PageInfo()
    info.feed(path.read_text(encoding="utf-8", errors="replace"))
    info.close()
    return info


def _rel_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _capped(items) -> str:
    items = list(items)
    shown = ", ".join(items[:MAX_LISTED])
    extra = len(items) - MAX_LISTED
    return shown + (f" (+{extra} more)" if extra > 0 else "")


def _sitemap_locs(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    return {e.text.strip() for e in root.iter() if e.tag.endswith("}loc") or e.tag == "loc" if e.text}


def _llms_facts(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = {" ".join(m.split()) for m in re.findall(r"^##[ \t]+(.+?)\s*$", text, re.M)}
    urls = set(re.findall(r"https?://[^\s)>\]]+", text))
    return sections, urls


def _rule_pages(old_pages, new_pages, allow):
    probs = [f"page missing from new site: {p}" for p in sorted(set(old_pages) - set(new_pages))]
    probs += [
        f"unexpected extra page in new site: {p}"
        for p in sorted(set(new_pages) - set(old_pages))
        if p not in allow
    ]
    return probs


def _rule_exact_files(old: Path, new: Path):
    probs = []
    for name in EXACT_FILES:
        o, n = old / name, new / name
        if o.is_file() and not n.is_file():
            probs.append(f"{name}: missing from new site")
        elif o.is_file() and o.read_bytes() != n.read_bytes():
            probs.append(f"{name}: not byte-identical to old site")
    return probs


def _rule_sitemap(old: Path, new: Path, allow=frozenset()):
    o, n = old / "sitemap.xml", new / "sitemap.xml"
    if not o.is_file():
        return []
    if not n.is_file():
        return ["sitemap.xml: missing from new site"]
    try:
        lo, ln = _sitemap_locs(o), _sitemap_locs(n)
    except ET.ParseError as exc:
        return [f"sitemap.xml: cannot be parsed as XML ({exc})"]
    if lo == ln:
        return []
    out = [f"sitemap.xml: <loc> missing from new: {u}" for u in sorted(lo - ln)]
    out += [f"sitemap.xml: <loc> only in new: {u}" for u in sorted(ln - lo)
            if f"sitemap-loc:{u}" not in allow]
    return out


def _rule_non_page_files(old_all, new_all, allow):
    probs = []
    new_set = set(new_all)
    for rel in old_all:
        if rel.endswith(".html") or rel in _DEDICATED or rel in allow:
            continue
        if any(rel == p or rel.startswith(p) for p in GENERATOR_INTERNAL):
            continue
        if rel not in new_set:
            probs.append(f"file missing from new site: {rel}")
    return probs


def _rule_llms(old: Path, new: Path, allow=frozenset()):
    o, n = old / "llms.txt", new / "llms.txt"
    if not (o.is_file() and n.is_file()):
        return []  # existence is reported by the non-page-file rule
    (so, uo), (sn, un) = _llms_facts(o), _llms_facts(n)
    probs = []
    if so != sn and "llms-sections" not in allow:
        probs.append(
            f"llms.txt: section headings differ (missing: {sorted(so - sn)}, extra: {sorted(sn - so)})"
        )
    missing = sorted(uo - un)
    extra = sorted(u for u in un - uo if f"llms-url:{u}" not in allow)
    if missing or extra:
        probs.append(
            f"llms.txt: linked URLs differ (missing: {_capped(missing)}; "
            f"extra: {_capped(extra)})"
        )
    return probs


def _rule_page(page, o: _PageInfo, n: _PageInfo, allow=frozenset()):
    probs = []
    if o.canonical != n.canonical:
        probs.append(f"{page}: canonical differs (old {o.canonical!r}, new {n.canonical!r})")
    if o.description != n.description and f"description:{page}" not in allow:
        probs.append(f"{page}: meta description differs (old {o.description!r}, new {n.description!r})")
    if o.title != n.title and f"title:{page}" not in allow:
        probs.append(f"{page}: <title> differs (old {o.title!r}, new {n.title!r})")
    missing_ids = [i for i in dict.fromkeys(o.heading_ids) if i not in set(n.heading_ids)]
    if missing_ids:
        probs.append(
            f"{page}: {len(missing_ids)} heading id(s) missing in new: {_capped(missing_ids)}"
        )
    lost = o.ld_types - n.ld_types
    for t, count in sorted(lost.items()):
        probs.append(f"{page}: JSON-LD @type {t} lost in new (old x{o.ld_types[t]}, new x{n.ld_types[t]})")
    for asset in sorted(o.assets - n.assets):
        probs.append(f"{page}: theme asset {asset} no longer referenced in new")
    missing_edit = sorted(h for h in o.edit_hrefs - n.edit_hrefs
                          if not _edit_link_moved(h, n.edit_hrefs, allow))
    if missing_edit:
        probs.append(f"{page}: edit link missing or changed in new (old href(s): {', '.join(missing_edit)})")
    return probs


def _edit_link_moved(href: str, new_hrefs, allow) -> bool:
    """True if an `edit-link-prefix:<old>=><new>` entry maps href onto one of new_hrefs."""
    for entry in allow:
        if not entry.startswith("edit-link-prefix:") or "=>" not in entry:
            continue
        old_p, new_p = entry[len("edit-link-prefix:"):].split("=>", 1)
        if old_p and href.startswith(old_p) and new_p + href[len(old_p):] in new_hrefs:
            return True
    return False


def compare(old: Path, new: Path, allow: set[str]) -> list[str]:
    """Return one human-readable problem per item; an empty list means parity."""
    old, new = Path(old), Path(new)
    old_all, new_all = _rel_files(old), _rel_files(new)
    old_pages = [p for p in old_all if p.endswith(".html")]
    new_pages = [p for p in new_all if p.endswith(".html")]

    probs = _rule_pages(old_pages, new_pages, allow)
    probs += _rule_exact_files(old, new)
    probs += _rule_non_page_files(old_all, new_all, allow)
    probs += _rule_sitemap(old, new, allow)
    probs += _rule_llms(old, new, allow)
    for page in sorted(set(old_pages) & set(new_pages)):
        probs += _rule_page(page, _parse(old / page), _parse(new / page), allow)
    return probs


def _read_allow(path: str | None) -> set[str]:
    if not path:
        return set()
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--allow", help="file of accepted differences: site-relative paths, or description:<page> / title:<page> lines")
    args = ap.parse_args(argv)
    problems = compare(args.old, args.new, _read_allow(args.allow))
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
