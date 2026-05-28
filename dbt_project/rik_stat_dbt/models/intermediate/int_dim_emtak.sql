WITH RECURSIVE hierarhia AS (
    SELECT kood, vanem, kood AS jaotis
    FROM {{ source('postgres_staging', 'emtak_2025') }}
    WHERE vanem IS NULL

    UNION ALL

    SELECT e.kood, e.vanem, h.jaotis
    FROM {{ source('postgres_staging', 'emtak_2025') }} e
    JOIN hierarhia h ON e.vanem = h.kood
)
SELECT 
    h.kood,
    k.tegevusala_tekst AS kood_nimi,
    h.jaotis AS kõrgeim_vanem,
    e.tegevusala_tekst AS kõrgeim_vanem_nimi
FROM hierarhia h
JOIN {{ source('postgres_staging', 'emtak_2025') }} e ON e.kood = h.jaotis
JOIN {{ source('postgres_staging', 'emtak_2025') }} k ON k.kood = h.kood