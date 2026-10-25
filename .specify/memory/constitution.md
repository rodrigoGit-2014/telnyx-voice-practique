# Cotizador de Exámenes por Voz Constitution

## Core Principles

### I. Un Solo Proveedor, Cero SDKs (NON-NEGOTIABLE)

Todo el stack de voz MUST resolverse con la API de Telnyx: telefonía (Call Control),
síntesis de voz, transcripción (ASR) y resumen (LLM). El proyecto MUST NOT incorporar SDKs de
Telnyx ni de terceros, ni API keys adicionales (OpenAI, Deepgram, ElevenLabs, etc.). Las
llamadas HTTP se hacen con la librería estándar de Python (`urllib`), centralizadas en
`agente/telnyx_api.py`. Cualquier capacidad nueva se evalúa primero contra la API de Telnyx.

**Rationale**: una sola factura, una sola credencial y una superficie de dependencias mínima.
El proyecto debe poder correr con Python 3.9+ y un único binario externo (`cloudflared`).

### II. Guion Único y Versionado

`agente/assistant.py` es la única fuente de verdad del comportamiento conversacional
(`INSTRUCTIONS`, `GREETING`, voz, modelo y límites). El examen se interpola exclusivamente con
`render()` sobre el marcador `<<EXAMEN>>`. El guion MUST NOT duplicarse en el webhook, en el
README ni en prompts auxiliares. Cambiar el guion exige: editar `assistant.py`, re-ejecutar
`python3 agente/assistant.py "<EXAMEN>"` y validar una llamada real de punta a punta antes de
considerar el cambio terminado.

**Rationale**: el assistant persistente y el dial envían el mismo guion; si divergen, la llamada
suena distinta según el camino. Una sola definición también hace auditable qué se le dice al
centro de exámenes.

### III. Registro Durable de Cada Llamada

Toda llamada que genere una conversación MUST terminar archivada como una fila en
`data/llamadas.csv` y un archivo en `data/llamadas/AAAA-MM-DD-<id8>.md`. `conversation_id` es
la clave idempotente: reprocesar MUST actualizar la fila existente, nunca duplicarla. La caída
del webhook o del túnel no pierde datos: `python3 resumenes.py --poll` es el mecanismo oficial
de recuperación. El CSV y el Markdown son el histórico; no hay base de datos.

**Rationale**: el valor del sistema es la evidencia de la cotización. Un dato perdido por un
túnel efímero es un fallo del producto, no un detalle operativo.

### IV. Secretos y Datos Personales Fuera del Repositorio

`TELNYX_API_KEY`, `WEBHOOK_SECRET`, `.env` y `.tunnel_url` MUST NOT versionarse ni imprimirse
en logs. La API key se lee solo desde el entorno. El webhook MUST validar el secreto de ruta con
comparación de tiempo constante (`hmac.compare_digest`) y responder 404 a rutas desconocidas.
`data/` contiene teléfonos y transcripciones reales: MUST tratarse como información sensible y
no publicarse.

**Rationale**: el repositorio puede compartirse o subirse sin filtrar credenciales ni
conversaciones de pacientes. La firma Ed25519 del webhook es deuda reconocida, no una licencia
para exponer el endpoint.

### V. Fidelidad al Dominio

El agente habla español de Chile y se presenta como paciente, nunca como IA, bot o asistente
virtual. MUST NOT inventar precios, coberturas, tramos, planes ni disponibilidad: si un dato no
se entrega, se declara como no informado. Los montos se repiten para confirmarlos y se archivan
como texto, tal como los dijo el centro. Las salidas usan `no informado` / `no atiende` de forma
consistente.

**Rationale**: una cotización inventada es peor que una cotización incompleta. El sistema existe
para reducir el costo de averiguar precios reales, no para estimarlos.

## Restricciones Técnicas

- **Runtime**: Python 3.9+ sin dependencias de terceros. Único binario externo: `cloudflared`.
- **Transporte**: HTTP/JSON contra `https://api.telnyx.com/v2` con `Authorization: Bearer`.
- **Almacenamiento**: archivos planos (`CSV` + `Markdown`). Sin base de datos, sin cola, sin
  servidor de aplicaciones.
- **Concurrencia**: un operador y una llamada a la vez. El webhook atiende en hilos, pero el
  archivado se serializa con un lock.
- **Límites de llamada**: `time_limit_secs = 600`; duración objetivo menor a 4 minutos.
- **Túnel**: URL efímera de `trycloudflare.com`. `.tunnel_url` manda sobre `PUBLIC_URL`.
- **Modelos**: voz, LLM y ASR se cambian solo en `assistant.py` / `resumenes.py`, no por
  variables de entorno.

## Flujo de Desarrollo

1. **Constitución → spec → plan → tasks → implementación.** Ningún cambio de comportamiento
   empieza por el código: primero se ajusta la spec y se verifica el Constitution Check del plan.
2. **Cambios de guion**: editar `assistant.py`, re-ejecutar el alta del assistant y hacer una
   llamada de prueba. El criterio de aceptación es el Markdown resultante.
3. **Cambios de archivado**: validar con `--reprocess <conversation_id>` sobre una conversación
   existente antes de tocar una llamada real.
4. **Cambios de webhook**: probar `GET /health`, un `POST` con secreto incorrecto (404) y un
   evento sintético antes de exponer el túnel.
5. **Verificación E2E manual** según `specs/001-cotizador-voz/quickstart.md`. No hay suite
   automatizada; la ausencia de tests es deuda explícita, no permiso para saltarse la validación.
6. **Commit**: nunca incluir `.env`, `.tunnel_url` ni `data/`. Un commit por cambio lógico.

## Governance

Esta constitución prevalece sobre cualquier otra práctica del proyecto. Toda spec y todo plan
MUST incluir un Constitution Check; una violación solo se acepta si `plan.md` la justifica en
Complexity Tracking con una alternativa más simple descartada. Las enmiendas requieren: propuesta
escrita, bump de versión semántica (MAJOR si se elimina o redefine un principio, MINOR si se
agrega, PATCH si se aclara), actualización de la línea de versión y revisión del impacto en las
specs activas. La versión de este documento es la que aparece al pie y MUST coincidir con la
referenciada en los planes.

**Version**: 1.0.0 | **Ratified**: 2026-10-25 | **Last Amended**: 2026-10-25
