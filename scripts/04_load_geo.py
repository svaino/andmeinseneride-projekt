# selle failiga tekitame andmebaasi maakondade geokoordinaadid

import json, psycopg2, os

conn = psycopg2.connect(
    host='db', dbname=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD')
)
cur = conn.cursor()

with open('/app/data/maakond_wgs84.geojson') as f:
    gj = json.load(f)

cur.execute('CREATE TABLE IF NOT EXISTS staging.maakond_geo (maakond TEXT, geometry TEXT)')
cur.execute('TRUNCATE staging.maakond_geo')


for feature in gj['features']:
    cur.execute('INSERT INTO staging.maakond_geo VALUES (%s, %s)',
        (feature['properties']['MNIMI'], json.dumps(feature['geometry'])))

conn.commit()
print('Valmis!')
