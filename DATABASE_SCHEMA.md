# Database Schema — Dawae-Check

PostgreSQL / Supabase. Compliant with GS1 Healthcare (GTIN-14, Lot/Batch,
Expiry, Serial) and DRAP Serialization Guidelines.

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Manufacturers
CREATE TABLE manufacturers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255) NOT NULL,
    drap_license_num VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Official Batch Registry
CREATE TABLE batch_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gtin VARCHAR(14) NOT NULL,
    brand_name VARCHAR(255) NOT NULL,
    batch_number VARCHAR(100) NOT NULL,
    manufacturer_id UUID REFERENCES manufacturers(id),
    official_expiry_date DATE NOT NULL,
    drap_reg_num VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_gtin_batch UNIQUE (gtin, batch_number)
);

-- 3. Scanned Logs (audit + clone tracking)
CREATE TABLE scanned_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(100) NOT NULL,
    facility_id VARCHAR(100) DEFAULT 'GENERAL_DISPENSARY',
    scanned_gtin VARCHAR(14),
    scanned_batch_number VARCHAR(100),
    scanned_expiry_date VARCHAR(20),
    verdict VARCHAR(50) NOT NULL,
    authenticity_score INT NOT NULL,
    visual_defect_count INT DEFAULT 0,
    geo_latitude DECIMAL(10, 8),
    geo_longitude DECIMAL(11, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_batch_lookup ON batch_registry(gtin, batch_number);
CREATE INDEX idx_scan_clone_check ON scanned_logs(scanned_gtin, scanned_batch_number);
```

## Query Patterns The Backend Needs
1. **Batch lookup (Layer 1 gate):**
   `SELECT * FROM batch_registry WHERE gtin = ? AND batch_number = ? AND is_active = TRUE`
2. **Clone detection:** check if the same `scanned_gtin` + `scanned_batch_number`
   has been logged from more than one distinct `facility_id`/`geo` combo within
   a short time window in `scanned_logs`.
3. **Every verification call writes one row to `scanned_logs`**, regardless of verdict.

## Seed Data Needed For Demo
Before the mobile app can be usefully tested, `batch_registry` needs at least
2–3 real-looking rows (one that will "pass" a genuine test photo, one with a
mismatched expiry to demonstrate a COUNTERFEIT verdict). Put seed SQL in
`backend/seed.sql` if it doesn't already exist.
