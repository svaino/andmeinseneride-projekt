import os
import datetime
import xml.etree.ElementTree as ET
import requests
import psycopg2
from dotenv import load_dotenv

# ==========================================
# 1. KESKKONNAMUUTUJAD (.env)
# ==========================================
load_dotenv()

# Äriregistri ametlik SOAP toodangukeskkond
API_URL = "https://ariregxmlv6.rik.ee/"

ARIREGISTER_USER = os.getenv("ARIREGISTER_USER")
ARIREGISTER_PASSWORD = os.getenv("ARIREGISTER_PASSWORD")

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")  
DB_PORT = os.getenv("DB_PORT_HOST", "5432")
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")


# ==========================================
# 2. POSTGRESQL STAGING TABELI SEADISTAMINE
# ==========================================
def seadista_postgres_staging():
    print("🐘 Ühendun PostgreSQL andmebaasiga...")
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cursor = conn.cursor()
    
    cursor.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    cursor.execute("DROP TABLE IF EXISTS staging.stg_ariregister_muudatused;")
    
    # Loome tabeli: Lisatud nõutud indikaatorveerg 'isikuandmed' (Y/N)
    cursor.execute('''
        CREATE TABLE staging.stg_ariregister_muudatused (
            id SERIAL PRIMARY KEY,
            ariregistri_kood INT,
            arinimi VARCHAR(255),
            oiguslik_vorm VARCHAR(50),
            kande_nr INT,
            kande_kuupaev DATE,
            kande_liik_tekst TEXT,
            kandevaline_muudatus INT DEFAULT 0,
            isikuandmed VARCHAR(10),
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    return conn, cursor


# ==========================================
# 3. SOAP XML PÄRINGU PANDI (ÜHE PÄEVA KOHTA)
# ==========================================
def küsi_päeva_muudatused(kuupaev_str):
    """Koostab dokumentatsioonile vastava SOAP XML ümbriku ja teeb post-päringu."""
    
    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:prod="http://arireg.x-road.eu/producer/">
       <soapenv:Header/>
       <soapenv:Body>
          <prod:ettevotjaMuudatusedTasuline_v1>
             <prod:keha>
                <prod:ariregister_kasutajanimi>{ARIREGISTER_USER}</prod:ariregister_kasutajanimi>
                <prod:ariregister_parool>{ARIREGISTER_PASSWORD}</prod:ariregister_parool>
                <prod:kuupaev>{kuupaev_str}</prod:kuupaev>
             </prod:keha>
          </prod:ettevotjaMuudatusedTasuline_v1>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": ""
    }

    response = requests.post(API_URL, data=soap_body.encode('utf-8'), headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


# ==========================================
# 4. XML PARSIMINE JA ANDMEBAASI SALVESTAMINE
# ==========================================
def töötle_ja_salvesta(xml_data, kuupaev_str, db_conn, db_cursor):
    # XML-ist nimeruumide (namespaces) eemaldamine parsimise lihtsustamiseks
    try:
        xml_puhas = xml_data.encode('utf-8')
        root = ET.fromstring(xml_puhas)
    except Exception as e:
        print(f"❌ XML parsimise viga kuupäeval {kuupaev_str}: {e}")
        return 0

    # Otsime üles kõik <ettevotja_muudatused> plokid sõltumata nimeruumist
    ettevotja_muudatused = root.findall('.//{*}ettevotja_muudatused')
    
    lisatud_sellel_päeval = 0

    for muudatus in ettevotja_muudatused:
        ari_kood = muudatus.findtext('{*}ariregistri_kood')
        arinimi = muudatus.findtext('{*}arinimi')
        vorm = muudatus.findtext('{*}oiguslik_vorm')
        
        # Kontrollime kandeväliseid isiku/sidevahendite/tegevusalade muudatusi (Y/N)
        kv_isikud = muudatus.findtext('{*}kandevalised_isikud')
        kv_sidevahendid = muudatus.findtext('{*}kandevalised_sidevahendid')
        kv_tegevusalad = muudatus.findtext('{*}kandevalised_tegevusalad')
        
        # Kui mõni neist on 'Y', siis on tegu kandevälise muudatusega
        on_kandevaline = 1 if (kv_isikud == 'Y' or kv_sidevahendid == 'Y' or kv_tegevusalad == 'Y') else 0

        # Vaatame, kas plokis on ametlikke kandeid (<kanded> element)
        kanded = muudatus.findall('{*}kanded')
        
        if not kanded:
            # Juhtum A: Ainult kandeväline muudatus (kandeid pole)
            db_cursor.execute('''
                INSERT INTO staging.stg_ariregister_muudatused 
                (ariregistri_kood, arinimi, oiguslik_vorm, kande_nr, kande_kuupaev, kande_liik_tekst, kandevaline_muudatus, isikuandmed)
                VALUES (%s, %s, %s, NULL, %s, 'Kandeväline muudatus', 1, %s);
            ''', (ari_kood, arinimi, vorm, kuupaev_str, kv_isikud))
            lisatud_sellel_päeval += 1
        else:
            # Juhtum B: Ametlikud kanded
            for kanne in kanded:
                kande_nr = kanne.findtext('{*}kande_nr')
                kande_kuupaev = kanne.findtext('{*}kande_kuupaev')
                kande_tekst = kanne.findtext('{*}kande_liik_tekst')
                
                # UUS JA NÕUTUD VEERG: võetakse kande seest element <isikuandmed> (tagastab Y/N)
                isikuandmed_indikaator = kanne.findtext('{*}isikuandmed')

                # Puhastame kuupäeva "Z" tähisest (nt 2018-06-07Z -> 2018-06-07)
                if kande_kuupaev:
                    kande_kuupaev = kande_kuupaev.replace('Z', '')

                db_cursor.execute('''
                    INSERT INTO staging.stg_ariregister_muudatused 
                    (ariregistri_kood, arinimi, oiguslik_vorm, kande_nr, kande_kuupaev, kande_liik_tekst, kandevaline_muudatus, isikuandmed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                ''', (ari_kood, arinimi, vorm, kande_nr, kande_kuupaev, kande_tekst, on_kandevaline, isikuandmed_indikaator))
                lisatud_sellel_päeval += 1
                
    db_conn.commit()
    return lisatud_sellel_päeval


# ==========================================
# 5. PEAPROTSESS (Kogu 2026. aasta laadimine)
# ==========================================
if __name__ == "__main__":
    db_conn = None
    db_cursor = None
    try:
        db_conn, db_cursor = seadista_postgres_staging()
        
        # Määrame perioodi: alates 2026-05-01 kuni tänaseni
        algus_kp = datetime.date(2026, 5, 1)
        lopp_kp = datetime.date.today()
        
        paevade_arv = (lopp_kp - algus_kp).days + 1
        print(f"📅 Alustan 2026. aasta andmete pärimist päeva kaupa (kokku {paevade_arv} päeva)...")
        
        kogu_lisatud_kirjeid = 0
        
        for i in range(paevade_arv):
            jooksev_kp = algus_kp + datetime.timedelta(days=i)
            kuupaev_str = jooksev_kp.strftime('%Y-%m-%d')
            
            print(f"📡 Päring kuupäevale: {kuupaev_str}...", end="", flush=True)
            
            try:
                xml_vastus = küsi_päeva_muudatused(kuupaev_str)
                leitud_kirjeid = töötle_ja_salvesta(xml_vastus, kuupaev_str, db_conn, db_cursor)
                print(f" laeti {leitud_kirjeid} kirjet.")
                kogu_lisatud_kirjeid += leitud_kirjeid
            except Exception as e:
                print(f" ❌ viga serveriga ühendumisel: {e}")
                
        print(f"\n🚀 Kogu 2026. aasta andmekorje valmis! Kokku stagingusse lisatud: {kogu_lisatud_kirjeid} kirjet.")

    except Exception as general_error:
        print(f"\n❌ Protsess katkes üldise vea tõttu: {general_error}")
    finally:
        if db_cursor: db_cursor.close()
        if db_conn: db_conn.close()