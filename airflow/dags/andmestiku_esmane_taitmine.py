from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from include.dbt_config import DBT


@dag(
    dag_id="andmestiku_esmane_taitmine",
    schedule=None,
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    tags=["bootstrap", "setup"],
    doc_md="""
    Ühekordne (või harv) käivitus pärast repo kloonimist või kui staatilised failid muutuvad.

    Laadib EMTAK CSV-d stagingusse, täidab dbt seemned ja dimensioonivaated.
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

    dbt_deps = BashOperator(
            task_id="dbt_deps",
            bash_command=f"{DBT} deps",
        )
    
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT} seed",
    )

    dbt_run_dims = BashOperator(
        task_id="dbt_run_dimensions",
        bash_command=f"{DBT} run --selector bootstrap_dims",
    )

    lae_emtak >> dbt_seed >> dbt_deps >> dbt_run_dims


andmestiku_esmane_taitmine()
