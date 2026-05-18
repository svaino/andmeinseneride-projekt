import os
import requests
import json
from dotenv import load_dotenv

# 1. Laeme keskkonnamuutujad
load_dotenv()

API_URL = os.getenv("STAT_API_URL")
TABELI_KOOD = "RV021" 
full_url = f"{API_URL}/{TABELI_KOOD}"

# 2. Korreetsed tekstilised koodid ("1")
payload = {
    "query": [
        {
            "code": "Sugu",
            "selection": {
                "filter": "item",
                "values": ["1"]
            }
        },
        {
            "code": "Vanuserühm",
            "selection": {
                "filter": "item",
                "values": ["1"]
            }
        },
        {
            "code": "Aasta",
            "selection": {
                "filter": "item",
                "values": ["2024"]  # Proovime tärni asemel konkreetset aastat
            }
        }
    ],
    "response": {
        "format": "json-stat2"
    }
}

def run_statistikaamet_pipeline():
    print(f"=== STATISTIKAAMETI PIPELINE KÄIVITATUD (Tabel {TABELI_KOOD}) ===")
    
    if not API_URL:
        print("❌ VIGA: `.env` failist ei leitud muutujat STAT_API_URL!")
        return

    # Määramise spetsiaalsed päised, mida PxWeb API sageli ootab
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }

    try:
        print(f"Teen päringu aadressile: {full_url}")
        
        # Kasutame json.dumps(), et tagada puhas UTF-8 string, ja lisame headers
        response = requests.post(
            full_url, 
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), 
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Andmed edukalt kätte saadud!")
            print("-" * 50)
            print(json.dumps(data, indent=2, ensure_ascii=False)[:800])
        else:
            print(f"❌ Viga! Server vastas staatuse koodiga: {response.status_code}")
            print("--- Serveri vastus ---")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Võrgu- või süsteemiviga päringu tegemisel: {e}")

if __name__ == "__main__":
    run_statistikaamet_pipeline()