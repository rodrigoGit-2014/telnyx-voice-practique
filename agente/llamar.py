"""Dispara una llamada saliente con el assistant ya enganchado desde el primer segundo."""

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.assistant import GREETING, INSTRUCTIONS, render  # noqa: E402
from agente.telnyx_api import TelnyxError, post  # noqa: E402


def b64(obj):
    return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("ascii")


def servidor_arriba(url):
    try:
        with urllib.request.urlopen(url + "/health", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Llama a un centro de exámenes simulando ser paciente.")
    parser.add_argument("--examen", default="PET-CT", help="examen a cotizar (default: PET-CT)")
    parser.add_argument("--to", default=config.get("TELNYX_TO"), help="número destino E.164")
    parser.add_argument("--timeout", type=int, default=45, help="segundos de timbrado")
    args = parser.parse_args()

    base_url = config.public_url()
    if not base_url:
        raise SystemExit("No hay URL pública. Corre ./tunel.sh primero.")
    if not servidor_arriba(base_url):
        raise SystemExit("El webhook no responde en %s/health. Corre ./tunel.sh primero." % base_url)

    payload = {
        "connection_id": config.get("TELNYX_CONNECTION_ID", required=True),
        "from": config.get("TELNYX_FROM", required=True),
        "to": args.to,
        "timeout_secs": args.timeout,
        "webhook_url": base_url + "/hook/" + config.get("WEBHOOK_SECRET", required=True),
        "client_state": b64({"examen": args.examen}),
        "assistant": {
            "id": config.get("ASSISTANT_ID", required=True),
            "instructions": render(INSTRUCTIONS, args.examen),
            "greeting": render(GREETING, args.examen),
        },
    }

    result = post("/calls", payload)
    data = result.get("data", {})
    print("Llamando a %s desde %s" % (args.to, payload["from"]))
    print("examen       :", args.examen)
    print("call_control :", data.get("call_control_id"))
    print("El assistant arranca solo cuando contesten. El resumen queda en data/llamadas.csv al colgar.")


if __name__ == "__main__":
    try:
        main()
    except TelnyxError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
