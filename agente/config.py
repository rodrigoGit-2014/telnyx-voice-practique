"""Configuración del proyecto: lee .env y .tunnel_url desde la raíz de v1."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
TUNNEL_FILE = ROOT / ".tunnel_url"


def load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get(name, default=None, required=False):
    load_env()
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(
            "Falta %s en .env. Corre primero: python3 agente/assistant.py" % name
        )
    return value


def public_url():
    """URL del túnel. .tunnel_url manda sobre .env porque cambia en cada arranque."""
    if TUNNEL_FILE.exists():
        url = TUNNEL_FILE.read_text(encoding="utf-8").strip()
        if url:
            return url.rstrip("/")
    return (get("PUBLIC_URL") or "").rstrip("/")


def set_env(name, value):
    """Escribe o actualiza una clave en .env conservando el resto."""
    load_env()
    lines = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.split("=", 1)[0].strip() == name:
                lines.append("%s=%s" % (name, value))
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append("%s=%s" % (name, value))
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
