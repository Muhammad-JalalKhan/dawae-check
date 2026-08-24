"""Seed script – populates the database with test manufacturers and batch data.

Run via:
    python -m backend.seed
    # or
    python backend/seed.py

Idempotent: checks for existing data before inserting.
"""

import asyncio
import sys
import os
from datetime import date

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory, engine, Base
from app.models.manufacturer import Manufacturer
from app.models.batch_registry import BatchRegistry


# ── Seed data ────────────────────────────────────────────────────────────────

MANUFACTURERS = [
    {
        "company_name": "GSK Pakistan",
        "drap_license_number": "DRAP-GSK-001",
        "contact_email": "compliance@gsk.com.pk",
        "contact_phone": "+92-21-111-222-333",
        "address": "Plot 23, SITE Industrial Area, Karachi, Pakistan",
    },
    {
        "company_name": "Abbott Laboratories Pakistan",
        "drap_license_number": "DRAP-ABB-002",
        "contact_email": "regulatory@abbott.com.pk",
        "contact_phone": "+92-21-111-444-555",
        "address": "Plot 63, SITE Industrial Area, Karachi, Pakistan",
    },
]

BATCHES = [
    # 1. Augmentin 625mg – valid, real batch
    {
        "brand_lookup": "GSK Pakistan",
        "gtin": "08964000123456",
        "brand_name": "Augmentin 625mg",
        "batch_number": "B492",
        "drap_reg_number": "REG-PAK-00201",
        "official_expiry": date(2026, 12, 31),
        "manufacture_date": date(2024, 6, 15),
    },
    # 2. Panadol Extra – valid batch, but expiry MISMATCH scenario
    #    (DB says 2025-03-31; a scan extracting a different expiry will mismatch)
    {
        "brand_lookup": "GSK Pakistan",
        "gtin": "08964000234567",
        "brand_name": "Panadol Extra",
        "batch_number": "P1137",
        "drap_reg_number": "REG-PAK-00302",
        "official_expiry": date(2025, 3, 31),
        "manufacture_date": date(2023, 3, 1),
    },
    # 3. Arinac Forte – NOT inserted into batch_registry on purpose.
    #    This medicine is meant to trigger "unregistered batch" failure during scans.
    #    No batch_registry row is created for GTIN/batch lookups to miss.
    #
    # (No entry here)
    #
    # 4. Brufen 400mg – valid DB match, visual/print score handled later
    {
        "brand_lookup": "Abbott Laboratories Pakistan",
        "gtin": "08964000345678",
        "brand_name": "Brufen 400mg",
        "batch_number": "BF-2210",
        "drap_reg_number": "REG-PAK-00415",
        "official_expiry": date(2027, 6, 30),
        "manufacture_date": date(2025, 1, 10),
    },
]


# ── Seeding logic ────────────────────────────────────────────────────────────

async def seed() -> None:
    """Insert manufacturers and batches idempotently."""

    # Ensure tables exist
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        session: AsyncSession

        # --- Manufacturers ---
        mfr_map: dict[str, Manufacturer] = {}
        for mfr_data in MANUFACTURERS:
            stmt = select(Manufacturer).where(
                Manufacturer.drap_license_number == mfr_data["drap_license_number"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  [skip] Manufacturer already exists: {mfr_data['company_name']}")
                mfr_map[mfr_data["company_name"]] = existing
            else:
                mfr = Manufacturer(**mfr_data)
                session.add(mfr)
                mfr_map[mfr_data["company_name"]] = mfr
                print(f"  [add]  Manufacturer: {mfr_data['company_name']}")

        await session.flush()  # ensure manufacturer_ids are assigned

        # --- Batches ---
        for batch_data in BATCHES:
            stmt = select(BatchRegistry).where(
                BatchRegistry.gtin == batch_data["gtin"],
                BatchRegistry.batch_number == batch_data["batch_number"],
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  [skip] Batch already exists: {batch_data['brand_name']} / {batch_data['batch_number']}")
                continue

            manufacturer = mfr_map[batch_data["brand_lookup"]]
            batch = BatchRegistry(
                manufacturer_id=manufacturer.manufacturer_id,
                gtin=batch_data["gtin"],
                brand_name=batch_data["brand_name"],
                batch_number=batch_data["batch_number"],
                drap_reg_number=batch_data["drap_reg_number"],
                official_expiry=batch_data["official_expiry"],
                manufacture_date=batch_data["manufacture_date"],
            )
            session.add(batch)
            print(f"  [add]  Batch: {batch_data['brand_name']} / {batch_data['batch_number']}")

        await session.commit()
        print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
