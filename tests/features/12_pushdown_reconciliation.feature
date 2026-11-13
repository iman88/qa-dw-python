@all @pushdown @REQ_01 @REQ_08
Feature: Push-down reconciliation — checksums in the database, fetch only what differs

  # At scale, rows cannot be pulled out to compare. The default engine asks the database for a
  # row count and a checksum per bucket of keys (sql/checks/recon_engine/bucket_checksums.sql) and
  # fetches rows only for buckets that differ (sql/checks/recon_engine/rows_in_buckets.sql), which
  # are then compared column by column. The full engine fetches everything and is the reference.

  Background:
    Given the clinical warehouse is built

  # ─── Clean warehouse ──────────────────────────────────────────────────────

  Scenario: On a clean warehouse every reconciliation passes without fetching a single row
    When I run every reconciliation with the "pushdown" engine
    Then every reconciliation passes
    And no row was fetched from the database

  Scenario: The push-down and full engines give the same verdicts and row counts
    When I run every reconciliation with the "pushdown" engine
    And I run every reconciliation with the "full" engine
    Then both engines give the same verdicts and row counts

  # ─── A defect ─────────────────────────────────────────────────────────────

  # Two grades are corrupted: the checksums point at the buckets holding those two rows only.
  Scenario Outline: A corrupted grade is found by fetching at most 2 of <buckets> buckets
    Given a fresh copy of every layer, in schemas prefixed "mut_"
    When I apply the defect "sql/defects/facts/corrupted_grade.sql"
    And I reconcile "sql/checks/recon/facts/fact_adverse_event_vs_source" on the copy with <buckets> push-down buckets
    Then the reconciliation finds 2 mismatched values
    And at most 2 of the <buckets> buckets were fetched

    Examples:
      | buckets |
      | 16      |
      | 64      |
      | 256     |
