# 🕯️ Hearth — an AI Expense Tracker

Type your expenses in plain English — *"Swiggy 350"*, *"movie with friends 800 split 4 ways"* — and the app extracts, validates, categorizes, and tracks them. Includes anomaly detection, budget tracking, and a next-month spend forecast.

🔗 **Live demo:** _(add your Hugging Face Spaces link here after deploying)_

---

## Why this exists

Most "AI expense tracker" tutorials are a thin LLM wrapper around a text field. This one is built around an actual **ETL pipeline** — the LLM only does extraction; everything after that (validation, normalization, dedup, recurring-subscription detection, anomaly flagging) is deterministic data-engineering logic that I can fully explain line by line.

## Architecture — and why each decision was made

| Layer | Choice | Why |
|---|---|---|
| **Parsing** | LLM (Llama 3.3 70B via Groq) with a **regex fallback** | The app works fully offline/without an API key for anyone cloning the repo — no one has to hunt for a key just to try it. |
| **HTTP** | Raw `requests` calls, no SDK | I can show exactly what JSON goes out and what comes back — understanding the contract, not hiding behind a library. |
| **Pipeline** | Explicit Extract → Transform → Load functions (`etl.py`) | Validation, category normalization, and recurring-charge detection are pipeline logic, not LLM guesswork — more reliable and fully testable. |
| **Storage** | SQLite, rows scoped by `username` | Gradio has no built-in auth. Instead of separate files per user, every table is scoped by username — same simplicity, slightly more "real" data model than CSV-per-user. |
| **Anomaly detection** | Flag any transaction ≥3x the rolling category average | Catches one-off bad-purchase days without needing a model — cheap, explainable, and works with very little data. |
| **Forecasting** | `numpy.polyfit` (degree-1 linear regression) on monthly totals | No scikit-learn dependency — the math is 3 lines and easy to defend in an interview. |
| **Design** | Parchment + ink + brass-gold, serif wordmark, monospaced numerals (custom CSS, no template UI kit) | A money app earns trust through legibility, not softness — numbers actually line up like a real ledger. |
| **Live preview** | Shows the parsed {amount, category, merchant} *before* you commit an entry | Builds trust in the parser — you see exactly what the pipeline extracted, not a black box.

## Project structure

```
expense-tracker-ai/
├── app.py            # Gradio UI (3 tabs: Add Expense, Dashboard, Budgets)
├── llm_parser.py      # LLM extraction + regex fallback
├── etl.py             # Extract -> Transform -> Load pipeline
├── analytics.py        # Category breakdown, trends, anomalies, forecast
├── db.py              # SQLite data layer
├── test_pipeline.py    # Smoke test (no API key or Gradio needed)
├── requirements.txt
└── .env.example
```

## Running it locally

```bash
git clone https://github.com/<your-username>/expense-tracker-ai.git
cd expense-tracker-ai
pip install -r requirements.txt

# Optional: add a free Groq API key for smarter parsing (https://console.groq.com)
cp .env.example .env   # then edit .env and add your key

# Quick sanity check — works even with no API key, no Gradio:
python test_pipeline.py

# Launch the full app
python app.py
```

Then open the local URL Gradio prints (usually `http://127.0.0.1:7860`).

## Deploying it live (Hugging Face Spaces)

1. Create a free account at [huggingface.co](https://huggingface.co)
2. New Space → SDK: **Gradio** → push this repo to it (or link your GitHub repo)
3. In Space **Settings → Variables and secrets**, add `GROQ_API_KEY` as a secret
4. Space builds automatically from `requirements.txt` and `app.py`

## What I'd build next

- Real auth (so usernames can't be spoofed)
- Receipt photo upload + OCR instead of typing
- Recurring-subscription auto-cancel reminders
- Export to CSV / monthly PDF statement

---

Built as part of my data engineering portfolio — every line typed by hand, every architecture decision deliberate.
