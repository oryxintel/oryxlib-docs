"""Tests for scripts/check_seo.py, on tiny sites built in tmp_path."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_seo", Path(__file__).resolve().parent.parent / "scripts" / "check_seo.py"
)
seo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seo)

GOOD_DESC = (
    "A page description that is long enough to sit inside the recommended range for "
    "search results, about one hundred thirty characters."
)


def page(title="T", desc=GOOD_DESC, canonical="https://x.dev/a/", extra="", skip=()):
    tags = {
        "title": f"<title>{title}</title>",
        "description": f'<meta name="description" content="{desc}">',
        "canonical": f'<link rel="canonical" href="{canonical}">',
        "og:title": f'<meta property="og:title" content="{title}">',
        "og:description": f'<meta property="og:description" content="{desc}">',
        "og:url": f'<meta property="og:url" content="{canonical}">',
    }
    body = "".join(v for k, v in tags.items() if k not in skip)
    return f"<html><head>{body}{extra}</head><body>x</body></html>"


def build(tmp_path, pages):
    for rel, html in pages.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    return tmp_path


def test_clean_site_passes(tmp_path):
    site = build(tmp_path, {"a/index.html": page("A"), "b/index.html": page("B", desc=GOOD_DESC + " B.")})
    assert seo.check_site(site) == ([], [])
    assert seo.main([str(site)]) == 0


def test_each_missing_field_is_an_error(tmp_path):
    for field in seo.REQUIRED:
        site = build(tmp_path / field.replace(":", "_"), {"a/index.html": page(skip=(field,))})
        errors, _ = seo.check_site(site)
        assert errors == [f"a/index.html: missing {field}"], (field, errors)


def test_duplicate_description_and_title_are_errors(tmp_path):
    site = build(tmp_path, {"a/index.html": page("Same"), "b/index.html": page("Same")})
    errors, _ = seo.check_site(site)
    assert any(e.startswith("duplicate title on 2 pages") for e in errors)
    assert any(e.startswith("duplicate description on 2 pages") for e in errors)
    assert seo.main([str(site)]) == 1


def test_404_and_noindex_pages_are_excluded(tmp_path):
    site = build(tmp_path, {
        "a/index.html": page("A"),
        "404.html": page("A", skip=("canonical", "og:url")),
        "n/index.html": page("A", extra='<meta name="robots" content="noindex">', skip=("title",)),
    })
    assert seo.check_site(site) == ([], [])


def test_length_outside_range_only_warns(tmp_path):
    site = build(tmp_path, {
        "short/index.html": page("S", desc="Too short."),
        "long/index.html": page("L", desc="x" * 161),
        "title/index.html": page("T" * 66),
    })
    errors, warnings = seo.check_site(site)
    assert errors == []
    assert any("short/index.html" in w and "description is 10 chars" in w for w in warnings)
    assert any("long/index.html" in w and "161 chars" in w for w in warnings)
    assert any("title/index.html" in w and "title is 66 chars" in w for w in warnings)
    assert seo.main([str(site)]) == 0
