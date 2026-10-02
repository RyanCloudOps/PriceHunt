# PriceHunt

Web que **busca todas las ofertas de las marcas que tú elijas** (Corsair, Apple, Samsung, Logitech…: tecnología, hogar, gaming, lo que haya) en tiendas conocidas, las guarda en una base de datos y **las revisa sola cada día**. Si una oferta desaparece o ya no tiene descuento, deja de mostrarse.

Es un proyecto interno: se ejecuta en local con Docker.

## Qué hace

- **Busca ofertas** en MediaMarkt y LDLC (y en Amazon si configuras su API oficial).
- **Las guarda** en PostgreSQL junto con el historial de precios de cada producto.
- **Las actualiza sola**: al arrancar (si los datos tienen más de 24 h), todos los días a las 07:00 y cuando pulsas *Refrescar ahora*.
- **Guarda accesos directos** a otras tiendas de confianza (PcComponentes, Coolmod, Alternate, Corsair…). Puedes añadir más desde la web.
- **Te deja elegir qué marcas vigilar** desde la web. De cada marca se busca todo tipo de producto, y se clasifica solo (móviles, TVs, portátiles, electrodomésticos, teclados…).
- **Muestra todo en una web animada** con una esfera de red 3D, filtros por tienda, categoría y descuento, y un registro de cada búsqueda.

## Cómo arrancarlo

Solo necesitas **Docker Desktop**.

```powershell
.\scripts\pricehunt.ps1 up      # buscar en las tiendas reales
.\scripts\pricehunt.ps1 demo    # datos de prueba, sin tocar ninguna web
.\scripts\pricehunt.ps1 down    # parar
```

En Linux o macOS: `make up`, `make demo` y `make down`.

Después abre **http://localhost:8080**.

| Extra | Comando | URL |
|---|---|---|
| Documentación de la API | — | http://localhost:8000/docs |
| Gráficas (Grafana) | `.\scripts\pricehunt.ps1 monitoring` | http://localhost:3000 |
| Ver la base de datos | `.\scripts\pricehunt.ps1 tools` | http://localhost:8081 |

## Cómo está hecho

```
Navegador → nginx (web) → FastAPI (API) → PostgreSQL
                              ↓
                MediaMarkt · LDLC · Amazon (API)
```

| Parte | Tecnología | Función |
|---|---|---|
| Web | HTML, CSS, JavaScript, **Three.js**, Vite, nginx | La interfaz, las animaciones y la esfera 3D |
| API | **Python + FastAPI** | Expone las ofertas y lanza las búsquedas |
| Scrapers | httpx + BeautifulSoup | Leen las tiendas y sacan precio, precio tachado e imagen |
| Programador | APScheduler | Refresco diario y recuperación si el PC estaba apagado |
| Base de datos | **PostgreSQL**, SQLAlchemy, Alembic | Tiendas, marcas, ofertas, historial de precios y registro de búsquedas |
| Contenedores | **Docker + Docker Compose** | Levantar todo con un solo comando |

## DevOps

- **CI** (GitHub Actions, en cada push o PR): revisión del código con Ruff, migraciones de la base de datos, 44 tests contra Postgres, build de la web, escaneo de seguridad con Trivy y una prueba completa con Docker.
- **CD**: si la CI pasa en `main`, publica las imágenes Docker en GitHub Container Registry.
- **Mantenimiento**: Dependabot actualiza dependencias y pre-commit revisa el código antes de cada commit.
- **Monitorización**: Prometheus y Grafana (ofertas por tienda, errores y duración de cada búsqueda).

## Sobre Amazon

Amazon bloquea la lectura automática de su web, así que se conecta por su **API oficial (PA-API 5)**. Para eso necesitas una cuenta de Amazon Afiliados con acceso a la API; pon las claves en `.env` (usa `.env.example` como plantilla):

```env
AMAZON_ACCESS_KEY=...
AMAZON_SECRET_KEY=...
AMAZON_PARTNER_TAG=...
```

Sin claves, Amazon aparece solo como acceso directo. Esta conexión aún no se ha probado contra la API real de Amazon.

## Configuración

Las opciones están en `.env.example`. Las más útiles:

| Variable | Por defecto | Qué controla |
|---|---|---|
| `DEMO_MODE` | `false` | Usar datos de prueba |
| `REFRESH_CRON_HOUR` | `7` | Hora del refresco diario |
| `REFRESH_INTERVAL_HOURS` | `24` | A partir de cuántas horas se consideran viejos los datos |
| `MIN_DISCOUNT_PCT` | `5` | Descuento mínimo para contar como oferta |
| `MAX_PAGES` | `60` | Tope de páginas de resultados por marca y tienda |

## Estructura

```
backend/    API, scrapers, base de datos y tests
frontend/   Web y esfera 3D
ops/        Prometheus y Grafana
scripts/    pricehunt.ps1 (Windows) y smoke.sh (prueba E2E)
.github/    CI/CD y Dependabot
```

> Los precios son orientativos: confirma siempre el precio final en la tienda.
