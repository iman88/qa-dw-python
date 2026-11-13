@all @partition @REQ_05
Feature: Date partitioning — monthly partitions, correct routing, pruned reads

  # Raw events are partitioned by the month they arrived, facts by the month the event
  # happened. The plan must be complete, every row must sit in its own month, and a date
  # filter must read only the partitions it needs. "The planner reads" is taken from EXPLAIN.

  Background:
    Given the clinical warehouse is built

  # ─── The partition plan ───────────────────────────────────────────────────

  Scenario Outline: <layer>.<table> has one partition per month from <first_month> to <last_month>
    When I run the check "sql/checks/rules/partitions/partition_plan.sql" with:
      | layer   | table   | first_month   | last_month   |
      | <layer> | <table> | <first_month> | <last_month> |
    Then it finds no offending rows

    Examples:
      | layer | table                | first_month | last_month |
      | dwh   | fact_adverse_event   | 2025-01-01  | 2026-12-01 |
      | dwh   | fact_visit           | 2025-01-01  | 2026-12-01 |
      | raw   | adverse_event_events | 2024-12-01  | 2026-12-01 |
      | raw   | visit_events         | 2024-12-01  | 2026-12-01 |

  # The DEFAULT partition catches dates nobody planned for (bad parse, wrong year...).
  Scenario Outline: Nothing lands in the DEFAULT partition of <layer>.<table>
    When I run the check "sql/checks/rules/partitions/default_partition_empty.sql" with:
      | layer   | table   |
      | <layer> | <table> |
    Then it finds no offending rows

    Examples:
      | layer | table                |
      | dwh   | fact_adverse_event   |
      | dwh   | fact_visit           |
      | raw   | adverse_event_events |
      | raw   | visit_events         |

  Scenario Outline: In <table>, the date key and the partition date are the same day
    When I run the check "sql/checks/rules/partitions/date_key_matches_partition_date.sql" with:
      | layer | table   | date_column   | date_key_column   |
      | dwh   | <table> | <date_column> | <date_key_column> |
    Then it finds no offending rows

    Examples:
      | table              | date_column | date_key_column |
      | fact_adverse_event | onset_date  | onset_date_key  |
      | fact_visit         | visit_date  | visit_date_key  |

  # ─── Routing ──────────────────────────────────────────────────────────────

  Scenario: Every fact row sits in the partition of its onset month
    When I run the query "sql/queries/partitions/fact_rows_by_partition.sql"
    Then the result has at least 12 rows
    When I run the query:
      """
      SELECT tableoid::regclass AS partition_name, onset_date
      FROM dwh.fact_adverse_event
      WHERE tableoid::regclass::text NOT LIKE '%' || to_char(onset_date, 'YYYYMM')
      """
    Then the result is empty

  Scenario: Raw events sit in the partition of the month they arrived, not when they happened
    When I run the query:
      """
      SELECT tableoid::regclass AS partition_name, changed_at, ingested_at
      FROM raw.adverse_event_events
      WHERE tableoid::regclass::text NOT LIKE '%' || to_char(ingested_at, 'YYYYMM')
      """
    Then the result is empty

  # The rows are written inside a transaction that is rolled back: nothing is left behind.
  Scenario: Rows dated on either side of a month boundary land in different partitions
    When I write with "sql/queries/partitions/insert_boundary_rows.sql", read back with "sql/queries/partitions/boundary_rows.sql" and roll back, with:
      | last_day   | first_day  |
      | 2025-09-30 | 2025-10-01 |
    Then the result contains:
      | onset_date | partition_name                |
      | 2025-09-30 | dwh.fact_adverse_event_202509 |
      | 2025-10-01 | dwh.fact_adverse_event_202510 |

  # ─── Pruning ──────────────────────────────────────────────────────────────

  Scenario Outline: Onset from <from> until <until> reads <n> partition(s) and matches the source
    When I run the query "sql/queries/partitions/fact_count_in_range.sql" with:
      | date_from | date_until |
      | <from>    | <until>    |
    Then the planner reads only the partitions:
      | partition    |
      | <partitions> |
    And the result is the same as the query "sql/queries/partitions/source_count_in_range.sql"

    Examples:
      | from       | until      | n | partitions                |
      | 2025-09-01 | 2025-10-01 | 1 | fact_adverse_event_202509 |

  Scenario: A range across three months reads exactly those three partitions
    When I run the query "sql/queries/partitions/fact_count_in_range.sql" with:
      | date_from  | date_until |
      | 2025-09-15 | 2025-12-01 |
    Then the planner reads only the partitions:
      | partition                 |
      | fact_adverse_event_202509 |
      | fact_adverse_event_202510 |
      | fact_adverse_event_202511 |
    And the result is the same as the query "sql/queries/partitions/source_count_in_range.sql"

  Scenario: A date filter through the reporting view still prunes
    When I run the query "sql/queries/partitions/view_count_in_range.sql" with:
      | date_from  | date_until |
      | 2025-09-01 | 2025-10-01 |
    Then the planner reads only the partitions:
      | partition                 |
      | fact_adverse_event_202509 |
    And the result is the same as the query "sql/queries/partitions/fact_count_in_range.sql"

  # Same answer, but every partition is read: the reason to filter on the raw column.
  Scenario: Wrapping the partition column in a function reads all 25 partitions
    When I run the query "sql/queries/partitions/function_filter_count_in_month.sql" with:
      | year_month | date_from  | date_until |
      | 2025-09    | 2025-09-01 | 2025-10-01 |
    Then the planner reads all 25 partitions of "fact_adverse_event"
    And the result is the same as the query "sql/queries/partitions/fact_count_in_range.sql"

  Scenario: Reading one partition directly gives the same rows as filtering the parent
    When I run the query "sql/queries/partitions/rows_in_partition.sql" with:
      | partition_name            | date_from  | date_until |
      | fact_adverse_event_202509 | 2025-09-01 | 2025-10-01 |
    Then the result has at least 1 rows
    And the result is the same as the query "sql/queries/partitions/rows_in_range_from_parent.sql"
