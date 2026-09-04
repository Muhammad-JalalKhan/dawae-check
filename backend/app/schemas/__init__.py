"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ── Verify endpoint schemas ──────────────────────────────────────────────────

class DetectedDefect(BaseModel):
    """Single visual defect from Layer-2 AI analysis."""
    label: str
    confidence: float
    bbox_2d: list[float]


class Layer1DatabaseCheck(BaseModel):
    """Layer-1 database gate result."""
    status: str  # PASSED | FAILED
    reasons: list[str] = Field(default_factory=list)
    matched_record: dict[str, Any] | None = None


class Layer2VisualCheck(BaseModel):
    """Layer-2 visual inspection result."""
    status: str  # PASSED | FAILED
    print_quality_score: float
    detected_defects: list[DetectedDefect] = Field(default_factory=list)


class VerifyResponse(BaseModel):
    """Full response contract for POST /api/v1/verify-packaging."""
    request_id: str
    verdict: str  # GENUINE | REVIEW_RECOMMENDED | SUSPECTED_COUNTERFEIT
    authenticity_score: float
    layer1_database_check: Layer1DatabaseCheck
    layer2_visual_check: Layer2VisualCheck
    technical_summary: str


# ── Batch schemas ────────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    """Request body for POST /api/v1/batches."""
    gtin: str | None = None
    brand_name: str
    batch_number: str
    manufacturer: str | None = None
    drap_reg_number: str | None = None
    mfg_lic_number: str | None = None
    mfg_date: date | None = None
    official_expiry: date
    mrp: Decimal | None = None


class BatchResponse(BaseModel):
    """Response for batch lookup / creation."""
    batch_id: str
    gtin: str | None = None
    brand_name: str
    batch_number: str
    manufacturer: str | None = None
    drap_reg_number: str | None = None
    mfg_lic_number: str | None = None
    mfg_date: date | None = None
    official_expiry: date
    mrp: Decimal | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Scan log schema ──────────────────────────────────────────────────────────

class ScanLogResponse(BaseModel):
    """Single scan log entry for audit trail."""
    scan_id: str
    request_id: str
    device_id: str
    facility_id: str
    extracted_gtin: str | None = None
    extracted_batch_number: str | None = None
    layer1_status: str
    layer2_status: str
    authenticity_score: float
    verdict: str
    created_at: str

    model_config = {"from_attributes": True}
