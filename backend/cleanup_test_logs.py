"""Cleanup script – removes dummy/test scan records from scanned_logs.

Deletes rows created by test_scoring_local.py clone scenarios and any other
test-device rows so that a clean Augmentin scan returns GENUINE (score 94)
instead of triggering the 24-hour clone alert.

Patterns removed:
    request_id LIKE 'clone-test-%'   (clone scenario logs)
    device_id  LIKE 'DEV-CLONE-%'    (clone scenario devices)
    device_id  LIKE 'test%'          (generic test devices)

Run via:
    cd backend/
    python cleanup_test_logs.py
"""

import asyncio
import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import delete, or_, select, func

from app.db.session import async_session_factory, engine
from app.models.scanned_log import ScannedLog


async def cleanup() -> None:
    """Delete dummy test rows from scanned_logs and report counts."""
    condition = or_(
        ScannedLog.request_id.like("clone-test-%"),
        ScannedLog.device_id.like("DEV-CLONE-%"),
        ScannedLog.device_id.like("test%"),
    )

    async with async_session_factory() as session:
        # Report what will be removed
        count_stmt = select(func.count()).select_from(ScannedLog).where(condition)
        total = (await session.execute(count_stmt)).scalar() or 0
        print(f"Found {total} dummy scan record(s) matching test patterns.")

        if total:
            result = await session.execute(delete(ScannedLog).where(condition))
            await session.commit()
            print(f"Deleted {result.rowcount} row(s) from scanned_logs.")
        else:
            print("Nothing to clean — scanned_logs has no test rows.")

        # Show what remains
        remaining = (await session.execute(
            select(func.count()).select_from(ScannedLog)
        )).scalar() or 0
        print(f"Remaining scanned_logs rows: {remaining}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(cleanup())
