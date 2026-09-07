"""Tests for the FastAPI serving app."""

from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import api.main as main


def _et_today() -> str:
    # Mirrors api.main._today(): the puzzle day starts at 6 AM Eastern, so
    # "today" is the ET date six hours ago.
    now = dt.datetime.now(ZoneInfo("America/New_York")) - dt.timedelta(hours=6)
    return now.date().strftime("%Y-%m-%d")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PUZZLE_STORE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("GEMINI_MODE", "stub")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return TestClient(main.app)


FIXTURE = {
    "date": "2026-01-01",
    "width": 3,
    "height": 3,
    "grid": [
        [None, {"solution": "A", "number": 1}, None],
        [{"solution": "D", "number": 2}, {"solution": "E"}, {"solution": "F"}],
        [None, {"solution": "G"}, None],
    ],
    "across": [
        {
            "number": 2,
            "clue": "DEF clue",
            "answer": "DEF",
            "direction": "across",
            "row": 1,
            "col": 0,
            "length": 3,
            "themed": False,
        }
    ],
    "down": [
        {
            "number": 1,
            "clue": "AEG clue",
            "answer": "AEG",
            "direction": "down",
            "row": 0,
            "col": 1,
            "length": 3,
            "themed": False,
        }
    ],
    "wordCount": 2,
    "theme": {"title": "Test", "voice": "neutral"},
}


def _write_fixture(store_dir, date, payload=FIXTURE):
    d = store_dir / "puzzles"
    d.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["date"] = date
    (d / f"{date}.json").write_text(json.dumps(body), encoding="utf-8")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["store"] == "local"
    assert body["date"] == _et_today()


def test_get_puzzle_dated(client, tmp_path):
    _write_fixture(tmp_path, "2026-01-01")
    r = client.get("/api/puzzle/2026-01-01")
    assert r.status_code == 200
    assert r.json()["date"] == "2026-01-01"
    assert r.headers["cache-control"].startswith("public")


def test_get_puzzle_missing(client):
    r = client.get("/api/puzzle/1999-01-01")
    assert r.status_code == 404


def test_get_puzzle_bad_date(client):
    r = client.get("/api/puzzle/notadate")
    assert r.status_code == 400


def test_get_puzzle_today(client, tmp_path):
    today = _et_today()
    _write_fixture(tmp_path, today)
    r = client.get("/api/puzzle")
    assert r.status_code == 200
    assert r.json()["date"] == today


def test_dev_generate_disabled_in_prod(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = client.post("/api/dev/generate", json={"date": "2026-01-01"})
    assert r.status_code == 404


_FAKE_INDEX = """<!DOCTYPE html>
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


def _write_fake_index(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(_FAKE_INDEX, encoding="utf-8")


def test_spa_dated_injects_seo(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_STATIC_DIR", tmp_path / "dist")
    _write_fake_index(tmp_path)
    _write_fixture(tmp_path, "2026-01-01")

    r = client.get("/puzzles/2026-01-01/")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/html; charset=utf-8"
    body = r.text
    assert "<title>Daily Crossword — Thursday, January 1, 2026</title>" in body
    assert 'rel="canonical" href="https://playdailycrossword.com/puzzles/2026-01-01/"' in body
    assert '"@type": "WebPage"' in body
    assert '"datePublished": "2026-01-01"' in body
    assert '"dateModified": "2026-01-01"' in body
    assert '"url": "https://playdailycrossword.com/"' in body
    # The static homepage title must be gone (no duplicate/conflicting tags).
    assert "A New Free Puzzle Every Day" not in body
    # The static homepage canonical must be gone.
    assert 'rel="canonical" href="https://playdailycrossword.com/"' not in body


def test_spa_dated_missing_puzzle_serves_plain_index(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_STATIC_DIR", tmp_path / "dist")
    _write_fake_index(tmp_path)
    # No fixture written -> puzzle missing.

    r = client.get("/puzzles/2026-01-01")
    assert r.status_code == 200
    assert r.text == _FAKE_INDEX
    assert "A New Free Puzzle Every Day" in r.text


def test_spa_no_build_serves_placeholder(client, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_STATIC_DIR", tmp_path / "dist")
    # dist dir exists but has no index.html
    r = client.get("/some/path")
    assert r.status_code == 200
    assert "SPA build has not been produced" in r.text


def test_dev_generate_stub(client):
    r = client.post(
        "/api/dev/generate",
        json={"date": "2026-01-05", "size": 10, "total_seconds": 30.0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["width"] == 10 and body["height"] == 10
    assert body["wordCount"] >= 10
    # persisted too
    r2 = client.get("/api/puzzle/2026-01-05")
    assert r2.status_code == 200
