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
BATCH_SIZE = 5000  # Mass-salvestuse suurus


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
    """Valmistab ette staging skeemi ja andmetabeli registrikaardi kannete jaoks."""
    print("Andmebaasi struktuuri kontroll ja ettevalmistamine...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("CREATE SCHEMA IF NOT EXISTS staging;")
    # Loome tabeli kõigi registrikaardi väljadega
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staging.ariregister_registrikaardid (
            reg_kood VARCHAR(50),
            nimi VARCHAR(255),
            kaardi_piirkond INT,
            kaardi_nr INT,
            kaardi_tyyp VARCHAR(10),
            kande_nr INT,
            kande_kuupaev DATE,
            kandeliik INT,
            kandeliik_tekstina TEXT,
            PRIMARY KEY (reg_kood, kaardi_nr, kande_nr)
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✓ Staging tabel `staging.ariregister_registrikaardid` on andmebaasis valmis.")


def find_latest_xml_link():
    """Leiab lehelt täpse registrikaartide XML ZIP faili viite."""
    target_filename = "ettevotja_rekvisiidid__registrikaardid.xml.zip"

    response = requests.get(AVAANDMED_URL, timeout=60)

    if response.status_code != 200:
        raise Exception(f"Viga avaandmete lehele sisenemisel: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        href_lower = href.lower()

        if target_filename in href_lower:
            if href.startswith("/"):
                return f"https://avaandmed.ariregister.rik.ee{href}"

            return href

    raise Exception(f"Ei leidnud faili: {target_filename}")


def convert_date_format(date_str):
    """Konverteerib kuupäeva tekstist andmebaasi DATE formaati."""
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
    """Teostab andmete mass-salvestuse (Upsert) andmebaasi registrikaartide tabelisse."""
    insert_query = """
        INSERT INTO staging.ariregister_registrikaardid (
            reg_kood, nimi, kaardi_piirkond, kaardi_nr, kaardi_tyyp, kande_nr, kande_kuupaev, kandeliik, kandeliik_tekstina
        )
        VALUES %s
        ON CONFLICT (reg_kood, kaardi_nr, kande_nr) DO NOTHING;
    """
    execute_values(cur, insert_query, batch_data)


def download_and_process_xml():
    """Laeb alla XML andmed ja parsib registrikaardid andmebaasi."""
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
            
            path = []
            
            # Ajutised muutujad hierarhia hoidmiseks
            reg_kood = None
            nimi = None
            
            current_kaart = {}
            current_kanne = {}
            
            in_registrikaardid = False
            in_kanded = False

            for event, elem in context:
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                if event == "start":
                    path.append(tag)

                    if tag == "registrikaardid":
                        in_registrikaardid = True
                    elif tag == "kanded":
                        in_kanded = True
                    
                    # Kui algab uus kaart (registrikaardid/item)
                    elif tag == "item" and in_registrikaardid and not in_kanded:
                        current_kaart = {
                            "kaardi_piirkond": None,
                            "kaardi_nr": None,
                            "kaardi_tyyp": None
                        }
                    
                    # Kui algab kaartide sees uus kanne (kanded/item)
                    elif tag == "item" and in_kanded:
                        current_kanne = {
                            "kande_nr": None,
                            "kpv": None,
                            "kandeliik": None,
                            "kandeliik_tekstina": None
                        }

                elif event == "end":
                    text = elem.text.strip() if elem.text and elem.text.strip() else None

                    # 1. Kogume ettevõtte põhiandmed
                    if text:
                        if path[-2:] == ["ettevotja", "ariregistri_kood"]:
                            reg_kood = text
                        elif path[-2:] == ["ettevotja", "nimi"]:
                            nimi = text
                        
                        # 2. Kogume kaardi andmed (kui oleme kaardi tasemel)
                        elif in_registrikaardid and not in_kanded and current_kaart:
                            if tag == "kaardi_piirkond":
                                current_kaart["kaardi_piirkond"] = int(text) if text.isdigit() else None
                            elif tag == "kaardi_nr":
                                current_kaart["kaardi_nr"] = int(text) if text.isdigit() else None
                            elif tag == "kaardi_tyyp":
                                current_kaart["kaardi_tyyp"] = text

                        # 3. Kogume kande andmed (kui oleme kande tasemel)
                        elif in_kanded and current_kanne:
                            if tag == "kande_nr":
                                current_kanne["kande_nr"] = int(text) if text.isdigit() else None
                            elif tag == "kpv":
                                current_kanne["kpv"] = convert_date_format(text)
                            elif tag == "kandeliik":
                                current_kanne["kandeliik"] = int(text) if text.isdigit() else None
                            elif tag == "kandeliik_tekstina":
                                current_kanne["kandeliik_tekstina"] = text

                    # Kui kande item saab läbi, lisame selle ridade jadasse
                    if tag == "item" and in_kanded and current_kanne:
                        if reg_kood and current_kaart.get("kaardi_nr") and current_kanne.get("kande_nr"):
                            batch.append((
                                reg_kood.strip(),
                                nimi[:255].strip() if nimi else "Määramata",
                                current_kaart["kaardi_piirkond"],
                                current_kaart["kaardi_nr"],
                                current_kaart["kaardi_tyyp"][:10] if current_kaart["kaardi_tyyp"] else None,
                                current_kanne["kande_nr"],
                                current_kanne["kpv"],
                                current_kanne["kandeliik"],
                                current_kanne["kandeliik_tekstina"]
                            ))

                            if len(batch) >= BATCH_SIZE:
                                save_batch(cur, batch)
                                conn.commit()
                                total_inserted += len(batch)
                                print(f"   .. laaditud {total_inserted} registrikaardi kannet ..")
                                batch = []
                        current_kanne = {}

                    # Tasemete sulgemised
                    elif tag == "kanded":
                        in_kanded = False
                    elif tag == "registrikaardid":
                        in_registrikaardid = False
                    elif tag == "item" and in_registrikaardid and not in_kanded:
                        current_kaart = {}
                    
                    # Ettevõte sai läbi, nullime põhiandmed järgmise jaoks
                    elif tag == "ettevotja":
                        reg_kood = None
                        nimi = None

                    path.pop()
                    elem.clear()    
            
            if batch:
                save_batch(cur, batch)
                conn.commit()
                total_inserted += len(batch)

    cur.close()
    conn.close()
    print(f"✓ Kogu fail edukalt töödeldud! Kokku laaditi staging kihti {total_inserted} kannet.")
    
    if os.path.exists(TEMP_ZIP):
        os.remove(TEMP_ZIP)
        print("✓ Ajutine ZIP-fail kettalt eemaldatud.")


def main():
    print("=== ÄRIREGISTRI XML PIPELINE (REGISTRIKAARDID) ===")
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