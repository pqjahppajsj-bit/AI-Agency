import os
import requests

OPENAI_URL = "https://api.openai.com/v1/responses"

def ask_ai(message):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        "input": [
            {
                "role": "system",
                "content": (
                    "You are AI Agency's business assistant. "
                    "Help businesses with customers, leads, orders, "
                    "sales, workflows and practical business operations. "
                    "Be concise, professional and useful."
                ),
            },
            {
                "role": "user",
                "content": message,
            },
        ],
    }

    response = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )

    response.raise_for_status()
    data = response.json()

    text = data.get("output_text")

    if text:
        return text

    # Safe fallback for response structures where output_text
    # is not directly present.
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")

    return "AI response was empty."
