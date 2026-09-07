"""
Synthetic room fixtures (decision D018). These stand in for real room
analysis + style recognition output until the CV pipeline is built. They
are used ONLY through the dev-only `scripts/seed_fixture_analysis.py`
path — the production recommendation/layout endpoints read real
RoomAnalysis/StylePrediction DB rows and never fall back to these
silently (see PLAN.md D018 guardrail).

Each fixture is deliberately realistic (plausible room dimensions,
plausible existing furniture) rather than a trivial empty box, so the
recommendation and layout algorithms are exercised against real-shaped
problems: an already-furnished room, a style mismatch to reconcile, a
small room where space is genuinely tight.
"""
from __future__ import annotations

from dataclasses import dataclass

from ai.room_analysis.room_model import FurnitureItem, Opening, RoomModel


@dataclass
class StyleFixture:
    predicted_style: str
    confidence: float
    alternatives: list[dict]  # [{"style": ..., "confidence": ...}, ...]
    abstained: bool = False


@dataclass
class RoomFixture:
    name: str
    room: RoomModel
    style: StyleFixture
    description: str


FIXTURES: dict[str, RoomFixture] = {
    "bedroom_small_scandinavian": RoomFixture(
        name="bedroom_small_scandinavian",
        description="A small, mostly empty bedroom with one old wardrobe. Existing style reads Scandinavian.",
        room=RoomModel(
            room_type="bedroom",
            width_cm=300,
            length_cm=350,
            openings=[
                Opening(kind="door", wall="south", position_cm=20, width_cm=80),
                Opening(kind="window", wall="north", position_cm=150, width_cm=120),
            ],
            existing_furniture=[
                FurnitureItem(
                    label="Old Wardrobe", width_cm=100, depth_cm=55, height_cm=180,
                    x_cm=270, y_cm=300, rotation_deg=90, is_existing=True, category="cabinet",
                ),
            ],
            free_space_ratio=0.78,
        ),
        style=StyleFixture(
            predicted_style="Scandinavian",
            confidence=0.81,
            alternatives=[{"style": "Minimalist", "confidence": 0.11}, {"style": "Contemporary", "confidence": 0.05}],
        ),
    ),
    "living_room_modern_cluttered": RoomFixture(
        name="living_room_modern_cluttered",
        description="A living room with dated, awkwardly-placed furniture. Existing style reads Traditional but is ambiguous with Contemporary.",
        room=RoomModel(
            room_type="living_room",
            width_cm=420,
            length_cm=520,
            openings=[
                Opening(kind="door", wall="west", position_cm=30, width_cm=90),
                Opening(kind="window", wall="east", position_cm=100, width_cm=180),
            ],
            existing_furniture=[
                FurnitureItem(
                    label="Old Sofa", width_cm=190, depth_cm=85, height_cm=80,
                    x_cm=150, y_cm=470, rotation_deg=0, is_existing=True, category="sofa",
                ),
                FurnitureItem(
                    label="CRT-era TV Stand", width_cm=110, depth_cm=40, height_cm=55,
                    x_cm=380, y_cm=260, rotation_deg=90, is_existing=True, category="cabinet",
                ),
            ],
            free_space_ratio=0.62,
        ),
        style=StyleFixture(
            predicted_style="Traditional",
            confidence=0.55,
            alternatives=[{"style": "Contemporary", "confidence": 0.30}, {"style": "Industrial", "confidence": 0.08}],
        ),
    ),
    "study_room_industrial": RoomFixture(
        name="study_room_industrial",
        description="A compact study with one existing desk. Existing style reads confidently Industrial.",
        room=RoomModel(
            room_type="study_room",
            width_cm=260,
            length_cm=300,
            openings=[
                Opening(kind="door", wall="south", position_cm=15, width_cm=75),
                Opening(kind="window", wall="west", position_cm=80, width_cm=100),
            ],
            existing_furniture=[
                FurnitureItem(
                    label="Existing Desk", width_cm=110, depth_cm=55, height_cm=75,
                    x_cm=200, y_cm=270, rotation_deg=0, is_existing=True, category="table",
                ),
            ],
            free_space_ratio=0.70,
        ),
        style=StyleFixture(
            predicted_style="Industrial",
            confidence=0.72,
            alternatives=[{"style": "Modern", "confidence": 0.14}, {"style": "Contemporary", "confidence": 0.06}],
        ),
    ),
    "office_contemporary_empty": RoomFixture(
        name="office_contemporary_empty",
        description="A nearly empty home office — good test case for a room needing almost everything.",
        room=RoomModel(
            room_type="office",
            width_cm=280,
            length_cm=320,
            openings=[
                Opening(kind="door", wall="south", position_cm=100, width_cm=85),
                Opening(kind="window", wall="north", position_cm=60, width_cm=140),
            ],
            existing_furniture=[],
            free_space_ratio=0.95,
        ),
        style=StyleFixture(
            predicted_style="Contemporary",
            confidence=0.68,
            alternatives=[{"style": "Modern", "confidence": 0.25}, {"style": "Minimalist", "confidence": 0.05}],
        ),
    ),
}


def get_fixture(name: str) -> RoomFixture:
    if name not in FIXTURES:
        raise KeyError(f"Unknown fixture {name!r}. Available: {sorted(FIXTURES)}")
    return FIXTURES[name]
