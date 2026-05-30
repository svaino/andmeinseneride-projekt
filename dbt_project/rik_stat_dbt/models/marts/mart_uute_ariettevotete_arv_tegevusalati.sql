
SELECT 
    ar.oiguslik_vorm_grupp AS jur_valdkond,
    ar.maakond,
    e.kõrgeim_vanem,
    e.kõrgeim_vanem_nimi,
    e. kõrgeim_vanem || '-' || e. kõrgeim_vanem_nimi as EMTAK_jaotis,
    COUNT(ar.reg_kood) AS ettevotete_arv

FROM {{ ref('int_ariregister_yldandmed') }} ar
JOIN {{ ref('int_dim_emtak') }} e ON ar.emtak_kood_2025 = e.kood
WHERE ar.liikuva_aasta_lopuaasta = '2026'
GROUP BY ar.oiguslik_vorm_grupp, ar.maakond, e.kõrgeim_vanem, e.kõrgeim_vanem_nimi