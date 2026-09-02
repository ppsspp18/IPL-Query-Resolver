"""Pluggable LLM backend for the Text-to-SQL pipeline.

Talks to any OpenAI-compatible chat-completions API. Defaults to **Groq**
with the **openai/gpt-oss-120b** model. When no API key is configured the
pipeline transparently falls back to the schema-aware rule-based engine in
`text2sql.py`.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
_MAX_RETRIES = 3


def _api_key() -> Optional[str]:
    return os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")


def is_configured() -> bool:
    return bool(_api_key())


def get_config() -> dict:
    return {
        "base_url": os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0")),
        "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
    }


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    api_key: Optional[str] = None,
    max_tokens: int = 1024,
) -> str:
    """Call the configured LLM and return the assistant text.

    Raises:
        RuntimeError: if the call fails or the API is not configured.
    """
    if not api_key:
        api_key = _api_key()
    if not api_key:
        raise RuntimeError(
            "LLM not configured: set GROQ_API_KEY (see .env.example)."
        )

    cfg = get_config()
    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    last_err = None
    with httpx.Client(timeout=cfg["timeout"]) as client:
        for attempt in range(_MAX_RETRIES):
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                # Transient rate-limit / server error: back off and retry.
                time.sleep(2 ** attempt + 1)
                last_err = f"LLM error {resp.status_code}"
                continue
            raise RuntimeError(f"LLM error {resp.status_code}: {resp.text[:300]}")
    raise RuntimeError(last_err or "LLM request failed")
