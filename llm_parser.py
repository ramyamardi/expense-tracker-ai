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
    "Food & Dining": [
        "lunch",
        "dinner",
        "breakfast",
        "restaurant",
        "cafe",
        "coffee",
        "pizza",
        "bbq",
    ],
}

SYSTEM_PROMPT = """
You are an expense parsing engine.

Extract expense information.

Return ONLY valid JSON.

Format:

{
  "amount": <total_amount>,
  "split_count": <number_of_people>,
  "category": "<Food Delivery | Groceries | Travel | Entertainment | Shopping | Bills & Utilities | Food & Dining | Other>",
  "merchant": "<merchant or null>"
}

Rules:

- amount MUST be the TOTAL bill.
- split_count MUST be the total number of people.
- If no split exists, split_count = 1.
- Never divide the amount yourself.

Examples:

Input:
Swiggy 350

Output:
{
  "amount":350,
  "split_count":1,
  "category":"Food Delivery",
  "merchant":"Swiggy"
}

Input:
Dinner at BBQ Nation 2400 split among 3 people

Output:
{
  "amount":2400,
  "split_count":3,
  "category":"Food & Dining",
  "merchant":"BBQ Nation"
}

Input:
Pizza 720 shared equally among 3 people

Output:
{
  "amount":720,
  "split_count":3,
  "category":"Food & Dining",
  "merchant":"Pizza"
}
"""


def _fallback_parse(text):
    print(">>> USING REGEX FALLBACK")

    amounts = re.findall(r"\d+(?:\.\d+)?", text)
    amount = float(amounts[0]) if amounts else 0.0

    split = 1

    split_match = re.search(
        r"(?:split(?:\s+equally)?(?:\s+among)?|divided\s+by)\s*(\d+)",
        text,
        re.IGNORECASE,
    )

    if split_match:
        split = int(split_match.group(1))

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
        "amount": round(amount / split, 2),
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 300,
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

        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]

        content = (
            content.replace("```json", "")
            .replace("```", "")
            .strip()
        )

        print("LLM Output:", content)

        parsed = json.loads(content)

        total = float(parsed.get("amount", 0))
        split_count = int(parsed.get("split_count", 1))

        if split_count < 1:
            split_count = 1

        print(">>> GROQ SUCCESS")

        return {
            "amount": round(total / split_count, 2),
            "category": parsed.get("category", "Other"),
            "merchant": parsed.get("merchant"),
        }

    except Exception as e:

        print("========== GROQ ERROR ==========")
        print(e)
        print("================================")

        return _fallback_parse(text)