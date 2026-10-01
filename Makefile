# Atajos para Linux/macOS/WSL. En Windows usa scripts/pricehunt.ps1
.PHONY: up demo down logs ps test lint fmt migration monitoring tools smoke reset

up:          ## Levanta el stack (scraping real)
	docker compose up -d --build --wait
	@echo "Web: http://localhost:8080  ·  API: http://localhost:8000/docs"

demo:        ## Levanta el stack con datos sintéticos
	DEMO_MODE=true docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs -f api

ps:
	docker compose ps

test:        ## Tests del backend (SQLite local)
	cd backend && python -m pytest

lint:
	cd backend && ruff check . && ruff format --check .

fmt:
	cd backend && ruff check --fix . && ruff format .

migration:   ## Nueva migración: make migration m="mensaje"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

monitoring:  ## Prometheus :9090 + Grafana :3000
	docker compose --profile monitoring up -d

tools:       ## Adminer :8081
	docker compose --profile tools up -d

smoke:
	./scripts/smoke.sh http://localhost:8080

reset:       ## ¡Borra la base de datos!
	docker compose down -v
