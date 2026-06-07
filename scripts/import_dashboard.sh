#!/usr/bin/env bash
# Impordib Superset dashboard'i definitsioonid repost.
#
# Kasutamine:
#   1. Käivita projekt: docker compose up -d
#   2. Oota, kuni Superset on käivitunud (http://localhost:8088)
#   3. Käivita see skript: bash scripts/import_dashboard.sh
#
# Dashboard eksport asub: superset/dashboards/ettevotted_dashboard.zip
# (lisatakse reposse pärast projekti esmakordset seadistamist)

set -e

DASHBOARD_FILE="/app/dashboards/ettevotted_dashboard.zip"
CONTAINER="andmeinseneeria-superset"

if [ ! -f "$DASHBOARD_FILE" ]; then
  echo "Dashboard faili ei leitud."
  exit 1
fi


echo "Impordime dashboard'i Supersetti..."
superset import-dashboards \
  --path "$DASHBOARD_FILE" \
  --username admin

echo "Valmis! Ava Superset: http://localhost:8088"