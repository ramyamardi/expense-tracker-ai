"""
llm_parser.py
-------------
Turns free-text expense entries into structured data:
    "Swiggy 350"                       -> {amount: 350, category: "Food Delivery", merchant: "Swiggy"}
    "movie with friends 800 split 4"   -> {amount: 200, category: "Entertainment", merchant: None}

Design decision: raw HTTP via `requests` to the Groq API instead of an SDK.
Same reasoning as any engineer who wants to actually understand the contract:
no library hides the request/response shape. You can see exactly what JSON
goes out and what comes back.

A REGEX FALLBACK is included so the whole app is fully demoable and testable
without an API key. This matters for a portfolio project — anyone cloning your
repo should be able to run it in under a minute. If GROQ_API_KEY is not set,
the fallback parser handles common patterns directly.
"""

import os
import re
import json
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

CATEGORY_KEYWORDS = {
    "Food Delivery": ["swiggy", "zomato", "uber eats"],
    "Groceries": ["bigbasket", "blinkit", "zepto", "grocery", "groceries"],
    "Travel": ["uber", "ola", "rapido", "flight", "train", "irctc"],
    "Entertainment": ["movie", "netflix", "spotify", "prime", "concert"],
    "Shopping": ["amazon", "myntra", "flipkart", "shopping"],
    "Bills & Utilities": ["electricity", "wifi", "recharge", "rent", "bill"],
    "Food & Dining": ["lunch", "dinner", "breakfast", "restaurant", "cafe", "coffee"],
}

SYSTEM_PROMPT = """You are an expense-parsing engine. Given a free-text expense entry,
extract structured data. Always account for bill-splitting language ("split 4 ways" means
divide the total amount by 4 to get the user's actual share).

Return ONLY valid JSON, no markdown, no preamble, in this exact shape:
{"amount": <float>, "category": "<one of: Food Delivery, Groceries, Travel, Entertainment,
Shopping, Bills & Utilities, Food & Dining, Other>", "merchant": "<string or null>"}
"""


def _fallback_parse(text: str) -> dict:
    """Regex-based parser used when no API key is configured, or as a safety net
    if the API call fails. Not as smart as the LLM, but keeps the app functional."""
    amounts = re.findall(r"\d+(?:\.\d+)?", text)
    amount = float(amounts[0]) if amounts else 0.0

    split_match = re.search(r"split\s*(\d+)", text, re.IGNORECASE)
    if split_match:
        n = int(split_match.group(1))
        if n > 0:
            amount = amount / n

    lower = text.lower()
    category = "Other"
    merchant = None
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                category = cat
                merchant = kw.title()
                break
        if category != "Other":
            break

    return {"amount": round(amount, 2), "category": category, "merchant": merchant}


def parse_expense(text: str) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return _fallback_parse(text)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 200,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(content)
        return {
            "amount": float(parsed.get("amount", 0)),
            "category": parsed.get("category", "Other"),
            "merchant": parsed.get("merchant"),
        }
    except (requests.RequestException, KeyError, json.JSONDecodeError, ValueError):
        # API failed or returned something unparseable — fall back rather than crash.
        return _fallback_parse(text)