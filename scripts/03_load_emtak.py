import pandas as pd
from sqlalchemy import create_engine
import os
from datetime import datetime, timezone

# see rida on lisatud view jaoks:
from sqlalchemy import create_engine, text

engine = create_engine(
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('POSTGRES_DB')}"
)

# EMTAK2025 failist import

df1 = pd.read_csv('/app/data/EMTAK_2025.csv', sep=';', quotechar='"', engine='python')
# Lisaveerud id ja created_at jaoks
df1.insert(0, 'id', range(1, len(df1) + 1))
df1['created_at'] = datetime.now(timezone.utc)

# Muudan veergude pealkirjad viisakaks
df1.columns = df1.columns.str.lower().str.replace(' ', '_').str.replace('?', '', regex=False)

# Lisan view kustutamise siia, sest pandas ei saa tabelit kustutada
with engine.connect() as conn:
    conn.execute(text("DROP VIEW IF EXISTS staging.emtak_2025_juur CASCADE"))
    conn.commit()


df1.to_sql('emtak_2025', engine, schema='staging', if_exists='replace', index=False)
print(f"✅ esimene_tabel laetud: {len(df1)} rida")

# Teine, üleminek 2008 --> 2025 CSV
df2 = pd.read_csv('/app/data/EMTAK_uleminekutabel_2008_EMTAK_2025.csv', sep=';')
# Lisaveerud id ja created_at jaoks
df2.insert(0, 'id', range(1, len(df2) + 1))
df2['created_at'] = datetime.now(timezone.utc)

# Muudan veergude pealkirjad viisakaks
df2.columns = df2.columns.str.lower().str.replace(' ', '_').str.replace('?', '', regex=False)

df2.to_sql('emtak_2008_2025', engine, schema='staging', if_exists='replace', index=False)
print(f"✅ teine_tabel laetud: {len(df2)} rida")


# Tekitan view (ajutine?), millest saab võtta alamkoodidele ülimad tegevusala tasemed
with engine.connect() as conn:
    conn.execute(text("""
        CREATE OR REPLACE VIEW staging.emtak_2025_juur AS
        WITH RECURSIVE hierarhia AS (
            SELECT kood, vanem, kood AS juur
            FROM staging.emtak_2025
            WHERE vanem IS NULL

            UNION ALL

            SELECT e.kood, e.vanem, h.juur
            FROM staging.emtak_2025 e
            JOIN hierarhia h ON e.vanem = h.kood
        )
        SELECT 
            h.kood, 
            h.juur AS kõrgeim_vanem,
            e.tegevusala_tekst AS kõrgeim_vanem_nimi
        FROM hierarhia h
        JOIN staging.emtak_2025 e ON e.kood = h.juur;
    """))
    conn.commit()