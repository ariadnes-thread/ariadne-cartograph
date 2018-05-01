from string import Template
import math
import requests
from io import BytesIO
from PIL import Image
import logging
from typing import Optional


class TiledDataProvider(object):
    def __init__(self, url_template, value_fn, tile_size=256, zoom=12):
        self.logger = logging.getLogger('dataproviders.TiledDataProvider')
        self.url = Template(url_template)
        self.value_fn = value_fn
        self.tile_size = tile_size
        self.zoom = zoom

    def get_value(self, lng, lat):
        raise NotImplementedError

    def project_4326_to_3857(self, lng: float, lat: float) -> (float, float):
        """
        Convert from EPSG:4326 CRS to EPSG:3857 CRS maintaining degrees
        as units.

        :param lng: longitude in EPSG:4326 CRS
        :param lat: latitude in EPSG:4326 CRS
        :return: lng lat in EPSG:3857 CRS
        """
        siny = math.sin(lat * math.pi / 180)
        # Truncating to 0.9999 effectively limits latitude to 89.189. This is
        # about a third of a tile past the edge of the world tile.
        siny = min(max(siny, -0.9999), 0.9999)
        return self.tile_size * (0.5 + lng / 360), \
               self.tile_size * (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi))

    def convert_3857_to_xyz(self, lng: float, lat: float, zoom: int) -> (int, int, int, int, int):
        """
        Convert from EPSG:3857 CRS with degree units into XYZ tile coordinates.
        
        :rtype: (int, int, int, int, int)
        :param lng: longitude in EPSG:3857 CRS
        :param lat: latitude in EPSG:3857 CRS
        :param zoom: zoom level
        :return: tuple of tile_x, tile_y, zoom, pixel_x, pixel_y
        """
        scale = 1 << zoom
        pixel_x = int(math.floor(lng * scale % self.tile_size))
        pixel_y = int(math.floor(lat * scale % self.tile_size))
        tile_x = int(math.floor(lng * scale / self.tile_size))
        tile_y = int(math.floor(lat * scale / self.tile_size))
        return tile_x, tile_y, zoom, pixel_x, pixel_y


class CachedTiledDataProvider(TiledDataProvider):
    def __init__(self, url_template, value_fn, tile_size=256, zoom=12, convert_args=None):
        super().__init__(url_template, value_fn, tile_size, zoom)
        self.logger = logging.getLogger('dataproviders.CachedTiledDataProvider')
        self.convert_args = convert_args
        self.cache = {}

    def get_value(self, lng: float, lat: float) -> float:
        """
        Gets value associated with a LngLat coordinate in EPSG:4326 CRS
        :param lng: longitude in EPSG:4326 CRS
        :param lat: latitude in EPSG:4326 CRS
        :return: value
        """
        x, y, z, px, py = self.convert_3857_to_xyz(*self.project_4326_to_3857(lng, lat), self.zoom)
        if (x, y, z) in self.cache:
            img = self.cache[(x, y, z)]
        else:
            img = self.get_fresh_tile(x, y, z)
            self.cache[(x, y, z)] = img
        return self.value_fn(img, px, py)

    def get_fresh_tile(self, x: int, y: int, z: int) -> Optional[Image.Image]:
        """
        Gets fresh copy of a tile from data provider.
        See https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames for tile format details.

        :param x: X-coordinate of tile
        :param y: Y-coordinate of tile
        :param z: Zoom level
        :return: `Image` returned from data provider
        """
        url = self.url.substitute({'x': x, 'y': y, 'z': z})
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            if self.convert_args:
                return img.convert(**self.convert_args)
            return img
        except requests.exceptions.RequestException as e:
            self.logger.error(e)
        return None
