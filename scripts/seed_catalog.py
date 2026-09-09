#!/usr/bin/env python3
"""
Seed the furniture_catalog table with real, purchasable products.

2026-09-09: replaced the original mock catalog with 30 real products,
manually researched (not scraped, not fabricated) from real Indian
retailers — IKEA India, Urban Ladder, Pepperfry, Home Centre, Wakefit,
Obeetee, Homesake — each with a real name, real current price, real
dimensions from the retailer's own spec sheet, and a real link to the
actual product page. `price_verified_at` records exactly when each was
checked, so a stale price reads as stale, not as live (see PLAN.md for the
full research methodology and the honest caveats noted per item below).

Every catalog item's price/link/dimensions are real. `image_url` is the ONE
field that deliberately remains a placeholder (picsum.photos) rather than a
hotlinked retailer photo — hotlinking a third party's product image raises
real ToS/copyright questions this project has no need to take on, and the
image was never the load-bearing fact here (the real name/price/link is).
This is a disclosed trade-off, not an oversight: the UI's "View real
product" link is what actually points at the genuine item.

Several items are the closest real, currently-in-stock match rather than an
exact match to the original mock description — flagged inline below with
NOTE comments, never silently substituted. A few thin/flat items (rugs,
curtains, a pendant lampshade) had one dimension not stated by the retailer;
those are flagged ESTIMATED inline and are the only non-retailer-sourced
numbers in this file.

Usage:
    source .venv/bin/activate
    python scripts/seed_catalog.py            # adds rows, skips if already seeded
    python scripts/seed_catalog.py --reset     # wipes and reseeds the catalog
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import get_config
from backend.db import init_engine
from backend.models import FurnitureCatalogItem
from sqlalchemy.orm import Session

VERIFIED = date(2026, 9, 9)  # the date every row below was actually checked live

# name, category, style_tags, color, price(INR), currency, W_cm, D_cm, H_cm, image_url, product_url
CATALOG_SEED = [
    # --- Sofas (real, IKEA India / Pepperfry / Urban Ladder) ---
    ("ÄPPLARYD 3-Seat Sofa", "sofa", ["Scandinavian", "Minimalist"], "Lejde light grey", 78990, "INR", 231, 93, 82,
     "https://picsum.photos/seed/sofa1/400/300", "https://www.ikea.com/in/en/p/aepplaryd-3-seat-sofa-lejde-light-grey-30506244/"),
    ("Chesterfield Leather Three Seater Sofa", "sofa", ["Traditional"], "Brown", 329000, "INR", 208, 86, 76,
     "https://picsum.photos/seed/sofa2/400/300", "https://www.pepperfry.com/product/chesterfield-leather-three-seater-sofa-in-brown-colour-2265127.html"),
    ("Chelsea Right Aligned 3 Seater Sectional Sofa", "sofa", ["Modern", "Contemporary"], "Vapour Grey", 64999, "INR", 271, 158, 75,
     "https://picsum.photos/seed/sofa3/400/300", "https://www.urbanladder.com/product/chelsea-right-sectional-sofa-vapour-grey-7520574"),
    # --- Chairs ---
    ("Owen Fabric Lounge Chair", "chair", ["Modern", "Contemporary"], "Matte mustard yellow", 9999, "INR", 55.9, 54.4, 82.3,
     "https://picsum.photos/seed/chair1/400/300", "https://www.urbanladder.com/product/owen-lounge-chair-in-matte-mustard-yellow-colour-8148082"),
    ("RÖNNINGE Chair", "chair", ["Scandinavian", "Minimalist"], "Birch", 8950, "INR", 46, 49, 79,
     "https://picsum.photos/seed/chair2/400/300", "https://www.ikea.com/in/en/p/roenninge-chair-birch-80400754/"),
    ("Raglan Metal Bar Stool", "chair", ["Industrial"], "Black", 5749, "INR", 40.64, 40.64, 106.68,
     "https://picsum.photos/seed/chair3/400/300", "https://www.pepperfry.com/product/raglan-metal-low-back-bar-stool-in-black-colour-1932943.html"),
    ("Genoa Fabric Wing Chair", "chair", ["Traditional"], "Cobalt", 19999, "INR", 95, 69, 107,
     "https://picsum.photos/seed/chair4/400/300", "https://www.urbanladder.com/product/genoa-wing-chair-in-cobalt-colour-8148077"),
    ("Green Soul Jupiter Superb Ergonomic Mesh Office Chair", "chair", ["Modern"], "Black", 8989, "INR", 65, 50, 115,
     "https://picsum.photos/seed/chair5/400/300", "https://www.amazon.in/Green-Jupiter-Superb-Multi-Tilt-2-Dimensional-Adjustable/dp/B0987V3K22"),
    # --- Beds ---
    # NOTE: engineered wood/particleboard wood-effect finish, not solid natural timber.
    ("NODELAND Bed Frame", "bed", ["Minimalist", "Scandinavian"], "Medium brown", 10990, "INR", 165.3, 204.6, 68.0,
     "https://picsum.photos/seed/bed1/400/300", "https://www.ikea.com/in/en/p/nodeland-bed-frame-medium-brown-s29308527/"),
    ("Lewis Fabric Queen Size Bed", "bed", ["Contemporary", "Modern"], "Cloud beige / walnut brown", 49610, "INR", 160, 213, 108,
     "https://picsum.photos/seed/bed2/400/300", "https://www.urbanladder.com/product/lewis-upholstered-queen-size-non-storage-bed-in-cloud-beige-and-walnut-brown-9821427"),
    ("Morris Metal Queen Size Bed", "bed", ["Industrial"], "Black", 11528, "INR", 160, 193, 91,
     "https://picsum.photos/seed/bed3/400/300", "https://www.urbanladder.com/product/morris-metal-queen-size-non-storage-bed-in-black-finish-7524322"),
    # --- Tables ---
    # NOTE: matte-black steel frame, not chrome.
    ("KLINGSBO Coffee Table", "table", ["Modern", "Contemporary"], "Black / clear glass", 6990, "INR", 116, 78, 49,
     "https://picsum.photos/seed/table1/400/300", "https://www.ikea.com/in/en/p/klingsbo-coffee-table-black-clear-glass-40161557/"),
    # NOTE: solid mango wood in a walnut finish, described by the retailer as "contemporary" —
    # closest in-stock real match for an industrial/reclaimed-look coffee table; true
    # industrial/reclaimed options found were out of stock at verification time.
    ("Quinn Rectangular Solid Wood Coffee Table", "table", ["Traditional"], "Danish walnut", 14999, "INR", 120, 59.95, 42.42,
     "https://picsum.photos/seed/table2/400/300", "https://www.urbanladder.com/product/quinn-rectangular-solid-wood-coffee-table-in-danish-walnut-finish-8340209"),
    ("BORGEBY Side Table", "table", ["Scandinavian", "Minimalist"], "Birch veneer", 7990, "INR", 46, 46, 55,
     "https://picsum.photos/seed/table3/400/300", "https://www.ikea.com/in/en/p/borgeby-side-table-birch-veneer-60619881/"),
    # NOTE: has 2 shelves + a pull-out keyboard tray, not a literal drawer — no
    # drawer-equipped walnut/black-steel desk was found in stock.
    ("Wakefit Elarox Multi Purpose Study Table", "table", ["Minimalist", "Industrial"], "Columbian walnut / matt black", 8877, "INR", 114.8, 55.8, 85.8,
     "https://picsum.photos/seed/desk1/400/300", "https://www.wakefit.co/study-tables/elarox-multi-purpose-study-table/WSTELAROXCW"),
    # --- Cabinets ---
    ("Rhodes 3 Door Solid Wood Sideboard", "cabinet", ["Modern", "Contemporary"], "Amber walnut", 22999, "INR", 130.048, 39.6, 74.93,
     "https://picsum.photos/seed/cabinet1/400/300", "https://www.urbanladder.com/product/rhodes-3-door-solid-wood-sideboard-in-amber-walnut-finish-7520279"),
    # NOTE: solid wood with woven rattan-mesh door fronts, not pure natural rattan —
    # true natural-rattan cabinets found were out of stock.
    ("Canvera 2-Door Sideboard with Rattan Mesh Front", "cabinet", ["Scandinavian", "Traditional"], "Walnut", 45499, "INR", 99, 43, 84,
     "https://picsum.photos/seed/cabinet2/400/300", "https://www.pepperfry.com/product/canvera-2-door-sideboard-with-rattan-mesh-front-in-wa-2286823.html"),
    ("BESTÅ TV Bench", "cabinet", ["Modern", "Minimalist"], "Black-brown", 9200, "INR", 120, 40, 48,
     "https://picsum.photos/seed/cabinet3/400/300", "https://www.ikea.com/in/en/p/besta-tv-bench-black-brown-s39219408/"),
    # --- Shelves ---
    # NOTE: a single shelf, not a multi-piece set.
    ("LACK Wall Shelf", "shelf", ["Minimalist", "Scandinavian"], "White", 1690, "INR", 110, 26, 5,
     "https://picsum.photos/seed/shelf1/400/300", "https://www.ikea.com/in/en/p/lack-wall-shelf-white-70282181/"),
    # NOTE: metal only (no pipe+wood combo) and grey rather than black — closest
    # in-stock industrial-style bookshelf found; a taller (~180cm) black
    # pipe-and-wood bookshelf could not be confirmed in current stock.
    ("Westin Metal Book Shelf", "shelf", ["Industrial", "Modern"], "Grey", 6599, "INR", 50, 32.5, 149,
     "https://picsum.photos/seed/shelf2/400/300", "https://www.pepperfry.com/product/westin-metal-book-shelf-in-grey-finish-1886561.html"),
    # --- Lighting ---
    # NOTE: a straight candlestick-style lamp, not arc-shaped — real arc floor
    # lamps found were only available in black, not gold; chosen for its
    # correct base size and color.
    ("HOMESAKE Contemporary Decor Floor Lamp", "lighting", ["Contemporary", "Modern"], "Gold", 4398, "INR", 33, 33, 142,
     "https://picsum.photos/seed/lamp1/400/300", "https://www.homecentre.in/in/en/Decor/Lighting/Floor-Lamps/HOMECENTRE-HOMESAKE-Contemporary-Decor-Gold-Metal-Floor-Lamp/p/1000011154516"),
    # ESTIMATED height: IKEA lists only a 45cm diameter for this lampshade, no
    # separate height — approximated as equal to diameter (a paper lantern
    # shade is roughly spherical); every other figure here is retailer-stated.
    ("GULLSUDARE Pendant Lamp Shade", "lighting", ["Scandinavian", "Minimalist"], "White", 399, "INR", 45, 45, 45,
     "https://picsum.photos/seed/lamp2/400/300", "https://www.ikea.com/in/en/p/gullsudare-pendant-lamp-shade-white-handmade-70603870/"),
    ("Industrial Metal Hanging Pendant Light", "lighting", ["Industrial"], "Black", 1299, "INR", 18.5, 18.5, 28,
     "https://picsum.photos/seed/lamp3/400/300", "https://www.homesake.in/products/industrial-metal-hanging-pendant-light-wire-mesh-metal-cage-black"),
    # --- Rugs ---
    ("Chevron Carpet", "rug", ["Scandinavian", "Minimalist"], "White / beige", 10300, "INR", 154.94, 220.98, 1,
     "https://picsum.photos/seed/rug1/400/300", "https://www.urbanladder.com/product/chevron-carpet-5-x-7-9657301"),
    # ESTIMATED height: retailer didn't state pile height for this item —
    # 1cm used to match the other real rug above (a standard pile thickness).
    ("Empress Hand Knotted Woollen Rug", "rug", ["Traditional"], "Deep red / burgundy with gold medallion", 69300, "INR", 152.4, 243.84, 1,
     "https://picsum.photos/seed/rug2/400/300", "https://www.obeetee.in/products/empress-hand-knotted-woollen-and-cotton-rug"),
    # --- Curtains ---
    # ESTIMATED depth: fabric thickness not stated by the retailer for either
    # curtain below — 1cm used (standard fabric-panel convention already used
    # elsewhere in this catalog for thin/flat items).
    ("DYTÅG Curtains (1 Pair)", "curtain", ["Contemporary", "Minimalist"], "White", 6490, "INR", 145, 250, 1,
     "https://picsum.photos/seed/curtain1/400/300", "https://www.ikea.com/in/en/p/dytag-curtains-1-pair-with-heading-tape-white-60466717/"),
    # NOTE: 100% polyester (mostly recycled), not velvet — no fetchable green
    # velvet blackout curtain was found in stock.
    ("MAJGULL Block-Out Curtains (1 Pair)", "curtain", ["Traditional", "Industrial"], "Dark green", 3990, "INR", 145, 250, 1,
     "https://picsum.photos/seed/curtain2/400/300", "https://www.ikea.com/in/en/p/majgull-block-out-curtains-1-pair-dark-green-with-heading-tape-30586028/"),
    # --- Decor ---
    # NOTE: pot material is listed as plastic, not confirmed ceramic.
    ("3Ft Artificial Variegated Dracaena Plant with Pot", "decor", ["Contemporary", "Scandinavian"], "Green", 3399, "INR", 48.1, 38.9, 85,
     "https://picsum.photos/seed/decor1/400/300", "https://www.pepperfry.com/product/3ft-artificial-variegated-dracaena-plant-with-pot-2313289.html"),
    ("Multicolor Canvas Framed Abstract Wall Art", "decor", ["Modern", "Contemporary"], "Multicolour", 2189, "INR", 58.42, 5.08, 88.9,
     "https://picsum.photos/seed/decor2/400/300", "https://www.pepperfry.com/product/1pc-multicolor-canvas-framed-abstract-wall-art-2271565.html"),
    ("Handmade Macrame Wall Hanging with Pine Wood Shelf", "decor", ["Scandinavian", "Traditional"], "Off white", 432, "INR", 30.48, 15.24, 67.056,
     "https://picsum.photos/seed/decor3/400/300", "https://www.pepperfry.com/product/handmade-macrame-wall-hanging-with-pine-wood-shelf-in-off-white-by-ecofynd-2104684.html"),
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

        for (name, category, styles, color, price, currency, w, d, h, image_url, product_url) in CATALOG_SEED:
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
                    product_url=product_url,
                    price_verified_at=VERIFIED,
                    # data_source defaults to 'REAL' at the model level — not set here.
                )
            )
        db.commit()

        total = db.query(FurnitureCatalogItem).count()
        real_count = db.query(FurnitureCatalogItem).filter_by(data_source="REAL").count()
        print(f"Seeded {len(CATALOG_SEED)} rows. Catalog total: {total}. data_source='REAL' rows: {real_count}.")
        assert total == real_count, "Every catalog row must be stamped data_source='REAL' — invariant violated."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete all existing catalog rows before seeding.")
    args = parser.parse_args()
    seed(reset=args.reset)
