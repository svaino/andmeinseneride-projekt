from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag


@dag(
    dag_id="03_ariregister_kuine_taislaadimine",
    schedule="0 3 1 * *",
    start_date=pendulum.datetime(2026, 5, 1, tz="Europe/Tallinn"),
    catchup=False,
    max_active_runs=1,
    tags=["ariregister", "monthly", "import"],
    doc_md="""
    Kuine Äriregistri täislaadimine (1. kuupäev 03:00).

    Laadib üldandmed; kontrollib EMTAK ja rahvastiku staging-tabelid ning laadib
    need vajadusel. dbt käivitub eraldi DAG-is `05_dbt_igapaevane` (05:00).
    """,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
)
def ariregister_kuine_taislaadimine():
    lae_yldandmed = BashOperator(
        task_id="lae_ariregister_yldandmed",
        bash_command="python /opt/airflow/scripts/02_01_load_ariregister_yldandmed.py",
    )

    tagab_emtak = BashOperator(
        task_id="tagab_emtak_tabelid",
        bash_command="""
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
print("Laen EMTAK CSV-d...")
subprocess.check_call(["python", "/opt/airflow/scripts/03_load_emtak.py"])
PY
""",
    )

    tagab_rahvastik = BashOperator(
        task_id="tagab_rahvastik",
        bash_command="""
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
conn.close()

if not need_stat_load:
    print("Rahvastiku andmed on olemas.")
    sys.exit(0)

print("Laen Statistikaameti rahvastiku andmed...")
subprocess.check_call(["python", "/opt/airflow/scripts/01_load_statistikaamet.py"])
PY
""",
    )

    lae_yldandmed >> tagab_emtak >> tagab_rahvastik


ariregister_kuine_taislaadimine()
