"""
analytics.py
------------
The "flex" layer: category breakdown, month-over-month trend, anomaly
detection, a simple linear-regression forecast for next month's spend,
budget-status scoring, recurring-subscription summary, and CSV/PDF export.

Charts are Plotly (not Matplotlib) — interactive hover tooltips, and they
render natively inside Gradio without a static PNG round-trip, which is
what makes the dashboard feel like a real product instead of a script
that "also makes a chart."

No scikit-learn dependency on purpose — the regression is plain numpy
(polyfit), which keeps the requirements.txt small and is easy to explain
line-by-line in an interview ("I didn't import a black box, here's the math").
"""

import io
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import db

# Shared palette — keeps every chart on-brand with the parchment/ink/gold UI
INK = "#1F2A24"
GOLD = "#B98B2E"
SAGE = "#6B8F71"
TERRACOTTA = "#B5533C"
PARCHMENT = "#FAF6EE"
HAIRLINE = "#E3DCC9"
CATEGORY_COLORS = [GOLD, SAGE, TERRACOTTA, "#7C9CBF", "#A8779A", "#C2A24E", "#5E8B7E", "#9C8265"]


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
    if not budgets:
        return pd.DataFrame(columns=["category", "spent", "budget", "pct", "status"])
    current_month = pd.Timestamp.now().to_period("M").strftime("%Y-%m")
    this_month = df[df["month"] == current_month] if not df.empty else df
    spent = this_month.groupby("category")["amount"].sum().to_dict() if not this_month.empty else {}
    rows = []
    for cat, limit in budgets.items():
        s = spent.get(cat, 0.0)
        pct = (s / limit * 100) if limit > 0 else 0
        if pct >= 100:
            status = "🔴 Over"
        elif pct >= 80:
            status = "🟡 Close"
        else:
            status = "🟢 On track"
        rows.append({"category": cat, "spent": round(s, 2), "budget": limit,
                      "pct": round(pct, 1), "status": status})
    return pd.DataFrame(rows).sort_values("pct", ascending=False)


def recurring_summary(username: str) -> pd.DataFrame:
    """Distinct recurring merchants with their amount and how many times seen —
    effectively a subscriptions view, built from the same flag etl.py already sets."""
    rows = db.get_recurring_expenses(username)
    if not rows:
        return pd.DataFrame(columns=["Merchant", "Amount", "Category", "Times Logged", "Last Seen"])
    df = pd.DataFrame(rows)
    grouped = df.groupby(["merchant", "category"]).agg(
        amount=("amount", "first"),
        times=("id", "count"),
        last_seen=("created_at", "max"),
    ).reset_index().sort_values("last_seen", ascending=False)
    grouped["last_seen"] = pd.to_datetime(grouped["last_seen"]).dt.strftime("%Y-%m-%d")
    grouped.columns = ["Merchant", "Category", "Amount", "Times Logged", "Last Seen"]
    return grouped[["Merchant", "Amount", "Category", "Times Logged", "Last Seen"]]


def export_csv(username: str) -> str:
    """Writes a CSV to disk and returns the path, for Gradio's gr.File download."""
    rows = db.get_expenses(username)
    path = f"data/{username}_expenses.csv"
    if not rows:
        pd.DataFrame(columns=["created_at", "raw_text", "amount", "category", "merchant", "is_recurring"]).to_csv(path, index=False)
        return path
    df = pd.DataFrame(rows)[["created_at", "raw_text", "amount", "category", "merchant", "is_recurring"]]
    df.to_csv(path, index=False)
    return path


def export_pdf(username: str) -> str:
    """Builds a simple monthly statement PDF using reportlab — no heavyweight
    templating engine, just direct canvas drawing, same philosophy as the rest
    of this codebase (no black boxes)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    path = f"data/{username}_statement.pdf"
    rows = db.get_expenses(username)
    cat_totals = category_breakdown(username)
    forecast = forecast_next_month(username)

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, y, "Hearth — Monthly Statement")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"User: {username}    Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Spend by Category")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    if cat_totals.empty:
        c.drawString(20 * mm, y, "No data yet.")
        y -= 6 * mm
    else:
        for _, row in cat_totals.iterrows():
            c.drawString(22 * mm, y, f"{row['category']:<25} Rs. {row['amount']:.2f}")
            y -= 6 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Forecast")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.drawString(22 * mm, y, forecast["message"])
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Recent Entries")
    y -= 7 * mm
    c.setFont("Helvetica", 9)
    for r in rows[:25]:
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm
            c.setFont("Helvetica", 9)
        line = f"{r['created_at'][:10]}  Rs.{r['amount']:.2f}  {r['category']}  {r['merchant'] or ''}"
        c.drawString(22 * mm, y, line[:90])
        y -= 5.5 * mm

    c.save()
    return path


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


def plot_category_breakdown(username: str, dark: bool = False):
    data = category_breakdown(username)
    bg = "#1A1F1C" if dark else PARCHMENT
    fg = PARCHMENT if dark else INK
    fig = go.Figure()
    if data.empty:
        fig.add_annotation(text="No data yet", showarrow=False, font=dict(color=fg, size=14))
    else:
        fig.add_trace(go.Bar(
            x=data["category"], y=data["amount"],
            marker_color=CATEGORY_COLORS[:len(data)],
            text=[f"₹{v:,.0f}" for v in data["amount"]],
            textposition="outside",
            hovertemplate="%{x}<br>₹%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        title="Spend by Category",
        paper_bgcolor=bg, plot_bgcolor=bg,
        font=dict(color=fg, family="Inter, sans-serif"),
        margin=dict(t=50, b=40, l=40, r=20),
        height=360,
        yaxis=dict(gridcolor=HAIRLINE if not dark else "#2E3530", title="₹"),
        xaxis=dict(gridcolor=bg),
    )
    return fig


def plot_monthly_trend(username: str, dark: bool = False):
    data = monthly_trend(username)
    bg = "#1A1F1C" if dark else PARCHMENT
    fg = PARCHMENT if dark else INK
    fig = go.Figure()
    if data.empty:
        fig.add_annotation(text="No data yet", showarrow=False, font=dict(color=fg, size=14))
    else:
        fig.add_trace(go.Scatter(
            x=data["month"], y=data["amount"],
            mode="lines+markers",
            line=dict(color=TERRACOTTA, width=2.5),
            marker=dict(size=8, color=GOLD),
            hovertemplate="%{x}<br>₹%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        title="Monthly Spend Trend",
        paper_bgcolor=bg, plot_bgcolor=bg,
        font=dict(color=fg, family="Inter, sans-serif"),
        margin=dict(t=50, b=40, l=40, r=20),
        height=360,
        yaxis=dict(gridcolor=HAIRLINE if not dark else "#2E3530", title="₹"),
        xaxis=dict(gridcolor=bg),
    )
    return fig