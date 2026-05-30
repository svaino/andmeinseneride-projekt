WITH yldandmed AS (
    SELECT * FROM {{ ref('int_ariregister_yldandmed') }}
),

agregeeritud AS (
    SELECT
        maakond,
        COUNT(DISTINCT reg_kood) AS aktiivsete_ettevotete_arv
    FROM yldandmed
    WHERE staatus = 'Registrisse kantud'
    GROUP BY 1
)

SELECT * FROM agregeeritud