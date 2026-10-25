"""Cliente mínimo de la API de Telnyx con la librería estándar de Python."""

import json
import urllib.error
import urllib.request

from agente.config import get

BASE = "https://api.telnyx.com/v2"


class TelnyxError(RuntimeError):
    pass


def request(method, path, body=None, timeout=60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + get("TELNYX_API_KEY", required=True),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise TelnyxError("%s %s -> %s: %s" % (method, path, exc.code, detail)) from None
    except urllib.error.URLError as exc:
        raise TelnyxError("%s %s -> sin conexión: %s" % (method, path, exc.reason)) from None


def get_json(path, **kwargs):
    return request("GET", path, **kwargs)


def post(path, body=None, **kwargs):
    return request("POST", path, body, **kwargs)


def patch(path, body=None, **kwargs):
    return request("PATCH", path, body, **kwargs)


def unwrap(payload):
    """La API devuelve los objetos sueltos sin envoltorio y las listas con .data."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), (dict, list)):
        return payload["data"]
    return payload


def llm(messages, model="deepseek-ai/DeepSeek-V4.1-Flash", temperature=0, max_tokens=700):
    """Chat completion con modelos alojados por Telnyx (sin API key adicional)."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    result = post("/ai/openai/chat/completions", payload, timeout=120)
    return result["choices"][0]["message"]["content"]
