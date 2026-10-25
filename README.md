# Agente de voz — cotizador de exámenes (Telnyx)

Llama por teléfono a un centro de exámenes simulando ser un paciente. Pregunta precio
particular, Fonasa, Isapre, disponibilidad y preparación. Al colgar, la conversación se
transcribe, se resume y queda registrada en CSV + Markdown.

Todo corre con la API key de Telnyx: no hay servidores externos, ni SDK, ni API keys de
OpenAI. El único binario extra es `cloudflared` (túnel para el webhook).

## Requisitos

- Python 3.9+ (sin dependencias)
- `brew install cloudflared`
- `.env` con la API key (ya generado)

## Flujo

```
llamar.py ──dial + assistant──> Telnyx ──llamada──> tu teléfono
                         │
                         ├── call.conversation.created ──> guarda el conversation_id
                         ├── call.conversation.ended   ──> cuelga la pierna
                         └── call.hangup               ──> busca los 29 mensajes,
                                                           resume con LLM y escribe CSV/MD
```

El assistant se engancha en el mismo `dial`, así que Telnyx lo "calienta" mientras timbra y
habla apenas contestan. No hay comando posterior desde el webhook.

## Uso

```bash
# 1. Crear (o actualizar) el assistant. El argumento es el examen por defecto.
python3 agente/assistant.py "PET-CT"

# 2. Levantar túnel + webhook (dejar corriendo en una terminal)
./tunel.sh

# 3. En otra terminal, hacer la llamada
python3 agente/llamar.py --examen "PET-CT"

# 4. Si el túnel estaba caído al colgar, recuperar lo pendiente
python3 resumenes.py --poll
```

## Salida

- `data/llamadas.csv` — una fila por llamada, con los datos capturados
- `data/llamadas/AAAA-MM-DD-<id>.md` — resumen + transcripción completa

## Configuración (`.env`)

| Variable | Para qué |
|---|---|
| `TELNYX_API_KEY` | Todo |
| `TELNYX_FROM` | número que marca (E.164, ej. `+56XXXXXXXXX`) |
| `TELNYX_TO` | número destino (E.164, ej. `+56YYYYYYYYY`) |
| `TELNYX_CONNECTION_ID` | app Call Control usada para originar |
| `ASSISTANT_ID` | se llena solo con `assistant.py` |
| `WEBHOOK_SECRET` | secreto en la ruta del webhook |
| `PORT` | puerto local del webhook (8000) |

`.tunnel_url` lo escribe `tunel.sh` en cada arranque y manda sobre `PUBLIC_URL`.

## Editar el guion

Las instrucciones del agente están en `agente/assistant.py` (`INSTRUCTIONS` y `GREETING`).
`<<EXAMEN>>` se reemplaza en cada llamada. Después de editar:

```bash
python3 agente/assistant.py "PET-CT"
```

## Limitaciones conocidas

- El agente cuelga al despedirse mediante el tool `hangup` del assistant. En Call Control el
  assistant no corta la pierna por sí solo: el webhook cierra la llamada al recibir
  `call.conversation.ended`.
- No hay firma Ed25519 en el webhook; la protección es el secreto en la ruta. Para
  producción, agregar verificación con la clave pública de la cuenta.
- El resumen usa `deepseek-ai/DeepSeek-V4.1-Flash` (alojado en Telnyx, sin costo extra de
  proveedor). Se puede cambiar en `resumenes.py`.
- Los insights nativos de Telnyx quedan activados para el portal, pero el CSV no depende
  de ellos porque la API no los expone.
- La transcripción se arma desde `GET /ai/conversations/{id}/messages` paginando de a 100;
  el default de la API es 20 y corta el inicio de la llamada.
