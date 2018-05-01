CREATE TABLE public.ways_metadata
(
    gid int PRIMARY KEY NOT NULL,
    popularity FLOAT,
    greenery FLOAT,
    CONSTRAINT ways_metadata_ways_gid_fk FOREIGN KEY (gid) REFERENCES ways (gid) ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE UNIQUE INDEX ways_metadata_gid_uindex ON public.ways_metadata (gid);
COMMENT ON TABLE public.ways_metadata IS 'Metadata on way segments for routing purposes.'