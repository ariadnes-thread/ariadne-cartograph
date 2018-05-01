from dataproviders import CachedTiledDataProvider
import psycopg2
import yaml
import json
import numpy as np
import logging
from tqdm import tqdm

logger = logging.getLogger('update_ways_metadata')


def process_strava_heatmap(cursor):
    from psycopg2.extras import execute_values

    def strava_value(img, x, y):
        return float(img.getpixel((x, y))) / 255

    logger.info('Gathering Strava popularity data')
    heaturl = 'https://heatmap-external-b.strava.com/tiles/all/hot/${z}/${x}/${y}.png?px=256'
    strava_provider = CachedTiledDataProvider(heaturl, strava_value, convert_args={'mode': 'L'})
    cursor.execute('SELECT osm_id, st_asgeojson(the_geom) FROM ways')

    ways_metadata = {}
    for osm_id, geojson in tqdm(cursor, total=cursor.rowcount, unit=' ways'):
        coordinates = json.loads(geojson)['coordinates']
        values = []
        for coord in coordinates:
            values.append(strava_provider.get_value(*coord))
        ways_metadata[osm_id] = np.median(values)

    logger.info('Updating table ways_metadata')
    insert_statement = '''INSERT INTO public.ways_metadata (osm_id, popularity)
VALUES %s
ON CONFLICT (osm_id) DO UPDATE
  SET popularity = excluded.popularity'''
    execute_values(cursor, insert_statement, ways_metadata.items())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info('Script initializing')
    with open('config.yaml', 'r') as f:
        config = yaml.load(f)
    with psycopg2.connect(**config['database']) as conn:
        cursor = conn.cursor()
        process_strava_heatmap(cursor)
        cursor.close()

    logger.info('Script finished')
