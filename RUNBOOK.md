# Operations Runbook

## Staging Deployment

1. Provision a Linux host with current Docker Engine and Docker Compose v2.24 or later. Create a protected persistent directory such as `/srv/crm-fidelizacion/backups` and restrict it to the deployment operator.
2. Copy `.env.production.example` to `/srv/crm-fidelizacion/.env.production`. Set unique, strong values for `APP_SECRET_KEY`, `POSTGRES_PASSWORD`, and `INITIAL_ADMIN_PASSWORD`. Keep this file out of source control and do not paste it into tickets or logs.
3. Set `APP_ENV_FILE=/srv/crm-fidelizacion/.env.production` and `BACKUP_HOST_PATH=/srv/crm-fidelizacion/backups` in the deployment shell or protected environment manager. The database password embedded in `DATABASE_URL` must be URL-encoded and match `POSTGRES_PASSWORD`.
4. Deploy: `docker compose -f docker-compose.yml -f compose.production.yml --env-file /srv/crm-fidelizacion/.env.production up -d --build`.
5. Verify: `docker compose -f docker-compose.yml -f compose.production.yml --env-file /srv/crm-fidelizacion/.env.production ps`, then `curl -fsS http://127.0.0.1:8080/health`.

The production override removes database and backend host ports and enables `unless-stopped`. Use a distinct Compose project and distinct secrets/data path for staging.

## HTTPS Reverse Proxy

An external reverse proxy, DNS record, firewall rules, and valid TLS certificate are prerequisites. This repository does not provision a domain or certificates. Configure the proxy to terminate HTTPS and forward only to `http://127.0.0.1:8080`; preserve `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto`. Redirect HTTP to HTTPS, restrict administrative host access, and renew/test certificates through the selected proxy and certificate tooling. Do not expose PostgreSQL or the backend directly to the internet.

## Backup And Restore Drill

Run backups from the deployment directory after setting the same Compose files and protected environment variables used for deployment. The scripts do not print passwords and create PostgreSQL custom-format archives.

```sh
export COMPOSE_FILE=docker-compose.yml:compose.production.yml
export BACKUP_DIR=/srv/crm-fidelizacion/backups
./scripts/backup-postgres.sh
```

Test restores only on staging. Announce the maintenance window, stop writers, retain the source archive, then restore with explicit safeguards:

```sh
docker compose stop backend
TARGET_ENV=staging RESTORE_CONFIRM=RESTORE ./scripts/restore-postgres.sh /srv/crm-fidelizacion/backups/crm_fidelizacion-YYYYMMDDTHHMMSSZ.dump
docker compose start backend
curl -fsS http://127.0.0.1:8080/health
```

Production restores additionally require `ALLOW_PRODUCTION_RESTORE=YES`. Perform and record a staging restore drill before each release and at least quarterly. Copy encrypted backups off-host, test retention/recovery ownership, and never rely solely on the local backup directory.

## Monitoring And Logging

Check service state with `docker compose ps`, recent logs with `docker compose logs --since=15m backend db`, and HTTP health at `/health`. Alert on unavailable health checks, container restart loops, backup failure/missing backup, disk capacity, database volume growth, and TLS expiry. Forward Docker logs to the organization-approved central log system; limit access, retain audit evidence, and keep credentials and authorization headers out of logs.

## Pilot Acceptance Checklist

- Staging deployment is healthy behind HTTPS and no database/backend port is internet-accessible.
- API authentication, user role access, customer/product import preview and commit, sale creation, alert workflow, and reports are accepted by pilot users through OpenAPI or an approved API client.
- Unauthorized access, expired session handling, invalid import rows, and a duplicate/annulled sale path are exercised.
- A current backup is present, an independent staging restore drill passed, and rollback owner/contact details are recorded.
- Monitoring, log access, support escalation, and training materials are accepted by operations and pilot owners.

## Production Go/No-Go

Go only when every pilot checklist item passes, release commit and CI are green, secrets are provisioned outside the repository, backup/rollback owners are on call, capacity is sufficient, and the HTTPS proxy is verified. No-go for failing health checks, unresolved security defects, absent restore evidence, unknown data migration impact, or missing business owner approval.
