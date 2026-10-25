# Quickstart: Validación del cotizador por voz

**Feature**: `001-cotizador-voz` | **Fecha**: 2026-10-25

Guía para comprobar que el sistema hace lo que dice la spec. No incluye implementación: solo
comandos, resultados esperados y cómo interpretar un fallo.

## Prerrequisitos

- Python 3.9+ (verificar con `python3 --version`).
- `cloudflared` instalado (`brew install cloudflared`).
- `.env` completo con `TELNYX_API_KEY`, `TELNYX_FROM`, `TELNYX_TO`, `TELNYX_CONNECTION_ID` y
  `WEBHOOK_SECRET`.
- Un número de destino que pueda contestar (el `TELNYX_TO` o uno pasado con `--to`).
- Salida a internet y permiso para originar llamadas en la cuenta de Telnyx.

> Verificar configuración sin imprimir secretos:
>
> ```bash
> python3 - <<'PY'
> from agente import config
> for k in ("TELNYX_API_KEY","TELNYX_FROM","TELNYX_TO","TELNYX_CONNECTION_ID","WEBHOOK_SECRET"):
>     print(k, "OK" if config.get(k) else "FALTA")
> print("assistant:", config.get("ASSISTANT_ID", "(sin configurar)"))
> print("public_url:", config.public_url() or "(sin túnel)")
> PY
> ```

## Escenario 0 — Smoke test sin llamada

**Objetivo**: validar imports, interpolación y webhook antes de gastar minutos.

```bash
# 1. El guion se renderiza y no quedan placeholders
python3 - <<'PY'
from agente.assistant import GREETING, INSTRUCTIONS, build_payload, render
g = render(GREETING, "PET-CT")
i = render(INSTRUCTIONS, "PET-CT")
assert "PET-CT" in g and "<<EXAMEN>>" not in g
assert "PET-CT" in i and "<<EXAMEN>>" not in i
p = build_payload("PET-CT")
assert p["tools"][0]["type"] == "hangup"
assert p["telephony_settings"]["time_limit_secs"] == 600
print("guion OK")
PY

# 2. El webhook responde salud (en otra terminal: ./tunel.sh)
curl -s http://localhost:8000/health
# Esperado: ok

# 3. Ruta incorrecta
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/hook/incorrecto
# Esperado: 404

# 4. Evento sin call_control_id no debe romper nada
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8000/hook/$(grep WEBHOOK_SECRET .env | cut -d= -f2)" \
  -H 'Content-Type: application/json' -d '{"data":{"event_type":"call.initiated","payload":{}}}'
# Esperado: 200 y ninguna excepción en el log del webhook
```

**Falla si**: queda `<<EXAMEN>>` en el guion, `/health` no responde o el webhook se cae con un
payload incompleto.

## Escenario 1 — Alta del assistant

```bash
python3 agente/assistant.py "PET-CT"
```

**Esperado**:

- Si no había `ASSISTANT_ID`: `Creando assistant...` y `ASSISTANT_ID` nuevo en `.env`.
- Si ya existía: `Actualizando assistant <id>...`.
- Se imprimen nombre, modelo (`moonshotai/Kimi-K2.6`) y voz (`Azure.es-CL-LorenzoNeural`).
- En el portal de Telnyx, el assistant tiene la tool `hangup`, `time_limit_secs=600` y
  transcripción `deepgram/flux` en `es`.

**Falla si**: la API devuelve 4xx (revisar `TELNYX_API_KEY` y el payload) o queda un
`ASSISTANT_ID` vacío.

## Escenario 2 — Llamada completa (E2E)

Terminal A:

```bash
./tunel.sh
# Esperado:
# Túnel público: https://<aleatorio>.trycloudflare.com
# Webhook:       https://<aleatorio>.trycloudflare.com/hook/<secreto>
```

Terminal B:

```bash
python3 agente/llamar.py --examen "PET-CT"
```

**Esperado durante la llamada**:

1. El teléfono destino timbra y, al contestar, el agente saluda en español de Chile con el
   examen: "Llamo para consultar por un PET-CT".
2. El agente confirma el lugar y pregunta, una por turno: realización → precio particular →
   Fonasa → Isapre → disponibilidad → preparación.
3. Cada monto se repite para confirmar.
4. Al final repite los cinco datos, agradece, se despide y la llamada se corta sola.
5. Duración menor a 4 minutos (límite duro 600 s).

**Log esperado del webhook**:

```text
[HH:MM:SS] marcando a +56...
[HH:MM:SS] conversación <id8> creada
[HH:MM:SS] conversación terminada v3:...
[HH:MM:SS] colgado (fin de conversación) v3:...
[HH:MM:SS] OK <id8> -> data/llamadas/AAAA-MM-DD-<id8>.md
```

**Falla si**: el agente no habla al contestar (assistant no enganchado), repite preguntas o
inventa un precio. En ese caso, revisar `assistant.py` y volver a ejecutar el Escenario 1.

## Escenario 3 — Verificar el archivo

```bash
tail -n 2 data/llamadas.csv
ls -lt data/llamadas | head -3
```

**Esperado**:

- Una fila nueva con 15 columnas y el `conversation_id` de la llamada.
- `examen` = `PET-CT`; `lo_realizan` ∈ {`si`, `no`, `no_se_sabe`}.
- `archivo_md` apunta a un archivo existente.
- El Markdown tiene las secciones `## Resumen`, `## Datos capturados` y `## Transcripción`.
- La transcripción incluye el saludo inicial y la despedida (no está cortada al inicio).
- Ningún dato no mencionado aparece inventado: debe decir `no informado` o `no atiende`.

**Falla si**: el CSV tiene una fila con `conversation_id` vacío, el Markdown no existe o la
transcripción empieza a mitad de la llamada (señal de paginación incompleta).

## Escenario 4 — Reprocesar una llamada

```bash
python3 resumenes.py --reprocess <CONVERSATION_ID> --examen "PET-CT"
```

**Esperado**: imprime la fila en JSON, reescribe el mismo Markdown y **no** agrega una segunda
fila al CSV.

```bash
# Antes y después debe haber la misma cantidad de filas
wc -l data/llamadas.csv
```

## Escenario 5 — Recuperación con `--poll`

Simular un webhook caído: cortar `tunel.sh` antes de que termine el archivado (o simplemente
llamar y matar el proceso al colgar). Luego:

```bash
python3 resumenes.py --poll
# Esperado: OK <id8> <resumen...>
python3 resumenes.py --poll
# Esperado: Sin llamadas nuevas.
```

**Falla si**: la conversación no aparece (revisar `call_control_id`, ventana de 24 h y
`number_of_messages`) o si la segunda ejecución vuelve a procesarla (fallo de idempotencia).

## Escenario 6 — Cambiar el guion

1. Editar `INSTRUCTIONS` o `GREETING` en `agente/assistant.py`.
2. `python3 agente/assistant.py "PET-CT"` (actualiza el assistant persistente).
3. Repetir el Escenario 2 y revisar que el cambio aparezca en la transcripción.

**Esperado**: el cambio se escucha y queda en el Markdown. No es necesario reiniciar el webhook,
pero sí volver a ejecutar el alta del assistant.

## Matriz de resultados vs. criterios de éxito

| Criterio | Cómo se verifica |
|---|---|
| SC-001 | Escenarios 2 y 5: toda llamada contestada deja fila + MD |
| SC-002 | Escenario 2: seis datos en ≤ 4 min, visibles en la transcripción |
| SC-003 | Escenario 3: campos sin dato dicen `no informado` / `no atiende` |
| SC-004 | Log del webhook: ACK inmediato y `OK` ≤ 60 s tras el colgado |
| SC-005 | Escenario 3: el MD se entiende sin abrir el portal |
| SC-006 | Escenario 5: `--poll` recupera y luego reporta `Sin llamadas nuevas` |
| SC-007 | `.env` solo tiene `TELNYX_API_KEY`; no hay claves de LLM |
| SC-008 | Escenario 2 con `--examen "Resonancia"` sin editar código |

## Troubleshooting

| Síntoma | Causa probable | Acción |
|---|---|---|
| `No hay URL pública` | No se corrió `tunel.sh` o `.tunnel_url` está vacío | Levantar el túnel |
| `El webhook no responde en .../health` | Túnel arriba pero servidor caído o puerto ocupado | Revisar `PORT`, reiniciar `tunel.sh` |
| El webhook escucha pero el túnel apunta a otro puerto | `PORT` distinto en `.env` y en la shell | `export PORT=<puerto>` antes de `./tunel.sh` |
| El assistant no habla al contestar | `ASSISTANT_ID` inválido o falta en el dial | Reejecutar `assistant.py`; revisar el payload |
| `call.conversation.start_failed` | Guion o configuración rechazada por Telnyx | Leer `reason` en el log; corregir y reintentar |
| La llamada queda abierta al despedirse | No llegó `conversation.ended` | Revisar webhook; el workaround es colgar desde el evento |
| `sin conversación para ...` | La conversación aún no se indexó | Esperar y correr `--poll` |
| `no se pudo resumir ...` | LLM sin JSON o API caída | `--reprocess <id>`; revisar el prompt |
| `Falta TELNYX_... en .env` | Variable ausente | Completar `.env`; no commitearlo |
| CSV con filas duplicadas | Se editó a mano o falló el lock | Reprocesar y deduplicar por `conversation_id` |
| Transcripción incompleta | Paginación o conversación aún en curso | `--reprocess`; verificar `total_pages` |

## Checklist de cierre

- [ ] Escenario 0 pasa sin tocar la API de llamadas.
- [ ] Escenario 1 actualiza el assistant sin errores.
- [ ] Escenario 2 produce una llamada completa y natural.
- [ ] Escenario 3 deja CSV + MD consistentes.
- [ ] Escenario 4 no duplica filas.
- [ ] Escenario 5 recupera y es idempotente.
- [ ] `.env`, `.tunnel_url` y `data/` no se versionaron.
