-- seeds tabelis ei ole maakondade ISO 3166-2 koodid, vaid Superset'i enda sisemise koodiandmestiku järgi.
-- Supersetis on Country Map kaardiandmed hardcoditud — 
-- url = 'https://raw.githubusercontent.com/apache/superset/master/superset-frontend/plugins/legacy-plugin-chart-country-map/src/countries/estonia.geojson

SELECT
    ROW_NUMBER() OVER (ORDER BY kuvajarjestus) AS maakond_id,
    maakond_nimi,
    iso_kood,
    regioon,
    kuvajarjestus
FROM {{ ref('dim_maakonnad') }}