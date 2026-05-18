-- ============================================================================
-- 1. KIHTIDE (SKEEMIDE) LOOMINE
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ============================================================================
-- 2. STAGING KIHT (Toorandmete maandumine Pythonist)
-- ============================================================================
CREATE TABLE IF NOT EXISTS staging.statistikaamet_raw (
    id SERIAL PRIMARY KEY,
    inserted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    table_code VARCHAR(10) NOT NULL,
    raw_content JSONB NOT NULL
);

-- ============================================================================
-- 3. INTERMEDIATE KIHT (Andmete teisendamine JSON-ist ja väärtuste fikseerimine)
-- ============================================================================
CREATE OR REPLACE VIEW intermediate.statistikaamet_normalized AS
WITH json_data AS (
    SELECT raw_content 
    FROM staging.statistikaamet_raw 
    ORDER BY inserted_at DESC 
    LIMIT 1
),
aastad AS (
    SELECT 
        (elem.value->>0)::INT AS aasta,
        (elem.key)::INT AS indeks
    FROM json_data,
    jsonb_each(raw_content->'dimension'->'Aasta'->'category'->'index') AS elem
),
väärtused AS (
    SELECT 
        val.value::INT AS rahvaarv,
        (val.ordinality - 1)::INT AS indeks
    FROM json_data,
    jsonb_array_elements(raw_content->'value') WITH ORDINALITY AS val
)
SELECT 
    a.aasta,
    -- Lisame siia selged väärtused, sest teame, mida me API-st küsisime (Sugu='1', Vanus='1')
    'Mehed ja naised kokku' AS sugu,
    'Vanuserühmad kokku' AS vanuserühm,
    v.rahvaarv,
    'Statistikaamet (RV021)' AS andmeallikas
FROM aastad a
JOIN väärtused v ON a.indeks = v.indeks;

-- ============================================================================
-- 4. ANALYTICS KIHT (Täiendatud struktuuriga lõpptabel)
-- ============================================================================
-- Kui tabel on juba loodud, võid selle enne dropida: DROP TABLE IF EXISTS analytics.fact_rahvaarv;
CREATE TABLE IF NOT EXISTS analytics.fact_rahvaarv (
    aasta INT,
    sugu TEXT NOT NULL,
    vanuserühm TEXT NOT NULL,
    rahvaarv INT NOT NULL,
    andmeallikas TEXT,
    uuendatud_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (aasta, sugu, vanuserühm) -- Komposiitvõti tagab, et meil ei teki topelt ridu sama aasta/soo/vanuse kohta
);