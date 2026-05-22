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
    """Finds the exact Äriregister yldandmed XML ZIP file."""
    target_filename = "ettevotja_rekvisiidid__yldandmed.xml.zip"

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
            
            path = []

            company = None
            activity = None
            in_teatatud_tegevusalad = False
            in_aadressid = False

            for event, elem in context:
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                if event == "start":
                    path.append(tag)

                    if tag == "ettevotja":
                        company = {
                            "reg_kood": None,
                            "nimi": None,
                            "raw_date": None,
                            "oiguslik_vorm": None,
                            "maakond": None,
                            "staatus": None,
                            "emtak_kood": None,
                            "emtak_nimetus": None,
                            "emtak_versioon": None,
                        }

                    elif tag == "teatatud_tegevusalad":
                        in_teatatud_tegevusalad = True

                    elif tag == "aadressid":
                        in_aadressid = True

                    elif tag == "item" and in_teatatud_tegevusalad:
                        activity = {
                            "kood": None,
                            "nimetus": None,
                            "versioon": None,
                            "on_pohi": False,
                        }

                elif event == "end":
                    text = elem.text.strip() if elem.text and elem.text.strip() else None

                    if company is not None and text:
                        # Top-level company fields
                        if path[-2:] == ["ettevotja", "ariregistri_kood"]:
                            company["reg_kood"] = text

                        elif path[-2:] == ["ettevotja", "nimi"]:
                            company["nimi"] = text

                        elif tag == "esmaregistreerimise_kpv":
                            company["raw_date"] = text

                        elif tag == "oiguslik_vorm_tekstina":
                            company["oiguslik_vorm"] = text

                        elif tag == "staatus_tekstina" and "yldandmed" in path:
                            # Prefer yldandmed/staatus_tekstina, not random nested statuses
                            company["staatus"] = text

                        # Address / county
                        elif in_aadressid and tag == "ehak_nimetus":
                            parts = [p.strip() for p in text.split(",") if p.strip()]
                            if parts:
                                company["maakond"] = parts[-1]

                        # Current declared activities
                        elif in_teatatud_tegevusalad and activity is not None:
                            if tag == "emtak_kood":
                                activity["kood"] = text
                            elif tag == "emtak_tekstina":
                                activity["nimetus"] = text
                            elif tag == "emtak_versioon_tekstina":
                                activity["versioon"] = text
                            elif tag == "emtak_versioon":
                                # fallback if text version is missing
                                activity["versioon"] = activity["versioon"] or text
                            elif tag == "on_pohitegevusala":
                                activity["on_pohi"] = text.lower() in ("true", "jah", "1")

                    # Close activity item
                    if tag == "item" and in_teatatud_tegevusalad and activity:
                        if activity["on_pohi"] or not company["emtak_kood"]:
                            company["emtak_kood"] = activity["kood"]
                            company["emtak_nimetus"] = activity["nimetus"]
                            company["emtak_versioon"] = activity["versioon"]
                        activity = None

                    elif tag == "teatatud_tegevusalad":
                        in_teatatud_tegevusalad = False

                    elif tag == "aadressid":
                        in_aadressid = False

                    # Close company
                    elif tag == "ettevotja" and company:
                        if company["reg_kood"] and company["nimi"]:
                            asutamise_kp = convert_date_format(company["raw_date"])

                            batch.append((
                                company["reg_kood"].strip(),
                                company["nimi"][:255].strip(),
                                (company["oiguslik_vorm"] or "Määramata")[:100].strip(),
                                asutamise_kp,
                                (company["maakond"] or "Määramata")[:100].strip(),
                                (company["staatus"] or "Registris")[:100].strip(),
                                company["emtak_kood"][:50].strip() if company["emtak_kood"] else None,
                                company["emtak_nimetus"][:255].strip() if company["emtak_nimetus"] else None,
                                company["emtak_versioon"][:50].strip() if company["emtak_versioon"] else None,
                            ))

                            if len(batch) >= BATCH_SIZE:
                                save_batch(cur, batch)
                                conn.commit()
                                total_inserted += len(batch)
                                print(f"   .. laaditud {total_inserted} ettevõtet ..")
                                batch = []

                        company = None

                    path.pop()
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