"""
llm_parser.py
-------------
Parses free-text expense entries using Groq Llama 3.3.
Falls back to regex if no API key exists or the API fails.
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
    "Food & Dining": ["lunch", "dinner", "breakfast", "restaurant", "cafe", "coffee", "pizza", "bbq"],
}

SYSTEM_PROMPT = """
You are an expense parser.

Extract:
- amount (user's actual share if the bill is split)
- category
- merchant

Recognize natural language such as:
- split equally among 3 people
- divided by 4
- shared with 2 friends
- split 5 ways

Return ONLY valid JSON.

Example:

{
  "amount": 800,
  "category": "Food & Dining",
  "merchant": "BBQ Nation"
}
"""


def _fallback_parse(text):
    print(">>> USING REGEX FALLBACK")

    amounts = re.findall(r"\d+(?:\.\d+)?", text)
    amount = float(amounts[0]) if amounts else 0

    split = re.search(r"split\s*(\d+)", text, re.IGNORECASE)
    if split:
        n = int(split.group(1))
        if n > 0:
            amount /= n

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

    return {
        "amount": round(amount, 2),
        "category": category,
        "merchant": merchant,
    }


def parse_expense(text):

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print(">>> NO GROQ API KEY FOUND")
        return _fallback_parse(text)

    print(">>> USING GROQ")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        "temperature": 0,
        "max_tokens": 200,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:

        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=20,
        )

        print("Status Code:", response.status_code)
        print("Response:", response.text)

        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]

        content = (
            content.replace("```json", "")
            .replace("```", "")
            .strip()
        )

        parsed = json.loads(content)

        print(">>> GROQ SUCCESS")

        return {
            "amount": float(parsed.get("amount", 0)),
            "category": parsed.get("category", "Other"),
            "merchant": parsed.get("merchant"),
        }

    except Exception as e:

        print("========== GROQ ERROR ==========")
        print(e)
        print("================================")

        return _fallback_parse(text)