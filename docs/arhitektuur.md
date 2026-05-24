# Arhitektuur

## Äriküsimus

Millistes valdkondades registreeritakse enim uusi ettevõtteid ja kus on juhatuse muudatuste sagedus kõige kõrgem?

## Mõõdikud

1. Uute ettevõtete arv tegevusvaldkonniti, maakonniti, aastati.
2. TOP5 enim kasvavat EMTAK valdkonda viimase 6kuu jooksul registreeritud ettevõtete arvu järgi.
3. Uute ettevõtete arv 1000 elaniku kohta maakonniti, aastati.

## Andmeallikad

| Allikas | Tüüp | Muutuvus ajas | Kasutus |
|---|---|---|---|
| Äriregistri avaandmete API | Avalik HTTP API | Igapäevased muutuste väljavõtted | Põhiandmevoog |
| Statistikaameti PxWeb API | Avalik JSON-stat API | Uueneb kord kuus | Rahvastiku andmed maakondade kaupa |
| EMTAK_2025.csv | Staatiline failiressurss | Automaatselt ei muutu. Muutub kui ise muuta | EMTAK tasemete nimekiri |
| EMTAK_uleminekutabel_2008_EMTAK_2025.csv | Staatiline failiressurss | Automaatselt ei muutu. Muutub kui ise muuta | EMTAK üleminekutabel |
| maakond.geojson | Staatiline failiressurss | Automaatselt ei muutu. Muutub kui ise muuta | Supersetti laadimiseks, et Supersetis kuvada visuaalselt maakondi. Maa- ja ruumiamet |

## Andmevoog

**Dimensioonid (staatilised):**

- `intermediate.dim_maakond` — `maakond_kood` (PK), `maakond_nimi`, `regioon`, `kuvajarjestus`
- `intermediate.dim_emtak` — `emtak_kood` (PK), `emtak_jaotis` (A–U), `nimi_1_tase`, `nimi_2_tase`

**Faktid:**

- `staging.ariregister_raw` — toorandmed RIK API-st (`run_id`, `kanne_kp`, `registrikood`, `kande_tyyp`, `emtak_kood`, `maakond_kood`, `laetud_kell`, `allikas_url`, ...)
- `staging.rahvastik_raw` — toorandmed Statistikaametist (`run_id`, `aasta`, `kuu`, `maakond_kood`, `rahvastik`, `laetud_kell`)
- `marts.ettevotted_ja_rahvastik` — periood × maakond: uute arv, rahvastikuga normaliseeritud määr
- `marts.uued_ettevotted_ja_tegevusvaldkonnad` — periood × maakond × EMTAK jaotis: uute arv
- `marts.juhatuse_muutused` — kuu × maakond: muutuste arv, määr aktiivse ettevõtte kohta??

**Põhilised arvutused (intermediate kihis):**

- `kande_tyyp` klassifitseerimine kolmeks: `registreerimine`, `juhatuse_muudatus`, `lopetamine`.
- `aktiivsete_ettevotete_arv` libisev 180-päevane keskmine maakonna kohta.
- Liitmine rahvastikuga: viimane teadaolev kuu rahvastik per maakond (`LEFT JOIN` ja `COALESCE`).

**NB!** Tegemist on prototüübiga. Andmevoog võib muutuda.

## Andmebaasi kihid

| Kiht | Roll |
|---|---|
| `staging` | Hoiab API-st saadud read allikalähedaselt. |
| `intermediate` | Andmete transformatsiooni kiht. |
| `marts` | Analüütikaks ehitatud tabelid (Supersetti loetav kiht). |
| `quality` | Hoiab kvaliteeditestide tulemusi. |


## Tööjaotus

| Roll | Vastutus | Täitja |
|---|---|---|
| Andmeallika omanik | Kontrollib API vastust ja kirjutab sissevõtu loogika. | Merliti, Sander
| Transformatsioonide omanik | Kirjutab `mart` kihi tabelid ja mõõdikute arvutuse. | Merliti, Sander
| Kvaliteedi omanik | Kirjutab testid ja vaatab läbi ebaõnnestunud kontrollid. | Kaja, Neeme, Merliti, Sander
| Airflow omanik | Airflow seadistamine. | Neeme
| Näidikulaua omanik | Ehitab Superseti dashboardi ja seob selle äriküsimusega. | Kaja


## Riskid

| Risk | Mõju | Maandus |
|---|---|---|
| Äriregistri või Statistikaameti API limiteerib päringute arvu või on ajutiselt maas | Andmeid ei saa värskendada. Vananenud andmed. | Skript annab veateate ning vajadusel uuesti käivitada. |
| Andmetüüpide ootamatu muutumine | Andmete laadimine peatub kuni koodi parandamiseni. | Test, mis kontrollib, kas parsimisel tuli andmeid. |
| EMTAK tegevusvaldkondi on väga palju | Dashboard ei ole hästi loetav. | Tegevusvaldkonad agregeerida.

## Privaatsus ja turve

Projekt kasutab ainult avalikke andmeid. Isikuandmeid ei käsitleta. Andmebaasi, Airflow, Superseti ja Dbt kasutajad ning paroolid on ainult .env failis, mis on .gitogner. Repos on ainult .env.example koos näiteväärtustega.
