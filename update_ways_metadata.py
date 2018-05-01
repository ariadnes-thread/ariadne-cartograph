from dataproviders import CachedTiledDataProvider
import psycopg2
import yaml
import json
import numpy as np
import logging
from tqdm import tqdm

logger = logging.getLogger('update_ways_metadata')


def extract_ways_metadata(cursor, provider):
    """
    Returns a dict of key-value pairs for each entry in ``public.ways``, with value
    given by the ``provider``.

    :param cursor: database cursor object
    :param provider: data provider to retrieve values from
    :return: dict containing key value pairs
    """
    ways_metadata = {}
    cursor.execute('SELECT gid, st_asgeojson(the_geom) FROM ways')
    max_observed = 0
    for gid, geojson in tqdm(cursor, total=cursor.rowcount, unit=' ways'):
        coordinates = json.loads(geojson)['coordinates']
        values = []
        for coord in coordinates:
            values.append(provider.get_value(*coord))
        median = np.median(values)
        max_observed = max(max_observed, median)
        ways_metadata[gid] = median
    for k in ways_metadata:
        ways_metadata[k] /= max_observed

    return ways_metadata


def upsert_ways_metadata(cursor, column, ways_metadata) -> None:
    """
    Upserts key-value pair stored in ``ways_metadata`` dict into the database table ways_metadata.
    Values of ``ways_metadata`` dict are inserted into ``column`` column, matching keys on the
    primary key.

    :param cursor: database cursor object
    :param column: column to insert/updates values to
    :param ways_metadata: dict containing key value pairs
    """
    from psycopg2.extras import execute_values
    logger.info('Updating table ways_metadata with {}.'.format(column))
    insert_statement = '''INSERT INTO public.ways_metadata (gid, {0})
        VALUES %s
        ON CONFLICT (gid) DO UPDATE
          SET {0} = excluded.{0}'''.format(column)
    execute_values(cursor, insert_statement, ways_metadata.items())


def process_strava_heatmap(cursor) -> None:
    """
    Gathers data from Strava heatmap tile maps

    :param cursor: database cursor object
    """

    def strava_value(img, x, y):
        return float(img.getpixel((x, y))) / 255

    logger.info('Gathering Strava popularity data.')
    heaturl = 'https://heatmap-external-b.strava.com/tiles/all/hot/${z}/${x}/${y}.png?px=256'
    strava_provider = CachedTiledDataProvider(heaturl, strava_value, convert_args={'mode': 'L'})

    ways_metadata = extract_ways_metadata(cursor, strava_provider)
    upsert_ways_metadata(cursor, 'popularity', ways_metadata)


def process_strava_heatmap_highres(cursor, config) -> None:
    """
    Gathers data from Strava heatmap tile maps

    :param cursor: database cursor object
    :param config: parsed config.yaml
    """

    def strava_value(img, x, y):
        return float(img.getpixel((x, y))) / 255

    logger.info('Gathering Highres Strava popularity data.')
    heaturl = 'https://heatmap-external-b.strava.com/tiles-auth/all/hot/${z}/${x}/${y}.png'
    strava_provider = CachedTiledDataProvider(heaturl, strava_value, tile_size=512, zoom=15, convert_args={'mode': 'L'},
                                              headers=config['strava']['headers'])

    ways_metadata = extract_ways_metadata(cursor, strava_provider)
    upsert_ways_metadata(cursor, 'popularity_highres', ways_metadata)


def process_gmaps_satellite(cursor) -> None:
    """
    Gathers data from Google satellite tile maps

    :param cursor: database cursor object
    """

    def greenery_value(img, x, y):
        box = (max(0, x - 10), max(0, y - 10), min(256, x + 10), min(256, y + 10))
        neighborhood = img.crop(box).resize((1, 1))
        r, g, b = neighborhood.getpixel((0, 0))
        return min(1., float(max(g - max(r, b), 0)) / 200)

    logger.info('Gathering Gmaps satellite data.')
    url = 'http://mt1.google.com/vt/lyrs=s&x=${x}&y=${y}&z=${z}'
    gmaps_provider = CachedTiledDataProvider(url, greenery_value, zoom=15, convert_args={'mode': 'RGB'})

    ways_metadata = extract_ways_metadata(cursor, gmaps_provider)
    upsert_ways_metadata(cursor, 'greenery', ways_metadata)


if __name__ == "__main__":
    def main():
        logging.basicConfig(level=logging.INFO)

        logger.info('Script initializing.')
        with open('config.yaml', 'r') as f:
            config = yaml.load(f)
        with psycopg2.connect(**config['database']) as conn:
            cursor = conn.cursor()
            process_strava_heatmap(cursor)
            # process_strava_heatmap_highres(cursor, config)
            process_gmaps_satellite(cursor)
            cursor.close()
        logger.info('Script finished.')


    main()
