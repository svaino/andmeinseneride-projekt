import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import BigInteger, String, TIMESTAMP, create_engine, text

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.getenv("DATA_DIR", os.path.join(os.path.dirname(script_dir), "data"))

engine = create_engine(
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('POSTGRES_DB')}"
)


def prepare_emtak_reload(conn):
    """Eemalda dbt vaated ja staging tabelid enne uuesti laadimist."""
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
    for view in (
        "staging.emtak_2025_juur",
        "intermediate.int_dim_emtak",
    ):
        conn.execute(text(f"DROP VIEW IF EXISTS {view} CASCADE"))
    for table in ("staging.emtak_2025", "staging.emtak_2008_2025"):
        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))


with engine.begin() as conn:
    prepare_emtak_reload(conn)

df1 = pd.read_csv(
    os.path.join(data_dir, "EMTAK_2025.csv"),
    sep=";",
    quotechar='"',
    engine="python",
)
df1.insert(0, "id", range(1, len(df1) + 1))
df1["created_at"] = datetime.now(timezone.utc)
df1.columns = df1.columns.str.lower().str.replace(" ", "_").str.replace("?", "", regex=False)

df1.to_sql("emtak_2025", engine, schema="staging", if_exists="append", index=False)
print(f"✅ esimene_tabel laetud: {len(df1)} rida")

df2 = pd.read_csv(
    os.path.join(data_dir, "EMTAK_uleminekutabel_2008_EMTAK_2025.csv"),
    sep=";",
    quotechar='"',
    engine="python",
    dtype=str,
)
df2.columns = df2.columns.str.lower().str.replace(" ", "_").str.replace("?", "", regex=False)
df2.insert(0, "id", range(1, len(df2) + 1))
df2["created_at"] = datetime.now(timezone.utc)

df2.to_sql(
    "emtak_2008_2025",
    engine,
    schema="staging",
    if_exists="append",
    index=False,
    dtype={
        "id": BigInteger(),
        "kood_emtak_2008": String(),
        "kood_emtak_2025": String(),
        "created_at": TIMESTAMP(timezone=True),
    },
)
print(f"✅ teine_tabel laetud: {len(df2)} rida")
