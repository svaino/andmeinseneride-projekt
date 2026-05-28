SELECT 
    e.aasta,
    e.maakond,
    e.regioon,
    e.ettevotlike_arv,
    e.ari_ettevotete_arv,
    e.ettevotteid_1000_ettevotliku_kohta,
    m.iso_kood
    -- m.geometry AS maakond_geo,
    -- n.geometry AS regioon_geo
FROM {{ ref('mart_ettevotlikus_6a') }} e
LEFT JOIN {{ ref('int_dim_maakonnad') }} m on e.maakond = m.maakond_nimi
-- LEFT JOIN {{ source('postgres_staging', 'maakond_geo') }} m ON e.maakond = m.maakond
-- LEFT JOIN {{ source('postgres_staging', 'nuts3_geo') }} n ON e.regioon = n.regioon