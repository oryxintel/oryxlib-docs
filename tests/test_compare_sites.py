"""Tests for scripts/compare_sites.py, on tiny sites built in tmp_path."""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "compare_sites", Path(__file__).resolve().parent.parent / "scripts" / "compare_sites.py"
)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)
compare = cs.compare


def page(canonical="https://x.dev/", headings=("intro",), desc="d", ld=(), head_extra="", body_extra="", title="t"):
    ld_blocks = "".join(
        f'<script type="application/ld+json">{json.dumps({"@type": t})}</script>' for t in ld
    )
    hs = "".join(f'<h2 id="{h}">{h}</h2>' for h in headings)
    return (
        f'<html><head><title>{title}</title><link rel="canonical" href="{canonical}">'
        f'<meta name="description" content="{desc}">{ld_blocks}{head_extra}</head>'
        f"<body>{hs}{body_extra}</body></html>"
    )


def sitemap(*locs):
    body = "".join(f"<url><loc>{u}</loc></url>" for u in locs)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def write(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
    return root


def base_files():
    return {
        "index.html": page(ld=["SoftwareApplication"]),
        "run/index.html": page(canonical="https://x.dev/run/"),
        "_redirects": "/a /b 301\n",
        "_headers": "/* \n  X: y\n",
        "robots.txt": "User-agent: *\n",
        "sitemap.xml": sitemap("https://x.dev/", "https://x.dev/run/"),
    }


def two(tmp_path, old_extra=None, new_extra=None, drop_new=()):
    o, n = base_files(), base_files()
    o.update(old_extra or {})
    n.update(new_extra or {})
    for d in drop_new:
        n.pop(d, None)
    return write(tmp_path / "old", o), write(tmp_path / "new", n)


RUN = "https://x.dev/run/"


def test_identical_sites_have_no_problems(tmp_path):
    old, new = two(tmp_path)
    assert compare(old, new, set()) == []


def test_missing_page_reported(tmp_path):
    old, new = two(tmp_path, drop_new=["run/index.html"])
    probs = compare(old, new, set())
    assert any("run/index.html" in p for p in probs)


def test_extra_page_reported_unless_allowed(tmp_path):
    old, new = two(tmp_path, new_extra={"extra/index.html": page()})
    assert any("extra/index.html" in p for p in compare(old, new, set()))
    assert compare(old, new, {"extra/index.html"}) == []


def test_redirects_must_be_byte_identical(tmp_path):
    old, new = two(tmp_path, new_extra={"_redirects": "/a /c 301\n"})
    assert any("_redirects" in p for p in compare(old, new, set()))
    old2, new2 = two(tmp_path / "m", drop_new=["_headers"])
    assert any("_headers" in p for p in compare(old2, new2, set()))


def test_canonical_mismatch_reported(tmp_path):
    old, new = two(tmp_path, new_extra={"run/index.html": page(canonical="https://x.dev/other/")})
    assert any("run/index.html" in p and "canonical" in p for p in compare(old, new, set()))


def test_sitemap_loc_sets_compared(tmp_path):
    old, new = two(tmp_path, new_extra={"sitemap.xml": sitemap("https://x.dev/")})
    assert any("sitemap.xml" in p for p in compare(old, new, set()))


def test_lost_json_ld_reported(tmp_path):
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, ld=["FAQPage"])},
        new_extra={"index.html": page()},
    )
    probs = compare(old, new, set())
    assert any("index.html" in p and "SoftwareApplication" in p for p in probs)
    assert any("run/index.html" in p and "FAQPage" in p for p in probs)


# --- addendum rules 7-13 ---

def test_non_page_file_missing_reported_and_internal_ignored(tmp_path):
    old, new = two(
        tmp_path,
        old_extra={
            "llms.txt": "# t\n",
            "assets/logo.png": b"png",
            "assets/javascripts/bundle.js": "x",
            "search/search_index.json": "{}",
            "sitemap.xml.gz": b"gz",
        },
    )
    probs = compare(old, new, set())
    assert any("llms.txt" in p for p in probs)
    assert any("assets/logo.png" in p for p in probs)
    assert not any("bundle.js" in p or "search_index" in p or "sitemap.xml.gz" in p for p in probs)
    assert not any("llms.txt" in p for p in compare(old, new, {"llms.txt", "assets/logo.png"}))


def test_heading_anchor_subset(tmp_path):
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, headings=["a", "b", "c"])},
        new_extra={"run/index.html": page(canonical=RUN, headings=["a", "z"])},
    )
    probs = [p for p in compare(old, new, set()) if "heading" in p]
    assert len(probs) == 1 and "run/index.html" in probs[0] and "b" in probs[0] and "c" in probs[0]
    # extras in new are fine
    old2, new2 = two(
        tmp_path / "m",
        new_extra={"run/index.html": page(canonical=RUN, headings=["intro", "more"])},
    )
    assert compare(old2, new2, set()) == []


def test_heading_anchor_cap(tmp_path):
    ids = [f"h{i}" for i in range(15)]
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, headings=ids)},
    )
    probs = [p for p in compare(old, new, set()) if "heading" in p]
    assert len(probs) == 1 and "15" in probs[0] and "h14" not in probs[0]


def test_meta_description_mismatch(tmp_path):
    old, new = two(tmp_path, new_extra={"run/index.html": page(canonical=RUN, desc="other")})
    assert any("run/index.html" in p and "description" in p for p in compare(old, new, set()))


def test_json_ld_multiset_generalized(tmp_path):
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, ld=["BreadcrumbList", "BreadcrumbList"])},
        new_extra={"run/index.html": page(canonical=RUN, ld=["BreadcrumbList"])},
    )
    assert any("run/index.html" in p and "BreadcrumbList" in p for p in compare(old, new, set()))


def test_theme_assets_referenced(tmp_path):
    old_head = (
        '<link rel="stylesheet" href="../css/extra.css">'
        '<script src="../js/extra.js"></script>'
        '<link rel="preload" href="../fonts/Inter.woff2" as="font" crossorigin>'
    )
    new_head = '<link rel="stylesheet" href="/assets/extra.css?v=2">'
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, head_extra=old_head)},
        new_extra={"run/index.html": page(canonical=RUN, head_extra=new_head)},
    )
    probs = compare(old, new, set())
    assert any("run/index.html" in p and "extra.js" in p for p in probs)
    assert any("run/index.html" in p and "Inter.woff2" in p for p in probs)
    assert not any("extra.css" in p for p in probs)


def test_llms_txt_sections_and_links(tmp_path):
    txt = "# T\n## Docs\n- [a](https://x.dev/a)\n## Api\n- [b](https://x.dev/b)\n"
    reflowed = "# T\n##  Docs\n- [a]( https://x.dev/a )\n## Api\n- [b](https://x.dev/b)\n\n"
    old, new = two(tmp_path, old_extra={"llms.txt": txt, "llms-full.txt": "full"},
                   new_extra={"llms.txt": reflowed, "llms-full.txt": "full2"})
    assert compare(old, new, set()) == []
    bad = "# T\n## Docs\n- [a](https://x.dev/a)\n"
    old2, new2 = two(tmp_path / "m", old_extra={"llms.txt": txt}, new_extra={"llms.txt": bad})
    assert any("llms.txt" in p for p in compare(old2, new2, set()))
    old3, new3 = two(tmp_path / "k", old_extra={"llms.txt": txt, "llms-full.txt": "f"},
                     new_extra={"llms.txt": txt})
    assert any("llms-full.txt" in p for p in compare(old3, new3, set()))


def test_edit_link_must_match(tmp_path):
    edit_old = '<a href="https://git/edit/run.md" title="Edit this page" class="md-content__button">e</a>'
    edit_new = '<a href="https://git/edit/other.md" title="Edit this page" class="md-content__button">e</a>'
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, body_extra=edit_old)},
        new_extra={"run/index.html": page(canonical=RUN, body_extra=edit_new)},
    )
    assert any("run/index.html" in p and "edit" in p.lower() for p in compare(old, new, set()))
    old2, new2 = two(
        tmp_path / "m",
        old_extra={"run/index.html": page(canonical=RUN, body_extra=edit_old)},
        new_extra={"run/index.html": page(canonical=RUN, body_extra=edit_old)},
    )
    assert compare(old2, new2, set()) == []


def test_json_ld_graph_types_found(tmp_path):
    graph = (
        '<script type="application/ld+json">'
        + json.dumps({"@context": "https://schema.org",
                      "@graph": [{"@type": "SoftwareApplication"}, {"@type": ["Organization", "Thing"]}]})
        + "</script>"
    )
    old, new = two(
        tmp_path,
        old_extra={"index.html": page(head_extra=graph)},
        new_extra={"index.html": page()},
    )
    probs = [p for p in compare(old, new, set()) if "index.html" in p and "SoftwareApplication" in p]
    assert probs
    assert any("Organization" in p for p in compare(old, new, set()))
    # identical graph block: no problem; top-level array also read
    old2, new2 = two(tmp_path / "m", old_extra={"index.html": page(head_extra=graph)},
                     new_extra={"index.html": page(head_extra=graph)})
    assert compare(old2, new2, set()) == []


def test_malformed_sitemap_reported_not_raised(tmp_path):
    old, new = two(tmp_path, new_extra={"sitemap.xml": "<urlset><url>"})
    assert any("sitemap.xml" in p for p in compare(old, new, set()))


def test_description_difference_allowed_per_page(tmp_path):
    old, new = two(
        tmp_path,
        old_extra={"run/index.html": page(canonical=RUN, desc="a")},
        new_extra={"run/index.html": page(canonical=RUN, desc="b")},
    )
    assert any("meta description" in p for p in compare(old, new, set()))
    assert compare(old, new, {"description:run/index.html"}) == []
    # the allowance is per page: another page's difference is still reported
    assert any("meta description" in p for p in compare(old, new, {"description:other/index.html"}))


def test_allow_sitemap_loc_and_llms_forms(tmp_path):
    txt = "# t\n\n## Old\n\n- [a](https://x.dev/a/index.md)\n"
    new_txt = "# t\n\n## New\n\n- [a](https://x.dev/a/index.md)\n- [b](https://x.dev/b/index.md)\n"
    new_map = sitemap("https://x.dev/", "https://x.dev/run/", "https://x.dev/b/")
    old, new = two(tmp_path, old_extra={"llms.txt": txt},
                   new_extra={"llms.txt": new_txt, "sitemap.xml": new_map})
    probs = compare(old, new, set())
    assert any("sitemap.xml" in p for p in probs) and any("section headings" in p for p in probs)
    assert any("linked URLs" in p for p in probs)
    allow = {"sitemap-loc:https://x.dev/b/", "llms-sections", "llms-url:https://x.dev/b/index.md"}
    assert compare(old, new, allow) == []
    # the allowance is exact: another extra URL is still reported
    assert compare(old, new, {"sitemap-loc:https://x.dev/other/", "llms-sections",
                              "llms-url:https://x.dev/b/index.md"}) != []


def test_edit_link_prefix_allowlist_is_narrow(tmp_path):
    def hrefs(repo, name):
        return f'<a href="https://gh/{repo}/edit/main/docs/{name}" title="Edit this page" class="md-content__button">e</a>'

    rule = {"edit-link-prefix:https://gh/old/edit/=>https://gh/new/edit/"}

    def run(sub, old_name, new_name, allow):
        old = write(tmp_path / sub / "o", base_files() | {"run/index.html": page(canonical=RUN, body_extra=hrefs("old", old_name))})
        new = write(tmp_path / sub / "n", base_files() | {"run/index.html": page(canonical=RUN, body_extra=hrefs("new", new_name))})
        return [p for p in compare(old, new, allow) if "edit" in p.lower()]

    assert run("a", "run.md", "run.md", set())            # not allowed without the entry
    assert not run("b", "run.md", "run.md", rule)         # repo moved, same file: accepted
    assert run("c", "run.md", "other.md", rule)           # different file path: still a problem


def test_title_difference_is_a_problem(tmp_path):
    old, new = two(tmp_path, old_extra={"run/index.html": page(canonical=RUN, title="Run - x")},
                   new_extra={"run/index.html": page(canonical=RUN, title="Run - y")})
    probs = compare(old, new, set())
    assert any("run/index.html" in p and "<title> differs" in p for p in probs)


def test_title_difference_allowed_per_page(tmp_path):
    old, new = two(tmp_path, old_extra={"run/index.html": page(canonical=RUN, title="Run - x")},
                   new_extra={"run/index.html": page(canonical=RUN, title="Run - y")})
    assert compare(old, new, {"title:run/index.html"}) == []
    assert any("<title> differs" in p for p in compare(old, new, {"title:other/index.html"}))


def test_equal_titles_pass(tmp_path):
    old, new = two(tmp_path)
    assert compare(old, new, set()) == []
