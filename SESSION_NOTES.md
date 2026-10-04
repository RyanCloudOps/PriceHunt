# Notas de sesión: dónde nos quedamos

Última actualización: 2026-10-05

## Qué estamos haciendo

Desarrollar **PriceHunt** (repo `RyanCloudOps/PriceHunt`) en WSL2 Debian 13. Tracker de ofertas con FastAPI + PostgreSQL, scrapers por tienda, frontend Vite + Three.js, todo con Docker Compose. Atajos en `Makefile`: `make up` (scraping real), `make demo`, `make down`, `make test`, `make lint`.

## Hecho

- Entorno listo, sin sudo:
  - Docker: grupo `docker` aplicado tras `wsl --shutdown`.
  - Python 3.12 con `uv` en `.venv/` (ignorado por git). Activar con `source .venv/bin/activate` antes de `make test` / `make lint`.
  - Node 22 en `~/.local/node` (PATH añadido a `~/.bashrc`). `npm ci` y `npm run build` funcionan.
- Nuevos scrapers:
  - `scrapers/corsair.py`: tienda oficial de Corsair (escritorios Platform, sillas, periféricos, etc.). Lee 14 categorías `/es/es/c/...`, hasta 24 productos por categoría porque la paginación se hace en el navegador. Solo actúa con el término `corsair`. Clasifica usando las categorías de la tienda y pide las imágenes a 400 px.
  - `scrapers/alternate.py`: Alternate.es, búsqueda por marca con paginación `&page=N`; descarta productos sin stock.
- `services/seed.py`: activa los scrapers nuevos en bases de datos ya existentes (`_enable_new_scrapers`), sin borrar nada.
- Demo: catálogo de Corsair ampliado con escritorios y sillas. Los datos demo no llevan imagen (el frontend muestra la letra de la marca); es intencionado.
- Tests: 78 pasan; `ruff check` y `ruff format --check` limpios.
- Probado en real: 279 ofertas (MediaMarkt 226, Corsair 46, Alternate 5, LDLC 2) y las imágenes cargan.

## Estado al cerrar

- Stack Docker apagado con `make down`; los datos de PostgreSQL se conservan en el volumen.
- Para retomar: `make up`, esperar a que arranque y, si hace falta refrescar, `curl -X POST localhost:8000/api/refresh`. Un refresco real completo tarda varios minutos (2 s entre peticiones). La web está en http://localhost:8080 y la API en http://localhost:8000/docs (las rutas llevan prefijo `/api`).

## Límites conocidos

- **PcComponentes**: 403 anti-bot. No se intenta saltar; sigue como enlace directo.
- **Coolmod**: la sonda devolvió 307 y no se investigó.
- **Amazon**: necesita credenciales PA-API en `.env`.
- Ahora mismo no hay ofertas en la categoría Escritorios: los Platform de Corsair no tienen descuento y el mínimo guardado es `MIN_DISCOUNT_PCT=5`.
- La paginación de Corsair en la tienda es del lado del cliente, así que solo se ven 24 productos por categoría.

## Ideas para mañana

1. Decidir si se bajan `MIN_DISCOUNT_PCT` o se muestran también productos sin rebaja (p. ej. con un filtro "ver todo").
2. Añadir marcas de escritorios y sillas a la lista de seguimiento (`POST /api/watchlist`): Secretlab, Elgato, etc.
3. Revisar Coolmod como siguiente tienda.
4. Imágenes en modo demo (SVG por marca): hay que tocar `DemoScraper` y `safeUrl` del frontend, que solo acepta `http(s)`.

## Notas

- Responder a Ryan en español.
