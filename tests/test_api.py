"""Tests for the FastAPI serving app."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

import api.main as main


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
    assert body["date"] == dt.datetime.now(dt.UTC).date().strftime("%Y-%m-%d")


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
    today = dt.datetime.now(dt.UTC).date().strftime("%Y-%m-%d")
    _write_fixture(tmp_path, today)
    r = client.get("/api/puzzle")
    assert r.status_code == 200
    assert r.json()["date"] == today


def test_dev_generate_disabled_in_prod(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = client.post("/api/dev/generate", json={"date": "2026-01-01"})
    assert r.status_code == 404


def test_dev_generate_stub(client):
    r = client.post(
        "/api/dev/generate",
        json={"date": "2026-01-02", "size": 10, "total_seconds": 8.0},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["width"] == 10 and body["height"] == 10
    assert body["wordCount"] >= 10
    # persisted too
    r2 = client.get("/api/puzzle/2026-01-02")
    assert r2.status_code == 200
