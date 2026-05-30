WITH rahvastik AS (
    SELECT 
        aasta,
        maakond,
        SUM(elanike_arv) AS ettevotlike_arv
    FROM {{ ref('int_stat_rahvastik') }}
    WHERE vanuseruhmad = '2_ettevotlikud_20-74' 
    AND aasta >= EXTRACT(YEAR FROM CURRENT_DATE) - 5
    GROUP BY aasta, maakond
),

ettevotted AS (
    SELECT * FROM {{ ref('int_ettevotete_arv_maakonniti_emtak') }} 
    where viimased_6a = 1 
)

SELECT
    r.aasta,
    r.maakond,
    r.ettevotlike_arv,
    COALESCE(e.aride_arv, 0) AS ari_ettevotete_arv,
    CASE 
        WHEN r.ettevotlike_arv > 0 
        THEN ROUND(COALESCE(e.aride_arv, 0) * 1000.0 / r.ettevotlike_arv, 1)
        ELSE NULL 
    END AS ettevotteid_1000_ettevotliku_kohta,
    dm.regioon,
    e.EMTAK_jaotis
FROM rahvastik r
LEFT JOIN ettevotted e ON r.maakond = e.maakond AND r.aasta::integer = e.liikuv_aasta::integer
JOIN {{ ref('int_dim_maakonnad') }} dm on dm.maakond_nimi = r.maakond