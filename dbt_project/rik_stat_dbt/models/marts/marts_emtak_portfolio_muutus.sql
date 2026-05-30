    
    WITH viimane AS (
    SELECT 
        maakond,
        emtak_jaotis,
        SUM(aride_arv) AS arid_viimane_aasta
    FROM {{ ref('int_ettevotete_arv_maakonniti_emtak') }}
    WHERE liikuv_aasta = EXTRACT(YEAR FROM CURRENT_DATE) and emtak_jaotis is not null
    GROUP BY maakond, emtak_jaotis
),
eelmised AS (
    SELECT 
        maakond,
        emtak_jaotis,
        SUM(aride_arv) AS arid_enne
    FROM {{ ref('int_ettevotete_arv_maakonniti_emtak') }}
    WHERE liikuv_aasta < EXTRACT(YEAR FROM CURRENT_DATE) and emtak_jaotis is not null
    GROUP BY maakond, emtak_jaotis
)
SELECT
    v.maakond,
    v.emtak_jaotis,
    v.arid_viimane_aasta,
    e.arid_enne,
    ROUND(v.arid_viimane_aasta * 100.0 / NULLIF(SUM(v.arid_viimane_aasta) OVER (PARTITION BY v.maakond), 0), 1) AS osakaal_viimane,
    ROUND(e.arid_enne * 100.0 / NULLIF(SUM(e.arid_enne) OVER (PARTITION BY e.maakond), 0), 1) AS osakaal_enne
FROM viimane v
LEFT JOIN eelmised e ON v.maakond = e.maakond AND v.emtak_jaotis = e.emtak_jaotis