"""Peter Broda scored wordlist loader + pattern index for grid filling.

The bank holds ~527k scored crossword answers. For the filler we need, at
every backtracking node, the set of words that fit a partially-filled slot
(``?A??E``). A per-length inverted index on (position, letter) makes that an
intersection of a few small sets rather than a scan of a 45k-word bucket.

Only pure A-Z words of length 3..MAX_LEN are indexed: a 15x15 grid never
contains a slot longer than 15, and cells hold single letters, so digit-laden
entries (``R2D2``, ``6PM``) are dropped up front.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from generator.models import Slot

_WILDCARD = "?"
_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "broda_scored.txt"
DEFAULT_MAX_LEN = 15
DEFAULT_MIN_SCORE = 75


class WordBank:
    """Scored answer bank with a (length x position x letter) inverted index.

    ``min_score`` is a quality floor: entries scored below it are dropped at
    load time, so the filler never offers obviously junk fill (``NRACODE``,
    ``DUAN``, ...) to the clue provider.
    """

    def __init__(
        self,
        entries: list[tuple[str, int]],
        *,
        max_len: int = DEFAULT_MAX_LEN,
        min_score: int = 0,
    ) -> None:
        self._score: dict[str, int] = {}
        self._by_length: dict[int, list[str]] = {}
        self._by_length_set: dict[int, frozenset[str]] = {}
        self._index: dict[int, dict[tuple[int, str], frozenset[str]]] = {}
        self._order_rank: dict[int, dict[str, int]] = {}
        self._max_len = max_len

        # dedup keeping the highest score if a word repeats
        seen: dict[str, int] = {}
        for raw_word, score in entries:
            w = raw_word.strip().upper()
            if len(w) < 3 or len(w) > max_len or not w.isalpha() or score < min_score:
                continue
            if w in seen:
                seen[w] = max(seen[w], score)
            else:
                seen[w] = score

        # sort each length bucket by score desc then alpha for deterministic ties
        buckets: dict[int, list[tuple[str, int]]] = {}
        for w, s in seen.items():
            buckets.setdefault(len(w), []).append((w, s))
        for length, items in buckets.items():
            items.sort(key=lambda ws: (-ws[1], ws[0]))
            self._by_length[length] = [w for w, _ in items]
            self._score.update({w: s for w, s in items})
            self._build_index(length, self._by_length[length])

    def _build_index(self, length: int, words: list[str]) -> None:
        idx: dict[tuple[int, str], set[str]] = {}
        for w in words:
            for pos, letter in enumerate(w):
                idx.setdefault((pos, letter), set()).add(w)
        self._index[length] = {k: frozenset(v) for k, v in idx.items()}
        # cache score-desc rank so candidates() never rebuilds a 50k-entry dict
        self._order_rank[length] = {w: i for i, w in enumerate(words)}
        # shared full-bucket frozenset for O(1) full-wildcard candidate sets
        self._by_length_set[length] = frozenset(words)

    # ---- queries -------------------------------------------------------

    def has_length(self, length: int) -> bool:
        return length in self._by_length

    def pool_size(self, length: int) -> int:
        return len(self._by_length.get(length, ()))

    def score_of(self, word: str) -> int:
        return self._score.get(word.upper(), 0)

    def words_of_length(self, length: int) -> list[str]:
        """All words of ``length``, best-scored first."""
        return list(self._by_length.get(length, ()))

    def contains(self, word: str) -> bool:
        return word.upper() in self._score

    def candidates(self, pattern: str, *, exclude: set[str] | None = None) -> list[str]:
        """Words matching ``pattern`` (``?`` = any), best-scored first.

        ``exclude`` removes already-placed words (and the ephemeral blacklist)
        so the filler never reuses a word within one grid.
        """
        result = self.candidates_set(pattern, exclude=exclude)
        rank = self._order_rank.get(len(pattern), {})
        fallback = len(rank)
        return sorted(result, key=lambda w: rank.get(w, fallback))

    def candidates_set(self, pattern: str, *, exclude: set[str] | None = None) -> frozenset[str]:
        """Unordered set of words matching ``pattern`` (no sorting cost).

        Used for forward-checking (size + emptiness) where ordering is irrelevant;
        :meth:`candidates` wraps this and sorts for the slot the solver commits to.
        """
        length = len(pattern)
        bucket = self._index.get(length)
        if bucket is None:
            return frozenset()

        fixed = [(i, ch) for i, ch in enumerate(pattern) if ch != _WILDCARD]
        if not fixed:
            result: frozenset[str] = self._by_length_set.get(length, frozenset())
        else:
            matched = [s for s in (bucket.get(pair) for pair in fixed) if s is not None]
            if len(matched) != len(fixed):
                return frozenset()
            result = matched[0]
            for s in matched[1:]:
                result = result & s
                if not result:
                    return frozenset()

        if exclude:
            result = result - exclude
        return result

    def rank_of(self, length: int) -> dict[str, int]:
        return self._order_rank.get(length, {})

    def slot_candidates(
        self, slot: Slot, grid: dict[tuple[int, int], str], *, exclude: set[str] | None = None
    ) -> list[str]:
        return self.candidates(slot.pattern(grid), exclude=exclude)

    def __len__(self) -> int:
        return len(self._score)


def _parse_broda(path: Path) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or ";" not in line:
                continue
            word, _, score_s = line.partition(";")
            try:
                score = int(score_s)
            except ValueError:
                continue
            entries.append((word, max(score, 0)))
    return entries


@lru_cache(maxsize=1)
def get_bank(
    path: str | os.PathLike[str] | None = None,
    *,
    max_len: int = DEFAULT_MAX_LEN,
    min_score: int | None = None,
) -> WordBank:
    """Load (and cache) the default bank from the data directory.

    ``min_score`` defaults to ``DEFAULT_MIN_SCORE`` (a quality floor so junk
    fill never reaches the clue provider); pass ``0`` to keep the full list.
    """
    p = Path(path) if path else _DEFAULT_PATH
    if min_score is None:
        min_score = int(os.environ.get("GEMINI_MIN_SCORE", DEFAULT_MIN_SCORE))
    return WordBank(_parse_broda(p), max_len=max_len, min_score=min_score)


def reset_cache() -> None:
    """Clear the cached bank (used by tests that swap in fixture banks)."""
    get_bank.cache_clear()
