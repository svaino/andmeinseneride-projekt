
SELECT 
    ar.oiguslik_vorm_grupp AS jur_valdkond,
    ar.maakond,
    e.kõrgeim_vanem,
    e.kõrgeim_vanem_nimi,
    coalesce(
    e.kõrgeim_vanem || '-' || TRIM(LEFT(e.kõrgeim_vanem_nimi, 60)) || CASE WHEN LENGTH(e.kõrgeim_vanem_nimi) > 60 THEN '...' ELSE '' END,
    'Määramata') as emtak_jaotis,
    COUNT(ar.reg_kood) AS ettevotete_arv

FROM {{ ref('int_ariregister_yldandmed') }} ar
JOIN {{ ref('int_dim_emtak') }} e ON ar.emtak_kood_2025 = e.kood
WHERE ar.liikuva_aasta_lopuaasta = '2026'
GROUP BY ar.oiguslik_vorm_grupp, ar.maakond, e.kõrgeim_vanem, e.kõrgeim_vanem_nimi