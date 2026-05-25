SELECT
    reg_kood,
    nimi AS ettevotte_nimi,
    oiguslik_vorm,
    asutamise_kuupaev,
    REPLACE(maakond, ' maakond', '') AS maakond,
    staatus,
    emtak_kood,
    loaded_at

FROM {{ source('postgres_staging', 'ariregister_uldandmed') }}