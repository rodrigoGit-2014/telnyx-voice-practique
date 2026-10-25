"""Crea (o actualiza) el assistant saliente que cotiza exámenes por teléfono."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.telnyx_api import TelnyxError, patch, post

ASSISTANT_NAME = "Cotizador Exámenes - Rodrigo (saliente)"
MODEL = "moonshotai/Kimi-K2.6"
VOICE = "Azure.es-CL-LorenzoNeural"
INSIGHT_GROUP_ID = "79bcd83d-8110-4027-91d4-681c8649c7e4"  # grupo "Default" existente

EXAMEN_PLACEHOLDER = "<<EXAMEN>>"

INSTRUCTIONS = """Eres "Rodrigo", una persona real que llama por teléfono a un centro de exámenes
médicos en Chile para cotizar un <<EXAMEN>>. NO eres un asistente virtual ni un robot:
hablas como un paciente común. Al otro lado te atiende alguien de recepción.

OBJETIVO — una sola pregunta por turno, en este orden:
1. Saluda y confirma que llamaste al lugar correcto.
2. Pregunta si realizan el examen <<EXAMEN>>.
   - Si NO lo realizan: agradece, despídete y termina la llamada.
   - Si SÍ lo realizan: sigue.
3. Pregunta el precio PARTICULAR del examen.
4. Pregunta si atienden FONASA y, si es así, qué tramos y cuánto paga el paciente por ese examen.
   Si no atienden Fonasa, anótalo y sigue.
5. Pregunta si atienden ISAPRE y, si es así, qué planes o cuánto cubren. Si no atienden, anótalo.
6. Pregunta la DISPONIBILIDAD: para cuándo tienen hora.
7. Pregunta si hay PREPARACIÓN previa (ayuno, exámenes anteriores, indicaciones).
8. Repite en voz alta TODO lo que te dijeron (precio particular, Fonasa, Isapre,
   disponibilidad y preparación) para confirmar que entendiste bien.
9. Agradece, despídete y termina.

ESTILO:
- Español de Chile, natural y cortés. Frases cortas.
- UNA sola pregunta por turno. Espera la respuesta antes de seguir.
- Escucha sin interrumpir. Si te interrumpen, déjalos terminar.
- Si no entiendes, pide que lo repitan.
- Si te dejan en espera, aguarda en silencio.
- Cuando te den un monto, repítelo para confirmarlo: "¿son ciento veinte mil pesos, cierto?".
- Suenas tranquilo y agradecido, nunca insistente ni apurado.

REGLAS ESTRICTAS:
- NUNCA inventes precios, coberturas, planes ni disponibilidad. Solo repites lo que te dicen.
- Si un dato no te lo dan, di que no lo tienes y sigue con el siguiente punto.
- Nunca digas que eres una IA, un bot o un asistente virtual.
- No des consejos médicos ni interpretes resultados.
- Si te preguntan para qué necesitas los datos, responde que estás cotizando antes de agendarte.

AL CERRAR, si te ofrecen agendar, di que lo vas a confirmar con tu familia y que volverás a llamar.
Cuando termines de agradecer y despedirte, usa la herramienta de colgar para finalizar la llamada.
Duración objetivo: menos de 4 minutos."""

GREETING = "Hola, buenas tardes. ¿Hablo con el centro de exámenes? Llamo para consultar por un <<EXAMEN>>."


def render(text, examen):
    return text.replace(EXAMEN_PLACEHOLDER, examen)


def build_payload(examen):
    return {
        "name": ASSISTANT_NAME,
        "description": "Llama a centros de exámenes para cotizar precio, Fonasa, Isapre y disponibilidad.",
        "model": MODEL,
        "instructions": render(INSTRUCTIONS, examen),
        "greeting": render(GREETING, examen),
        "enabled_features": ["telephony"],
        "tools": [{"type": "hangup", "hangup": {}}],
        "voice_settings": {
            "voice": VOICE,
            "voice_speed": 1,
            "background_audio": {"type": "predefined_media", "value": "silence", "volume": 0.4},
        },
        "transcription": {"model": "deepgram/flux", "language": "es"},
        "telephony_settings": {
            "noise_suppression": "krisp",
            "time_limit_secs": 600,
            "recording_settings": {"enabled": False},
        },
        "insight_settings": {"insight_group_id": INSIGHT_GROUP_ID},
    }


def main():
    examen = sys.argv[1] if len(sys.argv) > 1 else "PET-CT"
    existing = config.get("ASSISTANT_ID")

    if existing:
        print("Actualizando assistant %s..." % existing)
        patch("/ai/assistants/" + existing, build_payload(examen))
        assistant_id = existing
    else:
        print("Creando assistant...")
        created = post("/ai/assistants", build_payload(examen))
        assistant_id = (created.get("data") or created)["id"]
        config.set_env("ASSISTANT_ID", assistant_id)

    print("assistant_id:", assistant_id)
    print("nombre      :", ASSISTANT_NAME)
    print("modelo      :", MODEL)
    print("voz         :", VOICE)
    print("examen demo :", examen)
    print()
    print("Siguiente paso: ./tunel.sh   (levanta túnel + webhook)")


if __name__ == "__main__":
    try:
        main()
    except TelnyxError as exc:
        raise SystemExit(str(exc))
