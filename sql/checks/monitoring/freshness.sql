-- Monitor: the {table} feed delivered something in the {max_hours} hours before :as_of. A silent feed is the most common production incident.
SELECT '{table}' AS feed, max(ingested_at) AS last_delivery,
       round(extract(EPOCH FROM (CAST(:as_of AS timestamptz) - max(ingested_at))) / 3600) AS hours_silent
FROM {raw}.{table}
WHERE ingested_at <= CAST(:as_of AS timestamptz)
HAVING max(ingested_at) IS NULL
    OR max(ingested_at) < CAST(:as_of AS timestamptz) - interval '{max_hours} hours'
