from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from include.dbt_config import DBT


@dag(
    dag_id="ariregister_paevane",
    schedule="0 3 * * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    tags=["ariregister", "daily"],
    doc_md="""
    Igapäevane Äriregistri voog.

    dbt mudelid valitakse `selectors.yml` kaudu — uusi mudeleid lisades
    Airflow DAG-e muuta ei pea.
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

    tagab_emtak = BashOperator(
        task_id="tagab_emtak_tabelid",
        bash_command=f"""
python <<'PY'
import os
import subprocess
import sys

import psycopg2

required = ("staging.emtak_2025", "staging.emtak_2008_2025")
conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ.get("DB_PORT", "5432"),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
try:
    with conn, conn.cursor() as cur:
        missing = []
        for table in required:
            cur.execute("SELECT to_regclass(%s)", (table,))
            if cur.fetchone()[0] is None:
                missing.append(table)
finally:
    conn.close()

if not missing:
    print("EMTAK tabelid on olemas.")
    sys.exit(0)

print("Puuduvad tabelid:", ", ".join(missing))
print("Laen EMTAK CSV-d ja ehitan dimensioonivaated...")
subprocess.check_call(["python", "/opt/airflow/scripts/03_load_emtak.py"])
subprocess.check_call(["bash", "-c", "{DBT} run --selector bootstrap_dims"])
PY
""",
    )

    dbt_stg = BashOperator(
        task_id="dbt_run_staging_rik",
        bash_command=f"{DBT} run --selector staging_rik",
    )

    tagab_rahvastik = BashOperator(
        task_id="tagab_rahvastik",
        bash_command=f"""
python <<'PY'
import os
import subprocess
import sys

import psycopg2

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ.get("DB_PORT", "5432"),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)


def exists(cur, relation):
    cur.execute("SELECT to_regclass(%s)", (relation,))
    return cur.fetchone()[0] is not None


with conn:
    with conn.cursor() as cur:
        need_stat_load = not exists(cur, "staging.stat_rahvastik")
        need_seed = not exists(cur, "public.dim_maakonnad")
        need_stat_stg = not exists(cur, "staging.stg_stat_rahvastik")
        need_dim_mk = not exists(cur, "intermediate.int_dim_maakonnad")
conn.close()

if not any((need_stat_load, need_seed, need_stat_stg, need_dim_mk)):
    print("Rahvastiku andmed ja dbt vaated on olemas.")
    sys.exit(0)

if need_stat_load:
    print("Laen Statistikaameti rahvastiku andmed...")
    subprocess.check_call(["python", "/opt/airflow/scripts/01_load_statistikaamet.py"])

if need_seed:
    print("Käivitan dbt seed...")
    subprocess.check_call(["bash", "-c", "{DBT} seed"])

if need_stat_stg:
    print("Ehitan rahvastiku staging vaate...")
    subprocess.check_call(["bash", "-c", "{DBT} run --selector staging_stat"])

if need_dim_mk:
    print("Ehitan dimensioonivaated...")
    subprocess.check_call(["bash", "-c", "{DBT} run --selector bootstrap_dims"])
PY
""",
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
        bash_command=f"{DBT} test",
    )

    (
        lae_yldandmed
        >> tagab_emtak
        >> dbt_stg
        >> tagab_rahvastik
        >> dbt_intermediate
        >> dbt_marts
        >> dbt_test
    )


ariregister_paevane()
