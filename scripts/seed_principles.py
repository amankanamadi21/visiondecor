#!/usr/bin/env python3
"""
Seed (or reseed) the design_principles table from principles_data.py and
compute each row's embedding via the local all-MiniLM-L6-v2 model.

Usage:
    source .venv/bin/activate
    python scripts/seed_principles.py            # adds/updates rows
    python scripts/seed_principles.py --reset     # wipes and reseeds
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.recommendation.embeddings import embed_texts
from ai.recommendation.principles_data import PRINCIPLES
from backend.config import get_config
from backend.db import init_engine
from backend.models import DesignPrinciple
from sqlalchemy.orm import Session


def seed(reset: bool) -> None:
    config = get_config()
    engine = init_engine(config.DATABASE_URL)
    with Session(engine) as db:
        if reset:
            deleted = db.query(DesignPrinciple).delete()
            db.commit()
            print(f"Deleted {deleted} existing principle rows.")

        # Embed the title + body together — this is what gets matched against
        # a query built from room_type/style/category context at retrieval
        # time (see ai/recommendation/rag.py).
        texts = [f"{p['title']}. {p['body']}" for p in PRINCIPLES]
        print(f"Embedding {len(texts)} principles with all-MiniLM-L6-v2 (first run downloads the model)...")
        vectors = embed_texts(texts)

        added, updated = 0, 0
        for principle, vector in zip(PRINCIPLES, vectors):
            existing = db.query(DesignPrinciple).filter_by(code=principle["code"]).first()
            if existing:
                existing.category = principle["category"]
                existing.title = principle["title"]
                existing.body = principle["body"]
                existing.applies_to_room_types = principle["applies_to_room_types"]
                existing.applies_to_styles = principle["applies_to_styles"]
                existing.source_note = principle["source_note"]
                existing.embedding = vector.tolist()
                updated += 1
            else:
                db.add(
                    DesignPrinciple(
                        code=principle["code"],
                        category=principle["category"],
                        title=principle["title"],
                        body=principle["body"],
                        applies_to_room_types=principle["applies_to_room_types"],
                        applies_to_styles=principle["applies_to_styles"],
                        source_note=principle["source_note"],
                        embedding=vector.tolist(),
                    )
                )
                added += 1
        db.commit()

        total = db.query(DesignPrinciple).count()
        print(f"Added {added}, updated {updated}. Table total: {total}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed(reset=args.reset)
