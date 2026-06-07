#!/usr/bin/env python3
"""Unpause scheduled DAGs (02-05) and trigger 01 once if it has never succeeded."""

from __future__ import annotations

import os
import subprocess
import sys
import time

FIRST_DAG = "01_andmestiku_esmane_taitmine"
SCHEDULED_DAGS = (
    "02_rahvastik_kuuine_laadimine",
    "03_ariregister_kuuine_taielaadimine",
    "04_ariregister_igapaevane_increment",
    "05_dbt_igapaevane",
)
REGISTRATION_PROBE_DAG = "05_dbt_igapaevane"
DAG_REGISTER_TIMEOUT_SEC = 120
DAG_REGISTER_POLL_SEC = 5
TRIGGER_WAIT_TIMEOUT_SEC = 600
TRIGGER_POLL_SEC = 10


def log(msg: str) -> None:
    print(msg, flush=True)


def airflow_cmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["airflow", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def wait_for_dag_registration() -> None:
    deadline = time.monotonic() + DAG_REGISTER_TIMEOUT_SEC
    while time.monotonic() < deadline:
        result = airflow_cmd("dags", "list", "--output", "plain")
        if result.returncode == 0 and REGISTRATION_PROBE_DAG in result.stdout:
            log(f"DAG {REGISTRATION_PROBE_DAG} registered.")
            return
        time.sleep(DAG_REGISTER_POLL_SEC)
    raise TimeoutError(
        f"DAG {REGISTRATION_PROBE_DAG} not registered within {DAG_REGISTER_TIMEOUT_SEC}s"
    )


def unpause_dags() -> None:
    for dag_id in SCHEDULED_DAGS:
        result = airflow_cmd("dags", "unpause", dag_id)
        if result.returncode != 0:
            log(f"WARN: unpause {dag_id}: {result.stderr.strip() or result.stdout.strip()}")
        else:
            log(f"Unpaused {dag_id} (runs on cron).")


def has_successful_run(dag_id: str) -> bool:
    result = airflow_cmd(
        "dags",
        "list-runs",
        dag_id,
        "--state",
        "success",
        "--output",
        "plain",
    )
    if result.returncode != 0:
        log(f"WARN: list-runs for {dag_id}: {result.stderr.strip()}")
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return len(lines) > 0


def wait_for_run_terminal(dag_id: str, run_id: str) -> bool:
    deadline = time.monotonic() + TRIGGER_WAIT_TIMEOUT_SEC
    while time.monotonic() < deadline:
        result = airflow_cmd("dags", "list-runs", dag_id, "--output", "plain")
        if result.returncode != 0:
            time.sleep(TRIGGER_POLL_SEC)
            continue
        for line in result.stdout.splitlines():
            if run_id not in line:
                continue
            lower = line.lower()
            if "success" in lower:
                return True
            if "failed" in lower:
                log(f"ERROR: {dag_id} run {run_id} failed.")
                return False
        time.sleep(TRIGGER_POLL_SEC)
    log(f"WARN: timed out waiting for {dag_id} run {run_id}.")
    return False


def trigger_first_dag_if_needed() -> None:
    if has_successful_run(FIRST_DAG):
        log(f"Skip trigger {FIRST_DAG}: successful run already exists.")
        return

    log(f"Triggering {FIRST_DAG} (no prior successful run).")
    result = airflow_cmd("dags", "trigger", FIRST_DAG, "--output", "plain")
    if result.returncode != 0:
        log(f"ERROR: trigger {FIRST_DAG}: {result.stderr.strip()}")
        return

    run_id = None
    for line in result.stdout.splitlines():
        for part in line.split():
            if "manual__" in part:
                run_id = part.strip("|,")
                break
        if run_id:
            break

    if not run_id:
        log(f"Triggered {FIRST_DAG}; could not parse run_id from output.")
        return

    log(f"Waiting for {FIRST_DAG} run {run_id}...")
    wait_for_run_terminal(FIRST_DAG, run_id)


def main() -> int:
    if os.environ.get("AIRFLOW_AUTO_BOOTSTRAP", "true").lower() in ("0", "false", "no"):
        log("AIRFLOW_AUTO_BOOTSTRAP disabled, skipping.")
        return 0

    log("Airflow startup bootstrap...")
    try:
        wait_for_dag_registration()
        unpause_dags()
        trigger_first_dag_if_needed()
    except TimeoutError as exc:
        log(f"ERROR: {exc}")
        return 1

    log("Bootstrap finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
