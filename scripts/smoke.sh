#!/usr/bin/env bash
# Smoke test end-to-end contra el stack levantado con docker compose.
# Uso: ./scripts/smoke.sh [http://localhost:8080]
set -euo pipefail
BASE="${1:-http://localhost:8080}"

fail() { echo "✗ $*" >&2; exit 1; }
PY=python3; "$PY" -c "" 2>/dev/null || PY=python
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "→ Web en $BASE"
curl -fsS "$BASE/" | grep -q "PRICEHUNT" || fail "la home no contiene la marca"

echo "→ API health"
[ "$(curl -fsS "$BASE/api/health" | json 'd["status"]')" = "ok" ] || fail "health"

echo "→ Esperando al refresco de arranque"
for _ in $(seq 1 60); do
  status=$(curl -fsS "$BASE/api/stats" | json '(d["last_run"] or {}).get("status","none")')
  [ "$status" = "success" ] && break
  sleep 2
done
[ "$status" = "success" ] || fail "el refresco de arranque no terminó bien (status=$status)"

total=$(curl -fsS "$BASE/api/deals" | json 'd["total"]')
[ "$total" -gt 0 ] || fail "no hay ofertas"
echo "→ $total ofertas activas"

stores=$(curl -fsS "$BASE/api/stores" | json 'len(d)')
[ "$stores" -ge 5 ] || fail "faltan tiendas semilla"

echo "→ Refresco manual"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/refresh")
[ "$code" = "202" ] || [ "$code" = "409" ] || fail "POST /api/refresh devolvió $code"

echo "✓ Smoke test OK"
