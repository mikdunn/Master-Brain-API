<<<<<<< HEAD
-- Master Brain API BigQuery bootstrap schema
--
-- Usage:
-- 1) Edit project_id/location defaults below (or pass scripted replacements in CI)
-- 2) Run with:
--      bq query --use_legacy_sql=false < scripts/bigquery_schema.sql

DECLARE project_id STRING DEFAULT 'your-gcp-project-id';
DECLARE dataset_id STRING DEFAULT 'master_brain_analytics';
DECLARE dataset_location STRING DEFAULT 'US';

EXECUTE IMMEDIATE FORMAT(
  "CREATE SCHEMA IF NOT EXISTS `%s.%s` OPTIONS(location='%s')",
  project_id,
  dataset_id,
  dataset_location
);

-- -----------------------------------------------------------------------------
-- Query telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.query_telemetry` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    endpoint STRING,
    query_hash STRING,
    query_text STRING,
    mode STRING,
    confidence_score FLOAT64,
    selected_modules ARRAY<STRING>,
    k INT64,
    latency_ms INT64,
    status_code INT64,
    error STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY endpoint, mode
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Retrieval hit telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.retrieval_hits` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    endpoint STRING,
    query_hash STRING,
    mode STRING,
    retrieval_rank INT64,
    chunk_id STRING,
    source STRING,
    module_id STRING,
    page INT64,
    score FLOAT64,
    channel STRING,
    used_inheritance_expansion BOOL,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY module_id, endpoint
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Build run telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.build_runs` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    build_id STRING,
    build_type STRING,
    status STRING,
    total_files INT64,
    changed_files INT64,
    reused_files INT64,
    documents_ingested INT64,
    chunks_created INT64,
    modules_built INT64,
    failed_files INT64,
    quarantined_files INT64,
    checkpoint_writes INT64,
    index_path STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY status, build_type
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- File inventory snapshots
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.file_inventory_snapshot` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    build_id STRING,
    module_id STRING,
    file_path STRING,
    action STRING,
    file_signature STRING,
    chunk_count INT64,
    error STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY module_id, action
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Timeline / operational events
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.timeline_events` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    event_type STRING,
    severity STRING,
    source_component STRING,
    message STRING,
    context JSON,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY event_type, severity
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Chunk metadata catalog (Phase 3 emitter target)
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.chunk_metadata_catalog` (
    chunk_id STRING NOT NULL,
    source_file STRING,
    build_id STRING,
    module_id STRING,
    page INT64,
    section STRING,
    text_hash STRING,
    text_preview STRING,
    char_length INT64,
    tags ARRAY<STRING>,
    confidence_low_quality BOOL,
    has_equations BOOL,
    equation_count INT64,
    created_timestamp TIMESTAMP,
    last_seen_timestamp TIMESTAMP,
    retention_days INT64,
    period_start INT64,
    period_end INT64,
    region STRING,
    tradition STRING,
    source_type STRING,
    schema_version INT64
  )
  CLUSTER BY module_id, source_file
  ''',
  project_id,
  dataset_id
);
=======
-- Master Brain API BigQuery bootstrap schema
--
-- Usage:
-- 1) Edit project_id/location defaults below (or pass scripted replacements in CI)
-- 2) Run with:
--      bq query --use_legacy_sql=false < scripts/bigquery_schema.sql

DECLARE project_id STRING DEFAULT 'your-gcp-project-id';
DECLARE dataset_id STRING DEFAULT 'master_brain_analytics';
DECLARE dataset_location STRING DEFAULT 'US';

EXECUTE IMMEDIATE FORMAT(
  "CREATE SCHEMA IF NOT EXISTS `%s.%s` OPTIONS(location='%s')",
  project_id,
  dataset_id,
  dataset_location
);

-- -----------------------------------------------------------------------------
-- Query telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.query_telemetry` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    endpoint STRING,
    query_hash STRING,
    query_text STRING,
    mode STRING,
    confidence_score FLOAT64,
    selected_modules ARRAY<STRING>,
    k INT64,
    latency_ms INT64,
    status_code INT64,
    error STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY endpoint, mode
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Retrieval hit telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.retrieval_hits` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    endpoint STRING,
    query_hash STRING,
    mode STRING,
    retrieval_rank INT64,
    chunk_id STRING,
    source STRING,
    module_id STRING,
    page INT64,
    score FLOAT64,
    channel STRING,
    used_inheritance_expansion BOOL,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY module_id, endpoint
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Build run telemetry
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.build_runs` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    build_id STRING,
    build_type STRING,
    status STRING,
    total_files INT64,
    changed_files INT64,
    reused_files INT64,
    documents_ingested INT64,
    chunks_created INT64,
    modules_built INT64,
    failed_files INT64,
    quarantined_files INT64,
    checkpoint_writes INT64,
    index_path STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY status, build_type
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- File inventory snapshots
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.file_inventory_snapshot` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    build_id STRING,
    module_id STRING,
    file_path STRING,
    action STRING,
    file_signature STRING,
    chunk_count INT64,
    error STRING,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY module_id, action
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Timeline / operational events
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.timeline_events` (
    event_id STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    event_type STRING,
    severity STRING,
    source_component STRING,
    message STRING,
    context JSON,
    schema_version INT64
  )
  PARTITION BY DATE(timestamp)
  CLUSTER BY event_type, severity
  ''',
  project_id,
  dataset_id
);

-- -----------------------------------------------------------------------------
-- Chunk metadata catalog (Phase 3 emitter target)
-- -----------------------------------------------------------------------------
EXECUTE IMMEDIATE FORMAT(
  '''
  CREATE TABLE IF NOT EXISTS `%s.%s.chunk_metadata_catalog` (
    chunk_id STRING NOT NULL,
    source_file STRING,
    build_id STRING,
    module_id STRING,
    page INT64,
    section STRING,
    text_hash STRING,
    text_preview STRING,
    char_length INT64,
    tags ARRAY<STRING>,
    confidence_low_quality BOOL,
    has_equations BOOL,
    equation_count INT64,
    created_timestamp TIMESTAMP,
    last_seen_timestamp TIMESTAMP,
    retention_days INT64,
    period_start INT64,
    period_end INT64,
    region STRING,
    tradition STRING,
    source_type STRING,
    schema_version INT64
  )
  CLUSTER BY module_id, source_file
  ''',
  project_id,
  dataset_id
);
>>>>>>> a4d0660f0cf3ab765b38228594d0bdca1aa13246
