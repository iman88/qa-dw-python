@all @mutation @REQ_08 @REQ_10
Feature: Defect injection — the checks catch real pipeline bugs

  # A data test that has never failed proves nothing. Each scenario builds a separate copy of
  # every layer (schemas prefixed mut_), applies one realistic bug from sql/defects/, runs every
  # reconciliation, check and contract, and asserts that the one designed for that bug fails.
  # The first comment line of each defect script says which real-world mistake it imitates.

  Background:
    Given a fresh copy of every layer, in schemas prefixed "mut_"

  # ─── Caught by a check (offending rows) ───────────────────────────────────

  Scenario Outline: <defect> is caught by <check> on <target>
    When I apply the defect "<defect>"
    And I run every reconciliation, check and contract on the copy
    Then the check "<check>" fails on "<target>"

    Examples:
      | defect                                               | check                                                   | target                            |
      | sql/defects/latest/dedup_skipped.sql                 | sql/checks/rules/keys/unique.sql                        | latest.adverse_event (ae_id)      |
      | sql/defects/latest/delete_not_applied.sql            | sql/checks/rules/history/deletes_applied.sql            | latest.adverse_event              |
      | sql/defects/history/history_overlap.sql              | sql/checks/rules/history/scd2_no_overlap.sql            | hist.site_history                 |
      | sql/defects/dimensions/two_current_site_versions.sql | sql/checks/rules/history/scd2_single_current.sql        | dwh.dim_site                      |
      | sql/defects/dimensions/duplicate_subject.sql         | sql/checks/rules/keys/unique.sql                        | dwh.dim_subject (subject_id)      |
      | sql/defects/facts/wrong_site_version.sql             | sql/checks/rules/history/scd2_point_in_time_site.sql    | dwh                               |
      | sql/defects/facts/orphan_fact.sql                    | sql/checks/rules/keys/referential_integrity.sql         | dwh.fact_adverse_event.subject_sk |
      | sql/defects/partitions/out_of_range_date.sql         | sql/checks/rules/partitions/default_partition_empty.sql | dwh.fact_adverse_event            |
      | sql/defects/partitions/missing_partition.sql         | sql/checks/rules/partitions/partition_plan.sql          | dwh.fact_adverse_event            |

  Scenario Outline: <defect> is caught by the privacy check <check>
    When I apply the defect "<defect>"
    And I run every reconciliation, check and contract on the copy
    Then the check "<check>" fails on "dwh"

    Examples:
      | defect                                     | check                                              |
      | sql/defects/privacy/email_in_free_text.sql | sql/checks/rules/privacy/personal_data_values.sql  |
      | sql/defects/privacy/birth_date_exposed.sql | sql/checks/rules/privacy/personal_data_columns.sql |

  # ─── Caught by a reconciliation ───────────────────────────────────────────

  Scenario Outline: <defect> is caught by <reconciliation>
    When I apply the defect "<defect>"
    And I run every reconciliation, check and contract on the copy
    Then the reconciliation "<reconciliation>" fails

    Examples:
      | defect                                               | reconciliation                                           |
      | sql/defects/facts/dropped_fact_rows.sql              | sql/checks/recon/facts/fact_adverse_event_vs_source      |
      | sql/defects/facts/corrupted_grade.sql                | sql/checks/recon/facts/fact_adverse_event_vs_source      |
      | sql/defects/facts/lost_serious_flag.sql              | sql/checks/recon/aggregates/safety_totals_by_study       |
      | sql/defects/views/view_joins_site_by_natural_key.sql | sql/checks/recon/views/v_safety_by_study_month_vs_source |

  Scenario: sql/defects/latest/stale_latest_version.sql is caught by the latest-vs-source reconciliation
    When I apply the defect "sql/defects/latest/stale_latest_version.sql"
    And I run every reconciliation, check and contract on the copy
    Then the reconciliation "sql/checks/recon/latest/latest_vs_source" for entity "adverse_event" fails

  # ─── Caught by a schema contract ──────────────────────────────────────────

  # The data still reconciles after these two: only the contract notices.
  Scenario Outline: <defect> is caught by the contract <contract>
    When I apply the defect "<defect>"
    And I run every reconciliation, check and contract on the copy
    Then the contract "<contract>" fails

    Examples:
      | defect                                     | contract               |
      | sql/defects/schema/dropped_column.sql      | sql/contracts/dwh.json |
      | sql/defects/schema/column_type_changed.sql | sql/contracts/dwh.json |

  # ─── Coverage ─────────────────────────────────────────────────────────────

  Scenario: No defect script is left without a scenario
    Then every defect in "sql/defects" is covered by "08_defect_injection.feature"
