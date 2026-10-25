# Feature Specification: Catálogo de exámenes y agendamiento

**Feature Branch**: `003-multi-examen-y-agendamiento`

**Created**: 2026-10-25

**Status**: Borrador (no implementado)

**Input**: Deuda registrada en `specs/001-cotizador-voz/spec.md`: hoy se cotiza un examen por
llamada, pasado a mano, y el agente no agenda.

## Alcance

Extender el cotizador para trabajar con varios exámenes y cerrar el ciclo hasta la hora agendada.

- Catálogo de exámenes con nombre canónico, sinónimos y preparación esperada.
- Corrida por lote: una lista de exámenes y/o centros, con una llamada por combinación.
- Registro del resultado por examen, no solo por llamada.
- Agendamiento: si el centro ofrece hora, el agente puede reservarla o dejar el siguiente paso
  concreto, según lo que el operador defina.

## User Scenarios & Testing *(borrador)*

### User Story 1 - Cotizar varios exámenes (Priority: P1)

Como operador, quiero lanzar una corrida con varios exámenes sin editar código, para comparar
precios de un estudio completo.

**Independent Test**: una corrida de dos exámenes produce dos llamadas y dos filas diferenciadas
por examen.

### User Story 2 - Agendar la hora (Priority: P2)

Como operador, quiero que una cotización favorable termine en una hora reservada, para no volver a
llamar.

**Independent Test**: una conversación donde el centro ofrece hora deja una reserva confirmada o
un siguiente paso verificable.

## Requirements *(borrador)*

- **FR-001**: El examen MUST validarse contra un catálogo antes de marcar.
- **FR-002**: Una corrida MUST poder incluir varios exámenes y MUST registrar cada resultado por
  separado.
- **FR-003**: El catálogo MUST indicar la preparación esperada para contrastarla con lo que dice el
  centro.
- **FR-004**: El agente MUST poder agendar solo si el operador habilitó esa acción para la corrida.
- **FR-005**: Toda reserva MUST quedar registrada con fecha, hora, centro y confirmación.
- **FR-006**: El sistema MUST NOT agendar sin confirmación explícita del centro.

## Success Criteria *(borrador)*

- **SC-001**: Una corrida de N exámenes produce N filas, sin intervención manual entre llamadas.
- **SC-002**: Cero reservas inventadas: toda hora agendada tiene confirmación del centro en la
  transcripción.
- **SC-003**: El catálogo se puede extender sin tocar el guion ni el webhook.

## Preguntas abiertas

- ¿El catálogo vive en un CSV/JSON local o en Telnyx?
- ¿El agendamiento es una conversación o un handoff a una persona?
- ¿Qué pasa si el centro pide datos del paciente (RUT, previsión) que el agente no tiene?
- ¿Cómo se evita agendar dos veces el mismo examen en la misma corrida?
