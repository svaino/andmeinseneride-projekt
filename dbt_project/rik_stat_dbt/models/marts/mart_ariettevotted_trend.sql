SELECT 
    e.liikuv_aasta as aasta,
    e.maakond,
    m.regioon,
    sum(e.aride_arv) as aride_arv,
    e.emtak_jaotis, 
    e.viimased_6a   
FROM {{ ref('int_ettevotete_arv_maakonniti_emtak') }} e
LEFT JOIN {{ ref('int_dim_maakonnad') }} m on e.maakond = m.maakond_nimi
group by e.liikuv_aasta,e.maakond,m.regioon,e.emtak_jaotis,e.viimased_6a