    SELECT  
    perioodi_lopp as aasta,
    maakond,
    count(reg_kood) as aride_arv
    FROM {{ ref('stg_ariregister_viimased_6a') }}
    WHERE oiguslik_vorm_grupp != '3_Muud_jur_isikud'
    group by perioodi_lopp, maakond
