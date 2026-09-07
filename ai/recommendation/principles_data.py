"""
Curated interior-design-principles corpus for the RAG knowledge base
(decision D006a). These are widely-cited general practice guidelines and
rules of thumb (clearance standards, color theory conventions, lighting
layering, style definitions) — NOT quotes from a single formal academic
source. Each `source_note` says so honestly rather than inventing a
specific citation. This is deliberate: brief PART 28 forbids fabricating
results, and that extends to fabricating provenance for content used to
justify a recommendation.

Every principle here is retrievable by embedding similarity
(ai/recommendation/rag.py) and, when retrieved, is cited by `code` in the
rationale shown to the user — so a claim like "90cm walkway maintained"
always traces back to a real row a person can read, never an invented one.

`applies_to_room_types` / `applies_to_styles`: None means "applies
universally"; a list restricts retrieval relevance to those values.
"""
from __future__ import annotations

GENERAL_SOURCE_NOTE = "General interior design practice guideline / common rule of thumb — not a single formal citation."

PRINCIPLES: list[dict] = [
    # --- Clearance ---
    {
        "code": "CL-01",
        "category": "clearance",
        "title": "Main walkway width",
        "body": "Primary walkways through a room should be at least 90 cm (36 in) wide to allow comfortable single-person passage.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CL-02",
        "category": "clearance",
        "title": "Secondary walkway width",
        "body": "Secondary pathways between furniture pieces not on the main route should be at least 60 cm (24 in) wide.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CL-03",
        "category": "clearance",
        "title": "Coffee table to sofa clearance",
        "body": "Leave 35-45 cm (14-18 in) between a sofa and a coffee table for comfortable knee clearance while seated.",
        "applies_to_room_types": ["living_room"],
        "applies_to_styles": None,
    },
    {
        "code": "CL-04",
        "category": "clearance",
        "title": "Dining chair pull-back clearance",
        "body": "Allow at least 90 cm (36 in) behind each dining chair so it can be pulled back and a person can walk behind a seated diner.",
        "applies_to_room_types": ["living_room", "other"],
        "applies_to_styles": None,
    },
    {
        "code": "CL-05",
        "category": "clearance",
        "title": "TV viewing distance",
        "body": "For a flat-panel TV, viewing distance should be roughly 1.5 to 2.5 times the screen's diagonal size for comfortable viewing.",
        "applies_to_room_types": ["living_room"],
        "applies_to_styles": None,
    },
    {
        "code": "CL-06",
        "category": "clearance",
        "title": "Bed clearance",
        "body": "Leave at least 60 cm (24 in) on each accessible side of a bed for walking and making the bed comfortably.",
        "applies_to_room_types": ["bedroom"],
        "applies_to_styles": None,
    },
    {
        "code": "CL-07",
        "category": "clearance",
        "title": "Door swing clearance",
        "body": "No furniture should be placed within a door's swing arc; keep at least 10 cm clear beyond the swing radius.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CL-08",
        "category": "clearance",
        "title": "Window clearance for furniture",
        "body": "Avoid placing tall furniture (over 1m) directly in front of a window if it blocks more than half the window's height, to preserve natural light and views.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CL-09",
        "category": "clearance",
        "title": "Desk chair clearance",
        "body": "Allow at least 90 cm (36 in) behind a desk chair for it to be pushed back and for the user to stand comfortably.",
        "applies_to_room_types": ["office", "study_room"],
        "applies_to_styles": None,
    },
    {
        "code": "CL-10",
        "category": "clearance",
        "title": "Wardrobe door clearance",
        "body": "Leave clearance equal to the full width of a wardrobe's door swing (or slide travel) in front of it, unobstructed.",
        "applies_to_room_types": ["bedroom"],
        "applies_to_styles": None,
    },
    # --- Style ---
    {
        "code": "ST-01",
        "category": "style",
        "title": "Modern style characteristics",
        "body": "Modern interiors favor clean lines, neutral palettes, minimal ornamentation, and materials like glass, steel, and polished wood.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Modern"],
    },
    {
        "code": "ST-02",
        "category": "style",
        "title": "Minimalist style characteristics",
        "body": "Minimalist interiors emphasize 'less is more': very few furniture pieces, hidden storage, a near-monochromatic palette, and open floor space.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Minimalist"],
    },
    {
        "code": "ST-03",
        "category": "style",
        "title": "Contemporary style characteristics",
        "body": "Contemporary interiors reflect current trends rather than one fixed vocabulary: typically a neutral base with occasional bold accent colors, a mix of curved and straight lines, and varied materials.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Contemporary"],
    },
    {
        "code": "ST-04",
        "category": "style",
        "title": "Traditional style characteristics",
        "body": "Traditional interiors use classic furniture silhouettes, warm wood tones, symmetry, richer color palettes, and detailed elements like moldings, tufting, and patterned textiles.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Traditional"],
    },
    {
        "code": "ST-05",
        "category": "style",
        "title": "Industrial style characteristics",
        "body": "Industrial interiors expose structural materials (brick, concrete, metal ductwork), favor dark metals and reclaimed wood, and use utilitarian, exposed-hardware furniture.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Industrial"],
    },
    {
        "code": "ST-06",
        "category": "style",
        "title": "Scandinavian style characteristics",
        "body": "Scandinavian interiors combine light woods, white and soft neutral palettes, functional furniture, and simple textiles, with an emphasis on natural light.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Scandinavian"],
    },
    {
        "code": "ST-07",
        "category": "style",
        "title": "Modern vs. Contemporary overlap",
        "body": "Modern and Contemporary styles share neutral palettes and clean lines and are frequently confused even by trained observers. Contemporary is generally more eclectic and trend-responsive, while Modern refers to a specific historical (mid-20th-century) design vocabulary.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Modern", "Contemporary"],
    },
    {
        "code": "ST-08",
        "category": "style",
        "title": "Reconciling an existing style with a preferred style",
        "body": "When a room's detected existing style differs from the user's preferred style, favor introducing new pieces gradually in the preferred style's palette and material language rather than replacing everything, to avoid visual discord.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    # --- Color ---
    {
        "code": "CO-01",
        "category": "color",
        "title": "60-30-10 color rule",
        "body": "A balanced room typically uses a dominant color for 60% of the space (walls, large furniture), a secondary color for 30% (upholstery, rugs), and an accent color for the remaining 10% (decor, accessories).",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-02",
        "category": "color",
        "title": "Neutral base with accent",
        "body": "Pairing a neutral base palette (white, gray, beige, taupe) with one or two accent colors keeps a room visually calm while still allowing personality.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-03",
        "category": "color",
        "title": "Warm vs. cool light balance",
        "body": "Rooms with mostly cool-toned natural light (north-facing, or fluorescent-lit) often benefit from warm accent colors to balance the overall feel, and vice versa for warm-lit rooms.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-04",
        "category": "color",
        "title": "Color guidance for small rooms",
        "body": "Lighter, cooler wall colors tend to make small rooms feel more spacious, while dark, saturated colors tend to make a room feel smaller and more enclosed.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-05",
        "category": "color",
        "title": "Color consistency across recommended items",
        "body": "Recommended items should share at least one color family with the user's stated color preference to maintain visual cohesion across the room.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-06",
        "category": "color",
        "title": "Accent color repetition",
        "body": "An accent color reads as an intentional design choice when it appears at least twice in a room (e.g. a cushion and a piece of art), not just once.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-07",
        "category": "color",
        "title": "Wood tone matching",
        "body": "Mixing more than two distinct wood tones among a room's visible furniture can read as visually busy; aim to keep wood tones within one or two families.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "CO-08",
        "category": "color",
        "title": "Traditional palette guidance",
        "body": "Traditional interiors often pair richer, warmer colors (burgundy, forest green, navy) with wood tones, in contrast to the more neutral palettes typical of Modern or Minimalist rooms.",
        "applies_to_room_types": None,
        "applies_to_styles": ["Traditional"],
    },
    # --- Lighting ---
    {
        "code": "LT-01",
        "category": "lighting",
        "title": "Layered lighting",
        "body": "A well-lit room combines three layers: ambient (overall room light), task (focused light for an activity), and accent (highlighting a feature or decor item).",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "LT-02",
        "category": "lighting",
        "title": "Floor lamp placement near seating",
        "body": "A floor lamp placed beside a seating area (sofa or armchair) provides usable task/ambient light without requiring an additional side-table lamp.",
        "applies_to_room_types": ["living_room"],
        "applies_to_styles": None,
    },
    {
        "code": "LT-03",
        "category": "lighting",
        "title": "Pendant light hanging height",
        "body": "A pendant light over a dining or coffee table should typically hang so its bottom sits 75-90 cm above the table surface.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "LT-04",
        "category": "lighting",
        "title": "Preserving natural light",
        "body": "Furniture layouts should avoid blocking a room's primary window with tall pieces, to preserve daylight penetration into the room.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "LT-05",
        "category": "lighting",
        "title": "Light color temperature by activity",
        "body": "Warmer light (around 2700-3000K) suits relaxed living-room and bedroom spaces; cooler light (3500-4000K and above) suits task-oriented spaces like a study or office.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
    {
        "code": "LT-06",
        "category": "lighting",
        "title": "Reading light placement",
        "body": "A reading chair or bedside area benefits from a dedicated task light positioned so it does not cast the reader's own shadow onto the reading surface.",
        "applies_to_room_types": ["bedroom", "living_room", "study_room"],
        "applies_to_styles": None,
    },
    # --- Room type ---
    {
        "code": "RT-01",
        "category": "room_type",
        "title": "Living room focal point",
        "body": "A living room layout is generally organized around one focal point (a TV, fireplace, or window view), with seating arranged to face or angle toward it.",
        "applies_to_room_types": ["living_room"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-02",
        "category": "room_type",
        "title": "Living room conversational seating distance",
        "body": "Seating pieces in a living room work best placed within about 2.4-3m (8-10 ft) of each other, close enough to support conversation without raised voices.",
        "applies_to_room_types": ["living_room"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-03",
        "category": "room_type",
        "title": "Bedroom bed placement",
        "body": "A bed is generally best placed against a solid wall, positioned so it is not directly in the line of sight from the door, and ideally not directly beneath a window.",
        "applies_to_room_types": ["bedroom"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-04",
        "category": "room_type",
        "title": "Bedroom nightstand accessibility",
        "body": "At least one nightstand or surface within arm's reach of the bed is a widely followed baseline for functionality — for a lamp, glasses, or phone.",
        "applies_to_room_types": ["bedroom"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-05",
        "category": "room_type",
        "title": "Home office desk placement",
        "body": "A home office desk benefits from placement where the user can see the room's entrance without sitting directly in line with it, reducing surprise and improving comfort during video calls.",
        "applies_to_room_types": ["office"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-06",
        "category": "room_type",
        "title": "Home office glare avoidance",
        "body": "A home office desk should avoid placing a monitor directly facing a window, to reduce screen glare.",
        "applies_to_room_types": ["office"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-07",
        "category": "room_type",
        "title": "Study room storage accessibility",
        "body": "A study or reading room benefits from storage (shelving) within arm's reach of the primary seating, reducing the need to get up during study sessions.",
        "applies_to_room_types": ["study_room"],
        "applies_to_styles": None,
    },
    {
        "code": "RT-08",
        "category": "room_type",
        "title": "Furniture scale in small rooms",
        "body": "In smaller rooms (under roughly 10 sq m), oversized furniture pieces disproportionately reduce usable floor space; prefer furniture scaled to the room's actual footprint.",
        "applies_to_room_types": None,
        "applies_to_styles": None,
    },
]

# Every principle uses the same honest provenance note (see module docstring).
for _p in PRINCIPLES:
    _p["source_note"] = GENERAL_SOURCE_NOTE

assert len({p["code"] for p in PRINCIPLES}) == len(PRINCIPLES), "duplicate principle code detected"
