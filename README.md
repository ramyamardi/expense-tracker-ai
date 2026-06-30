---
title: Hearth
emoji: 🕯️
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: "5.35.0"
app_file: app.py
pinned: false
---

# 🕯️ Hearth — AI-Powered Expense Tracker

Hearth is an AI-powered expense tracking application that lets users record expenses in natural language. It uses **Groq's Llama 3.3 model** to extract structured information, processes it through a deterministic ETL pipeline, stores it in SQLite, and provides budgeting, analytics, anomaly detection, and spending forecasts.

### 🔗 Live Demo
https://huggingface.co/spaces/ramyaamardi/hearth-expense-tracker

### 💻 GitHub Repository
https://github.com/ramyamardi/expense-tracker-ai

---

## Features

- 🤖 AI-powered natural language expense parsing (Groq Llama 3.3)
- 🔄 Regex fallback parser when no API key is available
- 🧮 Automatic bill splitting (e.g., "₹2400 split among 3 people")
- 💾 SQLite database for persistent storage
- 📊 Expense dashboard and category-wise analytics
- 📈 Monthly spending forecast using NumPy linear regression
- 🚨 Anomaly detection for unusually large expenses
- 🎯 Budget tracking
- 🌐 Live deployment on Hugging Face Spaces

---

## Example Inputs

```text
Swiggy 350

Dinner at BBQ Nation 2400 split among 3 people

Uber to airport 850

Movie with friends 900 split 3

Paid electricity bill 1800
```

---

## Architecture

```
Natural Language Input
          │
          ▼
  Groq Llama 3.3 Parser
          │
          ▼
 Extract Structured Data
(amount, merchant, category, split_count)
          │
          ▼
     ETL Pipeline
 • Validation
 • Normalization
 • Split Calculation
 • Duplicate Checks
          │
          ▼
      SQLite Database
          │
          ▼
 Dashboard • Budgets
 Analytics • Forecasts
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python |
| UI | Gradio |
| AI | Groq Llama 3.3 70B |
| Database | SQLite |
| Data Processing | Pandas, NumPy |
| HTTP | requests |
| Deployment | Hugging Face Spaces |
| Version Control | Git & GitHub |

---

## Project Structure

```
expense-tracker-ai/
│
├── app.py               # Gradio application
├── analytics.py         # Charts, forecasting, anomaly detection
├── db.py                # SQLite database layer
├── etl.py               # ETL pipeline
├── llm_parser.py        # Groq + Regex parser
├── test_pipeline.py     # Pipeline tests
├── requirements.txt
├── README.md
├── .env.example
├── data/
└── web-demo/
```

---

## Running Locally

```bash
git clone https://github.com/ramyamardi/expense-tracker-ai.git

cd expense-tracker-ai

pip install -r requirements.txt
```

Create a `.env` file:

```text
GROQ_API_KEY=your_api_key_here
```

Run the application:

```bash
python app.py
```

---

## How It Works

1. User enters an expense in plain English.
2. Groq extracts:
   - Amount
   - Merchant
   - Category
   - Split count
3. Python calculates the user's share when expenses are split.
4. The ETL pipeline validates and normalizes the data.
5. The transaction is stored in SQLite.
6. Analytics, budgets, anomaly detection, and forecasts update automatically.

---

## Future Improvements

- User authentication
- Receipt OCR
- CSV/PDF export
- Multi-currency support
- Recurring subscription reminders
- Interactive charts

---

## Why This Project?

Many AI demos simply send text to an LLM and display the response.

Hearth demonstrates how an LLM can be integrated into a real data engineering workflow. The model is responsible only for extracting structured information, while Python handles validation, business logic, storage, analytics, and forecasting. This separation makes the system easier to test, explain, and maintain.

---

Built by **Ramya shree** as part of a Data Engineering portfolio.