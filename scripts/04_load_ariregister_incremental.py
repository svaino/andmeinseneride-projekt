import os
import time
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

import requests
import psycopg2
from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    load_dotenv(dotenv_path=os.path.join(project_root, ".env"))
except ImportError:
    pass


SOAP_URL = os.getenv("ARIREGISTER_SOAP_URL")
ARIREGISTER_USER = os.getenv("ARIREGISTER_USER")
ARIREGISTER_PASSWORD = os.getenv("ARIREGISTER_PASSWORD")

REQUEST_TIMEOUT = 60
DETAIL_REQUEST_SLEEP_SECONDS = 0.2


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "praktikum"),
        user=os.getenv("POSTGRES_USER", "praktikum"),
        password=os.getenv("POSTGRES_PASSWORD", "praktikum"),
    )


def prepare_database():
    print("Preparing database...", flush=True)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
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
                    emtak_versioon VARCHAR(50),
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS staging.ariregister_incremental_seen (
                    reg_kood VARCHAR(50) PRIMARY KEY,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_kande_kpv TIMESTAMP NULL,
                    source_maaruse_nr VARCHAR(100) NULL
                );
            """)

    print("Database prepared.", flush=True)


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def child_text(parent, name):
    if parent is None:
        return None

    for child in list(parent):
        if strip_ns(child.tag) == name:
            return child.text.strip() if child.text and child.text.strip() else None

    return None


def find_children(parent, name):
    if parent is None:
        return []

    return [child for child in list(parent) if strip_ns(child.tag) == name]


def parse_estonian_date(date_str):
    """
    Handles:
    - 21.01.2019
    - 2019-01-21Z
    - 2019-01-21
    """
    if not date_str:
        return None

    value = str(date_str).strip().replace("Z", "")

    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def parse_estonian_datetime(date_str):
    """
    For staging.ariregister_incremental_seen.source_kande_kpv.
    Handles date and datetime-like values.
    """
    if not date_str:
        return None

    value = str(date_str).strip().replace("Z", "")

    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    return None


def require_environment():
    missing = []

    if not SOAP_URL:
        missing.append("ARIREGISTER_SOAP_URL")

    if not ARIREGISTER_USER:
        missing.append("ARIREGISTER_USER")

    if not ARIREGISTER_PASSWORD:
        missing.append("ARIREGISTER_PASSWORD")

    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def post_soap(xml_body: str) -> str:
    response = requests.post(
        SOAP_URL,
        data=xml_body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    return response.text


def build_kanded_maarused_request(start_dt: str, end_dt: str, page: int = 1) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:prod="http://arireg.x-road.eu/producer/">
  <soapenv:Body>
    <prod:kandedMaarused_v1>
      <prod:keha>
        <prod:ariregister_kasutajanimi>{ARIREGISTER_USER}</prod:ariregister_kasutajanimi>
        <prod:ariregister_parool>{ARIREGISTER_PASSWORD}</prod:ariregister_parool>
        <prod:liik>K</prod:liik>
        <prod:algus_kpv>{start_dt}</prod:algus_kpv>
        <prod:lopp_kpv>{end_dt}</prod:lopp_kpv>
        <prod:keel>est</prod:keel>
        <prod:tulemuste_lk>{page}</prod:tulemuste_lk>
      </prod:keha>
    </prod:kandedMaarused_v1>
  </soapenv:Body>
</soapenv:Envelope>
"""


def build_lihtandmed_request(reg_kood: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:iden="http://x-road.eu/xsd/identifiers"
    xmlns:prod="http://arireg.x-road.eu/producer/"
    xmlns:xro="http://x-road.eu/xsd/xroad.xsd">
  <soapenv:Body>
    <prod:lihtandmed_v2>
      <prod:keha>
        <prod:ariregister_kasutajanimi>{ARIREGISTER_USER}</prod:ariregister_kasutajanimi>
        <prod:ariregister_parool>{ARIREGISTER_PASSWORD}</prod:ariregister_parool>
        <prod:ariregistri_kood>{reg_kood}</prod:ariregistri_kood>
      </prod:keha>
    </prod:lihtandmed_v2>
  </soapenv:Body>
</soapenv:Envelope>
"""


def extract_company_items(kanded_response_xml: str):
    root = ET.fromstring(kanded_response_xml)
    company_items = []

    for elem in root.iter():
        if strip_ns(elem.tag) != "ettevotjad":
            continue

        for child in list(elem):
            if strip_ns(child.tag) == "item":
                company_items.append(child)

    return company_items


def extract_new_company_reg_codes(kanded_response_xml: str):
    """
    Returns rows like:
    {
        "reg_kood": "...",
        "kande_kpv": "...",
        "maaruse_nr": "..."
    }
    """
    root = ET.fromstring(kanded_response_xml)
    results = []

    for ettevotjad in root.iter():
        if strip_ns(ettevotjad.tag) != "ettevotjad":
            continue

        for company_item in list(ettevotjad):
            if strip_ns(company_item.tag) != "item":
                continue

            reg_kood = child_text(company_item, "ariregistri_kood")
            if not reg_kood:
                continue

            kanded = None

            for child in list(company_item):
                if strip_ns(child.tag) == "kanded":
                    kanded = child
                    break

            if kanded is None:
                continue

            for kande_item in find_children(kanded, "item"):
                kandeliik_tekstina = child_text(kande_item, "kandeliik_tekstina")

                if kandeliik_tekstina == "Esmakanne":
                    results.append({
                        "reg_kood": reg_kood,
                        "kande_kpv": child_text(kande_item, "kande_kpv"),
                        "maaruse_nr": child_text(kande_item, "maaruse_nr"),
                    })

    return results


def fetch_new_company_reg_codes(start_dt: str, end_dt: str, max_pages: int = 500):
    all_rows = []
    seen = set()

    for page in range(1, max_pages + 1):
        print(f"Fetching kandedMaarused_v1 page {page}", flush=True)

        xml = build_kanded_maarused_request(start_dt, end_dt, page=page)
        response_xml = post_soap(xml)

        company_items = extract_company_items(response_xml)

        if not company_items:
            print(f"No company rows found on page {page}. Pagination finished.", flush=True)
            break

        page_rows = extract_new_company_reg_codes(response_xml)

        for row in page_rows:
            reg_kood = row["reg_kood"]

            if reg_kood not in seen:
                seen.add(reg_kood)
                all_rows.append(row)

        print(
            f"Page {page} had {len(company_items)} company rows "
            f"and {len(page_rows)} Esmakanne rows",
            flush=True,
        )

    else:
        raise RuntimeError(
            f"Reached max_pages={max_pages}. Pagination may be incomplete."
        )

    return all_rows


def find_first_company_item_from_lihtandmed(response_xml: str):
    root = ET.fromstring(response_xml)

    for elem in root.iter():
        if strip_ns(elem.tag) == "ettevotjad":
            for child in list(elem):
                if strip_ns(child.tag) == "item":
                    return child

    return None


def find_first_descendant_text(parent, possible_names):
    if parent is None:
        return None

    possible_names = set(possible_names)

    for elem in parent.iter():
        tag = strip_ns(elem.tag)

        if tag in possible_names:
            text = elem.text.strip() if elem.text and elem.text.strip() else None
            if text:
                return text

    return None


def extract_emtak_from_company_item(company_item):
    """
    lihtandmed_v2 may or may not include EMTAK fields.
    This tries to extract them if present.
    """
    emtak_kood = None
    emtak_nimetus = None
    emtak_versioon = None

    for elem in company_item.iter():
        tag = strip_ns(elem.tag)
        text = elem.text.strip() if elem.text and elem.text.strip() else None

        if not text:
            continue

        if tag == "emtak_kood" and not emtak_kood:
            emtak_kood = text

        elif tag in ("emtak_tekstina", "emtak_nimetus") and not emtak_nimetus:
            emtak_nimetus = text

        elif tag in ("emtak_versioon_tekstina", "emtak_versioon") and not emtak_versioon:
            emtak_versioon = text

    return emtak_kood, emtak_nimetus, emtak_versioon


def fetch_company_details(reg_kood: str):
    """
    Calls lihtandmed_v2 for one reg_kood and returns a dict compatible
    with upsert_company_details().
    """
    print(f"Calling lihtandmed_v2 for reg_kood={reg_kood}", flush=True)

    xml = build_lihtandmed_request(reg_kood)
    response_xml = post_soap(xml)

    company_item = find_first_company_item_from_lihtandmed(response_xml)

    if company_item is None:
        print(f"No company item found for reg_kood={reg_kood}", flush=True)
        return None

    found_reg_kood = child_text(company_item, "ariregistri_kood")

    if not found_reg_kood:
        print(f"No ariregistri_kood found in response for reg_kood={reg_kood}", flush=True)
        return None

    emtak_kood, emtak_nimetus, emtak_versioon = extract_emtak_from_company_item(company_item)

    details = {
        "reg_kood": found_reg_kood,
        "nimi": (
            child_text(company_item, "evnimi")
            or child_text(company_item, "nimi")
            or "Määramata"
        ),
        "oiguslik_vorm": (
            child_text(company_item, "oiguslik_vorm_tekstina")
            or child_text(company_item, "oiguslik_vorm")
        ),
        "asutamise_kuupaev": parse_estonian_date(
            child_text(company_item, "esmakande_aeg")
            or child_text(company_item, "esmaregistreerimise_kpv")
            or child_text(company_item, "asutamise_kuupaev")
        ),
        "maakond": (
            child_text(company_item, "piirkond_tekstina")
            or find_first_descendant_text(company_item, ["ehak_nimetus"])
        ),
        "staatus": (
            child_text(company_item, "staatus_tekstina")
            or child_text(company_item, "staatus")
        ),
        "emtak_kood": emtak_kood,
        "emtak_nimetus": emtak_nimetus,
        "emtak_versioon": emtak_versioon,
    }

    print(
        f"Parsed company: reg_kood={details['reg_kood']}, "
        f"nimi={details['nimi']}, "
        f"staatus={details['staatus']}, "
        f"asutamise_kuupaev={details['asutamise_kuupaev']}",
        flush=True,
    )

    return details


def upsert_company_details(rows):
    if not rows:
        return 0

    values = [
        (
            row["reg_kood"],
            row["nimi"][:255],
            (row["oiguslik_vorm"] or "Määramata")[:100],
            row["asutamise_kuupaev"],
            (row["maakond"] or "Määramata")[:100],
            (row["staatus"] or "Registris")[:100],
            row["emtak_kood"][:50] if row["emtak_kood"] else None,
            row["emtak_nimetus"][:255] if row["emtak_nimetus"] else None,
            row["emtak_versioon"][:50] if row["emtak_versioon"] else None,
        )
        for row in rows
    ]

    sql = """
        INSERT INTO staging.ariregister_uldandmed (
            reg_kood,
            nimi,
            oiguslik_vorm,
            asutamise_kuupaev,
            maakond,
            staatus,
            emtak_kood,
            emtak_nimetus,
            emtak_versioon
        )
        VALUES %s
        ON CONFLICT (reg_kood) DO UPDATE SET
            nimi = EXCLUDED.nimi,
            oiguslik_vorm = EXCLUDED.oiguslik_vorm,
            asutamise_kuupaev = EXCLUDED.asutamise_kuupaev,
            maakond = EXCLUDED.maakond,
            staatus = EXCLUDED.staatus,
            emtak_kood = COALESCE(EXCLUDED.emtak_kood, staging.ariregister_uldandmed.emtak_kood),
            emtak_nimetus = COALESCE(EXCLUDED.emtak_nimetus, staging.ariregister_uldandmed.emtak_nimetus),
            emtak_versioon = COALESCE(EXCLUDED.emtak_versioon, staging.ariregister_uldandmed.emtak_versioon),
            loaded_at = NOW();
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)

    return len(rows)


def insert_seen_reg_codes(rows):
    if not rows:
        return 0

    values = [
        (
            row["reg_kood"],
            parse_estonian_datetime(row.get("kande_kpv")),
            row.get("maaruse_nr"),
        )
        for row in rows
    ]

    sql = """
        INSERT INTO staging.ariregister_incremental_seen (
            reg_kood,
            source_kande_kpv,
            source_maaruse_nr
        )
        VALUES %s
        ON CONFLICT (reg_kood) DO NOTHING;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)

    return len(rows)


def get_unseen_rows(rows):
    if not rows:
        return []

    reg_codes = [row["reg_kood"] for row in rows]

    sql = """
        SELECT reg_kood
        FROM staging.ariregister_incremental_seen
        WHERE reg_kood = ANY(%s);
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (reg_codes,))
            already_seen = {r[0] for r in cur.fetchall()}

    return [row for row in rows if row["reg_kood"] not in already_seen]


def run_incremental_load(start_dt: str, end_dt: str):
    require_environment()

    prepare_database()

    print(
        f"Fetching new company registration codes from {start_dt} to {end_dt}...",
        flush=True,
    )

    discovered_rows = fetch_new_company_reg_codes(start_dt, end_dt)
    print(f"Discovered {len(discovered_rows)} Esmakanne reg codes.", flush=True)

    unseen_rows = get_unseen_rows(discovered_rows)
    print(f"Unseen reg codes to enrich: {len(unseen_rows)}", flush=True)

    detail_rows = []
    failed_rows = []

    for index, row in enumerate(unseen_rows, start=1):
        reg_kood = row["reg_kood"]

        print(
            f"[{index}/{len(unseen_rows)}] Fetching details for reg_kood={reg_kood}",
            flush=True,
        )

        try:
            details = fetch_company_details(reg_kood)

            if details:
                detail_rows.append(details)
                print(f"Details found for reg_kood={reg_kood}", flush=True)
            else:
                failed_rows.append(row)
                print(f"No details found for reg_kood={reg_kood}", flush=True)

            time.sleep(DETAIL_REQUEST_SLEEP_SECONDS)

        except Exception as e:
            failed_rows.append(row)
            print(f"Failed to fetch details for reg_kood={reg_kood}: {e}", flush=True)

    print(f"Upserting {len(detail_rows)} company detail rows...", flush=True)
    upserted = upsert_company_details(detail_rows)
    print(f"Upserted {upserted} company detail rows.", flush=True)

    successfully_loaded_reg_codes = {row["reg_kood"] for row in detail_rows}

    successfully_loaded_seen_rows = [
        row for row in unseen_rows
        if row["reg_kood"] in successfully_loaded_reg_codes
    ]

    print(
        f"Saving {len(successfully_loaded_seen_rows)} successfully loaded registration codes...",
        flush=True,
    )

    seen_inserted = insert_seen_reg_codes(successfully_loaded_seen_rows)

    print(f"Saved {seen_inserted} seen registration codes.", flush=True)

    if failed_rows:
        print(f"Failed detail rows: {len(failed_rows)}", flush=True)

    result = {
        "discovered": len(discovered_rows),
        "unseen": len(unseen_rows),
        "upserted": upserted,
        "seen_inserted": seen_inserted,
        "failed": len(failed_rows),
    }

    print("Incremental load finished.", flush=True)
    print(result, flush=True)

    return result


def main():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    start_dt = start_date.strftime("%Y-%m-%dT00:00:00")
    end_dt = end_date.strftime("%Y-%m-%dT00:00:00")

    print("Starting Äriregister incremental load", flush=True)
    print(f"SOAP URL: {SOAP_URL}", flush=True)
    print(f"Start datetime: {start_dt}", flush=True)
    print(f"End datetime: {end_dt}", flush=True)

    result = run_incremental_load(start_dt, end_dt)

    print("Finished Äriregister incremental load", flush=True)
    print(result, flush=True)


if __name__ == "__main__":
    main()