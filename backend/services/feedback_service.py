"""
Feedback text parsing (decision D024): Gemini-primary, rule-based fallback.

Both paths produce the SAME structured schema:
    {
      "keep_item_ids": [int, ...],      # catalog_item_id the user wants kept next iteration
      "remove_item_ids": [int, ...],    # catalog_item_id the user wants excluded next iteration
      "style_shift": "<FR-3 style name>" | None,
      "budget_delta": float | None,     # added to (or subtracted from) the current budget
      "crowding_shift": "less" | "more" | None,
      "notes": str,                     # anything the parser recognized but didn't structure
    }

Hard boundary (unchanged from D007a/D024): neither path ever decides prices,
never invents a catalog item that wasn't already recommended, and never
touches any model weights. This function only produces DELTAS; applying
them (backend/services/pipeline_stages.py) is separate, deterministic code.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("visiondecor.feedback")

FR3_STYLES = ["Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian"]

_CHEAPER_PATTERNS = [r"\bcheaper\b", r"\breduce (the )?cost\b", r"\blower (the )?budget\b", r"\bless expensive\b", r"\bspend less\b"]
_PRICIER_PATTERNS = [r"\bmore expensive\b", r"\bincrease (the )?budget\b", r"\bbigger budget\b", r"\bspend more\b"]
_LESS_CROWDED_PATTERNS = [r"\bless crowded\b", r"\bmore open\b", r"\bmore space\b", r"\btoo (much|many)\b", r"\bless cluttered\b"]
_MORE_FULL_PATTERNS = [r"\bmore furniture\b", r"\bmore items\b", r"\badd more\b"]

BUDGET_DELTA_FRACTION = 0.15  # a fixed, documented heuristic — not user-tunable, not a model weight


def _empty_deltas() -> dict:
    return {
        "keep_item_ids": [], "remove_item_ids": [], "style_shift": None,
        "budget_delta": None, "crowding_shift": None, "notes": "",
    }


_NAME_STOPWORDS = {"the", "a", "an", "with", "and", "of", "for", "in", "on", "to"}


def _significant_words(name: str) -> list[str]:
    """Every meaningful word in a catalog name, not just the last one — a
    user is as likely to say 'remove the plant' as 'remove the pot' for
    'Monstera Plant + Ceramic Pot', and as likely to say 'keep the bed' as
    'keep the bed frame' for 'Platform Bed Frame (Queen)'. Parenthetical
    qualifiers are stripped entirely (wherever they appear, not just at the
    end) since they're rarely how a person refers to the item in feedback."""
    name = re.sub(r"\([^)]*\)", "", name.lower())
    words = re.findall(r"[a-z]+", name)
    return [w for w in words if w not in _NAME_STOPWORDS and len(w) >= 3]


def _rule_based_parse(raw_text: str, current_items: list[dict], current_budget: float) -> dict:
    text = raw_text.lower()
    deltas = _empty_deltas()

    for item in current_items:
        name = item["catalog_item"]["name"].lower()
        sig_words = _significant_words(name)
        matched_words = [w for w in sig_words if re.search(rf"\b{re.escape(w)}\b", text)]
        if not matched_words:
            continue

        keep_context = any(
            re.search(rf"\bkeep\b.{{0,25}}\b{re.escape(w)}\b|\b{re.escape(w)}\b.{{0,25}}\bkeep\b", text)
            for w in matched_words
        )
        remove_context = any(
            re.search(rf"\b(remove|don'?t like|not (a fan of|keen on)|get rid of)\b.{{0,25}}\b{re.escape(w)}\b", text)
            for w in matched_words
        )
        if keep_context:
            deltas["keep_item_ids"].append(item["catalog_item"]["id"])
        elif remove_context:
            deltas["remove_item_ids"].append(item["catalog_item"]["id"])

    if re.search(r"\bkeep (the )?existing furniture\b", text):
        deltas["notes"] += "User asked to keep all existing furniture. "

    for style in FR3_STYLES:
        if style.lower() in text and re.search(rf"\b(more|like|prefer)\b.{{0,15}}{style.lower()}", text):
            deltas["style_shift"] = style
            break

    if any(re.search(p, text) for p in _CHEAPER_PATTERNS):
        deltas["budget_delta"] = -round(current_budget * BUDGET_DELTA_FRACTION, 2)
    elif any(re.search(p, text) for p in _PRICIER_PATTERNS):
        deltas["budget_delta"] = round(current_budget * BUDGET_DELTA_FRACTION, 2)

    if any(re.search(p, text) for p in _LESS_CROWDED_PATTERNS):
        deltas["crowding_shift"] = "less"
    elif any(re.search(p, text) for p in _MORE_FULL_PATTERNS):
        deltas["crowding_shift"] = "more"

    return deltas


_GEMINI_EXTRACTION_PROMPT_TEMPLATE = """Extract structured preferences from this interior design feedback.
Current recommended items: {items_desc}
Feedback: "{raw_text}"

Respond with ONLY a JSON object with these exact keys:
- keep_item_ids: array of integers (item ids from the list above the user wants kept)
- remove_item_ids: array of integers (item ids the user wants removed)
- style_shift: one of {styles} or null
- budget_delta: a number (positive or negative) or null
- crowding_shift: "less", "more", or null
- notes: a short string for anything else relevant

Do not include any text other than the JSON object."""


def _gemini_parse(raw_text: str, current_items: list[dict], current_budget: float, api_key: str) -> dict | None:
    try:
        from google import genai
    except ImportError:
        return None

    items_desc = ", ".join(f"{i['catalog_item']['id']}={i['catalog_item']['name']}" for i in current_items)
    prompt = _GEMINI_EXTRACTION_PROMPT_TEMPLATE.format(items_desc=items_desc, raw_text=raw_text, styles=FR3_STYLES)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt])
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("json").strip()
        parsed = json.loads(text)
        deltas = _empty_deltas()
        deltas.update({k: v for k, v in parsed.items() if k in deltas})
        return deltas
    except Exception as exc:  # noqa: BLE001 — any failure here means "fall back to rules"
        logger.info("Gemini feedback parse failed, falling back to rules: %s", exc)
        return None


def parse_feedback(
    raw_text: str, current_items: list[dict], current_budget: float, gemini_api_key: str | None = None
) -> dict:
    if gemini_api_key:
        result = _gemini_parse(raw_text, current_items, current_budget, gemini_api_key)
        if result is not None:
            return result
    return _rule_based_parse(raw_text, current_items, current_budget)
