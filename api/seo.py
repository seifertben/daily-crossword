"""Shared per-puzzle SEO rendering.

Used at two points:

*  **Runtime** — the FastAPI serving app (``api.main._serve_date_html``)
   injects a per-date ``<head>`` into the built SPA shell for dated routes.
*  **Build time** — ``api.static_pages`` writes a ``puzzles/<date>/index.html``
   next to each puzzle blob so GitHub Pages serves unique HTML per date.

Both use the same renderer so the tags stay consistent across deployments.
"""

from __future__ import annotations

import datetime as dt

SITE_ORIGIN = "https://playdailycrossword.com"
_DATE_FMT = "%Y-%m-%d"

# Markers delimiting the SEO block in the built index.html shell. If a host
# page lacks these markers the page is left untouched (render returns None).
_TITLE_MARKER = "    <title>"
_LD_MARKER = '    <script type="application/ld+json">'


def human_date(date: str) -> str:
    """Format an ISO date like "Thursday, January 1, 2026"."""
    return dt.datetime.strptime(date, _DATE_FMT).strftime("%A, %B %-d, %Y")


def _seo_block(date: str, human: str, url: str, title: str, desc: str) -> str:
    return (
        f"\n    <title>{title}</title>\n"
        f'    <meta name="description" content="{desc}" />\n'
        f'    <meta name="keywords" content="daily crossword, crossword puzzle, '
        f'free crossword, {human.lower()}" />\n'
        f'    <link rel="canonical" href="{url}" />\n'
        f"\n    <!-- Open Graph -->\n"
        f'    <meta property="og:type" content="website" />\n'
        f'    <meta property="og:site_name" content="Daily Crossword" />\n'
        f'    <meta property="og:title" content="{title}" />\n'
        f'    <meta property="og:description" content="{desc}" />\n'
        f'    <meta property="og:url" content="{url}" />\n'
        f"\n    <!-- Twitter -->\n"
        f'    <meta name="twitter:card" content="summary" />\n'
        f'    <meta name="twitter:title" content="{title}" />\n'
        f'    <meta name="twitter:description" content="{desc}" />\n'
        f"\n    <!-- Structured data -->\n"
        f'    <script type="application/ld+json">\n'
        f"    {{\n"
        f'      "@context": "https://schema.org",\n'
        f'      "@type": "WebPage",\n'
        f'      "name": "{title}",\n'
        f'      "url": "{url}",\n'
        f'      "description": "{desc}",\n'
        f'      "datePublished": "{date}",\n'
        f'      "dateModified": "{date}",\n'
        f'      "inLanguage": "en",\n'
        f'      "isPartOf": {{ "@type": "WebSite", "name": "Daily Crossword", '
        f'"url": "{SITE_ORIGIN}/" }}\n'
        f"    }}\n"
        f"    </script>"
    )


def render_date_html(shell: str, date: str) -> str | None:
    """Inject per-puzzle SEO tags into a built SPA shell.

    Returns the modified HTML, or ``None`` if the date is invalid or the
    puzzle markers are missing from the shell (caller should fall back to
    serving the shell untouched). Canonical/OG URLs use the trailing-slash
    form so they match the directory index GitHub Pages serves for
    ``/puzzles/<date>/``.
    """
    try:
        human = human_date(date)
    except ValueError:
        return None
    url = f"{SITE_ORIGIN}/puzzles/{date}/"
    title = f"Daily Crossword — {human}"
    desc = (
        f"Play the {human} Daily Crossword puzzle. Get hints, autocheck, "
        "and instant feedback. Free to play, no ads."
    )
    block = _seo_block(date, human, url, title, desc)

    start = shell.find(_TITLE_MARKER)
    scrub = shell.find(_LD_MARKER)
    if start == -1 or scrub == -1 or scrub <= start:
        return None
    end = shell.find("</script>", scrub)
    if end == -1:
        return None
    return shell[:start] + block + shell[end + len("</script>") :]
