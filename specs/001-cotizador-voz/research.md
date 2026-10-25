# Research: Cotizador de exámenes por voz

**Feature**: `001-cotizador-voz` | **Fecha**: 2026-10-25

Este documento reconstruye las decisiones técnicas que ya están implementadas. No hay preguntas
abiertas: cada decisión se contrastó contra el código.

## R1. Assistant enganchado en el mismo `POST /calls`

- **Decision**: enviar el assistant embebido (id, instructions y greeting renderizados) en la
  creación de la llamada, en vez de crear la llamada y arrancar el assistant después de contestar.
- **Rationale**: Telnyx "calienta" el assistant mientras timbra y empieza a hablar apenas
  contestan. Elimina un roundtrip y el silencio inicial que delata a un bot.
- **Alternatives considered**: `POST /calls/{id}/actions/start_ai_assistant` tras el evento
  `call.answered` — descartado por latencia y por depender del webhook para arrancar.
- **Implementation**: `agente/llamar.py` (`assistant` dentro del payload de `/calls`).

## R2. Assistant persistente con guion re-renderizado por llamada

- **Decision**: crear o actualizar un único assistant en Telnyx (`ASSISTANT_ID`) y reenviar
  `instructions` y `greeting` renderizados en cada dial.
- **Rationale**: un solo recurso que mantener; el examen cambia por llamada sin crear basura en
  la cuenta. El guion sigue viviendo en un solo archivo.
- **Alternatives considered**: crear un assistant nuevo por examen — descartado por acumulación
  de recursos y por duplicar la fuente de verdad; usar variables de entorno para el guion —
  descartado por legibilidad y por el límite de tamaño.
- **Implementation**: `agente/assistant.py` (`build_payload`, `render`), `agente/llamar.py`.

## R3. Cliente HTTP con la librería estándar

- **Decision**: `urllib.request` en `agente/telnyx_api.py`, con `request`, `get_json`, `post`,
  `patch`, `unwrap` y `llm`.
- **Rationale**: cero dependencias, control exacto del JSON, fácil de auditar y de correr en
  cualquier Python 3.9+. La API es pequeña y estable.
- **Alternatives considered**: SDK oficial de Telnyx o `requests` — descartados por dependencia
  y superficie de actualización; `httpx` — mismo motivo.
- **Implementation**: `agente/telnyx_api.py`.

## R4. Webhook con `http.server` y `ThreadingHTTPServer`

- **Decision**: servidor HTTP embebido, respuesta 200 inmediata y procesamiento en un hilo
  aparte.
- **Rationale**: Telnyx exige ACK rápido; el archivado incluye llamadas a la API y al LLM y puede
  tardar decenas de segundos. Sin framework no hay proceso que administrar.
- **Alternatives considered**: FastAPI/Flask — descartados por dependencias y por requerir un
  servidor ASGI/WSGI; procesar en el hilo del request — descartado porque Telnyx reintentaría.
- **Implementation**: `webhook/server.py` (`Handler.do_POST`, `threading.Thread`).

## R5. Túnel de Cloudflare en vez de ngrok

- **Decision**: `cloudflared tunnel --url http://localhost:8000` desde `tunel.sh`, guardando la
  URL en `.tunnel_url`.
- **Rationale**: no requiere cuenta ni token, es gratis y arranca en segundos. La URL efímera se
  reescribe y `.tunnel_url` tiene prioridad sobre `PUBLIC_URL`.
- **Alternatives considered**: ngrok — requiere cuenta y token; webhook en un servidor público
  permanente — infraestructura y costo que el MVP no necesita.
- **Implementation**: `tunel.sh`, `agente/config.py` (`public_url`).

## R6. Colgar desde el webhook al terminar la conversación

- **Decision**: en `call.conversation.ended`, llamar a `POST /calls/{call_control_id}/actions/hangup`.
- **Rationale**: el assistant no corta la pierna por sí solo en Call Control. Si no se cuelga
  desde el webhook, la línea queda tomada hasta que el otro lado corta.
- **Alternatives considered**: confiar en el `hangup` del assistant — no cierra la pierna;
  esperar el `call.hangup` del usuario — deja la llamada abierta y consume minutos.
- **Implementation**: `webhook/server.py` (`colgar`, evento `call.conversation.ended`).

## R7. Archivar en `call.hangup`, con espera y reintentos

- **Decision**: al recibir `call.hangup`, esperar 2 segundos y luego buscar la conversación;
  reintentar el archivado 3 veces con 5 segundos.
- **Rationale**: la conversación tarda unos segundos en indexarse después del colgado. Archivar
  en `conversation.ended` puede dejar mensajes fuera.
- **Alternatives considered**: archivar en `conversation.ended` — incompleto; archivar
  inmediatamente en `call.hangup` — la API aún no devuelve la conversación.
- **Implementation**: `webhook/server.py` (`recolectar`), `resumenes.py`
  (`buscar_por_call_control`).

## R8. LLM alojado en Telnyx para el resumen

- **Decision**: `POST /ai/openai/chat/completions` con
  `deepseek-ai/DeepSeek-V4.1-Flash`, `temperature=0`.
- **Rationale**: sin API key adicional ni costo de proveedor LLM; el resumen es extractivo y no
  necesita un modelo grande. `temperature=0` reduce variación entre reprocesos.
- **Alternatives considered**: OpenAI/Anthropic directo — otra credencial y costo; resumen local
  — calidad y peso de modelo; reglas/heurísticas — no cubren lenguaje natural.
- **Implementation**: `agente/telnyx_api.py` (`llm`), `resumenes.py` (`SUMMARY_PROMPT`,
  `resumir`).

## R9. Paginar mensajes de a 100

- **Decision**: `GET /ai/conversations/{id}/messages?page[size]=100&page[number]=n`, recorriendo
  `meta.total_pages`.
- **Rationale**: el default de la API es 20 y corta el inicio de la llamada; con 100 se cubre una
  conversación típica en una o dos páginas.
- **Alternatives considered**: tamaño default — pérdida de contexto; tamaño máximo no
  documentado — riesgo de error.
- **Implementation**: `resumenes.py` (`obtener_mensajes`).

## R10. CSV + Markdown en vez de base de datos

- **Decision**: una fila por llamada en `data/llamadas.csv` y un Markdown por conversación en
  `data/llamadas/`.
- **Rationale**: portable, legible, diff-able y compatible con cualquier hoja de cálculo; el
  operador compara centros sin escribir consultas. El Markdown conserva la transcripción
  completa, que no cabe cómoda en una celda.
- **Alternatives considered**: SQLite — más código y una migración para leer; solo JSON — menos
  legible para el usuario final; solo Markdown — difícil de comparar entre llamadas.
- **Implementation**: `resumenes.py` (`escribir_csv`, `guardar_markdown`).

## R11. Idempotencia por `conversation_id`

- **Decision**: indexar las filas por `conversation_id`; si existe, reemplazar; si no, agregar.
- **Rationale**: el webhook y `--poll` pueden procesar la misma conversación. Reprocesar no debe
  duplicar filas ni romper el histórico.
- **Alternatives considered**: borrar y reescribir todo el CSV — pierde filas ajenas; append
  ciego — duplica.
- **Implementation**: `resumenes.py` (`procesar`, `CSV_LOCK`).

## R12. `--poll` como respaldo, no como flujo principal

- **Decision**: comando manual que busca conversaciones de las últimas 24 horas con
  `call_control_id`, mensajes y sin fila en el CSV.
- **Rationale**: el túnel es el componente más frágil. Una recuperación idempotente de un comando
  evita montar una cola o un worker persistente.
- **Alternatives considered**: cola con reintentos — infraestructura; cron automático — no se
  implementó, pero el comando es compatible con él.
- **Implementation**: `resumenes.py` (`poll`).

## R13. Voz, ASR y modelo del assistant

- **Decision**: voz `Azure.es-CL-LorenzoNeural`, modelo `moonshotai/Kimi-K2.6`, ASR
  `deepgram/flux` en `es`, supresión de ruido `krisp`, sin grabación.
- **Rationale**: acento chileno creíble para el contexto, ASR robusto en audio telefónico y un
  modelo rápido/barato para diálogo corto. Sin grabación se reduce costo y exposición de datos.
- **Alternatives considered**: voz neutra en español — menos natural para un paciente chileno;
  grabar audio — costo, almacenamiento y privacidad; modelos mayores — latencia y costo sin
  mejora clara en un guion acotado.
- **Implementation**: `agente/assistant.py` (`VOICE`, `MODEL`, `transcription`,
  `telephony_settings`).

## R14. Secreto en la ruta en vez de firma Ed25519

- **Decision**: `POST /hook/<WEBHOOK_SECRET>` con comparación de tiempo constante; cualquier otra
  ruta responde 404.
- **Rationale**: es la protección mínima viable y no requiere gestionar la clave pública de la
  cuenta. Se reconoce como deuda, no como solución definitiva.
- **Alternatives considered**: verificar la firma Ed25519 de Telnyx — pendiente, especificado en
  `specs/002-firma-webhook-ed25519/spec.md`; exponer el webhook sin secreto — descartado.
- **Implementation**: `webhook/server.py` (`do_POST`).

## R15. Insights nativos activados pero no consumidos

- **Decision**: enviar `insight_settings.insight_group_id` al assistant, sin leer insights desde
  el CSV.
- **Rationale**: deja la información disponible en el portal para revisión humana, pero el
  archivo no depende de una API que no los expone.
- **Alternatives considered**: depender de insights para el resumen — la API no los entrega;
  desactivarlos — se pierde visibilidad en el portal.
- **Implementation**: `agente/assistant.py` (`INSIGHT_GROUP_ID`).
