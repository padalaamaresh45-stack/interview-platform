"""The default pipeline every position gets on creation. (name, day_limit_days).

Seeding itself lives on the Position model (app/models/position.py, after_insert
event) so every insert path gets it, not just the admin router — see the comment
there. This module just owns the constant both the model and the migration read."""

DEFAULT_STAGES: list[tuple[str, int | None]] = [
    ("Applied", 3),
    ("Screening", 5),
    ("Under review", 5),
    ("Offer", 3),
    ("Hired", None),
    ("Rejected", None),
]

# A candidate in one of these stages is done moving through the pipeline —
# matches the frontend's TERMINAL_STAGE_NAMES (HomePage.tsx), which uses the
# same name-based check to collapse these columns by default. Identified by
# name since Stage has no is_terminal flag yet.
TERMINAL_STAGE_NAMES = {"Hired", "Rejected"}
