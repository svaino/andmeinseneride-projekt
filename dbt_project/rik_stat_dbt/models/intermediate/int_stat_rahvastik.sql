-- Ettevõtlik elanikkond: 20-74 aastased
-- 0-19: valdavalt mitteaktiivsed ettevõtjad
-- 75+: eakad, väljunud aktiivsest majanduselust
-- Ei jäta siia vanusegruppe, kuna pole teada ettevõtte asutanute vanuseid
-- Ettevõtlikkust ei analüüsi soo ega rahvuse osakaalu järgi

SELECT
    aasta,
    case 
        when vanusegrupp in ('0-4','5-9','10-14','14-19') then '1_noored_0-19'        
        when vanusegrupp in ('75-79', '80-84','85-89','90-94','95-99', '100 ja vanemad') then '3_vanurid_80+'
        else '2_ettevotlikud_20-74'
    end as vanuseruhmad,
    REPLACE(maakond, ' maakond', '') as maakond,
    -- sugu,
    -- rahvus,
    elanike_arv,
    loaded_at
FROM {{ source('postgres_staging', 'stat_rahvastik') }}
WHERE maakond like '%maakond' 
    and vanusegrupp not in ('85 ja vanemad','Vanuserühmad kokku') 
    and sugu = 'Mehed ja naised'
    and rahvus = 'Rahvused kokku'

