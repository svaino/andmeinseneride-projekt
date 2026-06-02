from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag


@dag(
    dag_id="ariregister_incremental_daily",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 6, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["ariregister", "incremental"],
    doc_md="""
    Igapäevane Äriregistri inkrementaalne laadimine.

    Kontrollib eelmise päeva Esmakanded.
    Kui leitakse uued ettevõtted, küsib nende andmed lihtandmed_v2 API kaudu
    ja lisab/uuendab need staging.ariregister_uldandmed tabelis.
    """,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
)
def ariregister_incremental_daily():
    lae_ariregister_incremental = BashOperator(
        task_id="lae_ariregister_incremental",
        bash_command="python -u /opt/airflow/scripts/04_load_ariregister_incremental.py",
    )

    lae_ariregister_incremental


ariregister_incremental_daily()