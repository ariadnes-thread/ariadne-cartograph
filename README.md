# ariadne-cartograph
GIS data ingestion pipeline

# Requirements

We use [osm2pgsql](https://github.com/openstreetmap/osm2pgsql) to import OpenStreetMaps regions into PostGIS. Installation instructions for Linux/macOS/Windows are available at https://github.com/openstreetmap/osm2pgsql#installing. \
**Note:** Data imported with `osm2pgsql` is not routable out of the box.

We use [osm2pgrouting](https://github.com/pgRouting/osm2pgrouting) to import OpenStreetMaps in a manner that is routable by `pgRouting`. Build and installation instructions are available at it's GitHub repo linked above.

# Importing OSM feature data only

`osm/example.osm` contains an example OSM file of a tiny region of Caltech and it's neighborhood.

Here's an example command to import `osm/example.osm` into a remote DB.

    osm2pgsql osm/example.osm -H <DB Host> -U <DB User> -W -d <DB name> -S default.style --hstore
    
*  `-a|-c`: Append (`-a`) to existing data or remove all (`-c`) existing data. `-c` is default.
*  `-H`: Database server host name or socket location.
*  `-U`: PostgreSQL user name.
*  `-W`: Force PostgreSQL password (for CD / automated tools, set the `PGPASS` env variable instead).
*  `-d`: The name of the PostgreSQL database to connect to.
*  `-S`: Location of the style file. The style file determines *what* to import and *where* to import them to. [See Wiki](https://wiki.openstreetmap.org/wiki/Osm2pgsql#Import_style)
*  `--hstore`: Stores extra/uncommon tags as hstore key-value pair format.

Indices should then be built on hstore columns.

    CREATE INDEX idx_planet_osm_point_tags ON planet_osm_point USING gist(tags);
    CREATE INDEX idx_planet_osm_polygon_tags ON planet_osm_polygon USING gist(tags);
    CREATE INDEX idx_planet_osm_line_tags ON planet_osm_line USING gist(tags);
    
The following tables should have been created in the database:

* `planet_osm_line`: contains all imported ways. These are usually roads and pathways (**warning**: might contain invalid area objects, i.e. unclosed polygons).
* `planet_osm_point`: contains all imported nodes with tags. This seems to contain mix of all points, including speed limit signs, speed bumps, bus stops, tolls, etc.
* `planet_osm_polygon`: contains all imported polygons. These are usually buildings and structures.
* `planet_osm_roads`: contains subset of features intended for low zoom (overview) level map rendering. **DOES NOT CONTAIN JUST ROADS LIKE THE NAME SUGGESTS**

# Importing OSM data suitable for pgRouting

Here's an example command to import `osm/example.osm` into a remote DB using `osm2pgrouting`.

    ./osm2pgrouting --clean --addnodes --attributes --tags -h <DB host> -d <DB name> -U <DB User> -W <DB password> -f osm/example.osm -c /usr/share/osm2pgrouting/mapconfig.xml

Refer to this [pgRouting wiki page](https://github.com/pgRouting/osm2pgrouting/wiki/Documentation-for-osm2pgrouting-v2.3) for command line options.

After importing data, use this pgsql function to process pointsOfInterest table:

    osm2pgr_pois_update(radius default 200, within default 50)

      - Using areas of (radius)mts on POIS
      - Using edges that are at least (within) mts of each POI
    POIS that do not have a closest edge is considered as too far
