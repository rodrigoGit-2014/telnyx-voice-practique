# Tasks: Cotizador de exámenes por voz

**Input**: Design documents from `specs/001-cotizador-voz/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: no hay tests automatizados en el proyecto. La validación es manual y está en
`quickstart.md`; la falta de suite se registra como deuda en la Fase 7.

**Organización**: tareas agrupadas por historia de usuario. `[x]` = ya implementado y verificado
por lectura del código; `[ ]` = deuda conocida, no implementada. Esta es una reconstrucción
inversa: ninguna tarea de las fases 1 a 6 se ejecutó en esta sesión.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: podría ejecutarse en paralelo (archivos distintos, sin dependencia)
- **[Story]**: US1, US2, US3
- Las rutas son exactas, relativas a la raíz del proyecto

## Path Conventions

Proyecto único sin `src/` ni `tests/`:

- `agente/` — lo que se envía a Telnyx
- `webhook/` — lo que se recibe de Telnyx
- `resumenes.py` — derivación y archivado
- `data/` — salida (no versionar)
- `tunel.sh` — exposición local

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: estructura mínima y configuración compartida.

- [x] T001 Crear la estructura del proyecto (`agente/`, `webhook/`, `data/`) en la raíz
- [x] T002 Implementar el cargador de `.env` y los helpers `get`, `public_url`, `set_env` en `agente/config.py`
- [x] T003 Definir las claves de configuración (`TELNYX_API_KEY`, `TELNYX_FROM`, `TELNYX_TO`, `TELNYX_CONNECTION_ID`, `ASSISTANT_ID`, `WEBHOOK_SECRET`, `PORT`) y documentarlas en `README.md`
- [x] T004 Escribir `tunel.sh`: lanzar `cloudflared`, esperar la URL, escribir `.tunnel_url`, correr el webhook y limpiar procesos al salir

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: cliente de Telnyx y definición del assistant. Bloquea las tres historias.

**⚠️ CRITICAL**: ninguna historia puede implementarse sin esta fase.

- [x] T005 [P] Implementar `request()` con `urllib`, headers Bearer y timeout en `agente/telnyx_api.py`
- [x] T006 [P] Implementar `TelnyxError`, traducción de `HTTPError`/`URLError` y helpers `get_json`, `post`, `patch` en `agente/telnyx_api.py`
- [x] T007 Implementar `unwrap()` para respuestas con y sin envoltorio `data` en `agente/telnyx_api.py`
- [x] T008 Implementar `llm()` contra `/ai/openai/chat/completions` en `agente/telnyx_api.py`
- [x] T009 Definir `ASSISTANT_NAME`, `MODEL`, `VOICE` e `INSIGHT_GROUP_ID` en `agente/assistant.py`
- [x] T010 Escribir `INSTRUCTIONS` y `GREETING` con el marcador `<<EXAMEN>>` en `agente/assistant.py`
- [x] T011 Implementar `render()` como única interpolación del examen en `agente/assistant.py`
- [x] T012 Implementar `build_payload()` con tools, voz, transcripción, telefonía e insights en `agente/assistant.py`
- [x] T013 Implementar el alta/actualización del assistant y la persistencia de `ASSISTANT_ID` en `agente/assistant.py` (`main`) y `agente/config.py` (`set_env`)

**Checkpoint**: se puede crear un assistant válido en Telnyx.

---

## Phase 3: User Story 1 - Llamada de cotización con voz natural (Priority: P1) 🎯 MVP

**Goal**: originar una llamada en la que el agente conversa y obtiene los seis datos.

**Independent Test**: `python3 agente/llamar.py --examen "PET-CT"` con el túnel arriba produce
una llamada completa y natural.

### Implementation for User Story 1

- [x] T014 [P] [US1] Implementar el payload de `POST /calls` (connection, from, to, timeout) en `agente/llamar.py`
- [x] T015 [P] [US1] Codificar `client_state` en base64 con el examen en `agente/llamar.py` (`b64`)
- [x] T016 [US1] Enganchar el assistant (id + instructions + greeting renderizados) en el mismo dial en `agente/llamar.py`
- [x] T017 [US1] Implementar el preflight de `public_url()` y `GET /health` antes de marcar en `agente/llamar.py` (`servidor_arriba`)
- [x] T018 [US1] Construir `webhook_url` con el secreto de ruta en `agente/llamar.py`
- [x] T019 [US1] Agregar `--examen`, `--to` y `--timeout` con defaults en `agente/llamar.py`
- [x] T020 [US1] Redactar el guion conversacional: una pregunta por turno, orden de los seis datos, confirmación de montos y prohibición de inventar en `agente/assistant.py` (`INSTRUCTIONS`)
- [x] T021 [US1] Redactar el saludo de paciente en español de Chile en `agente/assistant.py` (`GREETING`)
- [x] T022 [US1] Configurar la tool `hangup` en `agente/assistant.py` (`build_payload`)
- [x] T023 [US1] Configurar voz, velocidad, audio de fondo, ASR, supresión de ruido, límite de 600 s y grabación desactivada en `agente/assistant.py`
- [x] T024 [US1] Imprimir `call_control_id` y el siguiente paso al operador en `agente/llamar.py`

**Checkpoint**: US1 usable de punta a punta, aunque todavía no archive nada.

---

## Phase 4: User Story 2 - Archivo automático al colgar (Priority: P2)

**Goal**: al colgar, dejar una fila CSV y un Markdown con transcripción y resumen.

**Independent Test**: una llamada deja `data/llamadas.csv` y
`data/llamadas/AAAA-MM-DD-<id8>.md`; `--reprocess` no duplica.

### Implementation for User Story 2

- [x] T025 [P] [US2] Implementar el servidor HTTP con `/health`, ruta secreta y ACK temprano en `webhook/server.py`
- [x] T026 [P] [US2] Procesar eventos en hilo aparte con captura de excepciones en `webhook/server.py` (`_seguro`)
- [x] T027 [US2] Mantener el mapa `call_control_id → conversation_id` en `webhook/server.py` (`CONVERSACIONES`)
- [x] T028 [US2] Implementar el despacho de eventos (`initiated`, `conversation.created`, `start_failed`, `conversation.ended`, `hangup`) en `webhook/server.py` (`procesar_evento`)
- [x] T029 [US2] Colgar la pierna en `conversation.ended` y `start_failed` en `webhook/server.py` (`colgar`)
- [x] T030 [US2] Disparar el archivado en `call.hangup` con espera de 2 s en `webhook/server.py` (`recolectar`)
- [x] T031 [P] [US2] Implementar `obtener_mensajes()` con paginación de 100 y orden por `created_at` en `resumenes.py`
- [x] T032 [US2] Implementar `construir_transcripcion()` con etiquetas paciente/centro en `resumenes.py`
- [x] T033 [US2] Implementar `duracion_seg()` a partir de los timestamps en `resumenes.py`
- [x] T034 [US2] Escribir `SUMMARY_PROMPT` con las nueve claves y la regla de `no informado` en `resumenes.py`
- [x] T035 [US2] Implementar `resumir()` con extracción tolerante del JSON en `resumenes.py`
- [x] T036 [US2] Implementar `leer_csv`, `escribir_csv` y `CSV_LOCK` con las 15 columnas en `resumenes.py`
- [x] T037 [US2] Implementar el upsert idempotente por `conversation_id` en `resumenes.py` (`procesar`)
- [x] T038 [US2] Implementar `guardar_markdown()` con resumen, datos capturados y transcripción en `resumenes.py`
- [x] T039 [US2] Reintentar el archivado 3 veces con 5 s y dejar pendiente para `--poll` en `webhook/server.py` (`recolectar`)

**Checkpoint**: US1 y US2 funcionan juntas; el histórico ya tiene valor.

---

## Phase 5: User Story 3 - Recuperación de llamadas no archivadas (Priority: P3)

**Goal**: recuperar conversaciones cuyo webhook no llegó a archivar.

**Independent Test**: una conversación sin fila se archiva con `--poll`; la segunda ejecución
dice `Sin llamadas nuevas`.

### Implementation for User Story 3

- [x] T040 [P] [US3] Implementar `listar_conversaciones()` con `page[size]` en `resumenes.py`
- [x] T041 [US3] Implementar `buscar_por_call_control()` con 18 intentos cada 5 s en `resumenes.py`
- [x] T042 [US3] Implementar `poll()` con filtros de ventana, `call_control_id`, mensajes y fila existente en `resumenes.py`
- [x] T043 [US3] Implementar `--poll`, `--horas` y `--reprocess` con argparse en `resumenes.py` (`main`)
- [x] T044 [US3] Ignorar conversaciones de chat y conversaciones sin mensajes en `resumenes.py` (`poll`)
- [x] T045 [US3] Reportar `OK`/`ERR` por conversación sin abortar el lote en `resumenes.py` (`poll`)

**Checkpoint**: las tres historias funcionan y el sistema tolera la caída del túnel.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: operación, diagnóstico y documentación.

- [x] T046 [P] Documentar instalación, flujo, uso, salida y limitaciones en `README.md`
- [x] T047 [P] Agregar logs con hora local y sin secretos en `webhook/server.py` (`log`)
- [x] T048 Ignorar el error `90018` al colgar una llamada ya cortada en `webhook/server.py` (`colgar`)
- [x] T049 Tolerar payload inválido y excepciones no controladas sin caer el webhook en `webhook/server.py`
- [x] T050 Documentar los contratos de API, webhook, CLI y archivos en `specs/001-cotizador-voz/contracts/`
- [x] T051 Documentar la validación manual E2E en `specs/001-cotizador-voz/quickstart.md`
- [x] T052 Fijar la constitución del proyecto en `.specify/memory/constitution.md`

---

## Phase 7: Deuda conocida (no implementada)

**Purpose**: brechas identificadas en la reconstrucción. No forman parte del MVP actual.

- [ ] T053 [P] Validar la firma Ed25519 del webhook y rechazar eventos no firmados (`specs/002-firma-webhook-ed25519/`)
- [ ] T054 [P] Agregar tests de contrato para los payloads de Telnyx y del webhook en `tests/contract/`
- [ ] T055 Agregar tests de integración para el flujo llamada → colgado → CSV/MD en `tests/integration/`
- [ ] T056 Reemplazar el túnel efímero por un webhook con URL estable y despliegue persistente
- [ ] T057 Consumir insights nativos de Telnyx vía API y contrastarlos con el resumen del LLM
- [ ] T058 Mover `INSIGHT_GROUP_ID` a configuración por entorno en `agente/assistant.py`
- [ ] T059 Agregar catálogo de exámenes y corrida por lote (`specs/003-multi-examen-y-agendamiento/`)
- [ ] T060 Implementar agendamiento de hora cuando el centro lo ofrece (`specs/003-...`)
- [ ] T061 Detectar buzón de voz, IVR y número equivocado antes de ejecutar el guion
- [ ] T062 Implementar rotación de `WEBHOOK_SECRET` sin cortar el servicio
- [ ] T063 Agregar `.gitignore` para `.env`, `.tunnel_url`, `data/` y `.opencode/` antes del primer commit
- [ ] T064 Soportar más de una llamada concurrente (estado persistente en vez de memoria)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sin dependencias.
- **Foundational (Fase 2)**: depende de Setup; bloquea US1, US2 y US3.
- **US1 (Fase 3)**: depende de Fase 2; puede entregarse sola (MVP conversacional).
- **US2 (Fase 4)**: depende de Fase 2; necesita una conversación real de US1 para validarse.
- **US3 (Fase 5)**: depende de Fase 4 (reutiliza `procesar()` y el CSV).
- **Polish (Fase 6)**: transversal; se puede hacer en paralelo desde la Fase 3.
- **Deuda (Fase 7)**: posterior a la validación del MVP.

### User Story Dependencies

- **US1 (P1)**: independiente; entrega una llamada que cotiza.
- **US2 (P2)**: depende de US1 para generar la conversación, pero su implementación (webhook +
  archivado) es independiente y testeable con una conversación existente.
- **US3 (P3)**: depende de US2 porque reutiliza el mismo archivado.

### Within Each User Story

- Cliente y configuración antes del assistant.
- Assistant antes del dial.
- Dial antes del webhook.
- Webhook antes del archivado.
- Archivado antes de `--poll`.
- Validar cada checkpoint con `quickstart.md` antes de avanzar.

### Parallel Opportunities

- T005, T006 y T009–T012 son paralelizables dentro de la Fase 2.
- T014, T015 y T025, T026, T031 son paralelizables dentro de su fase.
- US1 y la infraestructura de US2 pueden avanzar en paralelo una vez cerrada la Fase 2.
- La documentación (T046, T050, T051) puede escribirse en paralelo con la implementación.

---

## Parallel Example: Foundational

```text
Task: "Implementar request() con urllib en agente/telnyx_api.py"
Task: "Definir ASSISTANT_NAME, MODEL, VOICE e INSIGHT_GROUP_ID en agente/assistant.py"
Task: "Escribir INSTRUCTIONS y GREETING con <<EXAMEN>> en agente/assistant.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Fase 1: Setup.
2. Fase 2: cliente + assistant (bloqueante).
3. Fase 3: llamada completa.
4. **STOP and VALIDATE**: Escenario 2 de `quickstart.md`. Si la conversación no es natural o
   inventa datos, no avanzar.

### Incremental Delivery

1. US1 → llamada que cotiza (valor: ahorra el marcado).
2. US2 → histórico CSV/MD (valor: comparación entre centros).
3. US3 → recuperación (valor: confiabilidad ante el túnel).
4. Fase 7 → firma, tests y URL estable (valor: producción).

### Reconstruction Order

Para replicar el proyecto desde cero, seguir el orden de las fases. Para auditarlo, leer en orden
inverso: `tasks.md` → `spec.md` → código. Cada tarea `[x]` debe tener una función o archivo que la
respalde; si no lo tiene, la tarea está mal clasificada.

---

## Trazabilidad requisito → tarea

| Requisitos | Tareas | Archivo |
|---|---|---|
| FR-001–FR-004 | T009–T013, T022, T023 | `agente/assistant.py` |
| FR-005–FR-006 | T002, T003, T013 | `agente/config.py` |
| FR-007–FR-010 | T014–T019, T024 | `agente/llamar.py` |
| FR-011–FR-014 | T020, T021 | `agente/assistant.py` |
| FR-015–FR-021 | T025–T030, T039, T048, T049 | `webhook/server.py` |
| FR-022–FR-026 | T031–T035 | `resumenes.py` |
| FR-027–FR-031 | T036–T038, T042, T045 | `resumenes.py`, `webhook/server.py` |
| SC-001–SC-008 | T050, T051 | `contracts/`, `quickstart.md` |

## Notes

- `[x]` significa "existe en el código", no "pasó una suite". La única evidencia de ejecución es
  la llamada de ejemplo en `data/llamadas/2026-10-25-21109129.md`.
- No hay tests que ejecutar antes de implementar; la deuda T054–T055 es explícita.
- Evitar duplicar el guion fuera de `agente/assistant.py` (Principio II).
- Nunca commitear `.env`, `.tunnel_url` ni `data/` (Principio IV).
- Un cambio de comportamiento empieza en `spec.md`, no en el código.
