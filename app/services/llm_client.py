import json
import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, N_CTX, N_THREADS

OLLAMA_TIMEOUT = 600.0


async def chat(prompt: str, system: str | None = None, model: str | None = None, temperature: float = 0.1, num_predict: int = 8192) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": N_CTX,
            "num_thread": N_THREADS,
        },
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


def _extract_json(text: str):
    text = text.strip()
    first = text.find("{")
    bracket = text.find("[")
    if bracket != -1 and (first == -1 or bracket < first):
        first = bracket
    if first == -1:
        raise ValueError("No JSON found in response")
    text = text[first:]

    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            depth += 1
        elif ch in ("}", "]"):
            depth -= 1
            if depth == 0:
                return json.loads(text[: i + 1])
    raise ValueError(f"Unterminated JSON in response: {text[:200]}")


async def chat_json(prompt: str, system: str | None = None, model: str | None = None, temperature: float = 0.1, num_predict: int = 8192) -> dict | list:
    content = await chat(prompt, system=system, model=model, temperature=temperature, num_predict=num_predict)
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return _extract_json(content.strip())


async def chat_with_messages(messages: list[dict], model: str | None = None, temperature: float = 0.0, num_predict: int = 4096) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    body = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": N_CTX,
            "num_thread": N_THREADS,
        },
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def check_health() -> bool:
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


async def list_models() -> list[str]:
    url = f"{OLLAMA_BASE_URL}/api/tags"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
