"""Tiny stdlib-only Ollama client with on-disk caching (so reruns are free)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("POC_MODEL", "qwen3.8:27b-mlx")
CACHE = Path(__file__).parent / "out" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def chat(prompt: str, *, system: str = "", temperature: float = 0.7, seed: int = 0,
         max_tokens: int = 600, as_json: bool = True):
    """One chat call. Returns a dict when as_json else a str. Cached by full input."""
    key = hashlib.sha256(json.dumps([MODEL, system, prompt, temperature, seed, max_tokens, as_json]).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        raw = json.loads(path.read_text())["content"]
    else:
        body = {
            "model": MODEL, "stream": False, "think": False,
            "options": {"temperature": temperature, "seed": seed, "num_predict": max_tokens},
            "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}],
        }
        if as_json:
            body["format"] = "json"
        req = urllib.request.Request(f"{HOST}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        for attempt in range(3):  # the mlx runner occasionally stalls; fail fast and retry
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = json.load(r)["message"]["content"]
                break
            except OSError:
                if attempt == 2:
                    raise
        path.write_text(json.dumps({"content": raw}))
    if not as_json:
        return raw
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"no JSON in model output: {raw[:200]}")
    return json.loads(m.group(0))
