"""Standalone test script – runs gate + scoring scenarios against the seeded registry.

Usage:
    cd backend/
    python test_scoring_local.py

Connects to the database using the existing session infrastructure,
seeds data if needed, then runs each test scenario.
"""

import asyncio
import sys
import os
import uuid
from datetime import date, datetime, timedelta, timezone

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory, engine, Base
from app.models import Manufacturer, BatchRegistry, ScannedLog  # noqa: F401
from app.services.db_gate import check_database_gate
from app.services.scoring import compute_final_score

# ── Import seed to ensure data exists ──────────────────────────────────────
from seed import seed


# ── Test scenarios ─────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "name": "Lowplat Plus 75mg (valid match)",
        "gtin": "08964001422372",
        "batch_number": "6D284",
        "expiry": "2028-03-31",
        "s_visual": 85,
        "expected": {"s_db": 1, "s_rule": 100, "verdict": "GENUINE"},
    },
    {
        "name": "Valtic 40mg (expiry mismatch)",
        "gtin": "08964002023370",
        "batch_number": "205",
        "expiry": "2027-12-31",  # registry has 2027-04-30 for batch 205
        "s_visual": 35,
        "expected": {"s_db": 1, "s_rule": 0, "verdict": "SUSPECTED_COUNTERFEIT"},
        # The authoritative formula S_DB×(0.60×S_rule+0.40×S_visual)
        # yields max 40 when s_rule=0, so expiry mismatch → always SUSPECTED_COUNTERFEIT.
    },
    {
        "name": "Unregistered batch (control)",
        "gtin": "08964009999999",
        "batch_number": "ZZ-999",
        "expiry": "2028-01-31",
        "s_visual": 35,
        "expected": {"s_db": 0, "s_rule": 0, "verdict": "SUSPECTED_COUNTERFEIT"},
    },
    {
        "name": "Rosut-10 10mg (valid DB / fake print)",
        "gtin": "08964001581987",
        "batch_number": "051",
        "expiry": "2027-07-31",
        # Low s_visual simulates detected print defects (halftone dots, ink bleed).
        # This is the "valid DB / fake print" case — batch is real but the
        # physical packaging shows signs of counterfeiting.
        "s_visual": 30,
        "expected": {"s_db": 1, "s_rule": 100, "verdict": "REVIEW_RECOMMENDED"},
        # score = 1 × (0.60×100 + 0.40×30) = 72 → REVIEW_RECOMMENDED
    },
]

# Clone scenario will be added dynamically after seeding scanned_logs
CLONE_SCENARIO = {
    "name": "Lowplat Plus CLONE (cloned serial)",
    "gtin": "08964001422372",
    "batch_number": "6D284",
    "expiry": "2028-03-31",
    "s_visual": 85,
    "expected": {"s_db": 1, "s_rule": 50, "verdict": "REVIEW_RECOMMENDED"},
    # score = 1 × (0.60×50 + 0.40×85) = 64 → REVIEW_RECOMMENDED
}


async def seed_clone_logs(session: AsyncSession) -> None:
    """Insert scanned_log rows that trigger clone detection for Lowplat Plus.

    Creates 3 entries with distinct facility_ids within the last 24h
    for the same (gtin, batch_number) — Lowplat Plus 75mg / 6D284.
    The clone detection threshold is 3 distinct facilities.
    Idempotent: skips if clone-test logs already exist.
    """
    # Check if clone logs already exist (idempotency)
    from sqlalchemy import select as sa_select
    existing = await session.execute(
        sa_select(ScannedLog.request_id).where(
            ScannedLog.request_id.like("clone-test-%")
        )
    )
    if existing.scalars().all():
        print("  [skip] Clone-test scanned_logs already exist")
        return

    now = datetime.now(timezone.utc)
    facilities = ["FACILITY-CLONE-A", "FACILITY-CLONE-B", "FACILITY-CLONE-C"]

    for idx, fac_id in enumerate(facilities):
        log = ScannedLog(
            scan_id=uuid.uuid4(),
            request_id=f"clone-test-{idx+1:03d}",
            device_id=f"DEV-CLONE-{idx+1:03d}",
            facility_id=fac_id,
            matched_batch_id=None,
            extracted_gtin="08964001422372",
            extracted_batch_number="6D284",
            extracted_expiry=date(2028, 3, 31),
            layer1_status="PASSED",
            layer2_status="PENDING",
            authenticity_score=0,
            verdict="PENDING",
            created_at=now - timedelta(hours=idx + 1),
        )
        session.add(log)

    await session.commit()
    print("  [add]  3 clone-test scanned_logs inserted for Lowplat Plus (3 distinct facilities)")


async def run_tests() -> None:
    """Run all 5 test scenarios and print results."""

    # Ensure tables exist and data is seeded
    print("=" * 80)
    print("Dawae-Check — Local Scoring Test (5 scenarios)")
    print("=" * 80)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed data
    print("\n[1/3] Seeding database...")
    await seed()

    # Run tests
    print("\n[2/3] Running test scenarios...\n")

    all_passed = True
    results: list[dict] = []

    # ── Phase 1: Run the 4 regular tests (no clone logs yet) ────────────
    async with async_session_factory() as session:
        session: AsyncSession

        for i, tc in enumerate(TEST_CASES, 1):
            gate_result = await check_database_gate(
                session=session,
                extracted_gtin=tc["gtin"],
                extracted_batch_number=tc["batch_number"],
                extracted_expiry=tc["expiry"],
                facility_id="TEST-FACILITY-001",
            )

            score, verdict = compute_final_score(
                s_db=gate_result["s_db"],
                s_rule=gate_result["s_rule"],
                s_visual=tc["s_visual"],
            )

            s_db_ok = gate_result["s_db"] == tc["expected"]["s_db"]
            s_rule_ok = gate_result["s_rule"] == tc["expected"]["s_rule"]
            verdict_ok = verdict == tc["expected"]["verdict"]
            passed = s_db_ok and s_rule_ok and verdict_ok

            if not passed:
                all_passed = False

            results.append({
                "num": i,
                "name": tc["name"],
                "s_db": gate_result["s_db"],
                "s_rule": gate_result["s_rule"],
                "s_visual": tc["s_visual"],
                "score": score,
                "verdict": verdict,
                "expected_verdict": tc["expected"]["verdict"],
                "passed": passed,
                "status": gate_result["status"],
                "reasons": gate_result["reasons"],
            })

    # ── Phase 2: Seed clone logs, THEN run clone scenario ───────────────
    print("\n[2b/3] Seeding clone-test scanned_logs (after regular tests)...")
    async with async_session_factory() as session:
        await seed_clone_logs(session)

    async with async_session_factory() as session:
        session: AsyncSession
        tc = CLONE_SCENARIO
        i = len(TEST_CASES) + 1

        gate_result = await check_database_gate(
            session=session,
            extracted_gtin=tc["gtin"],
            extracted_batch_number=tc["batch_number"],
            extracted_expiry=tc["expiry"],
            facility_id="TEST-FACILITY-001",
        )

        score, verdict = compute_final_score(
            s_db=gate_result["s_db"],
            s_rule=gate_result["s_rule"],
            s_visual=tc["s_visual"],
        )

        s_db_ok = gate_result["s_db"] == tc["expected"]["s_db"]
        s_rule_ok = gate_result["s_rule"] == tc["expected"]["s_rule"]
        verdict_ok = verdict == tc["expected"]["verdict"]
        passed = s_db_ok and s_rule_ok and verdict_ok

        if not passed:
            all_passed = False

        results.append({
            "num": i,
            "name": tc["name"],
            "s_db": gate_result["s_db"],
            "s_rule": gate_result["s_rule"],
            "s_visual": tc["s_visual"],
            "score": score,
            "verdict": verdict,
            "expected_verdict": tc["expected"]["verdict"],
            "passed": passed,
            "status": gate_result["status"],
            "reasons": gate_result["reasons"],
        })

    # ── Print detailed results ───────────────────────────────────────────
    print("-" * 80)
    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"Test {r['num']}: {r['name']}")
        print(f"  Gate status : {r['status']}")
        print(f"  Reasons     : {r['reasons']}")
        print(f"  s_db={r['s_db']}  s_rule={r['s_rule']}  s_visual={r['s_visual']} (mock)")
        print(f"  Score       : {r['score']}")
        print(f"  Verdict     : {r['verdict']}  (expected {r['expected_verdict']})  [{icon}]")
        print("-" * 80)

    # ── Print summary table (FIX 4) ──────────────────────────────────────
    print("\n[3/3] Results Summary\n")
    header = f"| {'#':>2} | {'Medicine/Scenario':<42} | {'S_DB':>4} | {'S_rule':>6} | {'S_visual':>8} | {'Score':>6} | {'Verdict':<24} |"
    sep = f"|{'-'*4}|{'-'*44}|{'-'*6}|{'-'*8}|{'-'*10}|{'-'*8}|{'-'*26}|"
    print(header)
    print(sep)
    for r in results:
        icon = "OK" if r["passed"] else "FAIL"
        print(
            f"| {r['num']:>2} | {r['name']:<42} | {r['s_db']:>4} | {r['s_rule']:>6} "
            f"| {r['s_visual']:>8} | {r['score']:>6} | {r['verdict']:<22}{icon:>2} |"
        )
    print(sep)

    # Final summary
    print(f"\n{'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 80)

    # Dispose engine
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_tests())
