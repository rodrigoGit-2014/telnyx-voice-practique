# Contract: Telnyx API v2

**Feature**: `001-cotizador-voz` | **Consumidor**: `agente/telnyx_api.py`

## Convenciones

- **Base URL**: `https://api.telnyx.com/v2`
- **Autenticación**: `Authorization: Bearer <TELNYX_API_KEY>`
- **Content-Type**: `application/json`
- **Accept**: `application/json`
- **Timeout**: 60 s por defecto; 120 s para chat completions; 15 s para colgar.
- **Errores**: `HTTPError` se traduce a `TelnyxError("<METHOD> <path> -> <code>: <detalle>")`;
  `URLError` se traduce a `TelnyxError("<METHOD> <path> -> sin conexión: <motivo>")`.
- **Desempaquetado**: las listas vienen envueltas en `{"data": [...]}`; los objetos sueltos
  pueden venir sin envoltorio. `unwrap()` devuelve `data` si existe, o el payload tal cual.

> Los ejemplos usan placeholders. Nunca se documentan ni se imprimen credenciales.

## 1. Crear assistant

`POST /ai/assistants`

**Request** (campos relevantes; el payload completo está en `agente/assistant.py`):

```json
{
  "name": "Cotizador Exámenes - Rodrigo (saliente)",
  "description": "Llama a centros de exámenes para cotizar precio, Fonasa, Isapre y disponibilidad.",
  "model": "moonshotai/Kimi-K2.6",
  "instructions": "<guion con el examen ya interpolado>",
  "greeting": "<saludo con el examen ya interpolado>",
  "enabled_features": ["telephony"],
  "tools": [{"type": "hangup", "hangup": {}}],
  "voice_settings": {
    "voice": "Azure.es-CL-LorenzoNeural",
    "voice_speed": 1,
    "background_audio": {"type": "predefined_media", "value": "silence", "volume": 0.4}
  },
  "transcription": {"model": "deepgram/flux", "language": "es"},
  "telephony_settings": {
    "noise_suppression": "krisp",
    "time_limit_secs": 600,
    "recording_settings": {"enabled": false}
  },
  "insight_settings": {"insight_group_id": "<uuid del grupo>"}
}
```

**Response**: objeto con `id`. El CLI lo persiste como `ASSISTANT_ID` en `.env`.

## 2. Actualizar assistant

`PATCH /ai/assistants/{assistant_id}`

**Request**: mismo payload que la creación.

**Response**: objeto actualizado. El CLI conserva el `ASSISTANT_ID` existente.

## 3. Originar llamada

`POST /calls`

**Request**:

```json
{
  "connection_id": "<TELNYX_CONNECTION_ID>",
  "from": "+56XXXXXXXXX",
  "to": "+56YYYYYYYYY",
  "timeout_secs": 45,
  "webhook_url": "https://<tunel>.trycloudflare.com/hook/<WEBHOOK_SECRET>",
  "client_state": "<base64 de {\"examen\":\"PET-CT\"}>",
  "assistant": {
    "id": "<ASSISTANT_ID>",
    "instructions": "<guion interpolado>",
    "greeting": "<saludo interpolado>"
  }
}
```

**Response**: `{"data": {"call_control_id": "v3:...", ...}}`. El CLI imprime `call_control_id`.

**Regla**: el assistant se engancha en este mismo request; no hay llamada posterior para
iniciarlo. El `client_state` es la única forma en que el webhook conoce el examen.

## 4. Colgar

`POST /calls/{call_control_id}/actions/hangup`

**Request**: `{}`

**Response**: 200 con la acción aceptada.

**Error tolerado**: código `90018` (la llamada ya se había cortado). El webhook lo ignora. Otros
errores se registran en el log y no interrumpen el archivado.

## 5. Listar conversaciones

`GET /ai/conversations?page[size]={n}`

**Response**:

```json
{
  "data": [
    {
      "id": "<conversation_id>",
      "created_at": "2026-10-25T00:10:32Z",
      "number_of_messages": 29,
      "metadata": {"call_control_id": "v3:..."}
    }
  ],
  "meta": {"total_pages": 1}
}
```

**Uso**: `--poll` (50 por defecto) y búsqueda por `call_control_id` (30 por intento).

## 6. Obtener conversación

`GET /ai/conversations/{conversation_id}`

**Response**: objeto de conversación con `id`, `created_at`, `metadata` y `number_of_messages`.
**Uso**: obtener metadatos al archivar.

## 7. Listar mensajes

`GET /ai/conversations/{conversation_id}/messages?page[size]=100&page[number]={n}`

**Response**:

```json
{
  "data": [
    {
      "role": "assistant",
      "text": "Hola, buenas tardes...",
      "created_at": "2026-10-25T00:10:33Z"
    },
    {
      "role": "user",
      "text": "Hola, buenas, sí.",
      "created_at": "2026-10-25T00:10:35Z"
    }
  ],
  "meta": {"total_pages": 1}
}
```

**Regla**: se recorren todas las páginas; el default de la API (20) no se usa porque corta el
inicio de la llamada. Los mensajes se ordenan por `created_at`.

## 8. Chat completion (resumen)

`POST /ai/openai/chat/completions`

**Request**:

```json
{
  "model": "deepseek-ai/DeepSeek-V4.1-Flash",
  "messages": [
    {"role": "system", "content": "<SUMMARY_PROMPT>"},
    {"role": "user", "content": "Examen consultado: PET-CT\n\nTranscripción:\n..."}
  ],
  "temperature": 0,
  "max_tokens": 700
}
```

**Response**: `{"choices": [{"message": {"content": "<json>"}}]}`.

**Regla**: el contenido se parsea con una expresión regular que extrae el primer objeto `{...}`;
si no hay contenido o no hay JSON, se lanza `ValueError` y se reintenta el archivado.

## Matriz de errores

| Situación | Manejo |
|---|---|
| Falta `TELNYX_API_KEY` | `SystemExit` con instrucción de configurar `.env` |
| HTTP 4xx/5xx | `TelnyxError` con método, ruta, código y detalle (600 caracteres) |
| Sin conexión | `TelnyxError` con el motivo |
| `hangup` con `90018` | Se ignora (llamada ya cortada) |
| Conversación aún no indexada | Reintentos de búsqueda; si falla, `--poll` |
| LLM sin JSON | `ValueError`; 3 reintentos; queda para `--poll` |
