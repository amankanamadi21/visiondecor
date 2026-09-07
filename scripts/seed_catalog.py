#!/usr/bin/env python3
"""
Seed the furniture_catalog table with mock-but-schema-complete sample data.

Every row is stamped data_source='MOCK' by the model default (brief PART 6 /
PART 34.15) — these are placeholder prices and dimensions for demoing the
recommendation and layout-optimisation pipeline, not real product data or
real prices. Dimensions are realistic (checked against typical furniture
sizing) since the layout optimiser depends on them being physically sensible,
even though the specific catalog and prices are invented for the demo.

Usage:
    source .venv/bin/activate
    python scripts/seed_catalog.py            # adds rows, skips if already seeded
    python scripts/seed_catalog.py --reset     # wipes and reseeds the catalog
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import get_config
from backend.db import init_engine
from backend.models import FurnitureCatalogItem
from sqlalchemy.orm import Session

# name, category, style_tags, color, price(INR), currency, W_cm, D_cm, H_cm, image_url
CATALOG_SEED = [
    ("Nordic Oak 3-Seater Sofa", "sofa", ["Scandinavian", "Minimalist"], "light gray", 34999, "INR", 200, 90, 85, "https://picsum.photos/seed/sofa1/400/300"),
    ("Chesterfield Leather Sofa", "sofa", ["Traditional", "Industrial"], "brown", 52999, "INR", 210, 95, 80, "https://picsum.photos/seed/sofa2/400/300"),
    ("Modular Sectional Sofa", "sofa", ["Modern", "Contemporary"], "charcoal", 45999, "INR", 260, 160, 78, "https://picsum.photos/seed/sofa3/400/300"),
    ("Glass-Top Coffee Table", "table", ["Modern", "Contemporary"], "clear/chrome", 8999, "INR", 110, 60, 40, "https://picsum.photos/seed/table1/400/300"),
    ("Reclaimed Wood Coffee Table", "table", ["Industrial", "Traditional"], "walnut", 11999, "INR", 120, 65, 45, "https://picsum.photos/seed/table2/400/300"),
    ("Round Scandi Side Table", "table", ["Scandinavian", "Minimalist"], "white oak", 4499, "INR", 45, 45, 50, "https://picsum.photos/seed/table3/400/300"),
    ("Platform Bed Frame (Queen)", "bed", ["Minimalist", "Scandinavian"], "natural wood", 27999, "INR", 160, 200, 35, "https://picsum.photos/seed/bed1/400/300"),
    ("Upholstered Bed Frame (Queen)", "bed", ["Contemporary", "Modern"], "beige", 32999, "INR", 165, 210, 110, "https://picsum.photos/seed/bed2/400/300"),
    ("Iron Frame Bed (Queen)", "bed", ["Industrial", "Traditional"], "black iron", 24999, "INR", 160, 205, 120, "https://picsum.photos/seed/bed3/400/300"),
    ("Accent Armchair", "chair", ["Modern", "Contemporary"], "mustard yellow", 14999, "INR", 75, 80, 85, "https://picsum.photos/seed/chair1/400/300"),
    ("Wishbone-Style Dining Chair", "chair", ["Scandinavian", "Minimalist"], "natural wood", 6999, "INR", 55, 55, 75, "https://picsum.photos/seed/chair2/400/300"),
    ("Industrial Bar Stool", "chair", ["Industrial"], "black metal", 3999, "INR", 40, 40, 90, "https://picsum.photos/seed/chair3/400/300"),
    ("Wing-Back Armchair", "chair", ["Traditional"], "deep red", 17999, "INR", 80, 85, 105, "https://picsum.photos/seed/chair4/400/300"),
    ("Floating Wall Shelf Set", "shelf", ["Minimalist", "Scandinavian"], "white", 2999, "INR", 90, 20, 15, "https://picsum.photos/seed/shelf1/400/300"),
    ("Industrial Pipe Bookshelf", "shelf", ["Industrial"], "black/wood", 13999, "INR", 100, 35, 180, "https://picsum.photos/seed/shelf2/400/300"),
    ("Mid-Century Sideboard", "cabinet", ["Contemporary", "Modern"], "walnut", 22999, "INR", 150, 45, 75, "https://picsum.photos/seed/cabinet1/400/300"),
    ("Rattan Storage Cabinet", "cabinet", ["Scandinavian", "Traditional"], "natural rattan", 18999, "INR", 90, 40, 100, "https://picsum.photos/seed/cabinet2/400/300"),
    ("Arc Floor Lamp", "lighting", ["Modern", "Contemporary"], "brushed brass", 7999, "INR", 30, 30, 165, "https://picsum.photos/seed/lamp1/400/300"),
    ("Paper Lantern Pendant Light", "lighting", ["Minimalist", "Scandinavian"], "white", 2499, "INR", 40, 40, 40, "https://picsum.photos/seed/lamp2/400/300"),
    ("Edison Bulb Cage Light", "lighting", ["Industrial"], "black metal", 1999, "INR", 20, 20, 30, "https://picsum.photos/seed/lamp3/400/300"),
    ("Wool Area Rug (Geometric)", "rug", ["Scandinavian", "Minimalist"], "cream/gray", 6499, "INR", 200, 140, 1, "https://picsum.photos/seed/rug1/400/300"),
    ("Persian-Style Area Rug", "rug", ["Traditional"], "burgundy/gold", 12999, "INR", 240, 170, 1, "https://picsum.photos/seed/rug2/400/300"),
    ("Linen Curtain Panels (Pair)", "curtain", ["Contemporary", "Minimalist"], "off-white", 3499, "INR", 140, 240, 1, "https://picsum.photos/seed/curtain1/400/300"),
    ("Blackout Velvet Curtains (Pair)", "curtain", ["Traditional", "Industrial"], "deep green", 5999, "INR", 140, 240, 1, "https://picsum.photos/seed/curtain2/400/300"),
    ("Monstera Plant + Ceramic Pot", "decor", ["Scandinavian", "Contemporary", "Minimalist"], "green/terracotta", 1899, "INR", 40, 40, 90, "https://picsum.photos/seed/decor1/400/300"),
    ("Abstract Wall Art (Set of 3)", "decor", ["Modern", "Contemporary"], "multicolor", 3299, "INR", 50, 3, 70, "https://picsum.photos/seed/decor2/400/300"),
    ("Woven Wall Hanging", "decor", ["Scandinavian", "Traditional"], "cream/tan", 1499, "INR", 60, 3, 90, "https://picsum.photos/seed/decor3/400/300"),
    ("TV Console Unit", "cabinet", ["Modern", "Minimalist"], "matte black", 15999, "INR", 140, 40, 45, "https://picsum.photos/seed/cabinet3/400/300"),
    ("Study Desk with Drawer", "table", ["Minimalist", "Industrial"], "walnut/black steel", 9999, "INR", 110, 55, 75, "https://picsum.photos/seed/desk1/400/300"),
    ("Ergonomic Office Chair", "chair", ["Modern", "Contemporary"], "black mesh", 8999, "INR", 60, 60, 110, "https://picsum.photos/seed/chair5/400/300"),
]


def seed(reset: bool) -> None:
    config = get_config()
    engine = init_engine(config.DATABASE_URL)
    with Session(engine) as db:
        if reset:
            deleted = db.query(FurnitureCatalogItem).delete()
            db.commit()
            print(f"Deleted {deleted} existing catalog rows.")

        existing_count = db.query(FurnitureCatalogItem).count()
        if existing_count > 0 and not reset:
            print(f"Catalog already has {existing_count} rows — skipping (use --reset to reseed).")
            return

        for (name, category, styles, color, price, currency, w, d, h, image_url) in CATALOG_SEED:
            db.add(
                FurnitureCatalogItem(
                    name=name,
                    category=category,
                    style_tags=styles,
                    color=color,
                    price=price,
                    currency=currency,
                    width_cm=w,
                    depth_cm=d,
                    height_cm=h,
                    image_url=image_url,
                    # data_source defaults to 'MOCK' at the model level — not set here.
                )
            )
        db.commit()

        total = db.query(FurnitureCatalogItem).count()
        mock_count = db.query(FurnitureCatalogItem).filter_by(data_source="MOCK").count()
        print(f"Seeded {len(CATALOG_SEED)} rows. Catalog total: {total}. data_source='MOCK' rows: {mock_count}.")
        assert total == mock_count, "Every catalog row must be stamped data_source='MOCK' — invariant violated."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete all existing catalog rows before seeding.")
    args = parser.parse_args()
    seed(reset=args.reset)
