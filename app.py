"""
app.py
------
Gradio UI for the AI expense tracker — "Hearth".

Design language: a ledger, not a wellness app — but a warm one. Where
a mood-tracking companion earns trust with softness, a money app earns
trust with legibility, so the visual identity leans into that: parchment
+ ink + a single brass-gold accent, a serif wordmark, and monospaced
numerals everywhere money is shown (so digits actually line up, the
way they do in a real ledger). A dark "ink" mode keeps the same logic
inverted, for low-light use.

Signature element: a live "ledger preview" row under the input box
that shows exactly how an entry will be parsed — amount, category,
merchant — before it's committed. Built on etl.preview(), which runs
extract + transform without writing to the database.

v2 additions: color-coded budget status, a recurring-subscriptions
view, CSV/PDF export, and a dark-mode toggle persisted per username.
"""

import gradio as gr
import pandas as pd

import db
import etl
import analytics

db.init_db()

# ---------------------------------------------------------------- design tokens
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --ink: #1F2A24;
    --parchment: #FAF6EE;
    --surface: #FFFFFF;
    --gold: #B98B2E;
    --sage: #6B8F71;
    --terracotta: #B5533C;
    --hairline: #E3DCC9;
}

.gradio-container {
    background: var(--parchment) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--ink) !important;
    transition: background 0.25s ease, color 0.25s ease;
}

.dark-mode.gradio-container {
    background: #141815 !important;
    color: #F2EDE2 !important;
}
.dark-mode #tally-header .wordmark { color: #F2EDE2 !important; }
.dark-mode .gr-button-secondary, .dark-mode button.secondary {
    background: #1F2521 !important;
    border-color: #2E3530 !important;
    color: #F2EDE2 !important;
}
.dark-mode table, .dark-mode .dataframe {
    background: #1A1F1C !important;
    color: #F2EDE2 !important;
}
.dark-mode #ledger-preview { border-top-color: #2E3530; }

#tally-header {
    text-align: center;
    padding: 36px 16px 20px 16px;
    position: relative;
}
#tally-header .wordmark {
    font-family: 'Fraunces', serif;
    font-size: 44px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--ink);
    margin: 6px 0 4px 0;
}
#tally-header .tagline {
    font-family: 'Fraunces', serif;
    font-style: italic;
    font-size: 17px;
    color: var(--gold);
    margin-bottom: 14px;
}
#tally-header .rule {
    width: 64px;
    height: 1px;
    background: var(--hairline);
    margin: 0 auto 14px auto;
}

.gr-button-primary, button.primary {
    background: var(--ink) !important;
    border: none !important;
    color: var(--parchment) !important;
    font-weight: 500 !important;
}
.gr-button-secondary, button.secondary {
    background: var(--surface) !important;
    border: 1px solid var(--hairline) !important;
    color: var(--ink) !important;
}

#ledger-preview {
    font-family: 'IBM Plex Mono', monospace;
    border-top: 1px dashed var(--hairline);
    padding-top: 10px;
    margin-top: 6px;
    font-size: 15px;
    color: var(--ink);
    min-height: 24px;
}
#ledger-preview .amount { color: var(--gold); font-weight: 600; }
#ledger-preview .empty { color: #A8A096; font-style: italic; font-family: 'Inter', sans-serif; }

.tab-nav button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
}

table, .dataframe {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}

#theme-toggle {
    max-width: 130px;
}
"""

HEADER_HTML = """
<div id="tally-header">
  <div style="font-size:30px;">🕯️</div>
  <div class="wordmark">HEARTH</div>
  <div class="tagline">every rupee, explained</div>
  <div class="rule"></div>
</div>
"""

CATEGORIES = [
    "Food Delivery", "Groceries", "Travel", "Entertainment",
    "Shopping", "Bills & Utilities", "Food & Dining", "Other",
]


# ---------------------------------------------------------------- callbacks
def live_preview(text: str) -> str:
    if not text or not text.strip():
        return "<div id='ledger-preview'><span class='empty'>start typing — the parse will show up here before you log it</span></div>"
    p = etl.preview(text)
    if p["amount"] <= 0:
        return "<div id='ledger-preview'><span class='empty'>no amount detected yet</span></div>"
    merchant = f" · {p['merchant']}" if p["merchant"] else ""
    return (
        "<div id='ledger-preview'>"
        f"<span class='amount'>₹{p['amount']:.2f}</span> &nbsp; {p['category']}{merchant}"
        "</div>"
    )


def add_expense(username: str, text: str):
    if not username.strip():
        return "Enter a username above to start your ledger.", _history_table(username), text
    if not text.strip():
        return "Type an entry first — e.g. 'Swiggy 350'.", _history_table(username), text

    result = etl.process_expense(username.strip(), text.strip())
    return result.message, _history_table(username), ""


def _history_table(username: str) -> pd.DataFrame:
    cols = ["Date", "Entry", "Amount", "Category", "Merchant", "Recurring"]
    if not username or not username.strip():
        return pd.DataFrame(columns=cols)
    rows = db.get_expenses(username.strip())
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)[["created_at", "raw_text", "amount", "category", "merchant", "is_recurring"]]
    df.columns = cols
    df["Recurring"] = df["Recurring"].map({1: "Yes", 0: "No"})
    return df


def refresh_dashboard(username: str, theme: str):
    dark = theme == "Dark"
    if not username or not username.strip():
        empty_fig = analytics.plot_category_breakdown("", dark=dark)
        return empty_fig, empty_fig, "Enter a username to see insights.", "Add a few entries to unlock a forecast."

    username = username.strip()
    cat_fig = analytics.plot_category_breakdown(username, dark=dark)
    trend_fig = analytics.plot_monthly_trend(username, dark=dark)

    anomalies = analytics.detect_anomalies(username)
    if anomalies:
        lines = [
            f"⚠ {a['date']} — ₹{a['amount']:.0f} on {a['category']}"
            f"{' (' + a['merchant'] + ')' if a['merchant'] else ''}, "
            f"vs your usual ₹{a['average']:.0f}"
            for a in anomalies[-5:]
        ]
        anomaly_text = "\n".join(lines)
    else:
        anomaly_text = "Nothing unusual — every entry is within your normal range."

    forecast = analytics.forecast_next_month(username)
    return cat_fig, trend_fig, anomaly_text, forecast["message"]


def set_budget(username: str, category: str, limit: float):
    if not username.strip() or not category:
        return "Enter a username and pick a category first.", _budget_table(username)
    db.set_budget(username.strip(), category, float(limit))
    return f"Budget set: {category} → ₹{limit:.0f}/month", _budget_table(username)


def _budget_table(username: str) -> pd.DataFrame:
    cols = ["Category", "Spent This Month", "Budget", "% Used", "Status"]
    if not username or not username.strip():
        return pd.DataFrame(columns=cols)
    data = analytics.budget_vs_actual(username.strip())
    if data.empty:
        return pd.DataFrame(columns=cols)
    data = data.rename(columns={
        "category": "Category", "spent": "Spent This Month",
        "budget": "Budget", "pct": "% Used", "status": "Status",
    })
    return data[cols]


def _recurring_table(username: str) -> pd.DataFrame:
    if not username or not username.strip():
        return pd.DataFrame(columns=["Merchant", "Category", "Amount", "Times Logged", "Last Seen"])
    return analytics.recurring_summary(username.strip())


def do_export_csv(username: str):
    if not username or not username.strip():
        gr.Warning("Enter a username first.")
        return None
    return analytics.export_csv(username.strip())


def do_export_pdf(username: str):
    if not username or not username.strip():
        gr.Warning("Enter a username first.")
        return None
    return analytics.export_pdf(username.strip())


def toggle_theme(username: str, current: str):
    new_theme = "Light" if current == "Dark" else "Dark"
    if username and username.strip():
        db.set_preference(username.strip(), "theme", new_theme)
    return new_theme, gr.update(value=f"{'☀️ Light' if new_theme == 'Dark' else '🌙 Dark'} mode")


def apply_theme_class(theme: str):
    return gr.update(elem_classes=["dark-mode"] if theme == "Dark" else [])


def load_user_theme(username: str):
    if username and username.strip():
        saved = db.get_preference(username.strip(), "theme", "Light")
        return saved
    return "Light"


# ---------------------------------------------------------------- layout
with gr.Blocks(title="Hearth — every rupee, explained", css=CUSTOM_CSS) as demo:
    theme_state = gr.State("Light")

    with gr.Row():
        with gr.Column(scale=5):
            gr.HTML(HEADER_HTML)
        with gr.Column(scale=1, min_width=130):
            theme_btn = gr.Button("🌙 Dark mode", elem_id="theme-toggle", size="sm")

    username_box = gr.Textbox(label="", placeholder="✦ what's your name?", container=False)

    with gr.Tabs():
        with gr.Tab("📝 Log a Spend"):
            entry_box = gr.Textbox(
                label="What did you spend on?",
                placeholder="e.g. 'Swiggy 350' or 'movie with friends 800 split 4 ways'",
            )
            preview_html = gr.HTML(live_preview(""))
            submit_btn = gr.Button("Add to ledger", variant="primary")
            status_box = gr.Textbox(label="", interactive=False, container=False)
            history_table = gr.Dataframe(label="Recent entries", interactive=False)

            entry_box.change(live_preview, inputs=entry_box, outputs=preview_html)
            submit_btn.click(
                add_expense,
                inputs=[username_box, entry_box],
                outputs=[status_box, history_table, entry_box],
            ).then(live_preview, inputs=entry_box, outputs=preview_html)
            username_box.change(_history_table, inputs=username_box, outputs=history_table)

        with gr.Tab("📊 Insights"):
            refresh_btn = gr.Button("Refresh")
            with gr.Row():
                cat_plot = gr.Plot(label="Spend by category")
                trend_plot = gr.Plot(label="Monthly trend")
            anomaly_box = gr.Textbox(label="Anomalies", interactive=False, lines=4)
            forecast_box = gr.Textbox(label="Next month, projected", interactive=False)

            refresh_btn.click(
                refresh_dashboard,
                inputs=[username_box, theme_state],
                outputs=[cat_plot, trend_plot, anomaly_box, forecast_box],
            )

        with gr.Tab("🎯 Budgets"):
            with gr.Row():
                category_dropdown = gr.Dropdown(choices=CATEGORIES, label="Category")
                limit_input = gr.Number(label="Monthly limit (₹)")
            budget_btn = gr.Button("Set budget")
            budget_status = gr.Textbox(label="", interactive=False, container=False)
            budget_table = gr.Dataframe(
                label="Budget vs. actual — this month (🟢 on track · 🟡 80%+ · 🔴 over)",
                interactive=False,
            )

            budget_btn.click(
                set_budget,
                inputs=[username_box, category_dropdown, limit_input],
                outputs=[budget_status, budget_table],
            )

        with gr.Tab("🔁 Recurring"):
            gr.Markdown(
                "Merchants Hearth has spotted on a repeat schedule — same name, "
                "same amount, within ~35 days. Good place to check for subscriptions "
                "you forgot about."
            )
            recurring_refresh_btn = gr.Button("Refresh")
            recurring_table = gr.Dataframe(label="Recurring charges", interactive=False)
            recurring_refresh_btn.click(_recurring_table, inputs=username_box, outputs=recurring_table)
            username_box.change(_recurring_table, inputs=username_box, outputs=recurring_table)

        with gr.Tab("⬇️ Export"):
            gr.Markdown("Download your ledger as a spreadsheet, or a formatted monthly statement.")
            with gr.Row():
                csv_btn = gr.Button("Export CSV")
                pdf_btn = gr.Button("Export PDF statement")
            export_file = gr.File(label="Your download", interactive=False)

            csv_btn.click(do_export_csv, inputs=username_box, outputs=export_file)
            pdf_btn.click(do_export_pdf, inputs=username_box, outputs=export_file)

    # theme wiring
    theme_btn.click(
        toggle_theme, inputs=[username_box, theme_state], outputs=[theme_state, theme_btn]
    ).then(apply_theme_class, inputs=theme_state, outputs=demo)

    username_box.change(load_user_theme, inputs=username_box, outputs=theme_state).then(
        apply_theme_class, inputs=theme_state, outputs=demo
    ).then(
        lambda t: gr.update(value=f"{'☀️ Light' if t == 'Dark' else '🌙 Dark'} mode"),
        inputs=theme_state, outputs=theme_btn,
    )

if __name__ == "__main__":
    demo.launch()