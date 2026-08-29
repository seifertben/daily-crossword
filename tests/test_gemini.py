"""Tests for Gemini clue-response parsing and the junk-word sentinel."""

from __future__ import annotations

import json

import pytest

from generator.gemini import GeminiError, _parse_clue_batch


def test_parse_clue_batch_returns_clued_words():
    batch = ["APPLE", "BANANA"]
    text = json.dumps(
        {
            "clues": [
                {"answer": "APPLE", "clue": "Fruit"},
                {"answer": "BANANA", "clue": "Yellow fruit"},
            ]
        }
    )
    assert _parse_clue_batch(text, batch) == {"APPLE": "Fruit", "BANANA": "Yellow fruit"}


def test_parse_clue_batch_drops_invalid_sentinel():
    """Words the model flags INVALID must be absent so they get blacklisted."""
    batch = ["APPLE", "ONCEA"]
    text = json.dumps(
        {
            "clues": [
                {"answer": "APPLE", "clue": "Fruit"},
                {"answer": "ONCEA", "clue": "INVALID"},
            ]
        }
    )
    assert _parse_clue_batch(text, batch) == {"APPLE": "Fruit"}


def test_parse_clue_batch_sentinel_case_insensitive():
    batch = ["ONCEA"]
    text = json.dumps({"clues": [{"answer": "oncea", "clue": "invalid"}]})
    assert _parse_clue_batch(text, batch) == {}


def test_parse_clue_batch_ignores_words_outside_batch():
    batch = ["APPLE"]
    text = json.dumps({"clues": [{"answer": "BANANA", "clue": "Yellow fruit"}]})
    assert _parse_clue_batch(text, batch) == {}


def test_parse_clue_batch_rejects_bad_json():
    with pytest.raises(GeminiError):
        _parse_clue_batch("not json", ["APPLE"])


def test_parse_clue_batch_ignores_garbage_items():
    batch = ["APPLE"]
    text = json.dumps(
        {
            "clues": [
                {"answer": 42, "clue": "x"},
                {"answer": "APPLE", "clue": ""},
                "not a dict",
                {"answer": "APPLE", "clue": "Fruit"},
            ]
        }
    )
    assert _parse_clue_batch(text, batch) == {"APPLE": "Fruit"}
