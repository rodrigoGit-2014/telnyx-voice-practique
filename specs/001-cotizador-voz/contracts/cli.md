# Contract: Interfaz de línea de comandos

**Feature**: `001-cotizador-voz`

Todos los comandos se ejecutan desde la raíz del proyecto (`v1/`). No hay paquete instalable ni
entrypoints: son scripts que ajustan `sys.path` para importar `agente`.

## 1. Alta del assistant

```bash
python3 agente/assistant.py [EXAMEN]
```

| Argumento | Obligatorio | Default | Descripción |
|---|---|---|---|
| `EXAMEN` | no | `PET-CT` | Examen con el que se renderiza el guion del assistant |

**Efectos**:

- Si `ASSISTANT_ID` existe: `PATCH /ai/assistants/{id}`.
- Si no existe: `POST /ai/assistants` y escribe `ASSISTANT_ID=<id>` en `.env`.
- No toca el webhook ni hace llamadas.

**Salida** (stdout): `assistant_id`, `nombre`, `modelo`, `voz`, `examen demo` y el siguiente paso
(`./tunel.sh`).

**Errores**: `TelnyxError` ⇒ `SystemExit` con el mensaje de la API.

## 2. Túnel + webhook

```bash
./tunel.sh
```

**Precondiciones**: `cloudflared` instalado (`brew install cloudflared`), `WEBHOOK_SECRET` en
`.env` y, si se usa un puerto distinto de 8000, `PORT` exportado en la shell (el script no lee
`.env`).

**Efectos**:

1. Lanza `cloudflared tunnel --url http://localhost:${PORT}`.
2. Espera hasta 40 segundos a que aparezca la URL `https://*.trycloudflare.com`.
3. Escribe la URL en `.tunnel_url`.
4. Ejecuta `python3 webhook/server.py` en primer plano.
5. Al salir (EXIT/INT/TERM) mata `cloudflared`, mata el servidor y borra el log temporal.

**Salida**:

```text
Túnel público: https://<aleatorio>.trycloudflare.com
Webhook:       https://<aleatorio>.trycloudflare.com/hook/<secreto>
```

**Errores**: sin `cloudflared` ⇒ exit 1; sin URL en 40 s ⇒ muestra el log y exit 1.

## 3. Llamada saliente

```bash
python3 agente/llamar.py [--examen EXAMEN] [--to NUMERO] [--timeout SEGUNDOS]
```

| Argumento | Obligatorio | Default | Descripción |
|---|---|---|---|
| `--examen` | no | `PET-CT` | Examen a cotizar; se interpola y viaja en `client_state` |
| `--to` | no | `TELNYX_TO` | Destino E.164; override por llamada |
| `--timeout` | no | `45` | Segundos de timbrado |

**Preflight**:

1. `public_url()` debe existir (`.tunnel_url` o `PUBLIC_URL`); si no, `SystemExit`.
2. `GET <public_url>/health` debe responder 200 en ≤5 s; si no, `SystemExit` con instrucción de
   correr `./tunel.sh`.
3. `TELNYX_CONNECTION_ID`, `TELNYX_FROM`, `WEBHOOK_SECRET` y `ASSISTANT_ID` son obligatorios.

**Salida**:

```text
Llamando a +56XXXXXXXXX desde +56YYYYYYYYY
examen       : PET-CT
call_control : v3:...
```

**Errores**: `TelnyxError` ⇒ mensaje en stderr y exit 1.

## 4. Resúmenes

```bash
python3 resumenes.py --poll [--horas N]
python3 resumenes.py --reprocess CONVERSATION_ID [--examen EXAMEN]
```

| Argumento | Obligatorio | Default | Descripción |
|---|---|---|---|
| `--poll` | uno de los dos | — | Procesa conversaciones recientes sin fila en el CSV |
| `--reprocess` | uno de los dos | — | Rehace una conversación puntual |
| `--horas` | no | `24` | Ventana de `--poll` |
| `--examen` | no | `""` | Examen para `--reprocess`; si falta, se usa el del resumen |

**`--poll` selecciona** conversaciones que cumplan **todas**:

1. `created_at` dentro de la ventana.
2. `metadata.call_control_id` presente (descarta chats).
3. `number_of_messages > 0`.
4. `id` sin fila en `data/llamadas.csv`.

**Salida de `--poll`**: `Sin llamadas nuevas.` o una línea por conversación:
`OK  <id8>  <resumen[:70]>` / `ERR <id8>  <error>`.

**Salida de `--reprocess`**: la fila resultante en JSON indentado.

**Códigos de salida**: `0` éxito; `1` si `TelnyxError` no controlado. Los errores por
conversación en `--poll` no cambian el código de salida.

## Códigos y convenciones

| Código | Significado |
|---|---|
| `0` | Comando completado (incluye `--poll` con errores por conversación) |
| `1` | Error de configuración o de API que impide continuar |
| `SystemExit` con texto | Falta una variable requerida o el túnel no está arriba |

- stdout: información para el operador.
- stderr: errores de API y mensajes de fallo.
- No hay modo `--json` global ni `--verbose`; el log del webhook va a stdout con hora local.
