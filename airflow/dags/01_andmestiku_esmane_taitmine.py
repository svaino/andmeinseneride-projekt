from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag


@dag(
    dag_id="01_andmestiku_esmane_taitmine",
    schedule=None,
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["bootstrap", "setup", "import"],
    doc_md="""
    Ühekordne (või harv) käivitus pärast repo kloonimist või kui EMTAK CSV-d muutuvad.

    Laadib EMTAK CSV-d stagingusse. dbt käivitub eraldi DAG-is `05_dbt_igapaevane`.
    """,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
)
def andmestiku_esmane_taitmine():
    lae_emtak = BashOperator(
        task_id="lae_emtak",
        bash_command="python /opt/airflow/scripts/03_load_emtak.py",
    )

    lae_emtak


andmestiku_esmane_taitmine()
