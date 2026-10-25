# Feature Specification: Cotizador de exámenes por voz

**Feature Branch**: `001-cotizador-voz`

**Created**: 2026-10-25

**Status**: Implementado (reconstruido desde el código)

**Input**: User description: "Un agente de voz llama por teléfono a centros de exámenes médicos
en Chile simulando ser un paciente. Cotiza precio particular, Fonasa, Isapre, disponibilidad y
preparación del examen. Al colgar, la conversación se transcribe, se resume y queda registrada
en CSV y Markdown."

> Esta spec es una reconstrucción inversa del sistema ya construido en `agente/`,
> `webhook/server.py`, `resumenes.py` y `tunel.sh`. Describe el comportamiento real, incluidos
> sus workarounds, y separa la deuda conocida en "Limitaciones y fuera de alcance".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Llamada de cotización con voz natural (Priority: P1)

El operador configura el agente una vez, levanta el webhook y dispara una llamada a un centro de
exámenes. El agente contesta como "Rodrigo", se presenta como paciente, hace una pregunta por
turno y obtiene los seis datos de la cotización: si realizan el examen, precio particular,
Fonasa, Isapre, disponibilidad y preparación. Antes de despedirse repite todo para confirmar y
cuelga.

**Why this priority**: es el producto. Sin una conversación creíble y completa no hay nada que
archivar ni comparar. El resto de las historias solo conservan el valor generado aquí.

**Independent Test**: con `ASSISTANT_ID` configurado y el webhook arriba, ejecutar
`python3 agente/llamar.py --examen "PET-CT"`. El teléfono destino timbra, el agente saluda con el
examen interpolado, recorre los seis puntos en orden, confirma los montos, se despide y la
llamada termina sola.

**Acceptance Scenarios**:

1. **Given** un assistant creado y el webhook respondiendo `/health`, **When** el operador
   ejecuta `llamar.py`, **Then** Telnyx origina una llamada desde `TELNYX_FROM` hacia
   `--to` (o `TELNYX_TO`) y el assistant queda enganchado desde el primer segundo.
2. **Given** que recepción contesta, **When** el agente saluda, **Then** el saludo incluye el
   nombre del examen y no suena como un menú automático.
3. **Given** que el centro confirma que realiza el examen, **When** avanza la conversación,
   **Then** el agente pregunta en este orden: precio particular → Fonasa → Isapre →
   disponibilidad → preparación → repetición de todo → despedida, con una sola pregunta por
   turno.
4. **Given** que el centro dice que no realiza el examen, **When** el agente lo confirma,
   **Then** agradece, se despide y usa la herramienta de colgar sin preguntar precios.
5. **Given** que recepción entrega un monto, **When** el agente lo escucha, **Then** lo repite
   en voz alta para confirmarlo antes de continuar.
6. **Given** que recepción no entrega un dato (por ejemplo, no atienden Isapre), **When**
   corresponde ese punto, **Then** el agente lo registra mentalmente y sigue sin inventar una
   cobertura ni un precio.

---

### User Story 2 - Archivo automático de la llamada al colgar (Priority: P2)

Cuando la llamada termina, el operador no hace nada: el webhook recupera la conversación, arma
la transcripción completa, la resume con un LLM y escribe una fila en `data/llamadas.csv` más un
Markdown con el detalle. El operador puede comparar centros sin entrar al portal de Telnyx.

**Why this priority**: una llamada que no se registra se pierde. El CSV es la razón por la que
vale la pena automatizar la cotización; sin él, el agente solo ahorra el marcado.

**Independent Test**: después de una llamada, esperar unos segundos y verificar que existe una
fila nueva en `data/llamadas.csv` y un archivo `data/llamadas/AAAA-MM-DD-<id8>.md` con resumen,
datos capturados y transcripción. Reprocesar la misma conversación con `--reprocess` no debe
duplicar la fila.

**Acceptance Scenarios**:

1. **Given** una llamada con conversación creada, **When** llega el evento `call.hangup`,
   **Then** el sistema archiva la llamada en CSV y Markdown en no más de 60 segundos en
   condiciones normales.
2. **Given** que el agente terminó la conversación y se despidió, **When** llega
   `call.conversation.ended`, **Then** el webhook cuelga la pierna para liberar la línea.
3. **Given** una conversación ya archivada, **When** se ejecuta
   `resumenes.py --reprocess <id>`, **Then** la fila existente se actualiza y el resto del CSV
   queda intacto.
4. **Given** una transcripción de más de 100 mensajes, **When** se arma el texto, **Then** se
   recorren todas las páginas de la API y los mensajes quedan ordenados por `created_at`.
5. **Given** que el LLM devuelve el JSON envuelto en texto o markdown, **When** se parsea,
   **Then** se extrae el objeto JSON y la llamada se archiva igual.
6. **Given** que un dato no fue mencionado, **When** se resume, **Then** el campo correspondiente
   queda como `no informado` (o `no atiende` cuando el centro lo dijo explícitamente).

---

### User Story 3 - Recuperación de llamadas no archivadas (Priority: P3)

Si el túnel estaba caído al colgar o el archivado falló, el operador ejecuta un comando y
recupera las conversaciones recientes que no tienen fila. Nada se pierde por un problema de red.

**Why this priority**: el túnel efímero es el punto más frágil del sistema. La recuperación
convierte un fallo operativo en un reintento de un comando.

**Independent Test**: con una conversación real sin fila en el CSV, ejecutar
`python3 resumenes.py --poll`. La conversación aparece archivada y el comando reporta `Sin
llamadas nuevas` en una segunda ejecución.

**Acceptance Scenarios**:

1. **Given** una conversación de las últimas 24 horas con `call_control_id` y mensajes, **When**
   se ejecuta `--poll`, **Then** se archiva en CSV y Markdown.
2. **Given** conversaciones de chat sin `call_control_id`, **When** se ejecuta `--poll`,
   **Then** se ignoran.
3. **Given** una conversación sin mensajes, **When** se ejecuta `--poll`, **Then** se reporta
   `ERR` para esa conversación y no se escribe una fila vacía.
4. **Given** que el webhook no conoce el `conversation_id` al colgar, **When** busca por
   `call_control_id`, **Then** reintenta hasta 18 veces cada 5 segundos antes de rendirse y
   dejar la llamada para `--poll`.

---

### Edge Cases

- **El assistant no inicia**: llega `call.conversation.start_failed`; el webhook cuelga la
  llamada para no dejar la línea abierta.
- **La llamada ya estaba cortada**: el `hangup` responde el error `90018`; se ignora y se sigue
  con el archivado.
- **El túnel cambia de URL**: `.tunnel_url` se reescribe en cada arranque y tiene prioridad sobre
  `PUBLIC_URL`.
- **Payload inválido en el webhook**: se responde 200 (ACK) y se registra el error; el proceso no
  se cae.
- **La conversación aún no está indexada**: se busca por `call_control_id` con reintentos y
  espera; si no aparece, queda para `--poll`.
- **El LLM no devuelve contenido o no hay JSON**: se lanza error, se reintenta 3 veces con 5
  segundos y la conversación queda pendiente para `--poll`.
- **El destinatario no contesta**: Telnyx corta a los `timeout_secs` (45 por defecto); no se crea
  conversación y no hay nada que archivar.
- **La llamada se extiende**: el assistant corta a los 600 segundos por `time_limit_secs`.
- **El examen trae acentos o espacios**: se interpola tal cual en el guion, el saludo y el
  `client_state`; no se normaliza ni se traduce.
- **Dos llamadas simultáneas**: no es un escenario soportado; el estado de conversaciones es un
  diccionario en memoria y el CSV se serializa con un lock.

## Requirements *(mandatory)*

### Functional Requirements

**Configuración y assistant**

- **FR-001**: El sistema MUST permitir crear o actualizar un assistant saliente en Telnyx con
  nombre, descripción, modelo, voz, guion, saludo, tools, transcripción y ajustes de telefonía.
- **FR-002**: El guion MUST interpolar el examen en el marcador `<<EXAMEN>>`, tanto en las
  instrucciones como en el saludo, y hacerlo tanto al crear el assistant como al originar la
  llamada.
- **FR-003**: El assistant MUST usar la voz `Azure.es-CL-LorenzoNeural`, el modelo
  `moonshotai/Kimi-K2.6`, supresión de ruido `krisp`, transcripción `deepgram/flux` en español y
  un límite de 600 segundos, sin grabación de audio.
- **FR-004**: El assistant MUST exponer la herramienta `hangup` para que el agente pueda cerrar
  la llamada al despedirse.
- **FR-005**: El sistema MUST leer la configuración desde `.env` y MUST priorizar `.tunnel_url`
  sobre `PUBLIC_URL` para la URL pública del webhook.
- **FR-006**: El sistema MUST fallar con un mensaje accionable cuando falte una variable
  requerida (`TELNYX_API_KEY`, `TELNYX_CONNECTION_ID`, `TELNYX_FROM`, `WEBHOOK_SECRET`,
  `ASSISTANT_ID`). `TELNYX_TO` MUST estar configurado porque es el destino por defecto, aunque su
  ausencia se manifiesta como rechazo de la API y no como validación local.

**Origen de la llamada**

- **FR-007**: El sistema MUST originar la llamada con `POST /calls` incluyendo `connection_id`,
  `from`, `to`, `timeout_secs`, `webhook_url` y `client_state` con el examen codificado en base64.
- **FR-008**: El sistema MUST enganchar el assistant en el mismo `POST /calls` (id, instructions y
  greeting renderizados), de modo que empiece a hablar apenas contesten, sin un comando posterior.
- **FR-009**: El sistema MUST verificar que el webhook responde `/health` antes de marcar y MUST
  abortar con un mensaje claro si el túnel no está arriba.
- **FR-010**: El sistema MUST permitir cambiar el examen por llamada con `--examen` y el destino
  con `--to`, sin editar archivos.

**Comportamiento conversacional**

- **FR-011**: El guion MUST hacer una sola pregunta por turno y respetar el orden: confirmar
  lugar → realización del examen → precio particular → Fonasa → Isapre → disponibilidad →
  preparación → repetición completa → despedida.
- **FR-012**: El guion MUST prohibir inventar precios, coberturas, planes o disponibilidad, y MUST
  indicar que el agente no es una IA ni un asistente virtual.
- **FR-013**: El guion MUST pedir confirmación de cada monto repitiéndolo antes de continuar y
  MUST abstenerse de dar consejos médicos o interpretar resultados.
- **FR-014**: Si el centro no realiza el examen, el guion MUST terminar la llamada sin cotizar.

**Webhook**

- **FR-015**: El webhook MUST exponer `GET /health` con 200 y `POST /hook/<WEBHOOK_SECRET>`,
  respondiendo 404 a cualquier otra ruta.
- **FR-016**: El webhook MUST comparar el secreto de ruta con tiempo constante y MUST responder
  200 antes de procesar el evento, derivando el trabajo a un hilo aparte.
- **FR-017**: El webhook MUST registrar `conversation_id` al recibir
  `call.conversation.created`, asociándolo al `call_control_id`.
- **FR-018**: El webhook MUST colgar la pierna al recibir `call.conversation.ended` y
  `call.conversation.start_failed`.
- **FR-019**: El webhook MUST iniciar el archivado al recibir `call.hangup`, esperando 2 segundos
  para que la conversación esté disponible.
- **FR-020**: Si no conoce el `conversation_id`, el sistema MUST buscarlo por `call_control_id`
  con reintentos (18 intentos, 5 segundos de espera).
- **FR-021**: El webhook MUST ignorar eventos sin `call_control_id` y MUST sobrevivir a payloads
  inválidos o excepciones no controladas sin caerse.

**Transcripción y resumen**

- **FR-022**: El sistema MUST obtener los mensajes de la conversación paginando de a 100,
  recorriendo todas las páginas y ordenando por `created_at`.
- **FR-023**: El sistema MUST etiquetar los mensajes `assistant` como `Rodrigo (paciente)` y los
  `user` como `Centro`, descartando mensajes sin texto o con otro rol.
- **FR-024**: El sistema MUST resumir la transcripción con un LLM alojado en Telnyx, usando un
  prompt que devuelve exactamente las claves `examen`, `lo_realizan`, `precio_particular`,
  `fonasa`, `isapre`, `disponibilidad`, `preparacion`, `resumen` y `siguiente_paso`.
- **FR-025**: El resumen MUST usar `no informado` para datos ausentes y MUST NOT inventar
  valores; `lo_realizan` MUST ser `si`, `no` o `no_se_sabe`.
- **FR-026**: El sistema MUST calcular la duración desde las marcas de tiempo de los mensajes y
  usar 0 cuando haya menos de dos marcas.

**Archivado**

- **FR-027**: El sistema MUST escribir una fila por `conversation_id` en `data/llamadas.csv` con
  las 15 columnas definidas, actualizando la fila existente en vez de duplicarla.
- **FR-028**: El sistema MUST escribir `data/llamadas/AAAA-MM-DD-<id8>.md` con fecha, duración,
  teléfono, conversación, resumen, datos capturados y transcripción completa.
- **FR-029**: El archivado MUST reintentar hasta 3 veces con 5 segundos de espera y, si falla,
  dejar la llamada pendiente para `--poll`.
- **FR-030**: El sistema MUST ofrecer `--poll` (ventana de 24 horas por defecto) y `--reprocess
  <conversation_id>`; `--poll` MUST ignorar conversaciones sin `call_control_id`, sin mensajes o
  fuera de la ventana.
- **FR-031**: El sistema MUST serializar la escritura del CSV con un lock para evitar corrupción
  cuando el webhook y `--poll` coinciden.

### Key Entities *(include if feature involves data)*

- **Examen**: nombre del estudio a cotizar (por ejemplo `PET-CT`). Se interpola en el guion y
  viaja en `client_state`; no hay catálogo ni validación de nombres.
- **Assistant**: recurso persistente en Telnyx con nombre, descripción, modelo, voz, guion,
  saludo, tools, transcripción y ajustes de telefonía. Se identifica por `ASSISTANT_ID`.
- **Llamada**: solicitud de marcado con `connection_id`, `from`, `to`, `timeout_secs`,
  `webhook_url` y `client_state`; Telnyx la identifica con `call_control_id`.
- **Conversación**: registro de la interacción de voz, identificado por `conversation_id` y
  vinculado a la llamada por `metadata.call_control_id`; contiene fecha, cantidad de mensajes y
  mensajes.
- **Mensaje**: turno de la conversación con `role` (`assistant` o `user`), `text` y marcas de
  tiempo (`created_at`, `sent_at`, `ended_at`).
- **Resumen**: objeto JSON de nueve claves producido por el LLM a partir de la transcripción.
- **FilaLlamada**: registro del CSV con fecha, identificadores, teléfono, duración, examen, los
  seis datos capturados, resumen, siguiente paso y ruta del Markdown.
- **Configuración**: variables de `.env` más `.tunnel_url`; determina credenciales, números,
  puerto y URL pública.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las llamadas contestadas que generan conversación termina con una fila
  en `data/llamadas.csv` y un Markdown asociado, sea por webhook o por `--poll`.
- **SC-002**: Una llamada típica obtiene los seis datos de la cotización en 4 minutos o menos y
  deja evidencia de cada uno en la transcripción.
- **SC-003**: Cero precios o coberturas inventados: todo dato no entregado aparece como
  `no informado` o `no atiende` en el archivo.
- **SC-004**: El webhook responde el ACK en menos de 1 segundo y el archivado termina en 60
  segundos o menos tras el colgado en condiciones normales.
- **SC-005**: Una llamada archivada se puede entender y comparar leyendo solo el Markdown, sin
  abrir el portal de Telnyx.
- **SC-006**: `--poll` recupera el 100% de las conversaciones con `call_control_id` de las
  últimas 24 horas que no tengan fila, y una segunda ejecución reporta `Sin llamadas nuevas`.
- **SC-007**: El resumen no agrega costo de proveedor LLM: usa un modelo alojado en Telnyx y la
  única credencial del sistema sigue siendo `TELNYX_API_KEY`.
- **SC-008**: Cambiar el examen de una llamada no requiere editar código ni reiniciar el webhook:
  basta `--examen` en `llamar.py` o el argumento de `assistant.py`.

## Assumptions

- Un solo operador y una llamada a la vez; no hay multi-tenant ni autenticación de usuarios.
- El destino es un centro de exámenes en Chile que atiende en español.
- El operador tiene Python 3.9+, `cloudflared` instalado y salida a internet.
- Telnyx indexa la conversación a los pocos segundos del colgado; los reintentos cubren la
  demora normal.
- El CSV es la fuente de verdad del histórico y se puede abrir con cualquier hoja de cálculo.
- El agente solo cotiza: no agenda, no negocia ni recomienda alternativas.
- El número de origen, el destino y la conexión Call Control pertenecen a una cuenta de Telnyx
  operativa; el proyecto no incluye aprovisionamiento de números.
- Los insights nativos de Telnyx están activados en el portal, pero el CSV no depende de ellos
  porque la API no los expone.

## Limitaciones y fuera de alcance

Deuda conocida, registrada para que el plan no la presente como comportamiento esperado:

- **Sin firma Ed25519 en el webhook**: la única protección es el secreto en la ruta. Ver
  `specs/002-firma-webhook-ed25519/`.
- **El assistant no corta la pierna por sí solo**: en Call Control, el webhook debe colgar al
  recibir `call.conversation.ended`. Es un workaround, no un diseño ideal.
- **Túnel efímero**: `trycloudflare.com` cambia de URL en cada arranque; si el túnel cae antes
  del `hangup`, la llamada solo se recupera con `--poll`.
- **Sin tests automatizados**: la verificación es manual, guiada por `quickstart.md`.
- **Un examen por llamada**: no hay catálogo ni corrida por lote; el examen se pasa a mano.
- **Sin agendamiento**: el agente declara que confirmará con la familia y volverá a llamar.
- **Sin detección de buzón, IVR ni número equivocado**: el guion asume que contesta una persona.
- **Sin audio**: `recording_settings.enabled = false`; solo queda transcripción.
- **Errores de ASR se propagan**: el resumen depende del texto transcrito; no hay verificación
  contra audio.
- **`INSIGHT_GROUP_ID` hardcodeado**: el grupo de insights pertenece a una cuenta específica.
- **Una llamada concurrente**: el mapa de conversaciones vive en memoria del proceso del webhook.
- **Teléfono registrado**: el CSV guarda `TELNYX_TO`, no el `to` real de la llamada. Si se usa
  `--to` con otro número, la fila queda con el destino por defecto.
- **`PORT` en `.env` no lo lee `tunel.sh`**: el script usa la variable de shell o 8000. Si se
  cambia solo en `.env`, el túnel apunta a un puerto y el servidor escucha en otro; hay que
  exportar `PORT` antes de `./tunel.sh`.
