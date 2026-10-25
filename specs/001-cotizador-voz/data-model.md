# Data Model: Cotizador de exámenes por voz

**Feature**: `001-cotizador-voz` | **Fecha**: 2026-10-25

Modelo reconstruido desde el código. Las entidades marcadas **externas** viven en Telnyx; las
**locales** viven en el sistema de archivos del proyecto. No hay base de datos.

## Entidades externas (Telnyx)

### Assistant

Recurso persistente que define cómo habla el agente. Se crea o actualiza con
`agente/assistant.py` y su id se guarda en `ASSISTANT_ID`.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | string | Generado por Telnyx; se persiste en `.env` |
| `name` | string | `Cotizador Exámenes - Rodrigo (saliente)` |
| `description` | string | Texto fijo del cotizador |
| `model` | string | `moonshotai/Kimi-K2.6` |
| `instructions` | string | Guion con `<<EXAMEN>>` reemplazado antes de enviar |
| `greeting` | string | Saludo con `<<EXAMEN>>` reemplazado antes de enviar |
| `enabled_features` | string[] | `["telephony"]` |
| `tools` | object[] | `[{"type": "hangup", "hangup": {}}]` |
| `voice_settings.voice` | string | `Azure.es-CL-LorenzoNeural` |
| `voice_settings.voice_speed` | number | `1` |
| `voice_settings.background_audio` | object | `silence`, volumen `0.4` |
| `transcription.model` | string | `deepgram/flux` |
| `transcription.language` | string | `es` |
| `telephony_settings.noise_suppression` | string | `krisp` |
| `telephony_settings.time_limit_secs` | integer | `600` |
| `telephony_settings.recording_settings.enabled` | boolean | `false` |
| `insight_settings.insight_group_id` | string (UUID) | Grupo de insights de la cuenta |

**Regla**: el guion es la única fuente de verdad; `assistant.py` lo renderiza y `llamar.py` lo
reenvía en cada dial. Si se edita el guion, hay que volver a ejecutar el alta del assistant.

### Llamada (Call Control)

Solicitud de marcado creada por `POST /calls`.

| Campo | Tipo | Regla |
|---|---|---|
| `call_control_id` | string | Identificador de la pierna; clave del mapa de conversaciones |
| `connection_id` | string | App de Call Control; desde `TELNYX_CONNECTION_ID` |
| `from` | string E.164 | Número de origen; desde `TELNYX_FROM` |
| `to` | string E.164 | Destino; `--to` o `TELNYX_TO` |
| `timeout_secs` | integer | Timbrado; default `45` |
| `webhook_url` | string | `<public_url>/hook/<WEBHOOK_SECRET>` |
| `client_state` | string base64 | JSON `{"examen": "<nombre>"}` |
| `assistant.id` | string | `ASSISTANT_ID` |
| `assistant.instructions` | string | Guion renderizado |
| `assistant.greeting` | string | Saludo renderizado |

### Conversación

Registro de la interacción de voz. Es la unidad de archivado.

| Campo | Tipo | Regla |
|---|---|---|
| `id` | string (UUID v4) | Clave idempotente del CSV; `conversation_id` |
| `created_at` | string ISO-8601 | Se convierte a hora local para `fecha_hora` |
| `metadata.call_control_id` | string | Vincula la conversación con la llamada; obligatorio para archivar |
| `number_of_messages` | integer | `0` o ausente ⇒ no se archiva en `--poll` |
| `messages` | Mensaje[] | Se obtienen paginados; no vienen en el objeto de conversación |

### Mensaje

| Campo | Tipo | Regla |
|---|---|---|
| `role` | string | `assistant` ⇒ `Rodrigo (paciente)`; `user` ⇒ `Centro`; otros se descartan |
| `text` | string | Si está vacío, se omite de la transcripción |
| `created_at` | string ISO-8601 | Orden de la transcripción y cálculo de duración |
| `sent_at` | string ISO-8601 | Alternativa para calcular duración |
| `ended_at` | string ISO-8601 | Alternativa para calcular duración |

**Regla de duración**: se usan todas las marcas disponibles; si hay menos de dos, la duración es
`0`.

## Entidades locales (archivos)

### Configuración

| Variable | Obligatoria | Origen | Uso |
|---|---|---|---|
| `TELNYX_API_KEY` | sí | `.env` | Autenticación Bearer en toda la API |
| `TELNYX_FROM` | sí | `.env` | Número que marca |
| `TELNYX_TO` | sí | `.env` | Destino por defecto |
| `TELNYX_CONNECTION_ID` | sí | `.env` | App Call Control para originar |
| `ASSISTANT_ID` | sí (para llamar) | `.env`, lo escribe `assistant.py` | Assistant que habla |
| `WEBHOOK_SECRET` | sí | `.env` | Secreto de ruta del webhook |
| `PORT` | no (8000) | `.env` | Puerto local del webhook |
| `PUBLIC_URL` | no | `.env` | Respaldo si no existe `.tunnel_url` |
| `.tunnel_url` | no | archivo | URL efímera; prioridad sobre `PUBLIC_URL` |

**Regla**: `config.get(nombre, required=True)` termina con mensaje accionable si falta. `.env`
nunca se versiona.

### Resumen (salida del LLM)

Objeto JSON de exactamente nueve claves. El prompt exige JSON en una línea, sin markdown; el
parser tolera texto alrededor.

| Clave | Tipo | Valores / regla |
|---|---|---|
| `examen` | string | Examen consultado; se sobrescribe con el examen del `client_state` si existe |
| `lo_realizan` | enum | `si` \| `no` \| `no_se_sabe` |
| `precio_particular` | string | Monto como texto (ej. `142.500 pesos`) o `no informado` |
| `fonasa` | string | Tramos/valores, `no atienden` o `no informado` |
| `isapre` | string | Planes/coberturas, `no atienden` o `no informado` |
| `disponibilidad` | string | Texto o `no informado` |
| `preparacion` | string | Texto o `no informado` |
| `resumen` | string | 2 a 3 frases en español neutro |
| `siguiente_paso` | string | Acción concreta recomendada al paciente |

**Regla**: si el LLM devuelve un valor no-string, se serializa a JSON antes de escribir el CSV.
No se permiten montos numéricos: el CSV guarda texto para no perder matices (`desde`, `aprox.`).

### FilaLlamada (CSV)

Una fila por `conversation_id` en `data/llamadas.csv`, con estas 15 columnas en orden fijo:

| # | Columna | Tipo | Regla |
|---|---|---|---|
| 1 | `fecha_hora` | string | `YYYY-MM-DD HH:MM:SS`, hora local de `created_at` |
| 2 | `conversation_id` | string | Clave única; si existe, se reemplaza la fila |
| 3 | `call_control_id` | string | Desde `metadata.call_control_id` |
| 4 | `telefono` | string | `TELNYX_TO`; los llamadores actuales no pasan el `to` real de la llamada |
| 5 | `duracion_seg` | integer | Derivado de los mensajes; `0` si no se puede calcular |
| 6 | `examen` | string | Del `client_state`; si no, del resumen |
| 7 | `lo_realizan` | enum | `si` \| `no` \| `no_se_sabe` |
| 8 | `precio_particular` | string | Texto o `no informado` |
| 9 | `fonasa` | string | Texto, `no atienden` o `no informado` |
| 10 | `isapre` | string | Texto, `no atienden` o `no informado` |
| 11 | `disponibilidad` | string | Texto o `no informado` |
| 12 | `preparacion` | string | Texto o `no informado` |
| 13 | `resumen` | string | 2 a 3 frases |
| 14 | `siguiente_paso` | string | Acción recomendada |
| 15 | `archivo_md` | string | Ruta relativa a la raíz, ej. `data/llamadas/2026-10-25-21109129.md` |

**Invariantes**: encoding UTF-8; encabezado siempre presente; escritura serializada con
`CSV_LOCK`; columnas faltantes se escriben vacías; el orden de columnas no cambia sin migración.

### ArchivoMarkdown

Un archivo por conversación en `data/llamadas/AAAA-MM-DD-<id8>.md`, donde `AAAA-MM-DD` sale de
`fecha_hora` y `<id8>` son los primeros 8 caracteres de `conversation_id`.

Estructura obligatoria:

1. `# Llamada <fecha_hora>`
2. Metadatos: duración en segundos, teléfono y `conversation_id` entre backticks.
3. `## Resumen` con el texto del LLM.
4. `## Datos capturados` con los ocho campos (examen, ¿lo realizan?, precio, Fonasa, Isapre,
   disponibilidad, preparación, siguiente paso).
5. `## Transcripción` en bloque de código, con líneas `Rodrigo (paciente): ...` y `Centro: ...`.

## Transiciones de estado

### Llamada

```text
iniciada ──> timbrando ──> contestada ──> conversación creada ──> en curso
                                                   │
                                                   ├── start_failed ──> colgada
                                                   └── ended ──> colgada por webhook
                                                                       │
                                                                       v
                                                                  call.hangup
                                                                       │
                                                                       v
                                                                   archivada
```

- `call.initiated`: solo se registra en el log.
- `call.conversation.created`: se guarda `call_control_id → conversation_id` en memoria.
- `call.conversation.start_failed`: se cuelga la llamada.
- `call.conversation.ended`: se cuelga la pierna (workaround de Call Control).
- `call.hangup`: se dispara el archivado tras 2 segundos.
- Sin `call.hangup` (túnel caído): la conversación queda pendiente hasta `--poll`.

### Archivado

```text
pendiente ──> en proceso ──> archivada
                    │
                    ├── error transitorio ──> reintento (máx. 3, 5 s)
                    └── error definitivo ──> pendiente para --poll
```

- El estado no se persiste: se deduce de la existencia de la fila en el CSV.
- `procesar()` es idempotente por `conversation_id`.
- `--poll` solo considera conversaciones de las últimas 24 horas (configurable), con
  `call_control_id`, con mensajes y sin fila.

## Relaciones

```text
Examen 1 ──> N Llamada
Llamada 1 ──> 1 Conversación        (vía metadata.call_control_id)
Conversación 1 ──> N Mensaje
Conversación 1 ──> 1 Resumen        (derivado)
Conversación 1 ──> 1 FilaLlamada
Conversación 1 ──> 1 ArchivoMarkdown
Assistant 1 ──> N Llamada           (vía ASSISTANT_ID)
```

## Datos personales

`data/llamadas.csv` y `data/llamadas/*.md` contienen número telefónico y transcripción de una
conversación real. Deben tratarse como información sensible: no se versionan, no se publican y no
se comparten fuera del entorno del operador.
