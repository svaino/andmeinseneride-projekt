-- selles views ühtlustame EMTAK versioonid e teisendame kõik 2025 e uusima jaotise peale
-- Ettevõtlusvormid:  https://www.eesti.ee/eraisik/et/artikkel/ettevotlus/ettevotte-loomine/ettevotlusvormide-vordlus

SELECT
    reg_kood,
    nimi AS ettevotte_nimi,
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
        EXTRACT(YEAR FROM  (CURRENT_DATE - INTERVAL '1 year' * n.aastaid - INTERVAL '1 day')::date) AS perioodi_lopp, 
        -- TO_CHAR(CURRENT_DATE - INTERVAL '1 year' * (n.aastaid + 1), 'YY') || '-' ||
        -- TO_CHAR(CURRENT_DATE - INTERVAL '1 year' * n.aastaid, 'YY') AS periood,
        --  sellega tekitame tänasest alati aastase perioodi tagasi. Kaks eelmist ridavõimaldaks kuvada perioodi aastate vahemikuna aga siis ei saa siduda rahvastikuga
    REPLACE(maakond, ' maakond', '') AS maakond,
    staatus,
    emtak_kood,
        case 
            when emtak_versioon = 'EMTAK 2008' then e825.kood_emtak_2025::text
            else emtak_kood
        end as emtak_kood_2025,
    loaded_at


FROM {{ source('postgres_staging', 'ariregister_uldandmed') }} au
CROSS JOIN LATERAL (
    SELECT EXTRACT(YEAR FROM AGE(asutamise_kuupaev))::int AS aastaid
    ) n
LEFT JOIN (SELECT DISTINCT ON  (kood_emtak_2008) kood_emtak_2008, kood_emtak_2025 
    FROM {{ source('postgres_staging', 'emtak_2008_2025') }} ORDER BY kood_emtak_2008 ) e825 ON e825.kood_emtak_2008::text = au.emtak_kood

WHERE EXTRACT(YEAR FROM AGE(asutamise_kuupaev))::int < 6
