# Projektiplaan — Eesti äriregistri muutuste voog

> Andmeinseneeria kursuse rühmaprojekt. See plaan kirjeldab, mida ehitame, milliste tööriistadega, mis järjekorras ja kes mille eest vastutab. Plaan põhineb projekti kirjeldusel (`Projekt.md`) ning näidisprojektil `projekt/naidisprojekt-ilmaandmed-dbt-ja-airflow`.

## 1. Äriküsimus ja KPI-d

**Äriküsimus:** Millistes valdkondades (EMTAK tegevusalad) registreeritakse Eestis enim uusi ettevõtteid ja millistes maakondades on juhatuse muudatuste sagedus kõige kõrgem — kui rahvastiku suurust arvesse võtta?

**Mõõdikud (näidikulaua KPI-d):**

1. **Uusi ettevõtteid 1000 elaniku kohta** maakonna ja kuu lõikes (rahvastikuga normaliseeritud).
2. **Juhatuse muudatuste sagedus** (muudatused / aktiivsed ettevõtted, %) maakonna ja EMTAK 1. taseme jaotise lõikes, libisev 30-päevane aken.
3. **Top 10 kasvavat EMTAK valdkonda** viimase 90 päeva jooksul registreeritud ettevõtete arvu järgi.
4. **Aktiivsuse indeks** maakonnale (0–100): kaalutud kombinatsioon uutest registreerimistest, juhatuse muudatustest ja lõpetamistest 1000 elaniku kohta.
5. **Toetav kontekst:** rahvastikujaotus maakondades (Statistikaameti andmetest), kuvatakse kaardil / tulpdiagrammil.

## 2. Andmeallikad

| Allikas | Tüüp | Ajas muutuv? | Roll |
|---|---|---|---|
| [RIK avaandmed — Äriregister](https://avaandmed.ariregister.rik.ee/) | Avalik HTTP API / CSV väljavõtted | Jah, igapäevased muutuste väljavõtted | Põhiandmevoog: uued registreerimised, juhatuse muudatused, lõpetamised; EMTAK tegevusalad; maakonnad |
| [Statistikaamet PxWeb API](https://andmed.stat.ee/api/v1/et/stat/) | Avalik JSON-stat API | Jah, uueneb kord kuus | Rahvastiku andmed maakondade kaupa — KPI normaliseerimiseks |
| `seeds/maakonnad.csv` | Staatiline dbt seed | Ei, muutub ainult koodimuutusel | Maakondade dimensioonitabel (kood, nimi, vabariigi/regioon, kuvajärjestus) |
| `seeds/emtak.csv` | Staatiline dbt seed | Ei, muutub ainult koodimuutusel | EMTAK 1. taseme (jaotised A–U) ja 2. taseme nimekiri inimloetavate nimedega |

Andmete jagatavus: **avalikud** — võime hoida lähteandmeid avalikus repos (väljaspool `.env` faili).

## 3. Stack ja arhitektuuriotsus

Kahest näidisprojektist valime **edasijõudnute stacki** (`naidisprojekt-ilmaandmed-dbt-ja-airflow` järgi), sest:

- meil on **kaks erineva sagedusega allikat** (igapäevane vs kuine) — Airflow DAG-id sobivad selleks paremini kui üks cron-rida,
- transformatsioone on rohkem (faktid + libisevad aknad + normaliseerimine) — dbt mudelid + testid aitavad neid hoida puhtana,
- Superset annab interaktiivse filtreerimise maakonna / EMTAK / aja järgi, mis on selle äriküsimuse jaoks vajalik.

| Komponent | Tööriist |
|---|---|
| Orkestreerimine | Apache Airflow 3.x (kaks DAG-i) |
| Sissevõtt | Python `PythonOperator` (RIK + Statistikaamet) |
| Transformatsioon | dbt Core 1.10 (staging → intermediate → marts) |
| Andmehoidla | PostgreSQL |
| Näidikulaud | Apache Superset 6.x |
| Saladuste haldus | `.env` fail (repos ainult `.env.example`) |
| Konteinerid | Docker Compose |

## 4. Arhitektuur

```mermaid
flowchart LR
    rik[RIK Äriregistri API] -->|Airflow @daily| raw_rik[(staging.ariregister_raw)]
    stat[Statistikaamet PxWeb API] -->|Airflow @monthly| raw_pop[(staging.rahvastik_raw)]
    csv_mk[seeds/maakonnad.csv] -->|dbt seed| dim_mk[(marts.dim_maakond)]
    csv_em[seeds/emtak.csv] -->|dbt seed| dim_em[(marts.dim_emtak)]

    raw_rik -->|dbt staging| stg_rik[stg_ariregister_muutused]
    raw_pop -->|dbt staging| stg_pop[stg_rahvastik]

    stg_rik --> int_fact[intermediate.int_muutus_fakt]
    stg_pop --> int_norm[intermediate.int_rahvastik_kuine]
    dim_mk --> int_fact
    dim_em --> int_fact

    int_fact --> mart_uued[marts.mart_uued_ettevotted]
    int_fact --> mart_juh[marts.mart_juhatuse_muutused]
    int_norm --> mart_uued
    int_norm --> mart_juh
    int_fact --> mart_idx[marts.mart_aktiivsuse_indeks]

    mart_uued --> superset[Superset näidikulaud]
    mart_juh --> superset
    mart_idx --> superset

    airflow[Airflow scheduler] -->|@daily| rik
    airflow -->|@monthly| stat
    airflow -->|BashOperator| dbt[dbt run + dbt test]
```

### Andmebaasi kihid

| Kiht | Materiaalsus | Roll |
|---|---|---|
| `staging` | Tabel (raw) + dbt vaated | API/CSV toorandmed `_raw` tabelites; `stg_*` vaated puhastavad ja tüpiseerivad |
| `intermediate` | Vaade | Liidab muutused dimensioonidega, arvutab rahvastiku-normaliseeritud baasi |
| `marts` | Tabel | Äriküsimuste vastused — Supersetti loetav kiht |
| `quality` | Tabel | dbt testide tulemused (`dbt test --store-failures`) |

Iga Airflow käivitus saab oma `run_id`. Toorandmed jäävad alles auditeerimiseks; `marts` tabelid ehitatakse iga käivitusel uuesti (`materialized: table`).

## 5. Andmemudel — peamised tabelid

**Dimensioonid (staatilised):**

- `marts.dim_maakond` — `maakond_kood` (PK), `maakond_nimi`, `regioon`, `kuvajarjestus`
- `marts.dim_emtak` — `emtak_kood` (PK), `emtak_jaotis` (A–U), `nimi_1_tase`, `nimi_2_tase`

**Faktid:**

- `staging.ariregister_raw` — toorandmed RIK API-st (`run_id`, `kanne_kp`, `registrikood`, `kande_tyyp`, `emtak_kood`, `maakond_kood`, `laetud_kell`, `allikas_url`, ...)
- `staging.rahvastik_raw` — toorandmed Statistikaametist (`run_id`, `aasta`, `kuu`, `maakond_kood`, `rahvastik`, `laetud_kell`)
- `marts.mart_uued_ettevotted` — kuu × maakond × EMTAK jaotis: uute arv, rahvastikuga normaliseeritud määr
- `marts.mart_juhatuse_muutused` — kuu × maakond: muutuste arv, määr aktiivse ettevõtte kohta, libisev 30-päevane määr
- `marts.mart_aktiivsuse_indeks` — kuu × maakond: kompositiidiks arvutatud indeks 0–100

**Põhilised arvutused (intermediate kihis):**

- `kande_tyyp` klassifitseerimine kolmeks: `registreerimine`, `juhatuse_muudatus`, `lopetamine`.
- `aktiivsete_ettevotete_arv` libisev 90-päevane keskmine maakonna kohta.
- Liitmine rahvastikuga: viimane teadaolev kuu rahvastik per maakond (`LEFT JOIN` ja `COALESCE`).

## 6. Andmekvaliteedi testid (dbt `schema.yml`)

Vähemalt 10 testi, mis katavad mõlemad allikad ja kõik kihid:

1. `staging.stg_ariregister_muutused.registrikood` — `not_null`, `unique` käivituse + kande lõikes (`dbt_utils.unique_combination_of_columns`).
2. `staging.stg_ariregister_muutused.kande_kp` — `not_null`, vahemikus 2010-01-01 kuni täna+1.
3. `staging.stg_ariregister_muutused.kande_tyyp` — `accepted_values` (`registreerimine`, `juhatuse_muudatus`, `lopetamine`, `muu`).
4. `staging.stg_ariregister_muutused.emtak_kood` — `relationships` tabeliga `marts.dim_emtak`.
5. `staging.stg_ariregister_muutused.maakond_kood` — `relationships` tabeliga `marts.dim_maakond`.
6. `staging.stg_rahvastik.rahvastik` — `not_null`, > 0.
7. `staging.stg_rahvastik` — unikaalne `(aasta, kuu, maakond_kood)` kombinatsioon.
8. `intermediate.int_muutus_fakt.maakond_kood` — `not_null`.
9. `marts.mart_uued_ettevotted.uued_per_1000` — `not_null`, vahemikus 0–500 (sanity check).
10. `marts.mart_aktiivsuse_indeks.indeks` — `not_null`, vahemikus 0–100.
11. `marts.mart_juhatuse_muutused.muutuste_maar_pct` — `not_null`, vahemikus 0–100.
12. **Värskuse test:** viimane `kande_kp` ei ole vanem kui 7 päeva (custom singular test).

Tulemused salvestatakse `quality` skeemi ja kuvatakse näidikulaual eraldi tabilehel.

## 7. Näidikulaud (Superset)

**Dashboard pealkiri:** *Eesti äriregistri muutuste voog — maakondlik aktiivsus*

| Chart | Tüüp | Allikas | Mida näitab |
|---|---|---|---|
| Aktiivsuse indeksi kaart | Country Map (EE) | `mart_aktiivsuse_indeks` | Maakonnad värvitud aktiivsuse indeksi järgi |
| Top EMTAK valdkonnad | Horizontal Bar | `mart_uued_ettevotted` | Top 10 EMTAK jaotist uute ettevõtete järgi |
| Uued ettevõtted ajas | Line Chart | `mart_uued_ettevotted` | Kuised registreerimised, seeria = maakond |
| Juhatuse muudatuste määr | Heatmap | `mart_juhatuse_muutused` | Maakond × kuu, värv = määr % |
| KPI plokk | Big Number with Trendline | `mart_uued_ettevotted` | Selle kuu uute kogusumma + muutus eelmise kuu suhtes |
| Andmekvaliteet | Table | `quality.test_results` | Viimase käivituse testid (kõik PASS / FAIL) |

Filtrid (dashboard-tase): ajavahemik, maakond, EMTAK jaotis.

## 8. Töövoog (Airflow DAG-id)

**DAG 1 — `ariregister_paevane` (`@daily`, ajakava 03:00 EET):**

```
lae_ariregister_muutused  >>  dbt_run_staging_rik  >>  dbt_run_marts  >>  dbt_test
```

**DAG 2 — `rahvastik_kuine` (`@monthly`, 1. kuupäev 04:00 EET):**

```
lae_rahvastik  >>  dbt_run_staging_stat  >>  dbt_run_marts  >>  dbt_test
```

Mõlemad DAG-id on **idempotentsed** — `ON CONFLICT DO NOTHING` staging tabelisse, dbt mudelid `materialized: table` ehitavad marts kihi uuesti. `catchup=False`.

## 9. Projekti struktuur

```
.
├── README.md                              ← lõplik projekti kirjeldus (kursuse esitus)
├── Projekt.md                             ← algne teemakirjeldus
├── Projektiplaan.md                       ← see fail
├── compose.yml                            ← Postgres + Airflow + Superset
├── .env.example
├── .gitignore
├── Dockerfile.superset
├── airflow/
│   └── dags/
│       ├── ariregister_paevane.py
│       └── rahvastik_kuine.py
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── seeds/
│   │   ├── maakonnad.csv
│   │   └── emtak.csv
│   ├── models/
│   │   ├── staging/    (stg_ariregister_muutused, stg_rahvastik + schema.yml)
│   │   ├── intermediate/ (int_muutus_fakt, int_rahvastik_kuine + schema.yml)
│   │   └── marts/      (mart_uued_ettevotted, mart_juhatuse_muutused, mart_aktiivsuse_indeks + schema.yml)
│   └── macros/
│       └── generate_schema_name.sql
├── init/
│   └── 01_create_schemas.sql              ← staging + quality skeemid, raw tabelid
├── superset/
│   ├── superset_config.py
│   └── dashboards/ariregister_dashboard.zip
├── scripts/
│   └── import_dashboard.sh
└── docs/
    ├── arhitektuur.md                     ← nädal 1 väljund
    └── progress.md                        ← nädal 2 väljund
```

## 10. Ajakava

| Nädal | Kuupäevad | Eesmärk | Väljund |
|---|---|---|---|
| **N1** | k 19.05 – k 26.05 | Skoop, andmeallika tundmaõppimine, arhitektuur, repo skeleton | `docs/arhitektuur.md`, `compose.yml` käivitub, tühi DAG nähtav Airflow UI-s |
| **N2** | k 26.05 – k 02.06 | End-to-end MVP: RIK API → staging → 1 dbt mudel → 1 chart | `docs/progress.md`, esimene andmete tilk näidikulauale |
| **N3** | k 02.06 – k 09.06 | Teine allikas + normaliseerimine + kõik marts mudelid | Kõik 3 KPI-d arvutuvad, vähemalt 6 testi läbib |
| **N4** | k 09.06 – k 16.06 | Andmekvaliteet, Superset dashboard, dokumentatsioon, esitamine | Lõplik repo, ekspordin dashboard ZIP, kursuse esitus |

**Hilisemad kontrollpunktid:**

- iga reede 18:00 — lühike sünk Teams-is (15 min);
- N3 lõpus — sisekontroll: `docker compose up -d --build` puhtalt klooniti repost → kõik töötab → screenshot näidikulauast.

## 11. Tööjaotus

| Roll | Vastutus | Täitja |
|---|---|---|
| Andmeallika omanik (RIK) | DAG `ariregister_paevane`, `staging.ariregister_raw`, vigade käsitlemine | *[Nimi 1]* |
| Andmeallika omanik (Stat) | DAG `rahvastik_kuine`, rahvastiku normaliseerimise loogika | *[Nimi 2]* |
| Transformatsioonide omanik | dbt mudelid (staging, intermediate, marts), seemned | *[Nimi 3]* |
| Kvaliteedi + näidikulaua omanik | dbt `schema.yml`, custom testid, Superset chart'id ja dashboard | *[Nimi 4]* |

Iga liige teeb oma osa kohta PR-id ja vaatab vähemalt ühe teise liikme PR-i üle.

## 12. Riskid ja maandus

| Risk | Mõju | Maandus |
|---|---|---|
| RIK API limiteerib päringute arvu või on ajutiselt maas | DAG kukub, andmed vananevad | Airflow retried (3×, 5 min vahega); `staging.pipeline_runs` salvestab veateated; vajadusel laeme CSV väljavõtte |
| RIK ja Statistikaameti maakonnakoodid ei ühti | `JOIN` tagastab `NULL`-e | Seeme `maakonnad.csv` sisaldab mõlema mapingu kaardistust; dbt `relationships` test püüab puudujäägid |
| EMTAK koode on tuhandeid — graafikud üle koormatud | Dashboard ebaloetav | Agregeerime 1. tasemele (jaotised A–U); 2. tase on filtrina kättesaadav |
| dbt test ebaõnnestub produktsioonijooksul | Halvad andmed jõuavad näidikulauale | `dbt test` task märgib DAG-i punaseks; Superset näitab viimast edukat marts'i (mart tabelid uuendatakse alles peale testide õnnestumist — `dbt build` asemel `dbt run` + `dbt test` järjestus) |
| Superseti esmaseadistus aeglane / käsitsi | Repo klooni järel ei näe kohe dashboard'i | Eksporditud ZIP `superset/dashboards/` kaustas + `import_dashboard.sh` skript |
| Rahvastiku andmed on aasta vanad | Normaliseering pisut nihkes | Kasutame viimast saadaolevat kuu väärtust ja näitame UI-s `andmed seisuga YYYY-MM` |

## 13. Privaatsus ja turve

- Mõlemad allikad on **avalikud avaandmed** — isikuandmeid ei käsitle.
- Andmebaasi paroolid, Airflow ja Superseti administraatori paroolid ning Superseti `SECRET_KEY` on **ainult `.env` failis**, mis on `.gitignore`-s.
- Repos on ainult `.env.example` koos näiteväärtustega.
- TLS-i ei keera välja produktsiooniks (näidisprojekti SSL workaround on ainult kursuse keskkonna jaoks ja kommenteerime selle koodis välja, kui leiame stabiilse alternatiivi).

## 14. Kursuse nõuetele vastavus

| Nõue | Kuidas täidame |
|---|---|
| Selge äriküsimus | Kahe-tasemeline küsimus uutest registreerimistest ja juhatuse muudatustest, rahvastikuga normaliseeritud. |
| Ajas muutuv andmeallikas | RIK avaandmed uuenevad iga päev; Statistikaameti API kord kuus. |
| Automatiseeritud sissevõtt | Kaks Airflow DAG-i ajakavadega `@daily` ja `@monthly`. |
| Vähemalt üks transformatsioon | dbt staging → intermediate → marts, 3 marts mudelit. |
| Staatiline dimensioon | `seeds/maakonnad.csv` ja `seeds/emtak.csv` laetakse `dbt seed`-iga `marts.dim_*` tabelitesse. |
| Andmekvaliteedi testid | 12 dbt testi, sh värskuse custom test. |
| Näidikulaud | Superset dashboard 6 chart'iga, sh kaart ja KPI. |
| Saladused `.env` failis | Kõik paroolid + `SUPERSET_SECRET_KEY` `.env`-is; repos ainult `.env.example`. |
| README | `README.md` kohandatakse projekti lõpus näidisprojekti mallist. |

## 15. Definitsioon — "Valmis"

Projekt loetakse valmis, kui klooni-järgne käivitus täidab kõik järgmised punktid:

```bash
git clone <repo>
cd andmeinseneride-projekt
cp .env.example .env
docker compose up -d --build
# oota ~3 min
```

1. `docker compose ps` näitab Postgresi, Airflow scheduler/webserveri, Superseti olekuga `running` / `healthy`.
2. Airflow UI-s (`http://localhost:8080`) on mõlemad DAG-id nähtaval; käsitsi trigger lõpetab edukalt.
3. `dbt test` lõpus kõik 12+ testi läbivad (PASS).
4. Supersetis (`http://localhost:8088`) avaneb dashboard "Eesti äriregistri muutuste voog" kõigi 6 chart'iga, milles on andmed.
5. `docs/arhitektuur.md` ja `docs/progress.md` on täidetud (ei sisalda mall-kohatäiteid).
6. README seletab uuele lugejale, mis projekt teeb, kuidas seda käivitada ja millised on tulemused.
