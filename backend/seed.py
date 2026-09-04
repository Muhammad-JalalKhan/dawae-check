"""Seed script – populates the database with test manufacturers and batch data.

Run via:
    python -m backend.seed
    # or
    python backend/seed.py

Idempotent: inserts missing data and updates existing rows to match this file.
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
        "company_name": "GlaxoSmithKline",
        "drap_license_number": "DRAP-GSK-001",
        "contact_email": "compliance@gsk.com.pk",
        "contact_phone": "+92-21-111-222-333",
        "address": "Plot 23, SITE Industrial Area, Karachi, Pakistan",
        "is_active": True,
    },
    {
        "company_name": "Alpha Pharma",
        "drap_license_number": "DRAP-ALPHA-003",
        "contact_email": "regulatory@alphapharma.example",
        "contact_phone": "+966-000-000-000",
        "address": "King Abdullah Economic City, Saudi Arabia",
        "is_active": True,
    },
]

BATCHES = [
    # 1. Genuine baseline: Augmentin 14 Tablets (GlaxoSmithKline)
    {
        "brand_lookup": "GlaxoSmithKline",
        "gtin": "08964000123456",
        "brand_name": "Augmentin 14 Tablets",
        "batch_number": "B492",
        "drap_reg_number": "REG-PAK-00201",
        "official_expiry": date(2026, 12, 31),
        "manufacture_date": date(2024, 6, 15),
        "is_active": True,
    },
    # 2. Expiry mismatch test: Adol 24 Caplets (Paracetamol)
    #    DB expiry is intentionally expired to force S_rule=0 during testing.
    {
        "brand_lookup": "Alpha Pharma",
        "gtin": "08964000654321",
        "brand_name": "Adol 24 Caplets",
        "batch_number": "P811",
        "drap_reg_number": "REG-PAK-00184",
        "official_expiry": date(2024, 6, 30),
        "manufacture_date": date(2022, 6, 1),
        "is_active": True,
    },
    # 3. Unregistered control: C-Retard 500mg (Hikma)
    #    This product is deliberately NOT inserted into batch_registry so any
    #    scan should fail the database gate with S_DB=0.
]

UNSEEDED_PRODUCT_NAMES = ["C-Retard 500mg", "C-Retard"]


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
                existing.company_name = mfr_data["company_name"]
                existing.contact_email = mfr_data["contact_email"]
                existing.contact_phone = mfr_data["contact_phone"]
                existing.address = mfr_data["address"]
                existing.is_active = mfr_data["is_active"]
                print(f"  [sync] Manufacturer: {mfr_data['company_name']}")
                mfr_map[mfr_data["company_name"]] = existing
            else:
                mfr = Manufacturer(**mfr_data)
                session.add(mfr)
                mfr_map[mfr_data["company_name"]] = mfr
                print(f"  [add]  Manufacturer: {mfr_data['company_name']}")

        await session.flush()  # ensure manufacturer_ids are assigned

        # --- Unseeded controls ---
        # Keep C-Retard absent from Supabase so scans hard-fail with S_DB=0.
        for product_name in UNSEEDED_PRODUCT_NAMES:
            stmt = select(BatchRegistry).where(
                BatchRegistry.brand_name.ilike(f"%{product_name}%")
            )
            result = await session.execute(stmt)
            stale_rows = result.scalars().all()
            for stale in stale_rows:
                await session.delete(stale)
                print(
                    "  [delete] Unseeded control row removed: "
                    f"{stale.brand_name} / {stale.batch_number}"
                )

        # --- Batches ---
        for batch_data in BATCHES:
            stmt = select(BatchRegistry).where(
                BatchRegistry.gtin == batch_data["gtin"],
                BatchRegistry.batch_number == batch_data["batch_number"],
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            manufacturer = mfr_map[batch_data["brand_lookup"]]
            if existing:
                existing.manufacturer_id = manufacturer.manufacturer_id
                existing.brand_name = batch_data["brand_name"]
                existing.drap_reg_number = batch_data["drap_reg_number"]
                existing.official_expiry = batch_data["official_expiry"]
                existing.manufacture_date = batch_data["manufacture_date"]
                existing.is_active = batch_data["is_active"]
                print(
                    f"  [sync] Batch: {batch_data['brand_name']} / "
                    f"{batch_data['batch_number']}"
                )
                continue

            batch = BatchRegistry(
                manufacturer_id=manufacturer.manufacturer_id,
                gtin=batch_data["gtin"],
                brand_name=batch_data["brand_name"],
                batch_number=batch_data["batch_number"],
                drap_reg_number=batch_data["drap_reg_number"],
                official_expiry=batch_data["official_expiry"],
                manufacture_date=batch_data["manufacture_date"],
                is_active=batch_data["is_active"],
            )
            session.add(batch)
            print(
                f"  [add]  Batch: {batch_data['brand_name']} / "
                f"{batch_data['batch_number']}"
            )

        await session.commit()
        print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
