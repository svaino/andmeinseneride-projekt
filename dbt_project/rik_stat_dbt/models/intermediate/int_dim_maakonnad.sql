SELECT
    ROW_NUMBER() OVER (ORDER BY kuvajärjestus) AS maakond_id,
    maakond_nimi,
    regioon,
    kuvajärjestus
FROM {{ ref('dim_maakonnad') }}