"""
Toy RAG-style answer bot — the "app under eval".
Swap this out with your real LLM app; the eval runner calls run(question) -> answer.
"""

import anthropic

SYSTEM_PROMPT = """You are a helpful assistant that answers questions concisely and accurately.
When you don't know something, say so clearly rather than guessing.
Always cite if a claim is uncertain."""

client = anthropic.Anthropic()


def run(question: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text
