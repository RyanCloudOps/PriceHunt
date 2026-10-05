# Notas de sesión: dónde nos quedamos

Última actualización: 2026-10-06

## Qué estamos haciendo

Desarrollar **PriceHunt** (repo `RyanCloudOps/PriceHunt`) en WSL2 Debian 13. Tracker de ofertas con FastAPI + PostgreSQL, scrapers por tienda, frontend Vite + Three.js, todo con Docker Compose. Atajos en `Makefile`: `make up` (scraping real), `make demo`, `make down`, `make test`, `make lint`.

## Hecho

- Entorno listo, sin sudo:
  - Docker Desktop (hay que abrirlo en Windows antes de `make up`; si `docker` no se encuentra en WSL, activar Settings → Resources → WSL integration → Debian).
  - Python 3.12 con `uv` en `.venv/` (ignorado por git). Activar con `source .venv/bin/activate` antes de `make test` / `make lint`.
  - Node 22 en `~/.local/node` (PATH añadido a `~/.bashrc`). `npm ci` y `npm run build` funcionan. No hay `prettier` instalado.
- Scrapers de tecnología: `corsair.py` (tienda oficial, 14 categorías, hasta 24 productos por categoría) y `alternate.py` (búsqueda por marca con paginación).
- `services/seed.py`: activa los scrapers nuevos en bases de datos ya existentes sin borrar nada.
- Watchlist de tecnología: corsair, apple, elgato, secretlab (+ las de por defecto en BD nuevas).
- **Modo coches** (interruptor Tecnología / Coches junto al logo; recuerda la elección en `localStorage`):
  - Columna `vertical` (`tech`/`cars`) en `stores` y `watch_terms` (migración 0003). La API acepta `?vertical=` en deals, categories, stores, watchlist y stats. El refresco solo usa las marcas de cada modo en las tiendas de ese modo.
  - `scrapers/dasweltauto.py`: Das WeltAuto (concesionarios oficiales SEAT/CUPRA/Škoda/VW/Audi), solo coches con el filtro «rebajado» de la web. No publica el precio anterior: el refresco lo reconstruye del historial de precios. Hoy solo hay SEAT, CUPRA y Škoda (VW y Audi devuelven 0). Su coche más barato ronda 9.000 €, así que no sirve para <10k.
  - `scrapers/ocasionplus.py`: OcasionPlus (concesionarios propios). Su `robots.txt` prohíbe filtros por parámetro (`price_max`, `sort`…) pero no el listado por marca + `?page=N`, así que pagina hasta 15 páginas por marca y filtra en local con `CAR_MAX_PRICE=10000` y `CAR_MAX_KM=150000` (0 = sin límite). Categoría «Hasta 10.000 €».
  - `ScrapedItem.curated`: el scraper ya filtró el coche (rebajado o dentro de presupuesto), así que no exige descuento mínimo. Sin descuento conocido, la tarjeta muestra «Ocasión».
  - Marcas de coches vigiladas (16): seat, cupra, skoda, volkswagen, audi + toyota, renault, dacia, citroen, peugeot, opel, ford, fiat, kia, hyundai, nissan. El seed solo las añade la primera vez que aparece cada tienda (si se borran, no vuelven).
  - Demo con coches incluido.
- Última prueba real: 351 coches (335 OcasionPlus, 16 Das WeltAuto), ninguno por encima de 10.000 € ni 150.000 km en OcasionPlus. Tecnología sin cambios (~270 ofertas).
- Tests: 89 pasan; `ruff check` y `ruff format --check` limpios.

## Estado al cerrar

- Stack Docker apagado con `make down`; los datos de PostgreSQL se conservan en el volumen.
- Para retomar: abrir Docker Desktop, `make up` y, si hace falta refrescar, `curl -X POST localhost:8000/api/refresh`. Un refresco real completo tarda ~12 min (2 s entre peticiones y 16 marcas de coches × 15 páginas). La web está en http://localhost:8080 y la API en http://localhost:8000/docs (las rutas llevan prefijo `/api`).
- El interruptor y los textos del modo coches solo se han comprobado con la API y el HTML servido, **no visualmente en el navegador**.

## Límites conocidos

- **PcComponentes**: 403 anti-bot. No se intenta saltar; sigue como enlace directo.
- **Coolmod**: la sonda devolvió 307 y no se investigó.
- **Amazon**: necesita credenciales PA-API en `.env`.
- **Subastas BOE**: `robots.txt` con `Disallow: /`, no se rastrea; solo acceso directo.
- Coches descartados: Flexicar, Hyundai y Milanuncios (robots.txt lo prohíbe), Spoticar y coches.net (403), Autohero y Clicars (precios cargados desde el navegador, no vienen en el HTML).
- No hay ofertas en la categoría Escritorios: los Platform de Corsair no tienen descuento y `MIN_DISCOUNT_PCT=5`.
- La paginación de Corsair es del lado del cliente, así que solo se ven 24 productos por categoría.
- OcasionPlus: solo se miran 300 coches por marca (15 páginas), sin orden por precio, así que puede haber baratos que no se vean.

## Ideas para mañana

1. Comprobar visualmente el interruptor Tecnología / Coches en el navegador (móvil incluido).
2. Coches: más fuentes que permitan rastreo (revisar siempre `robots.txt`), o filtros por km/año en la web.
3. Decidir si se bajan `MIN_DISCOUNT_PCT` o se muestran también productos sin rebaja en tecnología (filtro "ver todo").
4. Revisar Coolmod como siguiente tienda.
5. Imágenes en modo demo (SVG por marca): hay que tocar `DemoScraper` y `safeUrl` del frontend, que solo acepta `http(s)`.

## Notas

- Responder a Ryan en español.
