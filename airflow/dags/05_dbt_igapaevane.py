from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from include.dbt_config import DBT


@dag(
    dag_id="05_dbt_igapaevane",
    schedule="0 5 * * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "daily"],
    doc_md="""
    Igapäevane dbt voog (05:00).

    Käivitab deps, seed, staging, intermediate, marts ja testid.
    Mudelite valik: `dbt_project/rik_stat_dbt/selectors.yml`.
    """,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
)
def dbt_igapaevane():
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT} deps",
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT} seed",
    )

    dbt_run_staging_rik = BashOperator(
        task_id="dbt_run_staging_rik",
        bash_command=f"{DBT} run --selector staging_rik",
    )

    dbt_run_staging_stat = BashOperator(
        task_id="dbt_run_staging_stat",
        bash_command=f"{DBT} run --selector staging_stat",
    )

    dbt_run_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=f"{DBT} run --selector layer_intermediate",
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT} run --selector layer_marts",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT} test",
    )

    (
        dbt_deps
        >> dbt_seed
        >> dbt_run_staging_rik
        >> dbt_run_staging_stat
        >> dbt_run_intermediate
        >> dbt_run_marts
        >> dbt_test
    )


dbt_igapaevane()
