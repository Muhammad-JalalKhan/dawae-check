"""Seed script – populates batch_registry with the verified medicine dataset.

Connection: DATABASE_URL is read from the environment / .env by
app.core.config (pydantic-settings) and consumed through the shared
async SQLAlchemy engine (postgresql+asyncpg) in app.db.session.

Run via:
    python backend/seed.py

Idempotent: every row is upserted with ON CONFLICT (batch_number) DO
UPDATE, so running the script repeatedly refreshes records in place
without duplicating rows.
"""

import asyncio
import os
import sys
from datetime import date
from decimal import Decimal

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.session import async_session_factory, engine, Base
from app.models.batch_registry import BatchRegistry


# ── Seed data: 15 verified medicines (extracted from packaging photos) ──────

MEDICINES = [
    {
        "brand_name": "Lowplat Plus 75mg",
        "gtin": "08964001422372",
        "batch_number": "6D284",
        "manufacturer": "PharmEvo (Pvt.) Ltd.",
        "drap_reg_number": "047177",
        "mfg_lic_number": "000504",
        "mfg_date": date(2026, 4, 1),
        "official_expiry": date(2028, 3, 31),
        "mrp": Decimal("298.76"),
    },
    {
        "brand_name": "Rosut-10 10mg",
        "gtin": "08964001581987",
        "batch_number": "051",
        "manufacturer": "Genix Pharma",
        "drap_reg_number": "056081",
        "mfg_lic_number": "000454",
        "mfg_date": date(2025, 7, 1),
        "official_expiry": date(2027, 7, 31),
        "mrp": Decimal("325.00"),
    },
    {
        "brand_name": "Valtic 40mg",
        "gtin": "08964002023370",
        "batch_number": "205",
        "manufacturer": "Tabros Pharma (Pvt) Ltd.",
        "drap_reg_number": "055899",
        "mfg_lic_number": "000106",
        "mfg_date": date(2025, 5, 1),
        "official_expiry": date(2027, 4, 30),
        "mrp": Decimal("330.00"),
    },
    {
        "brand_name": "Valtic 40mg",
        "gtin": "08964002023370",
        "batch_number": "217",
        "manufacturer": "Tabros Pharma (Pvt) Ltd.",
        "drap_reg_number": "055899",
        "mfg_lic_number": "000106",
        "mfg_date": date(2025, 10, 1),
        "official_expiry": date(2027, 9, 30),
        "mrp": Decimal("346.00"),
    },
    {
        "brand_name": "Nuberol Forte",
        "gtin": "08964000271960",
        "batch_number": "DH0273",
        "manufacturer": "The Searle Company Ltd.",
        "drap_reg_number": "027196",
        "mfg_lic_number": "000647",
        "mfg_date": date(2026, 5, 1),
        "official_expiry": date(2029, 5, 31),
        "mrp": Decimal("200.00"),
    },
    {
        "brand_name": "B-Card 5mg",
        "gtin": "08964001790990",
        "batch_number": "KSH002",
        "manufacturer": "The Searle Company Ltd.",
        "drap_reg_number": "104015",
        "mfg_lic_number": "000016",
        "mfg_date": date(2026, 4, 20),
        "official_expiry": date(2028, 4, 19),
        "mrp": Decimal("415.00"),
    },
    {
        "brand_name": "Nupenta 40mg",
        "gtin": "08964002066025",
        "batch_number": "T37031",
        "manufacturer": "Standpharm Pakistan",
        "drap_reg_number": "095820",
        "mfg_lic_number": "000844",
        "mfg_date": date(2025, 11, 1),
        "official_expiry": date(2027, 10, 31),
        "mrp": Decimal("486.00"),
    },
    {
        "brand_name": "Concor 2.5mg",
        "gtin": "08964001517108",
        "batch_number": "47235",
        "manufacturer": "Martin Dow Marker Ltd",
        "drap_reg_number": "028000",
        "mfg_lic_number": "000028",
        "mfg_date": date(2026, 4, 7),
        "official_expiry": date(2029, 4, 6),
        "mrp": Decimal("192.03"),
    },
    {
        "brand_name": "Ciprofloxacin 500mg",
        "gtin": "08964001786122",
        "batch_number": "A-173",
        "manufacturer": "Stanley Pharmaceuticals (Pvt) Ltd.",
        "drap_reg_number": "032008",
        "mfg_lic_number": "000434",
        "mfg_date": date(2026, 1, 1),
        "official_expiry": date(2029, 1, 31),
        "mrp": Decimal("170.00"),
    },
    {
        "brand_name": "Pediatric Cough/Allergy Syrup",
        "gtin": None,
        "batch_number": "07A26",
        "manufacturer": "Licensed Pharma",
        "drap_reg_number": "009763",
        "mfg_lic_number": "000140",
        "mfg_date": date(2026, 1, 1),
        "official_expiry": date(2029, 1, 31),
        "mrp": Decimal("155.00"),
    },
    {
        "brand_name": "Pasmec Tablets",
        "gtin": None,
        "batch_number": "414",
        "manufacturer": "Pasteur & Fleming Pharmaceuticals Pvt. Ltd.",
        "drap_reg_number": "01188",
        "mfg_lic_number": "1188910296",
        "mfg_date": date(2025, 6, 1),
        "official_expiry": date(2027, 5, 31),
        "mrp": Decimal("960.00"),
    },
    {
        "brand_name": "Mektum Homoeo Drops",
        "gtin": None,
        "batch_number": "50497",
        "manufacturer": "Mektum Homoeo Pharma",
        "drap_reg_number": "00126",
        "mfg_lic_number": None,
        "mfg_date": date(2025, 4, 1),
        "official_expiry": date(2028, 4, 30),
        "mrp": Decimal("210.00"),
    },
    {
        "brand_name": "Concor 5mg",
        "gtin": "08964001517115",
        "batch_number": "46955",
        "manufacturer": "Martin Dow Marker Ltd",
        "drap_reg_number": "010194",
        "mfg_lic_number": "000028",
        "mfg_date": date(2026, 3, 9),
        "official_expiry": date(2029, 3, 8),
        "mrp": Decimal("348.74"),
    },
    {
        "brand_name": "Gas-Gone Syrup",
        "gtin": None,
        "batch_number": "014",
        "manufacturer": "Swift Care Pharma (Pvt) Ltd.",
        "drap_reg_number": "00723",
        "mfg_lic_number": None,
        "mfg_date": date(2026, 4, 1),
        "official_expiry": date(2029, 3, 31),
        "mrp": Decimal("250.00"),
    },
    {
        "brand_name": "Calcimix Syrup",
        "gtin": None,
        "batch_number": "007",
        "manufacturer": "Swift Care Pharma (Pvt) Ltd.",
        "drap_reg_number": "00723",
        "mfg_lic_number": None,
        "mfg_date": date(2025, 12, 1),
        "official_expiry": date(2028, 11, 30),
        "mrp": Decimal("250.00"),
    },
]

# Columns refreshed by the upsert (everything except the natural key
# batch_number and the surrogate batch_id / timestamps).
_UPDATE_COLUMNS = (
    "gtin",
    "brand_name",
    "manufacturer",
    "drap_reg_number",
    "mfg_lic_number",
    "mfg_date",
    "official_expiry",
    "mrp",
    "is_active",
)


# ── Schema migration ────────────────────────────────────────────────────────

async def _ensure_schema() -> None:
    """Create or migrate the batch_registry table to the current schema.

    The legacy table (manufacturer FK + manufacture_date, no MRP) is
    dropped and recreated exactly once; scan history keeps its rows with
    the dangling batch references nulled. Re-runs on the current schema
    are no-ops, so the script stays fully idempotent.
    """
    import app.models  # noqa: F401 — populate Base.metadata

    async with engine.begin() as conn:
        # Create any missing tables first (fresh databases).
        await conn.run_sync(Base.metadata.create_all)

        table_exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'batch_registry'"
                )
            )
        ).scalar()

        if table_exists:
            # The current schema is identified by the `mrp` column.
            has_mrp = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'batch_registry' "
                        "AND column_name = 'mrp'"
                    )
                )
            ).scalar()
            if not has_mrp:
                print("  [migrate] Legacy batch_registry detected — recreating with current schema")
                # CASCADE drops the scanned_logs FK that points at the
                # legacy table.
                await conn.execute(text("DROP TABLE batch_registry CASCADE"))
                await conn.run_sync(
                    Base.metadata.create_all, tables=[BatchRegistry.__table__]
                )
                # Scan history referenced legacy batch ids — keep the audit
                # rows, null the dangling references.
                await conn.execute(
                    text("UPDATE scanned_logs SET matched_batch_id = NULL")
                )
                print("  [migrate] scanned_logs.matched_batch_id references cleared")

        # Restore the scanned_logs FK if the CASCADE above removed it.
        fk_exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM pg_constraint "
                    "WHERE conname = 'scanned_logs_matched_batch_id_fkey'"
                )
            )
        ).scalar()
        if not fk_exists:
            await conn.execute(
                text(
                    "ALTER TABLE scanned_logs ADD CONSTRAINT "
                    "scanned_logs_matched_batch_id_fkey FOREIGN KEY "
                    "(matched_batch_id) REFERENCES batch_registry (batch_id)"
                )
            )


# ── Seeding logic ───────────────────────────────────────────────────────────

async def seed() -> None:
    """Upsert all verified medicine batches (ON CONFLICT DO UPDATE)."""
    await _ensure_schema()

    print(f"  [seed] Target database: {settings.DATABASE_URL.split('@')[-1]}\n")

    async with async_session_factory() as session:
        for med in MEDICINES:
            stmt = insert(BatchRegistry).values(**med)
            stmt = stmt.on_conflict_do_update(
                index_elements=["batch_number"],
                set_={col: getattr(stmt.excluded, col) for col in _UPDATE_COLUMNS},
            )
            await session.execute(stmt)
            print(
                f"  [upsert] {med['brand_name']:<30} batch={med['batch_number']:<8} "
                f"expiry={med['official_expiry']} mrp={med['mrp']}"
            )
        await session.commit()

    # Confirmation table of everything now active in the registry.
    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(BatchRegistry)
                    .where(BatchRegistry.is_active.is_(True))
                    .order_by(BatchRegistry.brand_name, BatchRegistry.batch_number)
                )
            )
            .scalars()
            .all()
        )

    print(f"\n{'=' * 122}")
    print(f"SEED CONFIRMATION — {len(rows)} active batch_registry records")
    print(f"{'=' * 122}")
    header = (
        f"| {'#':>2} | {'Brand':<30} | {'Batch':<7} | {'GTIN':<14} | "
        f"{'DRAP':<6} | {'Mfg Date':<10} | {'Expiry':<10} | {'MRP':>7} | {'Manufacturer':<40} |"
    )
    print(header)
    print(
        f"|{'-' * 4}|{'-' * 32}|{'-' * 9}|{'-' * 16}|{'-' * 8}"
        f"|{'-' * 12}|{'-' * 12}|{'-' * 9}|{'-' * 42}|"
    )
    for i, row in enumerate(rows, 1):
        print(
            f"| {i:>2} | {row.brand_name:<30} | {row.batch_number:<7} | "
            f"{(row.gtin or '—'):<14} | {(row.drap_reg_number or '—'):<6} | "
            f"{str(row.mfg_date or '—'):<10} | {str(row.official_expiry):<10} | "
            f"{(row.mrp if row.mrp is not None else '—'):>7} | {(row.manufacturer or '—'):<40} |"
        )
    print(f"{'=' * 122}")
    print(f"Seed complete — {len(rows)}/{len(MEDICINES)} records active.\n")


async def _main() -> None:
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
