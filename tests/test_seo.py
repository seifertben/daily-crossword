"""Tests for the shared per-date SEO renderer and its build-time consumer."""

from __future__ import annotations

import json

from api.seo import render_date_html
from api.static_pages import generate_pages

SHELL = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Daily Crossword — A New Free Puzzle Every Day</title>
    <meta
      name="description"
      content="A new free crossword puzzle every day at 6 AM Eastern."
    />
    <link rel="canonical" href="https://playdailycrossword.com/" />
    <!-- Open Graph -->
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="Daily Crossword" />
    <meta property="og:title" content="Daily Crossword — A New Free Puzzle Every Day" />
    <meta property="og:url" content="https://playdailycrossword.com/" />
    <!-- Twitter -->
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="Daily Crossword — A New Free Puzzle Every Day" />
    <!-- Structured data -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "Daily Crossword",
      "url": "https://playdailycrossword.com/"
    }
    </script>
  </head>
  <body>
    <div id="root">
      <noscript><h1>Daily Crossword</h1></noscript>
    </div>
  </body>
</html>
"""


def test_render_injects_unique_seo():
    html = render_date_html(SHELL, "2026-09-07")
    assert html is not None
    assert "<title>Daily Crossword — Monday, September 7, 2026</title>" in html
    assert 'rel="canonical" href="https://playdailycrossword.com/puzzles/2026-09-07/"' in html
    assert '"datePublished": "2026-09-07"' in html
    assert '"@type": "WebPage"' in html
    # Static homepage tags are gone — no duplicates.
    assert "A New Free Puzzle Every Day" not in html
    assert 'rel="canonical" href="https://playdailycrossword.com/"' not in html
    # The rest of the shell still works for the SPA.
    assert 'id="root"' in html
    assert '<meta charset="UTF-8" />' in html


def test_render_different_dates_differ():
    a = render_date_html(SHELL, "2026-01-01")
    b = render_date_html(SHELL, "2026-01-02")
    assert a != b
    assert "Thursday, January 1, 2026" in a
    assert "Friday, January 2, 2026" in b


def test_render_none_when_markers_missing():
    assert render_date_html("<html><body>bare</body></html>", "2026-01-01") is None


def test_render_none_on_bad_date():
    assert render_date_html(SHELL, "not-a-date") is None


def test_generate_pages_writes_directory_indexes(tmp_path):
    dist = tmp_path / "dist"
    puzzles = dist / "puzzles"
    puzzles.mkdir(parents=True)
    (dist / "index.html").write_text(SHELL, encoding="utf-8")
    for d in ("2026-09-01", "2026-09-02"):
        puzzle = {"date": d, "width": 3, "height": 3}
        (puzzles / f"{d}.json").write_text(json.dumps(puzzle), encoding="utf-8")
    # Non-date files must be skipped.
    (puzzles / "notes.json").write_text("{}", encoding="utf-8")

    count = generate_pages(dist)

    assert count == 2
    for d in ("2026-09-01", "2026-09-02"):
        page = puzzles / d / "index.html"
        assert page.exists()
        assert f"/puzzles/{d}/" in page.read_text(encoding="utf-8")
    assert not (puzzles / "notes" / "index.html").exists()


def test_generate_pages_missing_shell(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    try:
        generate_pages(dist)
    except SystemExit as exc:
        assert "build the SPA first" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected SystemExit for missing shell")
