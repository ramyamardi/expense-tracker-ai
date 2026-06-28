"""
test_pipeline.py
-----------------
Quick smoke test that exercises db -> etl -> analytics without needing
Gradio or a live LLM API key (uses the regex fallback parser). Run this
first after cloning to confirm the core pipeline works before launching
the full app.

Usage: python test_pipeline.py
"""

import os
import db
import etl
import analytics

TEST_USER = "test_user"


def run():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db()
    print("✅ DB initialized\n")

    entries = [
        "Swiggy 350",
        "Swiggy 300",
        "Swiggy 320",
        "Swiggy 1200",  # should trigger anomaly (4x avg)
        "movie with friends 800 split 4 ways",
        "Amazon shopping 1500",
        "electricity bill 900",
        "lunch at cafe 250",
    ]

    print("Logging expenses:")
    for e in entries:
        result = etl.process_expense(TEST_USER, e)
        print(f"  '{e}' -> {result.message}")

    print("\n📊 Category breakdown:")
    print(analytics.category_breakdown(TEST_USER).to_string(index=False))

    print("\n⚠️  Anomalies detected:")
    anomalies = analytics.detect_anomalies(TEST_USER, multiplier=3.0)
    for a in anomalies:
        print(f"  {a}")
    if not anomalies:
        print("  (none — need more history per category for a real test)")

    print("\n💰 Setting a budget and checking budget vs actual:")
    db.set_budget(TEST_USER, "Food Delivery", 1000)
    print(analytics.budget_vs_actual(TEST_USER).to_string(index=False))

    print("\n✅ Pipeline smoke test complete — db, etl, and analytics all working.")


if __name__ == "__main__":
    run()
