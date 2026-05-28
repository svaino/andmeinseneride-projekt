# selle failiga tekitame andmebaasi maakondade geokoordinaadid

import json, psycopg2
import geopandas as gpd
import os

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


# NUTS3 regioonid
gdf_nuts3 = gpd.read_file('/app/data/NUTS3_2021/NUTS3_2021.shp')
gdf_nuts3 = gdf_nuts3.to_crs('EPSG:4326')

cur.execute('DROP TABLE IF EXISTS staging.nuts3_geo')
cur.execute('CREATE TABLE staging.nuts3_geo (nuts_id TEXT, regioon TEXT, geometry TEXT)')

for _, row in gdf_nuts3.iterrows():
    cur.execute('INSERT INTO staging.nuts3_geo VALUES (%s, %s, %s)',
        (row['NUTS_ID'], row['Nimi_et'], json.dumps(row['geometry'].__geo_interface__)))

conn.commit()
print('✅ nuts3_geo laetud')
