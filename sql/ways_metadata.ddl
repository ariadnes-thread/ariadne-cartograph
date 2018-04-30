CREATE TABLE public.ways_metadata
(
    osm_id int PRIMARY KEY NOT NULL,
    popularity FLOAT,
    greenery FLOAT,
    CONSTRAINT ways_metadata_osm_ways_osm_id_fk FOREIGN KEY (osm_id) REFERENCES osm_ways (osm_id) ON UPDATE CASCADE
);
CREATE UNIQUE INDEX ways_metadata_osm_id_uindex ON public.ways_metadata (osm_id);
COMMENT ON TABLE public.ways_metadata IS 'Metadata on way segments for routing purposes.'