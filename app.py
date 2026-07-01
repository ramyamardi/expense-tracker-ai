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
# Palette moved away from parchment/beige entirely. "Charcoal" (default) and
# "Midnight" (toggle target) are both dark themes now — the toggle switches
# between a warm deep-charcoal and a near-black, rather than light vs. dark.
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --ink: #ECE7DA;
    --bg: #1B1F1C;
    --surface: #232823;
    --surface-hover: #2B312B;
    --gold: #D8A94E;
    --gold-soft: #6B5A30;
    --sage: #86B392;
    --terracotta: #D9866A;
    --hairline: #343B35;
    --muted: #93998F;
    --shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}

.gradio-container {
    background: var(--bg) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--ink) !important;
    transition: background 0.25s ease, color 0.25s ease;
}

/* "Midnight" mode — the deeper, secondary dark theme reached via toggle */
.dark-mode.gradio-container {
    --bg: #0D0F0E;
    --surface: #161917;
    --surface-hover: #1E2220;
    --hairline: #262B27;
    background: var(--bg) !important;
    color: var(--ink) !important;
}
.dark-mode #tally-header .wordmark { color: var(--ink) !important; }
.dark-mode table, .dark-mode .dataframe {
    background: var(--surface) !important;
    color: var(--ink) !important;
}
.dark-mode #ledger-preview { border-top-color: var(--hairline); }

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

/* ---- buttons: rounded, layered, icon-friendly, with hover lift ---- */
button.primary, .gr-button-primary {
    background: linear-gradient(180deg, var(--gold) 0%, #C4903F 100%) !important;
    border: none !important;
    color: #1B1500 !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow);
    padding: 10px 18px !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
}
button.primary:hover, .gr-button-primary:hover {
    transform: translateY(-1px);
    filter: brightness(1.06);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
}
button.primary:active, .gr-button-primary:active {
    transform: translateY(0);
    filter: brightness(0.97);
}

button.secondary, .gr-button-secondary {
    background: var(--surface) !important;
    border: 1px solid var(--hairline) !important;
    color: var(--ink) !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    box-shadow: var(--shadow);
    padding: 10px 18px !important;
    transition: transform 0.12s ease, background 0.12s ease, border-color 0.12s ease;
}
button.secondary:hover, .gr-button-secondary:hover {
    background: var(--surface-hover) !important;
    border-color: var(--gold) !important;
    transform: translateY(-1px);
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
#ledger-preview .empty { color: var(--muted); font-style: italic; font-family: 'Inter', sans-serif; }

/* ---- tabs: pill-style, icon-forward, clear active state ---- */
.tab-nav {
    gap: 4px !important;
    border-bottom: 1px solid var(--hairline) !important;
}
.tab-nav button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 9px 16px !important;
    transition: background 0.15s ease, color 0.15s ease;
}
.tab-nav button:hover {
    background: var(--surface-hover) !important;
    color: var(--ink) !important;
}
.tab-nav button.selected {
    background: var(--surface) !important;
    color: var(--gold) !important;
    box-shadow: inset 0 -2px 0 var(--gold);
}

table, .dataframe {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
    border-radius: 8px !important;
    overflow: hidden;
}

#theme-toggle {
    max-width: 150px;
}

/* form surfaces get a subtle card treatment so they read as "ledger paper"
   rather than flat background */
.gr-box, .form, .block {
    border-radius: 12px !important;
}
input, textarea, .gr-box {
    background: var(--surface) !important;
    border-color: var(--hairline) !important;
    color: var(--ink) !important;
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
    return new_theme, gr.update(value=f"{'🌗 Charcoal' if new_theme == 'Dark' else '🌑 Midnight'} mode")


def load_user_theme(username: str):
    if username and username.strip():
        saved = db.get_preference(username.strip(), "theme", "Light")
        return saved
    return "Light"


# The previous approach tried to flip the theme by sending
# `gr.update(elem_classes=...)` to the top-level `demo` Blocks object as an
# event *output*. Blocks isn't a regular component, so it silently never
# applied the class — that's why neither toggle direction actually changed
# anything. Toggling a CSS class on the root container is a DOM operation,
# so it's done with a tiny bit of client-side JS instead, fired via the `js=`
# argument on `.then(...)`. This is the reliable way to do it in Gradio.
TOGGLE_THEME_JS = """(theme) => {
    const root = document.querySelector('.gradio-container');
    if (root) root.classList.toggle('dark-mode', theme === 'Dark');
    return theme;
}"""


# ---------------------------------------------------------------- layout
with gr.Blocks(title="Hearth — every rupee, explained", css=CUSTOM_CSS) as demo:
    theme_state = gr.State("Light")

    with gr.Row():
        with gr.Column(scale=5):
            gr.HTML(HEADER_HTML)
        with gr.Column(scale=1, min_width=130):
            theme_btn = gr.Button("🌑 Midnight mode", elem_id="theme-toggle", size="sm")

    username_box = gr.Textbox(label="", placeholder="✦ what's your name?", container=False)

    with gr.Tabs():
        with gr.Tab("📝 Log a Spend"):
            entry_box = gr.Textbox(
                label="What did you spend on?",
                placeholder="e.g. 'Swiggy 350' or 'movie with friends 800 split 4 ways'",
            )
            preview_html = gr.HTML(live_preview(""))
            submit_btn = gr.Button("➕ Add to Ledger", variant="primary")
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
            refresh_btn = gr.Button("🔄 Refresh Insights", variant="secondary")
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
            budget_btn = gr.Button("🎯 Set Budget", variant="primary")
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
            recurring_refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
            recurring_table = gr.Dataframe(label="Recurring charges", interactive=False)
            recurring_refresh_btn.click(_recurring_table, inputs=username_box, outputs=recurring_table)
            username_box.change(_recurring_table, inputs=username_box, outputs=recurring_table)

        with gr.Tab("⬇️ Export"):
            gr.Markdown("Download your ledger as a spreadsheet, or a formatted monthly statement.")
            with gr.Row():
                csv_btn = gr.Button("📊 Export CSV", variant="secondary")
                pdf_btn = gr.Button("📄 Export PDF Statement", variant="secondary")
            export_file = gr.File(label="Your download", interactive=False)

            csv_btn.click(do_export_csv, inputs=username_box, outputs=export_file)
            pdf_btn.click(do_export_pdf, inputs=username_box, outputs=export_file)

    # theme wiring — Python updates the state + persists the preference,
    # then the `js=` callback actually flips the CSS class on the page.
    theme_btn.click(
        toggle_theme, inputs=[username_box, theme_state], outputs=[theme_state, theme_btn]
    ).then(None, inputs=theme_state, outputs=None, js=TOGGLE_THEME_JS)

    username_box.change(load_user_theme, inputs=username_box, outputs=theme_state).then(
        None, inputs=theme_state, outputs=None, js=TOGGLE_THEME_JS
    ).then(
        lambda t: gr.update(value=f"{'🌗 Charcoal' if t == 'Dark' else '🌑 Midnight'} mode"),
        inputs=theme_state, outputs=theme_btn,
    )

    # Apply the right class immediately on first paint too (covers the case
    # where a returning user's saved theme is "Dark" but the page loads
    # before any component-level event fires).
    demo.load(None, inputs=theme_state, outputs=None, js=TOGGLE_THEME_JS)

if __name__ == "__main__":
    demo.launch()