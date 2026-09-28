#!/usr/bin/env sh
set -eu

umask 077

backup_dir=${BACKUP_DIR:-./backups}
postgres_user=${POSTGRES_USER:-crm}
postgres_db=${POSTGRES_DB:-crm_fidelizacion}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file="$backup_dir/${postgres_db}-${timestamp}.dump"
temporary_file="$backup_file.partial"

mkdir -p "$backup_dir"
trap 'rm -f "$temporary_file"' EXIT HUP INT TERM

docker compose exec -T db pg_dump --format=custom --no-owner --no-privileges --username "$postgres_user" --dbname "$postgres_db" > "$temporary_file"
mv "$temporary_file" "$backup_file"
trap - EXIT HUP INT TERM

printf 'Backup created: %s\n' "$backup_file"
