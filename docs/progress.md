# Edenemisraport

See fail on näidis projektitöö teise nädala väljundiks. Enda projektis uuenda seda lühidalt iga esitamise eel.

## Mis on valmis

- Docker Compose käivitab PostgreSQL-i, töövoo konteineri, scheduleri (Airflow) ja näidikulaua (Superset).
- Statistikaameti API-st saab kätte Eesti rahvastikuandmed.
- Avaandmetest saab kätte Eesti äriregistrisse kantud ettevõtted asutamisaja ja maakonna järgi.
- Ettevõtete EMTAK 2025 klassifikaator on laetud alla staatilise csv failina.
- EMTAK 2008-2025 muudatused on laetud alla staatilise csv failina.
- Maakondade ISO koodid joonise tarbeks on kirjutatud dpt seed kausta
- `staging` kihist liigutab dbt anmded `intermediate` kihti, puhastades liigsed vahekokkuvõtted rahvastiku andmetest ning lisades täiendavad kategooriad vanusegrupidele, ettevõtettete tegevusvormidele. Lisaks tekitatkse libisevad aastad, et aruandes saaks vaadata uusi ettevõtteid alati täisaastates kuni tänaseni.
- `intermediate` kihti tekitatakse eraldi dim tabelid EMTAK klassifikaatorile ja Maakondadele.
- Andmed liiguvad `staging` kihist `mart` kihti.
- `mart` kihis arvutatakse valmis summeeritud tabelid aruannete jaoks.
- Näidikulaud näitab vastuseid äriküsimustele. Kasutatud on tabeleid, Eesti kaarti, tulpdiagrammi ja suurt arvu.
- Scheduler käivitab äriregistrist ettevõtete laadimise igal kalendripäeval ja rahvastiu andmete laadimise iga kuu alguses. 
- Näidikulaud värskendab brauserivaadet automaatselt.

## Järgmised sammud

- Lisada dbt testid
- Kontrollida näidikualaua tulemust ja vajadusel täiendada seda
- Täpsustada README järelduste ja piirangute osa.

## Mis takistab

- Kui Open-Meteo API pole ajutiselt kättesaadav, tuleb laadimine hiljem uuesti käivitada.
- Kui port `8501` on hõivatud, tuleb `.env` failis muuta `DASHBOARD_PORT_HOST` väärtust.

## Kontrollpunkt

Viimane edukas käsurea kontroll:

```bash
docker compose exec pipeline python scripts/run_pipeline.py check
```

Oodatav tulemus: viimase laadimise real on `status = success` ja kvaliteeditestide olek on `passed`.
