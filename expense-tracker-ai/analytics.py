"""
analytics.py
------------
The "flex" layer: category breakdown, month-over-month trend, anomaly
detection, and a simple linear-regression forecast for next month's spend.

No scikit-learn dependency on purpose — the regression is plain numpy
(polyfit), which keeps the requirements.txt small and is easy to explain
line-by-line in an interview ("I didn't import a black box, here's the math").
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import db


def _to_dataframe(username: str) -> pd.DataFrame:
    rows = db.get_expenses(username)
    if not rows:
        return pd.DataFrame(columns=["id", "amount", "category", "merchant", "created_at"])
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["month"] = df["created_at"].dt.to_period("M").astype(str)
    return df


def category_breakdown(username: str) -> pd.DataFrame:
    df = _to_dataframe(username)
    if df.empty:
        return pd.DataFrame(columns=["category", "amount"])
    return df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)


def monthly_trend(username: str) -> pd.DataFrame:
    df = _to_dataframe(username)
    if df.empty:
        return pd.DataFrame(columns=["month", "amount"])
    return df.groupby("month")["amount"].sum().reset_index().sort_values("month")


def budget_vs_actual(username: str) -> pd.DataFrame:
    df = _to_dataframe(username)
    budgets = db.get_budgets(username)
    if df.empty or not budgets:
        return pd.DataFrame(columns=["category", "spent", "budget"])
    current_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
    this_month = df[df["month"] == current_month]
    spent = this_month.groupby("category")["amount"].sum().to_dict()
    rows = [{"category": cat, "spent": spent.get(cat, 0.0), "budget": limit}
            for cat, limit in budgets.items()]
    return pd.DataFrame(rows)


def detect_anomalies(username: str, multiplier: float = 3.0) -> list[dict]:
    """Flags any transaction that's `multiplier`x the user's historical average
    for that category. Needs at least 3 prior transactions in that category to
    have a meaningful baseline."""
    df = _to_dataframe(username)
    if df.empty:
        return []

    anomalies = []
    for category, group in df.groupby("category"):
        if len(group) < 4:
            continue
        group_sorted = group.sort_values("created_at")
        for i in range(3, len(group_sorted)):
            history = group_sorted.iloc[:i]
            current = group_sorted.iloc[i]
            avg = history["amount"].mean()
            if avg > 0 and current["amount"] >= multiplier * avg:
                anomalies.append({
                    "category": category,
                    "amount": current["amount"],
                    "average": round(avg, 2),
                    "date": current["created_at"].strftime("%Y-%m-%d"),
                    "merchant": current["merchant"],
                })
    return anomalies


def forecast_next_month(username: str) -> dict:
    """Simple linear regression (numpy polyfit, degree 1) over monthly totals
    to project next month's spend. Needs at least 2 months of history."""
    trend = monthly_trend(username)
    if len(trend) < 2:
        return {"forecast": None, "message": "Need at least 2 months of data to forecast."}

    x = np.arange(len(trend))
    y = trend["amount"].values
    slope, intercept = np.polyfit(x, y, 1)
    next_x = len(trend)
    forecast = slope * next_x + intercept
    trend_dir = "increasing" if slope > 0 else "decreasing"
    return {
        "forecast": round(max(forecast, 0), 2),
        "trend_direction": trend_dir,
        "message": f"Projected next month: ₹{round(max(forecast, 0), 2)} (spend is {trend_dir})",
    }


def plot_category_breakdown(username: str):
    data = category_breakdown(username)
    fig, ax = plt.subplots(figsize=(6, 4))
    if data.empty:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center")
    else:
        ax.bar(data["category"], data["amount"], color="#4C72B0")
        ax.set_ylabel("Total Spend (₹)")
        ax.set_title("Spend by Category")
        plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    return fig


def plot_monthly_trend(username: str):
    data = monthly_trend(username)
    fig, ax = plt.subplots(figsize=(6, 4))
    if data.empty:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center")
    else:
        ax.plot(data["month"], data["amount"], marker="o", color="#DD8452")
        ax.set_ylabel("Total Spend (₹)")
        ax.set_title("Monthly Spend Trend")
        plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    return fig
