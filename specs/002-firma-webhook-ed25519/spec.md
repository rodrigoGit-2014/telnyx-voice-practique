# Feature Specification: Verificación Ed25519 del webhook

**Feature Branch**: `002-firma-webhook-ed25519`

**Created**: 2026-10-25

**Status**: Borrador (no implementado)

**Input**: Deuda registrada en `specs/001-cotizador-voz/spec.md` (Limitaciones) y en
`contracts/webhook.md`: el webhook solo se protege con un secreto en la ruta.

## Alcance

Validar criptográficamente que cada evento recibido fue emitido por Telnyx, sin depender de que la
URL del túnel se mantenga secreta.

- Verificar la firma Ed25519 del encabezado `telnyx-signature-ed25519` contra
  `telnyx-timestamp` y el cuerpo crudo del request.
- Rechazar eventos con firma ausente, inválida o con timestamp fuera de la ventana aceptada.
- Mantener `GET /health` sin autenticación.
- Conservar el secreto de ruta como defensa en profundidad, o justificar su eliminación.

## User Scenarios & Testing *(borrador)*

### User Story 1 - Solo eventos auténticos (Priority: P1)

Como operador, quiero que el webhook descarte eventos que no provengan de Telnyx, para que nadie
pueda inyectar llamadas ni forzar archivados.

**Independent Test**: enviar un evento con firma válida (aceptado) y el mismo cuerpo con firma
manipulada (rechazado), sin alterar llamadas reales.

**Acceptance Scenarios**:

1. **Given** un evento firmado correctamente, **When** llega al webhook, **Then** se procesa y
   responde 200.
2. **Given** un evento con firma inválida o ausente, **When** llega al webhook, **Then** responde
   401 y no se ejecuta ninguna acción.
3. **Given** un evento con timestamp antiguo, **When** llega al webhook, **Then** se rechaza por
   posible replay.

## Requirements *(borrador)*

- **FR-001**: El webhook MUST validar la firma Ed25519 sobre el cuerpo crudo antes de parsear JSON.
- **FR-002**: El webhook MUST verificar que el timestamp esté dentro de una ventana configurable.
- **FR-003**: El webhook MUST responder 401 ante firma o timestamp inválidos, sin filtrar detalles.
- **FR-004**: La clave pública MUST obtenerse de la cuenta de Telnyx y configurarse sin
  hardcodearla en el repositorio.
- **FR-005**: El cambio MUST NOT romper `/health`, el ACK rápido ni el archivado existente.

## Success Criteria *(borrador)*

- **SC-001**: El 100% de los eventos con firma alterada se rechaza.
- **SC-002**: El 100% de los eventos legítimos de Telnyx sigue archivando llamadas sin cambios en
  el CSV ni en el Markdown.
- **SC-003**: El rechazo ocurre antes de cualquier llamada a la API de Telnyx o al LLM.

## Preguntas abiertas

- ¿La clave pública se obtiene por API en cada arranque o se configura una vez en `.env`?
- ¿Cuál es la ventana de tolerancia de timestamp (60 s, 5 min)?
- ¿Se elimina el secreto de ruta o se mantiene como segunda capa?
- ¿Cómo se prueba la firma sin depender de una llamada real (fixture firmado)?
