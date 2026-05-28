SELECT
    ROW_NUMBER() OVER (ORDER BY kuvajarjestus) AS maakond_id,
    maakond_nimi,
    iso_kood,
    regioon,
    kuvajarjestus
FROM {{ ref('dim_maakonnad') }}