"""
etl.py
------
The actual data-engineering core of this project. The LLM only does
extraction; everything after that — validation, normalization, dedup,
recurring-subscription detection — is deterministic pipeline logic.

EXTRACT -> llm_parser.parse_expense()
TRANSFORM -> validate amount, normalize category/merchant casing, detect duplicates/recurring
LOAD -> db.insert_expense()
"""

from datetime import datetime
import db
from llm_parser import parse_expense

VALID_CATEGORIES = {
    "Food Delivery", "Groceries", "Travel", "Entertainment",
    "Shopping", "Bills & Utilities", "Food & Dining", "Other",
}


class ETLResult:
    def __init__(self, success: bool, message: str, data: dict = None):
        self.success = success
        self.message = message
        self.data = data or {}


def _normalize(parsed: dict) -> dict:
    category = parsed.get("category", "Other")
    if category not in VALID_CATEGORIES:
        category = "Other"
    merchant = parsed.get("merchant")
    merchant = merchant.strip().title() if merchant else None
    return {
        "amount": round(float(parsed.get("amount", 0)), 2),
        "category": category,
        "merchant": merchant,
    }


def _validate(transformed: dict) -> ETLResult:
    if transformed["amount"] <= 0:
        return ETLResult(False, "Couldn't find a valid amount greater than 0 in that entry.")
    if transformed["amount"] > 1_000_000:
        return ETLResult(False, "That amount looks like a typo (over 10 lakh) — please re-check.")
    return ETLResult(True, "valid")


def preview(raw_text: str) -> dict:
    """Extract + transform only (no load) — used by the UI to show a live
    preview of how an entry will be parsed before the user commits it."""
    if not raw_text or not raw_text.strip():
        return {"amount": 0.0, "category": None, "merchant": None}
    parsed = parse_expense(raw_text)
    return _normalize(parsed)


def process_expense(username: str, raw_text: str) -> ETLResult:
    """Runs one expense entry through the full Extract -> Transform -> Load pipeline."""
    # EXTRACT
    parsed = parse_expense(raw_text)

    # TRANSFORM
    transformed = _normalize(parsed)
    validation = _validate(transformed)
    if not validation.success:
        return validation

    # Recurring-subscription detection: same merchant + same amount within ~35 days
    is_recurring = False
    if transformed["merchant"]:
        similar = db.find_recent_similar(username, transformed["merchant"], transformed["amount"])
        if similar:
            is_recurring = True

    # LOAD
    db.insert_expense(
        username=username,
        raw_text=raw_text,
        amount=transformed["amount"],
        category=transformed["category"],
        merchant=transformed["merchant"],
        is_recurring=is_recurring,
        created_at=datetime.now().isoformat(),
    )

    note = " (looks recurring — same merchant/amount seen recently)" if is_recurring else ""
    return ETLResult(
        True,
        f"Logged ₹{transformed['amount']} under {transformed['category']}{note}",
        transformed,
    )
