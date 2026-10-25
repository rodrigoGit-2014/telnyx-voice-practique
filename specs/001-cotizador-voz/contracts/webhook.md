# Contract: Webhook entrante

**Feature**: `001-cotizador-voz` | **Implementación**: `webhook/server.py`

## Superficie HTTP

| Método | Ruta | Respuesta | Propósito |
|---|---|---|---|
| `GET` | `/health` | `200 text/plain` `ok` | Preflight de `llamar.py` y del operador |
| `GET` | cualquier otra | `404` | No se expone nada más |
| `POST` | `/hook/{WEBHOOK_SECRET}` | `200 text/plain` `ok` | Recepción de eventos de Telnyx |
| `POST` | cualquier otra | `404` | Ruta desconocida |

- **Puerto**: `PORT` (default `8000`), escucha en `0.0.0.0`.
- **Protocolo**: HTTP/1.1.
- **Validación de ruta**: `hmac.compare_digest(path, "/hook/" + SECRET)` — comparación de tiempo
  constante.
- **ACK**: se responde 200 **antes** de procesar el evento. El trabajo corre en un hilo
  (`threading.Thread(daemon=True)`), de modo que Telnyx no reintenta por timeout.
- **Payload inválido**: se responde 200 (ya se envió el ACK) y se registra `payload inválido`.
- **Excepción no controlada**: se captura en `_seguro` y se imprime el traceback; el servidor
  sigue vivo.

## Formato del evento

```json
{
  "data": {
    "event_type": "call.conversation.created",
    "payload": {
      "call_control_id": "v3:...",
      "conversation_id": "<uuid>",
      "to": "+56XXXXXXXXX",
      "from": "+56YYYYYYYYY"
    }
  }
}
```

Solo se usan `data.event_type`, `data.payload.call_control_id` y, según el evento,
`payload.conversation_id`, `payload.reason` y `payload.to`.

## Eventos manejados

| `event_type` | Acción | Efecto |
|---|---|---|
| `call.initiated` | Log | `marcando a <to>` |
| `call.conversation.created` | Guarda `CONVERSACIONES[call_control_id] = conversation_id` | Permite archivar sin buscar |
| `call.conversation.start_failed` | `colgar(call_control_id, "fallo de inicio")` | Libera la línea |
| `call.conversation.ended` | `colgar(call_control_id, "fin de conversación")` | Workaround: el assistant no cierra la pierna |
| `call.hangup` | `sleep(2)` + `recolectar()` | Archiva en CSV + MD |

**Eventos sin `call_control_id`**: se ignoran silenciosamente (return temprano).
**Eventos desconocidos**: se ignoran; solo se registran los anteriores.

## Flujo de archivado al colgar

```text
call.hangup
   │
   ├── esperar 2 s (indexación de la conversación)
   ├── recuperar conversation_id del mapa en memoria
   │      └── si no está: buscar por call_control_id (18 intentos × 5 s)
   ├── resumenes.procesar(conversation_id, examen)
   │      ├── éxito → log "OK <id8> -> <archivo_md>"
   │      └── error → reintento (máx. 3, 5 s entre intentos)
   └── si falla todo → log "queda para --poll"
```

El `examen` se obtiene decodificando `payload.client_state` en base64; si falta o es inválido,
queda vacío y el resumen usa el examen que detecte el LLM.

## Seguridad

- **Protección actual**: secreto en la ruta. No se valida firma Ed25519. La URL completa es
  `https://<tunel>.trycloudflare.com/hook/<WEBHOOK_SECRET>`.
- **Consecuencia**: quien conozca la URL puede inyectar eventos. El webhook solo actúa sobre
  `call_control_id` existentes y operaciones idempotentes, pero no es autenticación fuerte.
- **Deuda**: `specs/002-firma-webhook-ed25519/spec.md`.
- **No loggear**: el secreto no se imprime; el log muestra `/hook/<secreto>` solo como texto
  literal en el arranque (`escuchando en http://localhost:<port>/hook/<secreto>`).

## Idempotencia y repetición

- Telnyx puede reintentar un evento si no recibe 200. El ACK temprano lo evita en la mayoría de
  los casos.
- El mapa `CONVERSACIONES` vive en memoria: se pierde si el webhook se reinicia.
- El archivado es idempotente por `conversation_id`; repetir `call.hangup` o ejecutar `--poll`
  actualiza la misma fila.

## Ejemplos de verificación

```bash
# Salud
curl -s http://localhost:8000/health

# Ruta incorrecta → 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/hook/incorrecto

# Evento sintético (con el secreto correcto) → 200 inmediato
curl -s -X POST "http://localhost:8000/hook/$WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"data":{"event_type":"call.initiated","payload":{"call_control_id":"v3:test","to":"+56XXXXXXXXX"}}}'
```
