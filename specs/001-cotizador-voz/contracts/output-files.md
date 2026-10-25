# Contract: Archivos de salida

**Feature**: `001-cotizador-voz` | **Implementación**: `resumenes.py`

## 1. CSV histórico

**Ruta**: `data/llamadas.csv` (relativa a la raíz del proyecto).
**Encoding**: UTF-8. **Formato**: RFC 4180 con encabezado. **Separador**: coma.
**Granularidad**: una fila por `conversation_id`. **Escritura**: completa cada vez, protegida por
`CSV_LOCK` dentro del proceso.

### Encabezado (orden fijo)

```csv
fecha_hora,conversation_id,call_control_id,telefono,duracion_seg,examen,lo_realizan,precio_particular,fonasa,isapre,disponibilidad,preparacion,resumen,siguiente_paso,archivo_md
```

### Ejemplo de fila

```csv
2026-10-25 00:10:32,21109129-fbb6-4971-9af2-61a202264385,v3:rThPfq9...,+56XXXXXXXXX,151,PET-CT,si,142.500 pesos,"tramos 1, 2 y 3; valor 91.354 pesos",se ve en el momento,próximo jueves,ninguna,"El paciente cotizó un PET-CT...",Llamar nuevamente para agendar la hora del PET-CT.,data/llamadas/2026-10-25-21109129.md
```

### Reglas de integridad

- **Clave**: `conversation_id`. Si ya existe, se reemplaza la fila en su misma posición; si no,
  se agrega al final.
- **Columnas**: siempre las 15, en ese orden. Una columna ausente se escribe vacía.
- **Montos**: texto, no números. No se normalizan símbolos ni se convierten a CLP.
- **`lo_realizan`**: `si`, `no` o `no_se_sabe`.
- **`telefono`**: se llena con `TELNYX_TO`; un `--to` alternativo no se refleja en la fila
  (deuda conocida).
- **`fecha_hora`**: `YYYY-MM-DD HH:MM:SS` en hora local del operador.
- **`archivo_md`**: ruta relativa a la raíz, con separador `/`.
- **Reprocesar**: `--reprocess` reemplaza la fila y reescribe el Markdown; no crea duplicados.
- **Compatibilidad**: abrir y guardar el CSV con una hoja de cálculo puede reordenar o reinterpretar
  montos; la fuente de verdad es la escritura del script.

## 2. Markdown por llamada

**Ruta**: `data/llamadas/<fecha>-<id8>.md`.

- `<fecha>` = primeros 10 caracteres de `fecha_hora` (`AAAA-MM-DD`).
- `<id8>` = primeros 8 caracteres de `conversation_id`.
- Si el archivo existe, se sobrescribe.

### Plantilla exacta

````markdown
# Llamada 2026-10-25 00:10:32

- **Duración:** 151 s
- **Teléfono:** +56XXXXXXXXX
- **Conversación:** `21109129-fbb6-4971-9af2-61a202264385`

## Resumen

El paciente cotizó un PET-CT. El centro confirmó que lo realizan...

## Datos capturados

- **Examen:** PET-CT
- **¿Lo realizan?:** si
- **Precio particular:** 142.500 pesos
- **Fonasa:** tramos 1, 2 y 3; valor 91.354 pesos
- **Isapre:** se ve en el momento
- **Disponibilidad:** próximo jueves
- **Preparación:** ninguna
- **Siguiente paso:** Llamar nuevamente para agendar la hora del PET-CT para el próximo jueves.

## Transcripción

```
Rodrigo (paciente): Hola, buenas tardes. ¿Hablo con el centro de exámenes?...
Centro: Hola, buenas, sí.
Rodrigo (paciente): ...
```
````

### Reglas de la transcripción

- Una línea por mensaje con texto: `Rodrigo (paciente): <texto>` o `Centro: <texto>`.
- Mensajes `assistant` ⇒ paciente; `user` ⇒ centro. Otros roles se omiten.
- Orden cronológico por `created_at`.
- Se incluyen **todas** las páginas de la API; el bloque no se trunca.
- El bloque va entre tres backticks; si el texto contiene backticks, no se escapa (limitación
  conocida, poco probable en habla).

## 3. Archivos de configuración

| Archivo | Versionado | Contenido | Regla |
|---|---|---|---|
| `.env` | **No** | Credenciales, números, puerto, `ASSISTANT_ID` | `config.set_env` conserva comentarios y otras claves |
| `.tunnel_url` | **No** | URL pública actual | Lo reescribe `tunel.sh`; prioridad sobre `PUBLIC_URL` |

`set_env(nombre, valor)` reemplaza la línea existente o agrega la clave al final; no reordena ni
elimina comentarios.

## 4. Datos de ejemplo

El repositorio puede contener un CSV y un Markdown de una llamada de prueba
(`data/llamadas/2026-10-25-21109129.md`). Son datos reales de demostración: no se deben usar
como fixtures en documentación pública ni versionar llamadas nuevas.
