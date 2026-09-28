#!/usr/bin/env sh
set -eu

usage() {
  printf 'Usage: TARGET_ENV=staging RESTORE_CONFIRM=RESTORE %s backup.dump\n' "$0" >&2
  exit 64
}

[ "$#" -eq 1 ] || usage
[ -f "$1" ] || { printf 'Backup file not found: %s\n' "$1" >&2; exit 66; }

case ${TARGET_ENV:-} in
  staging|production) ;;
  *) printf 'TARGET_ENV must be staging or production.\n' >&2; exit 64 ;;
esac

[ "${RESTORE_CONFIRM:-}" = "RESTORE" ] || { printf 'Set RESTORE_CONFIRM=RESTORE to continue.\n' >&2; exit 64; }

if [ "$TARGET_ENV" = production ] && [ "${ALLOW_PRODUCTION_RESTORE:-}" != "YES" ]; then
  printf 'Production restore also requires ALLOW_PRODUCTION_RESTORE=YES.\n' >&2
  exit 64
fi

postgres_user=${POSTGRES_USER:-crm}
postgres_db=${POSTGRES_DB:-crm_fidelizacion}

printf 'Restoring %s database from %s.\n' "$TARGET_ENV" "$1"
docker compose exec -T db pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction --username "$postgres_user" --dbname "$postgres_db" < "$1"
printf 'Restore completed. Run application smoke checks before reopening access.\n'
