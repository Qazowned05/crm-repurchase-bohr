# CRM Fidelizacion

## Inicio local

1. Copie `.env.example` como `.env` y cambie `APP_SECRET_KEY` e `INITIAL_ADMIN_PASSWORD`.
2. Ejecute `docker compose up --build`.
3. Abra la documentacion OpenAPI en `http://localhost:8001/docs` y autentique las solicitudes con el administrador configurado.

La API queda disponible en `http://localhost:8001` y su documentacion en `http://localhost:8001/docs`.

## Test and Operations

```sh
cd backend && python -m pytest
docker compose up --build
docker compose ps
docker compose logs --since=15m backend db
```

Deployment, HTTPS reverse-proxy prerequisites for the API, backup/restore drills, monitoring, and release acceptance are documented in [RUNBOOK.md](RUNBOOK.md). The production deployment template is `compose.production.yml`; it requires protected environment values and is intentionally separate from the local development stack.

## Flujo operativo

El flujo integral de ventas, alertas, seguimiento, recuperación, supervisión y los avances entregados está documentado en [docs/WORKFLOW.md](docs/WORKFLOW.md).
