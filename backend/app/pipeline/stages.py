"""The default pipeline every position gets on creation. (name, day_limit_days).

Seeding itself lives on the Position model (app/models/position.py, after_insert
event) so every insert path gets it, not just the admin router — see the comment
there. This module just owns the constant both the model and the migration read."""

DEFAULT_STAGES: list[tuple[str, int | None, bool]] = [
    ("Applied", 3, False),
    ("Screening", 5, False),
    ("Under review", 5, False),
    ("Offer", 3, False),
    ("Hired", None, True),
    ("Rejected", None, True),
]
