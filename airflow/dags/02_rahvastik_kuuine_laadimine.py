from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag


@dag(
    dag_id="02_rahvastik_kuuine_laadimine",
    schedule="0 4 1 * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["rahvastik", "monthly", "import"],
    doc_md="""
    Kuine Statistikaameti rahvastikuandmete laadimine (1. kuupäev 04:00).

    dbt transformatsioonid käivituvad eraldi DAG-is `05_dbt_igapaevane`.
    """,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
)
def rahvastik_kuuine_laadimine():
    lae_rahvastik = BashOperator(
        task_id="lae_rahvastik",
        bash_command="python /opt/airflow/scripts/01_load_statistikaamet.py",
    )

    lae_rahvastik


rahvastik_kuuine_laadimine()
