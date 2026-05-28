from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

DBT_DIR = "/opt/airflow/dbt_project/rik_stat_dbt"
DBT = f"cd {DBT_DIR} && dbt"


@dag(
    dag_id="andmestiku_esmane_taitmine",
    schedule=None,
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    tags=["bootstrap", "setup"],
    doc_md="""
    Ühekordne (või harv) käivitus pärast repo kloonimist või kui staatilised failid muutuvad.

    Laadib EMTAK CSV-d stagingusse, täidab dbt seemned (nt `dim_maakonnad`) ja
    ehitab dimensioonivaated. `stg_ariregister_*` mudelid käivituvad
    `ariregister_paevane` DAG-is pärast üldandmete laadimist.
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

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT} seed",
    )

    dbt_run_dims = BashOperator(
        task_id="dbt_run_dimensions",
        bash_command=f"{DBT} run --select int_dim_emtak int_dim_maakonnad",
    )

    lae_emtak >> dbt_seed >> dbt_run_dims


andmestiku_esmane_taitmine()
