-- selles views ühtlustame EMTAK versioonid e teisendame kõik 2025 e uusima jaotise peale
-- Ettevõtlusvormid:  https://www.eesti.ee/eraisik/et/artikkel/ettevotlus/ettevotte-loomine/ettevotlusvormide-vordlus

SELECT
    reg_kood,
    oiguslik_vorm,
        case 
            when oiguslik_vorm in ('Osaühing','Usaldusühing', 'Aktsiaselts','Täisühing', 'Tulundusühistu') then '1_äriettevõtted'
            when oiguslik_vorm = 'Füüsilisest isikust ettevõtja' then '2_FIE'
            else '3_Muud_jur_isikud'
        end as oiguslik_vorm_grupp,
    asutamise_kuupaev,
        n.aastaid,
        (CURRENT_DATE - INTERVAL '1 year' * (n.aastaid + 1))::date AS periood_alates,
        (CURRENT_DATE - INTERVAL '1 year' * n.aastaid - INTERVAL '1 day')::date AS periood_kuni,
        EXTRACT(YEAR FROM  (CURRENT_DATE - INTERVAL '1 year' * n.aastaid - INTERVAL '1 day')::date) AS liikuva_aasta_lopuaasta, 
        -- TO_CHAR(CURRENT_DATE - INTERVAL '1 year' * (n.aastaid + 1), 'YY') || '-' ||
        -- TO_CHAR(CURRENT_DATE - INTERVAL '1 year' * n.aastaid, 'YY') AS periood,
        --  sellega tekitame tänasest alati aastase perioodi tagasi. Kaks eelmist ridavõimaldaks kuvada perioodi aastate vahemikuna aga siis ei saa siduda rahvastikuga
    REPLACE(maakond, ' maakond', '') AS maakond,
    staatus,
    emtak_kood,
        case 
             when emtak_versioon = 'EMTAK 2008' then (
                 SELECT kood_emtak_2025::text
                 FROM {{ source('postgres_staging', 'emtak_2008_2025') }}  e
                 WHERE e.kood_emtak_2008::text = au.emtak_kood
                 ORDER BY 
                     CASE 
                         WHEN LEFT(e.kood_emtak_2025::text, 5) = LEFT(au.emtak_kood, 5) THEN 5
                         WHEN LEFT(e.kood_emtak_2025::text, 4) = LEFT(au.emtak_kood, 4) THEN 4
                         WHEN LEFT(e.kood_emtak_2025::text, 3) = LEFT(au.emtak_kood, 3) THEN 3
                         WHEN LEFT(e.kood_emtak_2025::text, 2) = LEFT(au.emtak_kood, 2) THEN 2
                         WHEN LEFT(e.kood_emtak_2025::text, 1) = LEFT(au.emtak_kood, 1) THEN 1
                        ELSE 0
                     END DESC,
                     e.kood_emtak_2025
                 LIMIT 1
             )
             else emtak_kood
        end as emtak_kood_2025,
    CASE 
    WHEN EXTRACT(YEAR FROM AGE(asutamise_kuupaev))::int < 6 THEN 1
    ELSE 0
    END AS viimased_6a,
    loaded_at
FROM {{ source('postgres_staging', 'ariregister_uldandmed') }} au
CROSS JOIN LATERAL (
    SELECT EXTRACT(YEAR FROM AGE(asutamise_kuupaev))::int AS aastaid
    ) n

