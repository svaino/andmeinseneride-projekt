#!/usr/bin/env bash
set -euo pipefail

if [[ "${AIRFLOW_AUTO_BOOTSTRAP:-true}" == "false" ]]; then
  echo "AIRFLOW_AUTO_BOOTSTRAP=false, skipping bootstrap."
  exit 0
fi

echo "Running Airflow startup bootstrap..."
/entrypoint python /opt/airflow/scripts/airflow_startup_bootstrap.py
