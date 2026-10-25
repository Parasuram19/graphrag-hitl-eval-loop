import json
from typing import Any, Dict

from openai import OpenAI
from rich.console import Console

from app.config import settings

console = Console()


def get_llm_client() -> OpenAI:
    """Create and return the OpenRouter client."""
    if not settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )


def extract_first_json_object(s: str) -> str:
    """
    Extracts the first valid JSON object from a string.
    Handles cases where the LLM outputs multiple JSONs or includes markdown/text.
    """
    start = s.find("{")
    if start == -1:
        return s

    decoder = json.JSONDecoder()
    try:
        _, end_index = decoder.raw_decode(s, start)
        return s[start:end_index]
    except json.JSONDecodeError:
        end = s.rfind("}")
        if end != -1:
            return s[start : end + 1]
        return s


def call_llm(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """
    Calls OpenRouter. Auto-unwraps single-key root dicts to handle LLM quirks.
    Returns a parsed dictionary.
    """
    client = get_llm_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or ""

    clean_content = extract_first_json_object(content)

    try:
        parsed = json.loads(clean_content)
    except json.JSONDecodeError as e:
        console.print(f"\n[red]❌ JSON Parse Error: {e}[/red]")
        console.print(f"[dim]Raw LLM Output (first 500 chars): {content[:500]}...[/dim]\n")
        raise

    if isinstance(parsed, dict) and len(parsed) == 1:
        inner_value = next(iter(parsed.values()))
        if isinstance(inner_value, dict):
            return inner_value

    return parsed