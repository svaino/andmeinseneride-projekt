SELECT 
    e.aasta,
    e.maakond,
    e.regioon,
    e.ettevotlike_arv,
    e.ari_ettevotete_arv,
    e.ettevotteid_1000_ettevotliku_kohta,
    e.EMTAK_jaotis,
    m.iso_kood
FROM {{ ref('mart_ettevotlikus_6a') }} e
LEFT JOIN {{ ref('int_dim_maakonnad') }} m on e.maakond = m.maakond_nimi
