# Eesti äriregistri muutuste voog

Otsast lõpuni andmeinseneeria töövoog: Äriregistri avaandmete API-st igapäevased muutused (EMTAK, maakondad), Statistikaameti rahvastikuandmed, PostgreSQL, dbt transformatsioonid, Airflow orkestreerimine ja Superseti näidikulaud.

Äriregistri avaandmed uuenevad igapäevaselt; Statistikaameti andmed kord kuus.

## Olulised lingid

- Projekti kirjeldus: [Moodle](https://moodle.ut.ee/mod/data/view.php?d=1231&advanced=0&paging&filter=1&page=0&rid=19075)

## Äriküsimus

Millises tegevusvaldkonnas ja maakonnas registreeritakse enim uusi äriettevõtteid Eestis ja kuidas see on ajas muutunud?

Äriettevõteteks loeme kasumit taotlevaid ettevõtteid (AS, OÜ, UÜ, TÜ, TÜH ja FIE).
KPI-na defineerime ettevõtlikkust - uute äriettevõtte arvu tuhande tööealise (20-74a) elaniku kohta.
Ajaperioodina kasutame libisevat aastat (ingl. k. rolling year) - pidevalt muutuv aastane periood, mis võimaldab andmeid võrrelda teatud määratud kuupäevast alates sama kuupäevani aasta tagasi (nt. 4. juuni 2025 - 3. juuni 2026)
Rahvastikustatistikat arvestame kalendriaasta alguse seisuga (1. jaanuar).

Täpsem mõõdikute ja otsuste kirjeldus: [`docs/arhitektuur.md`](docs/arhitektuur.md).

## Nõuete täitmine

| Nõue | Kuidas projekt seda täidab |
|---|---|
| Selge äriküsimus | EMTAK ja maakondade kaupa uute ettevõtete ning ettevõtlikkuse analüüs. |
| Ajas muutuv andmeallikas | Äriregistri igapäevased väljavõtted; Statistikaameti kuine uuendus. |
| Automatiseeritud sissevõtt | Airflow import-DAG-id (`01_`–`04_` failid `airflow/dags/`). |
| Transformatsioon | dbt mudelid (`dbt_project/rik_stat_dbt/`): staging → intermediate → marts; igapäevane DAG `05_dbt_igapaevane`. |
| Staatiline dimensioon | EMTAK CSV-d → staging; maakondade seemned (`dbt seed` → `staging.dim_maakonnad`). |
| Andmekvaliteedi testid | `dbt test` (`05_dbt_igapaevane` lõpus). |
| Näidikulaud | Superset (automaatne import `superset/dashboards/` zipist käivitamisel). |
| Saladused | `.env` (repos ainult `.env.example`). |

## Arhitektuur

```mermaid
flowchart LR
    A[Äriregistri API] --> B[Python laadimisskriptid]
    S[Statistikaameti API] --> B
    F[EMTAK CSV] --> B
    B --> C[(PostgreSQL staging)]
    C --> D[dbt]
    D --> E[(intermediate / marts)]
    E --> G[Superset]
    H1[Airflow import DAG-id] --> B
    H2[Airflow 05_dbt_igapaevane] --> D
```

Andmekihtide ülevaade: [`docs/arhitektuur.md`](docs/arhitektuur.md).

## Eeldused

- Docker Desktop (või muu keskkond, kus töötab `docker compose`)
- Internet (RIK ja Statistikaameti API)
- Vabad portid vastavalt `.env`-ile (vaikimisi analüütika-DB `55432`, Airflow `8081`, Superset `8088`, dbt docs `18080`)

## Käivitamine

```bash
cd andmeinseneride-projekt
cp .env.example .env
# täida .env (POSTGRES_*, ARIREGISTER_*, SUPERSET_*, vajadusel AIRFLOW_UID)
docker compose up -d --build
docker compose ps
```

Kui vana stacki skeem või maht segab (tühi algus):

```bash
docker compose down -v
docker compose up -d --build
```

Esimene käivitus võtab mõne minuti (`airflow-init`, `superset-init`).

### Teenused

| Teenus | URL / ligipääs |
|---|---|
| Airflow UI | http://localhost:8081 — kasutaja/parool `.env`-ist (`_AIRFLOW_WWW_USER_*`, vaikimisi `airflow` / `airflow`) |
| Superset | http://localhost:8088 — admin `.env`-ist (`SUPERSET_ADMIN_*`) |
| PostgreSQL (analüütika) | `localhost:${DB_PORT_HOST:-55432}` — `POSTGRES_*` |
| dbt dokumentatsioon | http://localhost:18080 (vt allpool) |

### Airflow DAG-id

Import ja dbt on **eraldi DAG-id**: laadimisskriptid (`01_`–`04_`) ja transformatsioonid (`05_`). Failinimed `airflow/dags/` algavad järjekorranumbriga; `dag_id` ühtib failinimega.

DAG-id on vaikimisi **pausil** — ava UI, **unpause**, seejärel käivita bootstrap.

| DAG | Ajakava | Mida teeb |
|---|---|---|
| `01_andmestiku_esmane_taitmine` | käsitsi | EMTAK CSV → staging |
| `02_rahvastik_kuuine_laadimine` | iga kuu, 1. kp 04:00 | Statistikaameti rahvastik → staging |
| `03_ariregister_kuuine_taielaadimine` | iga kuu, 1. kp 03:00 | Äriregistri täislaadimine + tingimuslik EMTAK/rahvastik |
| `04_ariregister_igapaevane_increment` | iga päev 03:30 | Inkrementaalne Äriregistri laadimine |
| `05_dbt_igapaevane` | iga päev 05:00 | `dbt deps` → seed → staging → intermediate → marts → test |

**1. kuupäeva järjekord:** 03:00 täislaadimine → 03:30 inkrement → 04:00 rahvastik → 05:00 dbt.

**Esmane käivitus pärast kloonimist:**

1. **Trigger** `01_andmestiku_esmane_taitmine` (üks kord).
2. **Trigger** `02_rahvastik_kuuine_laadimine`.
3. **Trigger** `03_ariregister_kuuine_taielaadimine` (või oota ajakava).
4. **Unpause** `04_ariregister_igapaevane_increment` igapäevaseks täienduseks.
5. **Trigger** või **unpause** `05_dbt_igapaevane` (transformatsioonid ja testid; ilma selleta puuduvad `intermediate` / `marts` kihid).

Mudelite valik: [`dbt_project/rik_stat_dbt/selectors.yml`](dbt_project/rik_stat_dbt/selectors.yml). Uue `.sql` faili lisamisel `models/marts/` piisab `05_dbt_igapaevane` uuesti käivitamisest.

`./dbt_project` on mountitud Airflow konteineritesse; dbt-mudelite puhul piisab `05_dbt_igapaevane` DAG-ist.

### PostgreSQL (analüütika)

Ainult andmebaas:

```bash
docker compose up -d db
docker compose exec db bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

`POSTGRES_USER` ja `POSTGRES_DB` tulevad konteinerisse `.env`-ist (`compose.yml` teenus `db`).

Skeemid: `staging` (tabelid + seemned), `intermediate` (dbt **vaated**), `marts` (dbt tabelid). Vaadete loetelu: `\dv intermediate.*` (mitte `\dt`, mis näitab ainult tabeleid).

## Logid ja peatamine

```bash
docker compose logs -f airflow-scheduler
docker compose logs superset-init   # Superseti esmane seadistus / dashboard import
docker compose down                 # peatab teenused
docker compose down -v              # + kustutab mahud (PostgreSQL, Airflow meta, Superset)
```

Ainult Airflow peatamiseks (ülejäänud jääb tööle):

```bash
docker compose stop airflow-apiserver airflow-scheduler airflow-dag-processor airflow-db
```

Windows Git Bash: lisa `MSYS_NO_PATHCONV=1` eesliiteks, kui `docker exec` teekonda moonutab.

## Arendus ja diagnostika (valikuline)

Töövoog jookseb Airflow kaudu. Käsitsi testimiseks saab sama skripte käivitada `pipeline` konteineris:

```bash
MSYS_NO_PATHCONV=1 docker compose exec pipeline python scripts/03_load_emtak.py
MSYS_NO_PATHCONV=1 docker compose exec pipeline python scripts/01_load_statistikaamet.py
MSYS_NO_PATHCONV=1 docker compose exec pipeline python scripts/02_01_load_ariregister_yldandmed.py
MSYS_NO_PATHCONV=1 docker compose exec pipeline python scripts/04_load_ariregister_incremental.py
```

dbt (`dbt` teenus; sama järjekord mis `05_dbt_igapaevane`):

```bash
docker compose run --rm dbt bash -c "dbt deps && dbt seed"
docker compose run --rm dbt bash -c "dbt run --selector staging_rik && dbt run --selector staging_stat"
docker compose run --rm dbt bash -c "dbt run --selector layer_intermediate && dbt run --selector layer_marts"
docker compose run --rm dbt bash -c "dbt test"
docker compose exec dbt dbt debug
```

### dbt dokumentatsioon (veeb)

```bash
docker compose up -d dbt
docker compose exec dbt dbt docs generate
docker compose exec dbt dbt docs serve --port 8080 --host 0.0.0.0 --no-browser
```

Ava http://localhost:18080 — peatamiseks `Ctrl+C` exec-sessioonis.

### Superset ja analüütika-andmebaas

Kui automaatne dashboardi import ebaõnnestub (`superset-init` logid), lisa ühendus käsitsi: **Settings → Database Connections → PostgreSQL**

| Väli | Väärtus |
|---|---|
| Host | `db` |
| Port | `5432` |
| Database | `POSTGRES_DB` |
| User / Password | `POSTGRES_USER` / `POSTGRES_PASSWORD` |

## Andmeallikad

| Allikas | Kasutus |
|---|---|
| [Äriregistri avaandmed](https://avaandmed.ariregister.rik.ee/) | Põhivoog (`ARIREGISTER_*` `.env`-is) |
| [Statistikaameti PxWeb API](https://andmed.stat.ee/) | Rahvastik (`STAT_API_URL`) |
| `data/EMTAK_*.csv` | EMTAK dimensioonid |

## Projekti struktuur

| Kaust / fail | Roll |
|---|---|
| `compose.yml` | PostgreSQL, pipeline, dbt, Superset, Airflow |
| `airflow/dags/` | Orkestreerimine (`01_`–`04_` import, `05_dbt_igapaevane`) |
| `scripts/` | Python laadimisskriptid |
| `dbt_project/rik_stat_dbt/` | Transformatsioonid ja testid |
| `superset/` | Konfiguratsioon ja dashboardi eksport |
| `data/` | EMTAK CSV-failid |
| `.env.example` | Keskkonnamuutujad |
| `docs/arhitektuur.md` | Arhitektuur, mõõdikud, andmemudel |

## Koristamine

```bash
docker compose down
docker compose down -v
```