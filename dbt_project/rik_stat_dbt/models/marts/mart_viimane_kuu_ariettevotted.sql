SELECT 
    e.maakond,
    count(e.reg_kood) as ettevotete_arv,
    coalesce(
    t.kõrgeim_vanem || '-' || TRIM(LEFT(t.kõrgeim_vanem_nimi, 60)) || CASE WHEN LENGTH(t.kõrgeim_vanem_nimi) > 60 THEN '...' ELSE '' END,
    'Määramata'
) as emtak_jaotis
FROM {{ ref('int_ariregister_yldandmed') }} e
LEFT JOIN {{ ref('int_dim_emtak') }} t on e.emtak_kood = t.kood
where asutamise_kuupaev >= CURRENT_DATE - 30
and oiguslik_vorm in ('Osaühing','Usaldusühing', 'Aktsiaselts','Täisühing', 'Tulundusühistu','Füüsilisest isikust ettevõtja')     
group by e.maakond,t.kõrgeim_vanem, t.kõrgeim_vanem_nimi