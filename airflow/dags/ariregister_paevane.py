from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

DBT_DIR = "/opt/airflow/dbt_project/rik_stat_dbt"
DBT = f"cd {DBT_DIR} && dbt"


@dag(
    dag_id="ariregister_paevane",
    schedule="0 3 * * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    tags=["ariregister", "daily"],
    doc_md="""
    Igapäevane Äriregistri voog.

    Eeldab, et `andmestiku_esmane_taitmine` on juba käivitatud (EMTAK + dbt seed).
    """,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
)
def ariregister_paevane():
    lae_yldandmed = BashOperator(
        task_id="lae_ariregister_yldandmed",
        bash_command="python /opt/airflow/scripts/02_01_load_ariregister_yldandmed.py",
    )

    lae_muudatused = BashOperator(
        task_id="lae_ariregister_muudatused",
        bash_command="python /opt/airflow/scripts/02_02_load_ariregister_muudatused.py",
    )

    dbt_stg = BashOperator(
        task_id="dbt_run_staging_rik",
        bash_command=(
            f"{DBT} run --select stg_ariregister_yldandmed stg_ariregister_viimased_6a"
        ),
    )

    dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            f"{DBT} run --select "
            "int_ettevotete_arv_maakonniti int_ettevotete_arv_maakonniti_6a "
            "mart_maakondade_statistika mart_ettevotlikus_6a "
            "mart_elanikke_ettevõtte_kohta_20250101"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"{DBT} test --select "
            "stg_ariregister_yldandmed stg_ariregister_viimased_6a "
            "int_ettevotete_arv_maakonniti int_ettevotete_arv_maakonniti_6a"
        ),
    )

    lae_yldandmed >> lae_muudatused >> dbt_stg >> dbt_marts >> dbt_test


ariregister_paevane()
