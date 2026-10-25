# Implementation Plan: Cotizador de exámenes por voz

**Branch**: `001-cotizador-voz` | **Date**: 2026-10-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-cotizador-voz/spec.md`

**Note**: Plan reconstruido desde el código existente. No propone una arquitectura nueva: documenta
la que está en producción y la contrasta con la constitución del proyecto.

## Summary

Automatizar la cotización telefónica de exámenes médicos con un agente de voz alojado en Telnyx.
El operador crea un assistant persistente (`agente/assistant.py`), levanta un webhook local
expuesto por un túnel de Cloudflare (`tunel.sh` + `webhook/server.py`) y dispara la llamada con
`agente/llamar.py`, que engancha el assistant en el mismo `POST /calls` para que hable apenas
contestan. Al colgar, el webhook recupera la conversación, arma la transcripción paginada, la
resume con un LLM alojado en Telnyx y archiva una fila en `data/llamadas.csv` más un Markdown con
el detalle (`resumenes.py`). `--poll` recupera llamadas cuyo webhook no alcanzó a ejecutarse.

## Technical Context

**Language/Version**: Python 3.9+ (solo librería estándar; sin `requirements.txt`)

**Primary Dependencies**: ninguna de terceros. Binario externo: `cloudflared` (túnel). Servicio
externo: Telnyx API v2 (Call Control, AI Assistants, Conversations, chat completions).

**Storage**: sistema de archivos. `data/llamadas.csv` (histórico tabular),
`data/llamadas/AAAA-MM-DD-<id8>.md` (detalle + transcripción), `.env` (configuración),
`.tunnel_url` (URL efímera). Sin base de datos ni cola.

**Testing**: sin suite automatizada. Validación manual E2E documentada en
`specs/001-cotizador-voz/quickstart.md`; verificación puntual con `--reprocess`.

**Target Platform**: macOS o Linux local del operador, con salida a internet y túnel HTTP público
(`trycloudflare.com`). No hay despliegue en servidor.

**Project Type**: single project — CLI (`agente/`, `resumenes.py`) + webhook HTTP
(`webhook/server.py`).

**Performance Goals**: ACK del webhook < 1 s; archivado completo ≤ 60 s tras el colgado; llamada
≤ 600 s (`time_limit_secs`), con objetivo conversacional < 4 min.

**Constraints**: una llamada concurrente y un operador; sin SDKs ni API keys adicionales; el
túnel cambia de URL en cada arranque; `data/` contiene datos personales; el assistant no cierra
la pierna por sí solo en Call Control.

**Scale/Scope**: decenas de llamadas por día, ~30 mensajes por llamada, un destino configurable
(`TELNYX_TO`) y un número de origen (`TELNYX_FROM`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Evidencia / nota |
|---|---|---|
| I. Un solo proveedor, cero SDKs | PASS | Todo pasa por `agente/telnyx_api.py`; no hay SDKs ni claves de OpenAI/Deepgram. ASR, TTS y LLM son recursos de Telnyx. |
| II. Guion único y versionado | PASS | `INSTRUCTIONS` y `GREETING` viven solo en `agente/assistant.py`; `llamar.py` los importa y `render()` es la única interpolación. |
| III. Registro durable | PASS con deuda | CSV + MD por `conversation_id`; `--poll` recupera. La deuda es no tener tests que lo verifiquen automáticamente. |
| IV. Secretos y datos personales | PASS con deuda | `.env` y `.tunnel_url` fuera de control de versiones; secreto de ruta con `compare_digest`. Deuda: falta firma Ed25519 (spec 002). |
| V. Fidelidad al dominio | PASS | Guion en español de Chile, prohibición explícita de inventar datos y de declararse IA; el resumen usa `no informado`. Se cumple por prompt, no por validación de código. |

**Post-diseño**: sin cambios en el veredicto. Las dos deudas (tests y firma) quedan registradas en
"Limitaciones y fuera de alcance" de la spec y en la fase final de `tasks.md`; no bloquean el
MVP porque no afectan el flujo principal.

## Project Structure

### Documentation (this feature)

```text
specs/001-cotizador-voz/
├── plan.md              # Este archivo
├── spec.md              # Comportamiento observable (as-built)
├── research.md          # Decisiones técnicas y alternativas descartadas
├── data-model.md        # Entidades, campos y transiciones
├── quickstart.md        # Guía de validación E2E
├── contracts/
│   ├── telnyx-api.md    # Endpoints de Telnyx consumidos
│   ├── webhook.md       # Contrato HTTP entrante
│   ├── cli.md           # Comandos y argumentos
│   └── output-files.md  # Esquema del CSV y del Markdown
└── tasks.md             # Reconstrucción con tareas marcadas
```

### Source Code (repository root)

```text
agente/
├── __init__.py
├── assistant.py         # Guion, voz, modelo y alta/actualización del assistant
├── config.py            # .env, .tunnel_url y helpers de configuración
├── llamar.py            # POST /calls con assistant enganchado
└── telnyx_api.py        # Cliente HTTP mínimo, errores y helper de LLM

webhook/
└── server.py            # HTTP server, eventos de Call Control y archivado

resumenes.py             # Transcripción paginada, resumen LLM, CSV + Markdown
tunel.sh                 # cloudflared + webhook local
data/
├── llamadas.csv         # Histórico (15 columnas)
└── llamadas/            # Un Markdown por conversación
.env                     # Configuración sensible (no versionar)
.tunnel_url              # URL pública efímera (no versionar)
```

**Structure Decision**: proyecto único sin `src/` ni `tests/`. La separación es por
responsabilidad: `agente/` contiene lo que se envía a Telnyx, `webhook/` lo que se recibe,
`resumenes.py` lo que se deriva de la conversación. Se descartó una capa de servicios o un
framework web porque el volumen (una llamada a la vez) no la justifica; ver Principle I y V
(YAGNI) en la constitución.

## Phase 0: Outline & Research

**Output**: [research.md](./research.md)

Decisiones registradas: assistant enganchado en el dial, assistant persistente con guion
re-renderizado, stdlib `urllib`, `http.server` con hilos, `cloudflared` en vez de ngrok, colgar
desde el webhook, archivar en `call.hangup` con espera y reintentos, LLM alojado en Telnyx,
paginación de 100 mensajes, CSV + Markdown en vez de base de datos, `--poll` como respaldo e
idempotencia por `conversation_id`. No quedan preguntas abiertas.

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` completo.

**Outputs**:

- [data-model.md](./data-model.md): entidades, campos, reglas de validación y transiciones de
  estado de llamada y archivado.
- [contracts/telnyx-api.md](./contracts/telnyx-api.md): endpoints, payloads y errores.
- [contracts/webhook.md](./contracts/webhook.md): rutas, eventos, ACK y limitaciones de seguridad.
- [contracts/cli.md](./contracts/cli.md): comandos, argumentos, salidas y códigos de error.
- [contracts/output-files.md](./contracts/output-files.md): columnas del CSV, plantilla del
  Markdown y nombres de archivo.
- [quickstart.md](./quickstart.md): escenarios de validación con resultados esperados.

## Complexity Tracking

Sin violaciones de la constitución que justificar. No se agrega infraestructura (base de datos,
cola, framework web, SDK) más allá de la ya existente.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
