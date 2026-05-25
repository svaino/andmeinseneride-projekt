SELECT
    aasta,
    vanusegrupp,
    maakond,
    sugu,
    rahvus,
    elanike_arv,
    loaded_at
FROM {{ source('postgres_staging', 'stat_rahvastik') }}