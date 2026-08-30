"""Gemini clue/theme provider: live, stub, and replay modes.

``GEMINI_MODE`` selects the backend:
* ``live``  - real calls to the Gemini REST API (needs ``GEMINI_API_KEY``)
* ``stub``  - deterministic canned theme + placeholder clues, no network/key
* ``replay``- serve canned cassettes (for offline tests)

The pipeline only depends on the :class:`ClueProvider` protocol, so the
serving/production wiring can swap backends freely.
"""

from __future__ import annotations

import json
import os
import random
from typing import Any, Protocol

import httpx

from generator.models import Theme

DEFAULT_MODEL = "gemini-3.7-flash"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_TIMEOUT = 60.0
_CLUE_BATCH = 25  # words per generateContent call
_INVALID_MARKER = "INVALID"  # clue sentinel: answer is not a real word

# Each level is a full *clue-writing* brief, not a one-line hint. It spells out
# the concrete dimensions the model must control -- vocabulary, clue technique,
# degree of misdirection, outside knowledge, and wordplay -- plus a target solve
# time so "difficulty" maps to an actual player experience, not a vague vibe.
_DIFFICULTY_SPECS: dict[int, dict[str, str]] = {
    1: {
        "label": "Beginner",
        "solve_time": "about 5 minutes",
        "guidance": (
            "Vocabulary: only very common everyday words a young or casual "
            "solver knows cold.\n"
            "Clues: simple, literal, single-definition clues that make the "
            "answer obvious. No wordplay, no puns, no anagram/cryptic "
            "indicators, no abbreviations, no trickery.\n"
            "Proper nouns: globally famous household names only (e.g. the "
            "president, a blockbuster movie star, a major country/city).\n"
            "Misdirection: none. A clue should essentially hand over the answer."
        ),
    },
    2: {
        "label": "Easy",
        "solve_time": "about 7 minutes",
        "guidance": (
            "Vocabulary: common, widely-understood words.\n"
            "Clues: straightforward definitions, with an occasional friendly "
            "fill-in-the-blank. Wordplay only in the gentlest, most "
            "self-evident form.\n"
            "Proper nouns: only well-known figures, places, and pop culture.\n"
            "Misdirection: very mild at most; the intended meaning is still "
            "the first one a solver reaches."
        ),
    },
    3: {
        "label": "Standard",
        "solve_time": "about 10 minutes",
        "guidance": (
            "Vocabulary: everyday-to-common words; nothing obscure.\n"
            "Clues: a balanced mix of clear definitions, fill-in-the-blank, "
            "and light trivia. One or two clues may rely on a modest but fair "
            "double meaning or a fresh angle.\n"
            "Proper nouns: recognizable to a generally-informed solver.\n"
            "Misdirection: gentle and fair -- the clue still points clearly, "
            "just from a slightly off-center direction. Every clue should be "
            "gettable by a typical hobbyist without external help."
        ),
    },
    4: {
        "label": "Hard",
        "solve_time": "about 15 minutes",
        "guidance": (
            "Vocabulary: broader, including some less-common but real words.\n"
            "Clues: expect wordplay, puns, and double meanings; several clues "
            "should be oblique or require connecting two ideas. Use anagram "
            "hints and cryptic-style indicators sparingly and fairly.\n"
            "Proper nouns: may require solid general knowledge or a passing "
            "familiarity with less-front-page culture.\n"
            "Misdirection: deliberate -- the surface reading misleads, but the "
            "real answer still follows cleanly once seen."
        ),
    },
    5: {
        "label": "Expert",
        "solve_time": "about 25 minutes",
        "guidance": (
            "Vocabulary: may include obscure, archaic, or technical words.\n"
            "Clues: heavy wordplay -- anagrams, hidden words, homophones, and "
            "cryptic conventions -- freely mixed with demanding trivia.\n"
            "Proper nouns: less-famous names and esoteric references are "
            "acceptable; the clue should still be fair to a dedicated solver.\n"
            "Misdirection: sophisticated. The surface meaning is often a red "
            "herring, and the intended parse frequently rewards lateral thinking."
        ),
    },
}

_DEFAULT_DIFFICULTY = 3


def _difficulty_brief(difficulty: int) -> dict[str, str]:
    """Return the {label, solve_time, guidance} brief for a difficulty level."""
    return _DIFFICULTY_SPECS.get(difficulty, _DIFFICULTY_SPECS[_DEFAULT_DIFFICULTY])


class GeminiError(Exception):
    def __init__(self, message: str, *, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def _clean_answer(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    w = "".join(ch for ch in raw.upper() if ch.isalpha())
    return w or None


def _clean_clue(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    c = " ".join(raw.split())
    return c or None


def _parse_clue_batch(text: str, batch: list[str]) -> dict[str, str]:
    """Parse one generateContent clue response into {answer: clue}.

    Answers the model flags with the ``INVALID`` sentinel are dropped (treated
    as unclueable) so the pipeline can blacklist and re-fill them.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"clue response not JSON: {text[:200]}") from exc
    items = data.get("clues", []) if isinstance(data, dict) else data
    allowed = {w.upper() for w in batch}
    out: dict[str, str] = {}
    for item in items if isinstance(items, list) else []:
        ans = _clean_answer(item.get("answer") if isinstance(item, dict) else None)
        clue = _clean_clue(item.get("clue") if isinstance(item, dict) else None)
        if ans and clue and ans in allowed and clue.upper() != _INVALID_MARKER:
            out[ans] = clue
    return out


class ClueProvider(Protocol):
    async def generate_theme(self, *, seed: int) -> Theme: ...
    async def generate_clues(
        self, words: list[str], *, voice: str, difficulty: int
    ) -> dict[str, str]: ...


# ---------------------------------------------------------------- live ----


class GeminiClient:
    """Live Gemini REST API client."""

    def __init__(
        self, api_key: str, model: str = DEFAULT_MODEL, *, timeout: float = _TIMEOUT
    ) -> None:
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is not set", status=401)
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def _post(self, prompt: str) -> str:
        url = f"{_BASE_URL}/{self._model}:generateContent"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(
                        url,
                        params={"key": self._api_key},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "responseMimeType": "application/json",
                                "temperature": 0.9,
                            },
                        },
                    )
                except httpx.HTTPError as exc:
                    if attempt == 2:
                        raise GeminiError(f"network error: {exc}") from exc
                    continue
                if resp.status_code in (400, 401, 403, 429):
                    raise GeminiError(
                        f"Gemini API error {resp.status_code}: {resp.text[:200]}",
                        status=resp.status_code,
                    )
                if resp.status_code >= 500:
                    if attempt == 2:
                        raise GeminiError(
                            f"Gemini server error {resp.status_code}",
                            status=resp.status_code,
                        )
                    continue
                resp.raise_for_status()
                data = resp.json()
                try:
                    return str(data["candidates"][0]["content"]["parts"][0]["text"])
                except (KeyError, IndexError) as exc:
                    raise GeminiError(f"unexpected Gemini response: {data}") from exc

        raise GeminiError("Gemini request failed after retries")

    async def generate_theme(self, *, seed: int) -> Theme:
        prompt = (
            "You are a crossword constructor. Invent a fresh, appealing daily "
            "crossword THEME that has not been overused. Return STRICT JSON:\n"
            '{"title": string, "voice": string, "answers": [\n'
            '  {"answer": "UPPERCASE A-Z, 5-15 letters", "clue": "one-line clue"}, ...\n'
            "]}\n"
            "Rules:\n"
            "- Provide 12 to 18 themed answers as a working pool (oversubscribed: "
            "only a subset will fit the final grid).\n"
            "- Range the lengths: a few long 13-15, several 10-12, several medium "
            "7-9, and several short 5-6, so plenty fit and the puzzle fills cleanly.\n"
            "- All answers uppercase letters only (no spaces/punct), each thematically "
            "tied to the title.\n"
            "- voice: one short phrase describing the clue tone for the whole puzzle.\n"
            "- clues: concise, in the theme's voice.\n"
            "- No duplicate answers.\n"
            f"Provide only the JSON. Seed for variety: {seed}."
        )
        text = await self._post(prompt)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"theme response not JSON: {text[:200]}") from exc
        root = data if isinstance(data, dict) else {}
        title = str(root.get("title", "Daily Crossword")).strip() or "Daily Crossword"
        voice = str(root.get("voice", "")).strip()
        themed: dict[str, str] = {}
        for item in root.get("answers", []):
            ans = _clean_answer(item.get("answer") if isinstance(item, dict) else None)
            clue = _clean_clue(item.get("clue") if isinstance(item, dict) else None)
            if ans and clue and 5 <= len(ans) <= 15 and ans not in themed:
                themed[ans] = clue
        if len(themed) < 3:
            raise GeminiError("theme yielded too few usable answers")
        return Theme(title=title, voice=voice, themed_answers=themed)

    async def generate_clues(
        self, words: list[str], *, voice: str, difficulty: int
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for i in range(0, len(words), _CLUE_BATCH):
            batch = words[i : i + _CLUE_BATCH]
            brief = _difficulty_brief(difficulty)
            prompt = (
                "You are a fresh, inventive crossword clue writer. For each "
                "answer, write one concise clue. Return STRICT JSON:\n"
                '{"clues": [{"answer": "WORD", "clue": "..."}, ...]}\n'
                f"Difficulty level: {brief['label']}\n"
                "Calibration: the whole puzzle should be solvable by a typical "
                f"hobbyist in {brief['solve_time']}, so hold every clue to "
                "exactly this standard.\n"
                f"Clue-writing brief:\n{brief['guidance']}\n"
                "- Be CREATIVE and ORIGINAL while staying inside the brief "
                "above. Prefer fresh, surprising, and witty clues over the "
                "same well-worn dictionary definitions or stale trivia found "
                "in every published puzzle; do not let creativity drift the "
                "clue beyond the requested difficulty.\n"
                "- These are regular fill answers: clues should be lively and "
                "fun, but still fair and solvable. Do NOT tie them to any "
                "theme or forced wordplay gimmick.\n"
                "- Vary clue types: clever definitions, offbeat trivia, "
                "fill-in-the-blank, and light wordplay.\n"
                "- Do NOT include the answer in the clue.\n"
                "- Some answers are flattened phrases with spaces and punctuation "
                'removed, e.g. ONCEA is "once a" and CUFFEM is "cuff \'em". When '
                "an answer is a recognizable phrase, split it apart at the word "
                "boundaries and write a clue for that phrase; fill-in-the-blank "
                'partial clues such as "Once a ___" or "___ \'em" are welcome '
                "for these.\n"
                "- Only if an answer is neither a real word nor a recognizable "
                "phrase (pure gibberish or a misspelling) do NOT invent a clue: "
                f"set the clue to the literal value {_INVALID_MARKER}.\n"
                "- Answer each real word or phrase exactly once, same case as given.\n"
                f"Answers: {', '.join(batch)}\n"
                "Provide only the JSON."
            )
            text = await self._post(prompt)
            out.update(_parse_clue_batch(text, batch))
        return out


# --------------------------------------------------------------- stub -----

_STUB_THEMES = [
    Theme(
        title="Cinema Classics",
        voice="Playful and film-loving",
        themed_answers={
            "BLOCKBUSTER": "Summer tentpole",
            "MATINEE": "Afternoon showing",
            "DIRECTOR": "One calling the shots on set",
            "SCREENING": "Private preview",
            "SCREENPLAY": "Script for the screen",
            "PREMIERE": "Red-carpet first showing",
            "CINEMATOGRAPHY": "The art of the moving image",
            "OSCARS": "Academy prizes",
            "ACTRESS": "Leading lady",
        },
    ),
    Theme(
        title="Ocean Depths",
        voice="Nautical and curious",
        themed_answers={
            "CURRENTS": "Ocean movers",
            "TIDEPOOL": "Bordered coastal pocket",
            "PLANKTON": "Drifting ocean drifters",
            "SAILORS": "Crew on a tall ship",
            "SUBMARINE": "Underwater vessel",
            "DOLPHIN": "Playful cetacean",
            "ANCHOR": "Ships brake",
            "CORAL": "Reef builder",
            "ABALONE": "Iridescent-shelled mollusk",
        },
    ),
]


class StubProvider:
    """Deterministic, no-network provider for local dev and tests."""

    def __init__(self, *, seed: int = 0) -> None:
        self._seed = seed

    async def generate_theme(self, *, seed: int) -> Theme:
        rng = random.Random(seed)
        return _STUB_THEMES[rng.randrange(len(_STUB_THEMES))]

    async def generate_clues(
        self, words: list[str], *, voice: str, difficulty: int
    ) -> dict[str, str]:
        return {w.upper(): f"Stub clue for {w.upper()}" for w in words}


# -------------------------------------------------------------- replay ----


class ReplayProvider:
    """Serve canned cassettes: {"theme": Theme, "clues": {word: clue}}."""

    def __init__(self, cassettes: dict[str, Any]) -> None:
        self._c = cassettes

    async def generate_theme(self, *, seed: int) -> Theme:
        t = self._c.get("theme")
        if not isinstance(t, Theme):
            raise GeminiError("replay cassette missing 'theme'")
        return t

    async def generate_clues(
        self, words: list[str], *, voice: str, difficulty: int
    ) -> dict[str, str]:
        clues = self._c.get("clues", {})
        return {w.upper(): clues[w.upper()] for w in words if w.upper() in clues}


# ------------------------------------------------------------- factory ----


def get_provider(
    *,
    mode: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> ClueProvider:
    """Build a provider from env (mode/key/model) or explicit args."""
    mode = mode or os.environ.get("GEMINI_MODE", "").strip() or None
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip() or None
    model = model or os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL

    if mode == "stub":
        return StubProvider()
    if mode == "replay":
        raise GeminiError("replay mode requires explicit cassette construction")
    if mode == "live" or (mode in (None, "") and api_key):
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is required for live mode", status=401)
        return GeminiClient(api_key, model)
    # default when nothing is configured: stub (offline-friendly)
    return StubProvider()
