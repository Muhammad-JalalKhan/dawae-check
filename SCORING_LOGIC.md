# Scoring Logic — Dawae-Check

This formula is authoritative and matches backend/app/services/scoring.py.

## Composite Formula
$$S_{final} = S_{DB} \times (0.60 \times S_{rule} + 0.40 \times S_{visual})$$

## Variables
- **S_DB ∈ {0, 1}** — binary hard gate:
  - `0` if: batch does not exist in registry OR expiry date does not match official record.
  - If `S_DB = 0`, then `S_final = 0` immediately (hard gate reject).
  - `1` if batch exists and expiry matches.

- **S_rule ∈ {0, 50, 100}**:
  - `100`: Clean batch (exists, expiry matches, no clone detected).
  - `50`: Cloned serial anomaly (same GTIN/batch scanned across multiple distinct facilities within detection window).
  - `0`: Expiry mismatch or unregistered batch.

- **S_visual ∈ [0, 100]**:
  - Micro-texture print quality score returned by Qwen2.5-VL. Penalties applied for:
    * Digital halftone dithering: -45 pts
    * Typography edge blur / ink bleed: -25 pts
    * Barcode contrast degradation: -20 pts
    * Color / logo boundary shift: -15 pts

## Decision Verdict Bands
| Score Range | Verdict String | Badge |
|---|---|---|
| 80–100 | GENUINE | 🟢 |
| 50–79 | REVIEW RECOMMENDED | 🟡 |
| 0–49 | SUSPECTED_COUNTERFEIT | 🔴 |