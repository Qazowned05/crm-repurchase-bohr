# Despliegue Y Mantenimiento

## Desarrollo Local

1. Copia `.env.example` a `.env`.
2. Define una clave de aplicación de al menos 32 caracteres y las credenciales del administrador inicial.
3. Ejecuta `docker compose up --build`.
4. Abre `http://localhost:5173` y consulta la API en `http://localhost:8001/docs`.

El contenedor backend ejecuta `alembic upgrade head` antes de iniciar, por lo que las migraciones se aplican automáticamente.

## Ejecución Sin Docker

```bash
# Terminal 1: PostgreSQL disponible y .env configurado para localhost
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.create_initial_admin
uvicorn app.main:app --reload --port 8001

# Terminal 2
cd frontend
npm install
npm run dev
```

Si el frontend no usa el proxy de Vite, define `VITE_API_URL` con el origen de la API.

## Producción

1. Copia `.env.production.example` fuera del repositorio, por ejemplo a `/srv/crm-fidelizacion/.env.production`.
2. Configura secretos únicos: `APP_SECRET_KEY`, `POSTGRES_PASSWORD` e `INITIAL_ADMIN_PASSWORD`.
3. Establece `APP_ENV_FILE` y `BACKUP_HOST_PATH` en el entorno de despliegue.
4. Ejecuta:

```bash
docker compose -f docker-compose.yml -f compose.production.yml \
  --env-file /srv/crm-fidelizacion/.env.production up -d --build
```

El override productivo no expone PostgreSQL ni la API. El frontend queda ligado, por defecto, a `127.0.0.1:8080`; un proxy HTTPS externo debe terminar TLS y reenviar a ese puerto.

## Verificación Posterior

```bash
docker compose ps
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
docker compose logs --since=15m backend db
```

El proxy de frontend reenvía `/api/` al backend. Comprueba además inicio de sesión, creación de venta, generación de alertas e informe Excel como prueba funcional mínima.

## Copias Y Recuperación

Mantén los respaldos de PostgreSQL fuera del host y prueba restauraciones en staging antes de producción. Detén escritores durante una restauración y conserva el archivo fuente. No almacenes `.env` ni secretos en Git.

## Observabilidad

Supervisa salud HTTP, reinicios de contenedores, almacenamiento del volumen PostgreSQL, resultados de respaldos y vencimiento del certificado TLS. Conserva los eventos de auditoría como evidencia operativa.
