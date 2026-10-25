"""Transcribe, resume y archiva cada llamada en CSV + Markdown.

Uso:
    python3 resumenes.py --poll          # procesa llamadas nuevas (respaldo del webhook)
    python3 resumenes.py --reprocess ID  # rehace una conversación puntual
"""

import argparse
import csv
import json
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agente import config
from agente.telnyx_api import TelnyxError, get_json, llm, unwrap

DATA_DIR = config.ROOT / "data"
MD_DIR = DATA_DIR / "llamadas"
CSV_FILE = DATA_DIR / "llamadas.csv"

COLUMNS = [
    "fecha_hora",
    "conversation_id",
    "call_control_id",
    "telefono",
    "duracion_seg",
    "examen",
    "lo_realizan",
    "precio_particular",
    "fonasa",
    "isapre",
    "disponibilidad",
    "preparacion",
    "resumen",
    "siguiente_paso",
    "archivo_md",
]

CSV_LOCK = threading.Lock()

SUMMARY_PROMPT = """Eres un analista que procesa transcripciones de llamadas de un paciente
cotizando un examen médico en Chile. Devuelve SOLO un objeto JSON válido, sin markdown,
con exactamente estas claves:

{
  "examen": "examen consultado",
  "lo_realizan": "si" | "no" | "no_se_sabe",
  "precio_particular": "monto en pesos tal como lo dijeron, o 'no informado'",
  "fonasa": "tramos y valores mencionados, o 'no atienden' / 'no informado'",
  "isapre": "planes y coberturas mencionados, o 'no atienden' / 'no informado'",
  "disponibilidad": "para cuándo hay hora, o 'no informado'",
  "preparacion": "indicaciones previas mencionadas, o 'no informado'",
  "resumen": "2 a 3 frases en español neutro describiendo qué se cotizó y qué respondió el centro",
  "siguiente_paso": "acción concreta recomendada para el paciente"
}

Reglas:
- No inventes datos: si algo no se dijo, usa 'no informado'.
- Los montos van como texto, sin símbolos raros (ej: "120.000 pesos").
- Escribe el JSON en una sola línea."""


def _fecha_local(iso):
    if not iso:
        return datetime.now()
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt
    except ValueError:
        return datetime.now()


def listar_conversaciones(limit=50):
    return unwrap(get_json("/ai/conversations?page[size]=%d" % limit))


def buscar_por_call_control(call_control_id, intentos=18, espera=5):
    """La conversación tarda unos segundos en indexarse después del colgado."""
    import time

    for i in range(intentos):
        for conv in listar_conversaciones(limit=30):
            meta = conv.get("metadata") or {}
            if meta.get("call_control_id") == call_control_id:
                return conv
        if i < intentos - 1:
            time.sleep(espera)
    return None


def obtener_mensajes(conversation_id, tamano=100):
    mensajes = []
    pagina = 1
    while True:
        respuesta = get_json(
            "/ai/conversations/%s/messages?page[size]=%d&page[number]=%d"
            % (conversation_id, tamano, pagina)
        )
        lote = respuesta.get("data") or []
        mensajes.extend(lote)
        total_paginas = (respuesta.get("meta") or {}).get("total_pages") or 1
        if not lote or pagina >= total_paginas:
            break
        pagina += 1
    return sorted(mensajes, key=lambda m: m.get("created_at") or "")


def construir_transcripcion(mensajes):
    lineas = []
    for msg in mensajes:
        texto = (msg.get("text") or "").strip()
        if not texto:
            continue
        if msg.get("role") == "assistant":
            quien = "Rodrigo (paciente)"
        elif msg.get("role") == "user":
            quien = "Centro"
        else:
            continue
        lineas.append("%s: %s" % (quien, texto))
    return "\n".join(lineas)


def duracion_seg(mensajes):
    marcas = []
    for msg in mensajes:
        for campo in ("created_at", "sent_at", "ended_at"):
            valor = msg.get(campo)
            if valor:
                try:
                    marcas.append(datetime.fromisoformat(valor.replace("Z", "+00:00")))
                except ValueError:
                    pass
    if len(marcas) < 2:
        return 0
    return int((max(marcas) - min(marcas)).total_seconds())


def resumir(transcripcion, examen):
    content = llm(
        [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": "Examen consultado: %s\n\nTranscripción:\n%s" % (examen, transcripcion)},
        ]
    )
    if not content:
        raise ValueError("el modelo no devolvió contenido")
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("respuesta sin JSON: %r" % content[:200])
    return json.loads(match.group(0))


def leer_csv():
    if not CSV_FILE.exists():
        return []
    with CSV_FILE.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def escribir_csv(filas):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for fila in filas:
            writer.writerow({col: fila.get(col, "") for col in COLUMNS})


def guardar_markdown(fila, transcripcion):
    MD_DIR.mkdir(parents=True, exist_ok=True)
    fecha = fila["fecha_hora"][:10]
    nombre = "%s-%s.md" % (fecha, fila["conversation_id"][:8])
    ruta = MD_DIR / nombre

    campos = [
        ("Examen", fila["examen"]),
        ("¿Lo realizan?", fila["lo_realizan"]),
        ("Precio particular", fila["precio_particular"]),
        ("Fonasa", fila["fonasa"]),
        ("Isapre", fila["isapre"]),
        ("Disponibilidad", fila["disponibilidad"]),
        ("Preparación", fila["preparacion"]),
        ("Siguiente paso", fila["siguiente_paso"]),
    ]
    lineas = [
        "# Llamada %s" % fila["fecha_hora"],
        "",
        "- **Duración:** %s s" % fila["duracion_seg"],
        "- **Teléfono:** %s" % fila["telefono"],
        "- **Conversación:** `%s`" % fila["conversation_id"],
        "",
        "## Resumen",
        "",
        fila["resumen"],
        "",
        "## Datos capturados",
        "",
    ]
    for etiqueta, valor in campos:
        lineas.append("- **%s:** %s" % (etiqueta, valor))
    lineas += ["", "## Transcripción", "", "```", transcripcion, "```", ""]
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return str(ruta.relative_to(config.ROOT))


def procesar(conversation_id, examen="", telefono=""):
    conv = unwrap(get_json("/ai/conversations/%s" % conversation_id))
    meta = conv.get("metadata") or {}
    mensajes = obtener_mensajes(conversation_id)
    transcripcion = construir_transcripcion(mensajes)

    if not transcripcion.strip():
        raise ValueError("conversación %s sin mensajes" % conversation_id)

    datos = resumir(transcripcion, examen or "no especificado")
    inicio = _fecha_local(conv.get("created_at"))

    fila = {
        "fecha_hora": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "conversation_id": conversation_id,
        "call_control_id": meta.get("call_control_id", ""),
        "telefono": telefono or config.get("TELNYX_TO", ""),
        "duracion_seg": duracion_seg(mensajes),
        "archivo_md": "",
    }
    for clave in ("examen", "lo_realizan", "precio_particular", "fonasa", "isapre",
                  "disponibilidad", "preparacion", "resumen", "siguiente_paso"):
        valor = datos.get(clave, "")
        fila[clave] = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    if examen:
        fila["examen"] = examen
    fila["archivo_md"] = guardar_markdown(fila, transcripcion)

    with CSV_LOCK:
        filas = leer_csv()
        indexado = {f.get("conversation_id"): i for i, f in enumerate(filas)}
        if conversation_id in indexado:
            filas[indexado[conversation_id]] = fila
        else:
            filas.append(fila)
        escribir_csv(filas)

    return fila


def poll(horas=24):
    filas = leer_csv()
    ya = {f.get("conversation_id") for f in filas}
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    pendientes = []
    for conv in listar_conversaciones(limit=50):
        if conv.get("id") in ya:
            continue
        if not (conv.get("metadata") or {}).get("call_control_id"):
            continue  # ignora conversaciones de chat, solo llamadas reales
        if _fecha_local(conv.get("created_at")) < desde:
            continue
        if not conv.get("number_of_messages"):
            continue
        pendientes.append(conv["id"])

    if not pendientes:
        print("Sin llamadas nuevas.")
        return

    for conversation_id in pendientes:
        try:
            fila = procesar(conversation_id)
            print("OK  %s  %s" % (conversation_id[:8], fila["resumen"][:70]))
        except (TelnyxError, ValueError, json.JSONDecodeError) as exc:
            print("ERR %s  %s" % (conversation_id[:8], exc))


def main():
    parser = argparse.ArgumentParser(description="Genera resúmenes de llamadas en CSV y Markdown.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--poll", action="store_true", help="procesa conversaciones recientes sin fila en el CSV")
    grupo.add_argument("--reprocess", metavar="CONVERSATION_ID", help="rehace una conversación")
    parser.add_argument("--horas", type=int, default=24, help="ventana de --poll en horas")
    parser.add_argument("--examen", default="", help="examen consultado (solo con --reprocess)")
    args = parser.parse_args()

    if args.poll:
        poll(args.horas)
    else:
        fila = procesar(args.reprocess, args.examen)
        print(json.dumps(fila, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except TelnyxError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)
