@all @history @REQ_02 @REQ_03
Feature: History and latest layers — full history and deduplicated current state

  # hist keeps every real change once, with a validity range per version (SCD type 2) and
  # deleted records kept as tombstones. latest keeps one row per business key: the newest
  # change wins and deleted keys drop out. Each check returns the offending rows; none = pass.

  Background:
    Given the clinical warehouse is built

  # ─── Latest: one row per key ──────────────────────────────────────────────

  Scenario Outline: latest.<table> holds exactly one row per <key>
    When I run the check "sql/checks/rules/keys/unique.sql" with:
      | layer  | table   | columns |
      | latest | <table> | <key>   |
    Then it finds no offending rows

    Examples:
      | table         | key        |
      | study         | study_id   |
      | site          | site_id    |
      | subject       | subject_id |
      | visit         | visit_id   |
      | adverse_event | ae_id      |

  Scenario Outline: A <entity> deleted in the source is absent from latest
    When I run the check "sql/checks/rules/history/deletes_applied.sql" with:
      | layer  | entity   | key   | history_table    |
      | latest | <entity> | <key> | <entity>_history |
    Then it finds no offending rows

    Examples:
      | entity        | key        |
      | subject       | subject_id |
      | visit         | visit_id   |
      | adverse_event | ae_id      |

  # ─── History: one row per change, clean timeline per key ──────────────────

  Scenario Outline: hist.<table> keeps every change once, without overlaps or gaps
    When I run the check "sql/checks/rules/keys/unique.sql" with:
      | layer | table   | columns    |
      | hist  | <table> | change_seq |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/history/scd2_no_overlap.sql" with:
      | layer | table   | key   |
      | hist  | <table> | <key> |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/history/scd2_single_current.sql" with:
      | layer | table   | key   |
      | hist  | <table> | <key> |
    Then it finds no offending rows

    Examples:
      | table                 | key        |
      | study_history         | study_id   |
      | site_history          | site_id    |
      | subject_history       | subject_id |
      | visit_history         | visit_id   |
      | adverse_event_history | ae_id      |

  # ─── Tombstones ───────────────────────────────────────────────────────────

  Scenario: Every deleted adverse event is kept in history as a tombstone
    When I run the query "sql/queries/history/deletes_without_tombstone.sql"
    Then the result is empty
    When I run the query:
      """
      SELECT count(*) FROM hist.adverse_event_history WHERE is_current AND is_deleted
      """
    Then the result value is at least 1

  Scenario: No deleted adverse event is left in latest
    When I run the query "sql/queries/history/deleted_in_latest.sql"
    Then the result value is 0

  # ─── Updates ──────────────────────────────────────────────────────────────

  Scenario: Adverse events that worsened show their latest grade, not the first one
    When I run the query:
      """
      SELECT count(DISTINCT ae_id) FROM hist.adverse_event_history
      GROUP BY ae_id HAVING count(DISTINCT grade) > 1
      """
    Then the result has at least 1 rows
    When I run the query "sql/queries/warehouse/worsened_adverse_event_stale.sql"
    Then the result is empty
