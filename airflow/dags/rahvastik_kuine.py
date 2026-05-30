from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from include.dbt_config import DBT


@dag(
    dag_id="rahvastik_kuine",
    schedule="0 4 1 * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["rahvastik", "monthly"],
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
)
def rahvastik_kuine():
    lae = BashOperator(
        task_id="lae_rahvastik",
        bash_command="python /opt/airflow/scripts/01_load_statistikaamet.py",
    )

    dbt_stg = BashOperator(
        task_id="dbt_run_staging_stat",
        bash_command=f"{DBT} run --selector staging_stat",
    )

    dbt_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=f"{DBT} run --selector layer_intermediate",
    )

    dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT} run --selector layer_marts",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT} test --select stg_stat_rahvastik+",
    )

    lae >> dbt_stg >> dbt_intermediate >> dbt_marts >> dbt_test


rahvastik_kuine()
