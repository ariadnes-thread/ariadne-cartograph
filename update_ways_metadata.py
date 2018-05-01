from dataproviders import CachedTiledDataProvider
import psycopg2
import yaml
import json
import numpy as np
import logging
from tqdm import tqdm

logger = logging.getLogger('update_ways_metadata')


def extract_ways_metadata(cursor, provider):
    ways_metadata = {}
    cursor.execute('SELECT osm_id, st_asgeojson(the_geom) FROM ways')
    max_observed = 0
    for osm_id, geojson in tqdm(cursor, total=cursor.rowcount, unit=' ways'):
        coordinates = json.loads(geojson)['coordinates']
        values = []
        for coord in coordinates:
            values.append(provider.get_value(*coord))
        median = np.median(values)
        max_observed = max(max_observed, median)
        ways_metadata[osm_id] = median
    for k in ways_metadata:
        ways_metadata[k] /= max_observed

    return ways_metadata


def process_strava_heatmap(cursor):
    from psycopg2.extras import execute_values

    def strava_value(img, x, y):
        return float(img.getpixel((x, y))) / 255

    logger.info('Gathering Strava popularity data.')
    heaturl = 'https://heatmap-external-b.strava.com/tiles/all/hot/${z}/${x}/${y}.png?px=256'
    strava_provider = CachedTiledDataProvider(heaturl, strava_value, convert_args={'mode': 'L'})
    ways_metadata = extract_ways_metadata(cursor, strava_provider)

    logger.info('Updating table ways_metadata with popularity.')
    insert_statement = '''INSERT INTO public.ways_metadata (osm_id, popularity)
VALUES %s
ON CONFLICT (osm_id) DO UPDATE
  SET popularity = excluded.popularity'''
    execute_values(cursor, insert_statement, ways_metadata.items())


def process_gmaps_satellite(cursor):
    from psycopg2.extras import execute_values

    def greenery_value(img, x, y):
        box = (max(0, x - 10), max(0, y - 10), min(256, x + 10), min(256, y + 10))
        neighborhood = img.crop(box).resize((1, 1))
        r, g, b = neighborhood.getpixel((0, 0))
        return min(1., float(max(g - max(r, b), 0)) / 200)

    logger.info('Gathering Gmaps satellite data.')
    url = 'http://mt1.google.com/vt/lyrs=s&x=${x}&y=${y}&z=${z}'
    gmaps_provider = CachedTiledDataProvider(url, greenery_value, zoom=15, convert_args={'mode': 'RGB'})
    ways_metadata = extract_ways_metadata(cursor, gmaps_provider)

    logger.info('Updating table ways_metadata with greenery.')
    insert_statement = '''INSERT INTO public.ways_metadata (osm_id, greenery)
    VALUES %s
    ON CONFLICT (osm_id) DO UPDATE
      SET greenery = excluded.greenery'''
    execute_values(cursor, insert_statement, ways_metadata.items())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info('Script initializing.')
    with open('config.yaml', 'r') as f:
        config = yaml.load(f)
    with psycopg2.connect(**config['database']) as conn:
        cursor = conn.cursor()
        process_strava_heatmap(cursor)
        process_gmaps_satellite(cursor)
        cursor.close()

    logger.info('Script finished.')
