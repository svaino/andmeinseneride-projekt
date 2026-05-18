# Edenemisraport

See fail on näidis projektitöö teise nädala väljundiks. Enda projektis uuenda seda lühidalt iga esitamise eel.

## Mis on valmis

- Docker Compose käivitab PostgreSQL-i, töövoo konteineri, scheduleri ja näidikulaua.
- Open-Meteo API-st saab kätte valitud Eesti asulate tunnipõhise prognoosi.
- Asukohad on eraldi staatilises `mart.dim_location` dimensioonitabelis.
- Andmed liiguvad `staging` kihist `mart` kihti.
- `mart` kihis arvutatakse tunnipõhine sobivuse skoor ja 3-tunnised ajaaknad.
- Näidikulaud näitab parimaid ajaaknaid, sobivuse kalendrit, temperatuuri, sademeid, tuult ja kvaliteediteste.
- Scheduler käivitab töövoo vaikimisi iga tunni alguses ning näidikulaud värskendab brauserivaadet automaatselt.

## Järgmised sammud

- Kontrollida, kas skoori kaalud vastavad äriküsimusele piisavalt hästi.
- Lisada vajadusel teine ilmamuutuja või muuta asukohadimensiooni ridu.
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
