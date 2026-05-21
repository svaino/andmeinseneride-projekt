import os
import requests
import xml.etree.ElementTree as ET
import psycopg2
from psycopg2.extras import execute_values
import zipfile
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime

# Projektijuure ja keskkonnamuutujate seadistamine
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

AVAANDMED_URL = "https://avaandmed.ariregister.rik.ee/et/avaandmete-allalaadimine"
TEMP_ZIP = "ariregister_temp.zip"
BATCH_SIZE = 5000  # Optimaalne suurus mass-salvestuseks (Upsert)


def get_db_connection():
    """Loob ühenduse PostgreSQL andmebaasiga."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "praktikum"),
        user=os.getenv("POSTGRES_USER", "praktikum"),
        password=os.getenv("POSTGRES_PASSWORD", "praktikum")
    )


def prepare_database():
    """Valmistab ette staging skeemi ja andmetabeli."""
    print("Andmebaasi struktuuri kontroll ja ettevalmistamine...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staging.ariregister_uldandmed (
            reg_kood VARCHAR(50) PRIMARY KEY,
            nimi VARCHAR(255) NOT NULL,
            oiguslik_vorm VARCHAR(100),
            asutamise_kuupaev DATE,
            maakond VARCHAR(100),
            staatus VARCHAR(100),
            emtak_kood VARCHAR(50),
            emtak_nimetus VARCHAR(255),
            emtak_versioon VARCHAR(50)
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✓ Staging tabel on andmebaasis valmis.")


def find_latest_xml_link():
    """Tuvastab Äriregistri avaandmete lehelt värskeima Üldandmete XML ZIP-faili lingi."""
    response = requests.get(AVAANDMED_URL)
    if response.status_code != 200:
        raise Exception(f"Viga avaandmete lehele sisenemisel: {response.status_code}")
        
    soup = BeautifulSoup(response.text, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '.zip' in href and 'xml' in href.lower() and ('uldandmed' in href.lower() or 'yldandmed' in href.lower() or 'rekvisiidid' in href.lower()):
            if href.startswith('/'):
                return f"https://avaandmed.ariregister.rik.ee{href}"
            return href
            
    return "https://avaandmed.ariregister.rik.ee/sites/default/files/avaandmed/ettevotja_rekvisiidid__yldandmed.xml.zip"


def convert_date_format(date_str):
    """Konverteerib kuupäeva tekstist (PP.KK.AAAA või AAAA-KK-PP) andmebaasi DATE formaati."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def save_batch(cur, batch_data):
    """Teostab andmete mass-salvestuse (Upsert) andmebaasi."""
    insert_query = """
        INSERT INTO staging.ariregister_uldandmed (
            reg_kood, nimi, oiguslik_vorm, asutamise_kuupaev, maakond, staatus, emtak_kood, emtak_nimetus, emtak_versioon
        )
        VALUES %s
        ON CONFLICT (reg_kood) DO UPDATE SET
            nimi = EXCLUDED.nimi,
            oiguslik_vorm = EXCLUDED.oiguslik_vorm,
            asutamise_kuupaev = EXCLUDED.asutamise_kuupaev,
            maakond = EXCLUDED.maakond,
            staatus = EXCLUDED.staatus,
            emtak_kood = EXCLUDED.emtak_kood,
            emtak_nimetus = EXCLUDED.emtak_nimetus,
            emtak_versioon = EXCLUDED.emtak_versioon;
    """
    execute_values(cur, insert_query, batch_data)


def download_and_process_xml():
    """Laeb alla XML andmed ja parsib need striimina otse andmebaasi."""
    if os.path.exists(TEMP_ZIP):
        if not zipfile.is_zipfile(TEMP_ZIP) or os.path.getsize(TEMP_ZIP) < 1024:
            print("⚠️ Kettal olev ZIP-fail on vigane või poolik. Kustutan selle.")
            os.remove(TEMP_ZIP)

    if not os.path.exists(TEMP_ZIP):
        try:
            download_url = find_latest_xml_link()
            print(f"Alustan värskeima faili allalaadimist aadressilt: {download_url}")
            response = requests.get(download_url, stream=True)
            with open(TEMP_ZIP, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            print("✓ Fail edukalt alla laaditud ja salvestatud.")
        except Exception as e:
            print(f"❌ Allalaadimise tõrge: {e}")
            return
    else:
        print("ℹ️ Kasutan kettal juba olevat ZIP-faili.")

    print("Alustan andmete töötlemist ja laadimist andmebaasi...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    batch = []
    total_inserted = 0
    
    with zipfile.ZipFile(TEMP_ZIP) as archive:
        xml_files = [f for f in archive.namelist() if f.endswith('.xml')]
        if not xml_files:
            print("❌ VIGA: ZIP-faili seest ei leitud ühtegi .xml laiendiga faili!")
            cur.close()
            conn.close()
            return
            
        xml_filename = xml_files[0]
        
        with archive.open(xml_filename) as xml_file:
            context = ET.iterparse(xml_file, events=('start', 'end'))
            
            # Ettevõtte andmete ajutised muutujad
            reg_kood = None
            nimi = None
            raw_date = None
            oiguslik_vorm = None
            maakond = "Määramata"
            staatus = "Registris"
            
            emtak_kood = None
            emtak_nimetus = None
            emtak_versioon = None
            
            # Tegevusala rea muutujad
            temp_kood = None
            temp_nimetus = None
            temp_versioon = None
            temp_on_pohi = False

            for event, elem in context:
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                # --- SÜNDMUS: START ---
                if event == 'start':
                    if tag_name in ['ettevotja', 'ettevote', 'keha']:
                        reg_kood = None
                        nimi = None
                        raw_date = None
                        oiguslik_vorm = None
                        maakond = "Määramata"
                        staatus = "Registris"
                        emtak_kood = None
                        emtak_nimetus = None
                        emtak_versioon = None
                        
                    elif tag_name == 'item':
                        temp_kood = None
                        temp_nimetus = None
                        temp_versioon = None
                        temp_on_pohi = False

                # --- SÜNDMUS: END ---
                elif event == 'end':
                    val_text = elem.text.strip() if elem.text else None
                    
                    if val_text:
                        if tag_name in ['ariregistri_kood', 'reg_kood']:
                            reg_kood = val_text
                        elif tag_name in ['nimi', 'ari_nimi', 'evnimi']:
                            nimi = val_text
                        elif tag_name == 'esmaregistreerimise_kpv':
                            raw_date = val_text
                        elif tag_name in ['oiguslik_vorm_tekstina', 'oiguslik_vorm']:
                            oiguslik_vorm = val_text
                        elif tag_name in ['staatus_tekstina', 'staatus']:
                            staatus = val_text
                        elif tag_name in ['aadress_ads__ads_normaliseeritud_taisaadress', 'aadress']:
                            maakond = val_text.split(',')[0].strip()
                        
                        # EMTAK väärtuste kogumine
                        elif tag_name == 'emtak_kood':
                            temp_kood = val_text
                        elif tag_name == 'emtak_tekstina':
                            temp_nimetus = val_text
                        elif tag_name == 'emtak_versioon':
                            temp_versioon = val_text
                        elif tag_name == 'on_pohitegevusala':
                            temp_on_pohi = val_text.lower() in ['true', 'jah', '1']

                    # Kui tegevusala objekt sulgus
                    if tag_name == 'item' and temp_kood:
                        if temp_on_pohi or not emtak_kood:
                            emtak_kood = temp_kood
                            emtak_nimetus = temp_nimetus
                            emtak_versioon = temp_versioon

                    # Kui kogu ettevõtte blokk sai läbi, teeme andmebaasi-kõlblikuks
                    if tag_name in ['ettevotja', 'ettevote', 'keha'] and reg_kood and nimi:
                        asutamise_kp = convert_date_format(raw_date)
                        
                        # Turvaline õigusliku vormi tuletamine
                        if not oiguslik_vorm:
                            nimi_upper = nimi.upper()
                            tunnused = {'OÜ': 'Osaühing', 'AS': 'Aktsiaselts', 'FIE': 'Füüsilisest isikust ettevõtja', 'MTÜ': 'Mittetulundusühing'}
                            for tunnus, taisnimis in tunnused.items():
                                if tunnus in nimi_upper or taisnimis.upper() in nimi_upper:
                                    oiguslik_vorm = tunnus
                                    break
                            oiguslik_vorm = oiguslik_vorm or "Määramata"

                        # Turvaline stringide lõikamine (kui väärtus on olemas, siis lõikame, muidu None)
                        clean_nimi = nimi[:255].strip() if nimi else "Tundmatu"
                        clean_vorm = oiguslik_vorm[:100].strip() if oiguslik_vorm else "Määramata"
                        clean_maakond = maakond[:100].strip() if maakond else "Määramata"
                        clean_staatus = staatus[:100].strip() if staatus else "Registris"
                        clean_emtak_kood = emtak_kood[:50].strip() if emtak_kood else None
                        clean_emtak_nim = emtak_nimetus[:255].strip() if emtak_nimetus else None
                        clean_emtak_ver = emtak_versioon[:50].strip() if emtak_versioon else None

                        batch.append((
                            reg_kood.strip(), clean_nimi, clean_vorm, asutamise_kp,
                            clean_maakond, clean_staatus, clean_emtak_kood, clean_emtak_nim, clean_emtak_ver
                        ))
                        
                        if len(batch) >= BATCH_SIZE:
                            save_batch(cur, batch)
                            conn.commit()
                            total_inserted += len(batch)
                            if total_inserted % 25000 == 0:
                                print(f"   .. laaditud {total_inserted} ettevõtet ..")
                            batch = []
                    
                    # Vabastame elemendi mälust
                    elem.clear()
            
            if batch:
                save_batch(cur, batch)
                conn.commit()
                total_inserted += len(batch)

    cur.close()
    conn.close()
    print(f"✓ Kogu fail edukalt töödeldud! Kokku laaditi staging kihti {total_inserted} ettevõtet.")
    
    if os.path.exists(TEMP_ZIP):
        os.remove(TEMP_ZIP)
        print("✓ Ajutine ZIP-fail kettalt eemaldatud.")


def main():
    print("=== ÄRIREGISTRI XML PIPELINE (TOOTMISREŽIIM) ===")
    start_time = datetime.now()
    prepare_database()
    
    try:
        download_and_process_xml()
    except Exception as e:
        print(f"❌ Süsteem tõrkus töö käigus: {e}")
        
    duration = datetime.now() - start_time
    print(f"=== TÖÖ LÕPETATUD (Aeg: {duration}) ===")


if __name__ == "__main__":
    main()