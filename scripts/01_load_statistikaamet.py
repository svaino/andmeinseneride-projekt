import os
import requests
import json
import itertools
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# 1. Keskkonnamuutujate laadimine
load_dotenv()

API_URL = os.getenv("STAT_API_URL")
TABELI_KOOD = "RV022U" 
full_url = f"{API_URL}/{TABELI_KOOD}"
BATCH_SIZE = 5000

# Päringu payload (kõik 5 dimensiooni)
payload = {
    "query": [
        {"code": "Aasta", "selection": {"filter": "all", "values": ["*"]}},
        {"code": "Vanuserühm", "selection": {"filter": "all", "values": ["*"]}},
        {"code": "Maakond", "selection": {"filter": "all", "values": ["*"]}},
        {"code": "Sugu", "selection": {"filter": "all", "values": ["*"]}},
        {"code": "Rahvus", "selection": {"filter": "all", "values": ["*"]}}
    ],
    "response": {"format": "json-stat2"}
}


def get_db_connection():
    """Loob ühenduse PostgreSQL andmebaasiga."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT_HOST", "5432"),
        database=os.getenv("POSTGRES_DB", "praktikum"),
        user=os.getenv("POSTGRES_USER", "praktikum"),
        password=os.getenv("POSTGRES_PASSWORD", "praktikum")
    )


def prepare_database():
    """Valmistab ette staging skeemi ja andmetabeli Statistikaameti andmetele."""
    print("Andmebaasi struktuuri kontroll ja ettevalmistamine...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staging.stat_rahvastik (
            aasta INT,
            vanusegrupp VARCHAR(100),
            maakond VARCHAR(150),
            sugu VARCHAR(50),
            rahvus VARCHAR(100),
            elanike_arv INT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (aasta, vanusegrupp, maakond, sugu, rahvus)
        );
    """)
    cur.execute("""
        ALTER TABLE staging.stat_rahvastik
        ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✓ Staging tabel `staging.stat_rahvastik` on valmis.")


def parse_and_insert_json_stat(data):
    """Parsib keerulise json-stat2 formaadi lamedaks tabeliks ja salvestab baasi."""
    print("Alustan json-stat2 formaadi parsimist ja andmebaasi laadimist...")
    
    # 1. Võtame vastusest dimensioonide järjekorra ja tekstilised väärtused
    dimension_ids = data['id'] 
    dimensions = data['dimension']
    
    dim_lists = []
    for dim_id in dimension_ids:
        labels = list(dimensions[dim_id]['category']['label'].values())
        dim_lists.append(labels)
        
    # 2. Võtame tegelikud andmeväärtused
    values_list = data['value']
    
    # 3. Genereerime kõik võimalikud dimensioonide kombinatsioonid
    all_combinations = list(itertools.product(*dim_lists))
    
    if len(all_combinations) != len(values_list):
        print(f"⚠️ Hoiatus: Kombinatsioonide arv ({len(all_combinations)}) ei kattu väärtuste arvuga ({len(values_list)})!")

    conn = get_db_connection()
    cur = conn.cursor()
    
    batch = []
    inserted_count = 0
    
    aasta_idx = dimension_ids.index("Aasta")
    vanus_idx = dimension_ids.index("Vanuserühm")
    maakond_idx = dimension_ids.index("Maakond")
    sugu_idx = dimension_ids.index("Sugu")
    rahvus_idx = dimension_ids.index("Rahvus")

    for idx, combo in enumerate(all_combinations):
        value = values_list[idx]
        
        if value is None:
            continue
            
        aasta = int(combo[aasta_idx])
        vanusegrupp = combo[vanus_idx]
        maakond = combo[maakond_idx]
        sugu = combo[sugu_idx]
        rahvus = combo[rahvus_idx]
        elanike_arv = int(value)
        
        batch.append((aasta, vanusegrupp, maakond, sugu, rahvus, elanike_arv))
        
        if len(batch) >= BATCH_SIZE:
            insert_batch(cur, batch)
            conn.commit()
            inserted_count += len(batch)
            print(f"   .. andmebaasi lükatud {inserted_count} rida ..")
            batch = []
            
    if batch:
        insert_batch(cur, batch)
        conn.commit()
        inserted_count += len(batch)

    cur.close()
    conn.close()
    print(f"✓ Valmis! Staging kihti laeti edukalt {inserted_count} rida.")


def insert_batch(cur, batch_data):
    """Teostab kiire mass-salvestuse (Upsert režiimis) ja värskendab loaded_at aega konflikti korral."""
    # MUUDATUS: Konflikti korral uuendatakse elanike arvu ning loaded_at seatakse väärtusele NOW()
    query = """
        INSERT INTO staging.stat_rahvastik (
            aasta, vanusegrupp, maakond, sugu, rahvus, elanike_arv
        ) VALUES %s
        ON CONFLICT (aasta, vanusegrupp, maakond, sugu, rahvus) DO UPDATE SET
            elanike_arv = EXCLUDED.elanike_arv,
            loaded_at = NOW();
    """
    execute_values(cur, query, batch_data)


def run_statistikaamet_pipeline():
    print(f"=== STATISTIKAAMETI PIPELINE KÄIVITATUD (Tabel {TABELI_KOOD}) ===")
    
    if not API_URL:
        print("❌ VIGA: `.env` failist ei leitud muutujat STAT_API_URL!")
        return

    prepare_database()

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }

    try:
        print(f"Teen päringu aadressile: {full_url}")
        response = requests.post(
            full_url, 
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), 
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Andmed edukalt kätte saadud!")
            print("-" * 50)
            
            parse_and_insert_json_stat(data)
            
        else:
            print(f"❌ Viga! Server vastas staatuse koodiga: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Võrgu- või süsteemiviga päringu tegemisel: {e}")


if __name__ == "__main__":
    run_statistikaamet_pipeline()