
SELECT 
    ar.oiguslik_vorm_grupp AS jur_valdkond,
    ar.maakond,
    e.kõrgeim_vanem,
    e.kõrgeim_vanem_nimi,
    COUNT(ar.reg_kood) AS ettevotete_arv

FROM {{ ref('stg_ariregister_viimased_6a') }} ar
JOIN {{ ref('int_dim_emtak') }} e ON ar.emtak_kood_2025 = e.kood
WHERE ar.perioodi_lopp = '2026'
GROUP BY ar.oiguslik_vorm_grupp, ar.maakond, e.kõrgeim_vanem, e.kõrgeim_vanem_nimi