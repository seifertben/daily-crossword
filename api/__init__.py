"""FastAPI serving app: reads generated puzzles from the store and serves the SPA."""

from generator.store import get_store

__all__ = ["get_store"]
