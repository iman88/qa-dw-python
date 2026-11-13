-- BigQuery: the CDC landing zone, partitioned by ingestion month and clustered by key and change sequence. require_partition_filter makes BigQuery refuse any query that would scan every partition.
CREATE SCHEMA IF NOT EXISTS {raw};

CREATE OR REPLACE TABLE {raw}.adverse_event_events (
    ae_id STRING NOT NULL, subject_id STRING NOT NULL, meddra_pt STRING, soc STRING, grade INT64, serious BOOL,
    related BOOL, onset_date DATE, resolved_date DATE, outcome STRING,
    change_seq INT64 NOT NULL, op STRING NOT NULL, changed_at TIMESTAMP NOT NULL, ingested_at TIMESTAMP NOT NULL,
    batch_id STRING NOT NULL
)
PARTITION BY TIMESTAMP_TRUNC(ingested_at, MONTH)
CLUSTER BY ae_id, change_seq
OPTIONS (require_partition_filter = TRUE);

CREATE OR REPLACE TABLE {raw}.visit_events (
    visit_id STRING NOT NULL, subject_id STRING NOT NULL, visit_type STRING, visit_date DATE, status STRING,
    change_seq INT64 NOT NULL, op STRING NOT NULL, changed_at TIMESTAMP NOT NULL, ingested_at TIMESTAMP NOT NULL,
    batch_id STRING NOT NULL
)
PARTITION BY TIMESTAMP_TRUNC(ingested_at, MONTH)
CLUSTER BY visit_id, change_seq
OPTIONS (require_partition_filter = TRUE);
