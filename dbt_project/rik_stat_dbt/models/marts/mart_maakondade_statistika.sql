WITH rahvastik AS (
    SELECT 
        maakond,
        SUM(elanike_arv) AS elanike_arv
    FROM {{ ref('int_stat_rahvastik') }}
    WHERE aasta = 2024
    GROUP BY 1
),

ettevotted AS (
    -- JA SIIN: peab olema ref intermediate mudelile
    SELECT * FROM {{ ref('int_ettevotete_arv_maakonniti') }}
)

SELECT
    r.maakond,
    r.elanike_arv,
    COALESCE(e.aktiivsete_ettevotete_arv, 0) AS aktiivsete_ettevotete_arv,
    CASE 
        WHEN COALESCE(e.aktiivsete_ettevotete_arv, 0) > 0 
        THEN ROUND(r.elanike_arv::numeric / e.aktiivsete_ettevotete_arv, 2)
        ELSE NULL 
    END AS elanikke_yhe_ettevotte_kohta
FROM rahvastik r
LEFT JOIN ettevotted e ON r.maakond = e.maakond