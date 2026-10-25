#!/usr/bin/env bash
# Levanta el túnel de Cloudflare y el webhook local.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Falta cloudflared. Instálalo con: brew install cloudflared"
  exit 1
fi

LOG="$(mktemp)"
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate >"$LOG" 2>&1 &
CF_PID=$!

cleanup() {
  kill "$CF_PID" 2>/dev/null || true
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null || true
  rm -f "$LOG"
}
trap cleanup EXIT INT TERM

URL=""
for _ in $(seq 1 40); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

if [ -z "$URL" ]; then
  echo "No se pudo obtener la URL del túnel:"
  tail -20 "$LOG"
  exit 1
fi

echo "$URL" > .tunnel_url
echo "Túnel público: $URL"
echo "Webhook:       $URL/hook/<secreto>"
echo

python3 webhook/server.py &
SRV_PID=$!
wait "$SRV_PID"
