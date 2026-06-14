"""
Toy RAG-style answer bot — the "app under eval".
Swap this out with your real LLM app; the eval runner calls run(question) -> answer.
"""

import os

from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are a helpful assistant that answers questions concisely and accurately.
When you don't know something, say so clearly rather than guessing.
Always cite if a claim is uncertain."""

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def run(question: str) -> str:
    response = _client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text
