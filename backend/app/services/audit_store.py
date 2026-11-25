"""Separate audit persistence — Day 10.

Stores audit findings independently from evaluation records so the
two can be versioned and queried without coupling.  Uses flat JSON
files under ``data/audits/`` as a lightweight bridge until Day 11
introduces PostgreSQL / SQLite.
"""

import json
from pathlib import Path
from typing import Optional

from app.schemas.audit import AuditRecord, BatchAuditResult


AUDIT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audits"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(document_id: str) -> str:
    """Sanitise a document ID into a safe file-system name."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in document_id)


def save_batch_audit(result: BatchAuditResult) -> Path:
    """Persist a batch audit result to a JSON file.

    Returns the path of the written file.
    """
    name = _safe_filename(result.bidder_document_id)
    path = AUDIT_DIR / f"{name}_audit.json"
    path.write_text(
        json.dumps(result.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    return path


def load_batch_audit(bidder_document_id: str) -> Optional[BatchAuditResult]:
    """Load previously saved audit findings for a bidder.

    Returns ``None`` when no audit file exists.
    """
    name = _safe_filename(bidder_document_id)
    path = AUDIT_DIR / f"{name}_audit.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return BatchAuditResult(**data)


def list_audit_files() -> list[str]:
    """Return bidder document IDs for which audit files exist."""
    return [
        p.stem.replace("_audit", "")
        for p in AUDIT_DIR.glob("*_audit.json")
    ]
