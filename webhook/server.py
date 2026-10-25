"""Webhook local: sigue el ciclo de la conversación y archiva la llamada al colgar."""

import base64
import hmac
import json
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import resumenes  # noqa: E402
from agente import config  # noqa: E402
from agente.telnyx_api import TelnyxError, post  # noqa: E402

PORT = int(config.get("PORT", "8000"))
SECRET = config.get("WEBHOOK_SECRET", required=True)

# call_control_id -> conversation_id, para no tener que buscarla al colgar
CONVERSACIONES = {}


def log(mensaje):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), mensaje), flush=True)


def examen_de(payload):
    bruto = payload.get("client_state")
    if not bruto:
        return ""
    try:
        return json.loads(base64.b64decode(bruto).decode("utf-8")).get("examen", "")
    except Exception:
        return ""


def colgar(call_control_id, motivo):
    try:
        post("/calls/%s/actions/hangup" % call_control_id, {}, timeout=15)
        log("colgado (%s) %s" % (motivo, call_control_id[:24]))
    except TelnyxError as exc:
        if "90018" not in str(exc):  # la llamada ya se había cortado
            log("no se pudo colgar: %s" % exc)


def recolectar(call_control_id, payload):
    examen = examen_de(payload)
    conversacion = CONVERSACIONES.pop(call_control_id, None)

    if not conversacion:
        log("colgó %s, buscando conversación..." % call_control_id[:24])
        encontrada = resumenes.buscar_por_call_control(call_control_id)
        conversacion = encontrada["id"] if encontrada else None

    if not conversacion:
        log("sin conversación para %s (usa: python3 resumenes.py --poll)" % call_control_id[:24])
        return

    for intento in range(3):
        try:
            fila = resumenes.procesar(conversacion, examen)
            log("OK %s -> %s" % (conversacion[:8], fila["archivo_md"]))
            return
        except Exception as exc:
            log("reintento %d: %s" % (intento + 1, exc))
            time.sleep(5)
    log("no se pudo resumir %s; queda para --poll" % conversacion[:8])


def procesar_evento(evento):
    data = evento.get("data") or {}
    tipo = data.get("event_type", "")
    payload = data.get("payload") or {}
    call_control_id = payload.get("call_control_id")

    if not call_control_id:
        return

    if tipo == "call.conversation.created":
        CONVERSACIONES[call_control_id] = payload.get("conversation_id")
        log("conversación %s creada" % str(payload.get("conversation_id"))[:8])

    elif tipo == "call.conversation.start_failed":
        log("ERROR al iniciar assistant: %s" % payload.get("reason"))
        colgar(call_control_id, "fallo de inicio")

    elif tipo == "call.conversation.ended":
        # El assistant no cuelga solo: si terminó la conversación, cerramos la pierna.
        log("conversación terminada %s" % call_control_id[:24])
        colgar(call_control_id, "fin de conversación")

    elif tipo == "call.hangup":
        time.sleep(2)
        recolectar(call_control_id, payload)

    elif tipo == "call.initiated":
        log("marcando a %s" % payload.get("to", "?"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _responder(self, codigo, cuerpo=b"ok"):
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self._responder(200 if self.path == "/health" else 404)

    def do_POST(self):
        if not hmac.compare_digest(self.path, "/hook/" + SECRET):
            self._responder(404)
            return

        largo = int(self.headers.get("Content-Length") or 0)
        crudo = self.rfile.read(largo)
        self._responder(200)  # Telnyx exige ACK rápido

        try:
            evento = json.loads(crudo.decode("utf-8"))
        except ValueError:
            log("payload inválido")
            return

        threading.Thread(target=self._seguro, args=(evento,), daemon=True).start()

    @staticmethod
    def _seguro(evento):
        try:
            procesar_evento(evento)
        except Exception:
            traceback.print_exc()

    def log_message(self, *args):
        pass


def main():
    if not config.public_url():
        log("AVISO: no hay URL pública (.tunnel_url). El webhook no recibirá eventos.")
    log("escuchando en http://localhost:%d/hook/<secreto>" % PORT)
    log("assistant: %s" % config.get("ASSISTANT_ID", "(sin configurar)"))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
