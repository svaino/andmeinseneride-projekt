    SELECT  
    r.liikuva_aasta_lopuaasta as liikuv_aasta,
    r. maakond,
    coalesce(
    e.kõrgeim_vanem || '-' || TRIM(LEFT(e.kõrgeim_vanem_nimi, 60)) || CASE WHEN LENGTH(e.kõrgeim_vanem_nimi) > 60 THEN '...' ELSE '' END,
    'Määramata'
) as emtak_jaotis,
    r.viimased_6a,
    count(reg_kood) as aride_arv
    FROM {{ ref('int_ariregister_yldandmed') }} r
    LEFT JOIN {{ ref('int_dim_emtak') }} e on e.kood = r.emtak_kood_2025
    WHERE r.oiguslik_vorm_grupp != '3_Muud_jur_isikud'
    -- and viimased_6a = 1
    group by r.liikuva_aasta_lopuaasta, r.maakond,  e. kõrgeim_vanem , e. kõrgeim_vanem_nimi, r.viimased_6a


