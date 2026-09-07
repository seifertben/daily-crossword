"""Build-time generation of per-date SEO pages for GitHub Pages.

Vite copies ``web/public/puzzles/*.json`` into the build output; this walks
that directory and, for every valid puzzle date, writes ``puzzles/<date>/``
index.html (next to the JSON) using the freshly built ``index.html`` as the
shell. GitHub Pages then serves that file for ``/puzzles/<date>/``, giving each
archive puzzle its own title, canonical URL, and structured data.

Usage::

    uv run python -m api.static_pages [--dist web/dist]

Run after ``npm run build`` so the per-date pages reference the hashed assets
in the exact build being deployed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .seo import render_date_html

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def generate_pages(dist: Path, puzzles: Path | None = None) -> int:
    """Write ``puzzles/<date>/index.html`` for every puzzle in ``dist``.

    Returns the number of pages generated. Puzzles whose date does not match
    strict ``YYYY-MM-DD`` are skipped, and dates whose shell lacks the SEO
    markers are skipped (render returns ``None``).
    """
    dist = Path(dist)
    puzzles_dir = Path(puzzles) if puzzles else dist / "puzzles"
    index_html = dist / "index.html"
    if not index_html.exists():
        raise SystemExit(f"missing SPA shell: {index_html} — build the SPA first")
    shell = index_html.read_text(encoding="utf-8")

    count = 0
    for puzzle in sorted(puzzles_dir.glob("*.json")):
        date = puzzle.stem
        if not _DATE_RE.match(date):
            continue
        page = render_date_html(shell, date)
        if page is None:
            continue
        target = puzzles_dir / date / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate per-date SEO pages into a built SPA directory."
    )
    parser.add_argument(
        "--dist",
        default="web/dist",
        help="Path to the built SPA directory (default: web/dist)",
    )
    parser.add_argument(
        "--puzzles",
        default=None,
        help="Directory of puzzle JSON blobs (default: <dist>/puzzles)",
    )
    args = parser.parse_args()
    count = generate_pages(Path(args.dist), Path(args.puzzles) if args.puzzles else None)
    print(f"Generated {count} per-date SEO page(s)")


if __name__ == "__main__":
    main()
