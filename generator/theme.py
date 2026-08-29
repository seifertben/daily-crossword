"""Theme fallbacks and helpers."""

from __future__ import annotations

import random

from generator.models import Theme

# A small curated list used only when the LLM theme call fails or repeats.
# Each entry is a fully-formed Theme so the pipeline can always ship *something*.
CURATED_THEMES: list[Theme] = [
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
    Theme(
        title="Kitchen Tools",
        voice="Warm and culinary",
        themed_answers={
            "WHISK": "Beat eggs by hand",
            "SPATULA": "Flip and scrape",
            "GRATER": "Cheese shredder",
            "COLANDER": "Drain the pasta",
            "LADLE": "Serving spoon's deep cousin",
            "BLENDER": "Smoothie maker",
            "TOASTER": "Browns the bread",
            "SKILLET": "Fry pan",
            "MANDOLINE": "Slices paper-thin",
        },
    ),
]


def pick_fallback_theme(rng: random.Random) -> Theme:
    return rng.choice(CURATED_THEMES)
