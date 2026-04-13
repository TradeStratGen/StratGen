"""
llm/client.py — Ollama + OpenRouter clients
Key change: temperature lowered to 0.1 for more deterministic JSON output
"""

import os, json, time, re, requests
from typing import Optional

OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b-instruct"

OPENROUTER_URL    = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = {
    "gemma":   "google/gemma-4-31b-it:free",
    "qwen":    "qwen/qwen3-next-80b-a3b-instruct:free",
    "minimax": "minimax/minimax-m2.5:free",
}


class OllamaClient:
    """
    Local LLM via Ollama. Temperature=0.1 for consistent JSON output.
    Run: ollama serve  (in a separate terminal)
    """
    def __init__(self, model=OLLAMA_MODEL, temperature=0.1, timeout=120):
        self.model       = model
        self.temperature = temperature
        self.timeout     = timeout

    def generate(self, prompt,
                 system="You are a quantitative trading system. Output only valid JSON."):
        payload = {
            "model":   self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "stream":  False,
            "options": {
                "temperature":   self.temperature,
                "repeat_penalty": 1.1,   # discourages repetitive/looping output
            },
        }
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot reach Ollama at localhost:11434.\n"
                "Start it with:  ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")

    def generate_json(self, prompt):
        return _safe_parse_json(self.generate(prompt))


class OpenRouterClient:
    """Cloud LLM via OpenRouter (rate-limited on free tier)."""
    def __init__(self, api_key=None, model="gemma", max_tokens=512,
                 temperature=0.1, max_retries=1, retry_delay=5.0):
        self.api_key     = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model       = OPENROUTER_MODELS.get(model, model)
        self.max_tokens  = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/TradeStratGen/StratGen",
            "X-Title":       "StratGen",
        }

    def generate(self, prompt,
                 system="You are a quantitative trading system. Output only valid JSON."):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens":  self.max_tokens,
            "temperature": self.temperature,
        }
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                r = requests.post(OPENROUTER_URL, headers=self.headers,
                                  json=payload, timeout=30)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", "?")
                print(f"[LLM] HTTP {status} attempt {attempt}/{self.max_retries}")
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        raise RuntimeError(f"OpenRouter failed: {last_error}")

    def generate_json(self, prompt):
        return _safe_parse_json(self.generate(prompt))


def _safe_parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines   = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse failed: {e}\nRaw:\n{text[:300]}")
        return {}


if __name__ == "__main__":
    print("Testing Ollama (qwen2.5:7b-instruct, temp=0.1)...\n")
    client = OllamaClient()
    result = client.generate_json(
        "Market regime: Bullish\n\n"
        'Output JSON: {"entry_condition":"","exit_condition":"","stop_loss":0.0,"take_profit":0.0}\n'
        "Use only Close, SMA_20, SMA_50, RSI. JSON only."
    )
    print(json.dumps(result, indent=2))