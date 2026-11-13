@all @compliance @REQ_10 @REQ_13
Feature: Compliance — personal data, access control, traceability and evidence

  # Clinical data is regulated. The warehouse must hold no unapproved personal data, show the
  # approved personal data (investigator names) only to authorised roles, trace every requirement
  # (docs/requirements.json) to the scenarios that verify it, and keep each run's evidence
  # with hashes that reveal any later change (GxP / FDA 21 CFR Part 11 style records).

  # ─── Personal data ────────────────────────────────────────────────────────

  Scenario: The star schema holds no personal data except the approved investigator names
    Given the clinical warehouse is built
    When I run the check "sql/checks/rules/privacy/personal_data_columns.sql" with:
      | layer | approved                                                                                               |
      | dwh   | 'dim_site.investigator', 'v_site_current.investigator', 'v_adverse_event_detail.investigator_at_onset' |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/privacy/personal_data_values.sql"
    Then it finds no offending rows

  # ─── Access control ───────────────────────────────────────────────────────

  # Granted in sql/build/security/60_analyst_role.sql. Each query runs as the role and is rolled back.
  Scenario: Analysts read the reporting views but never investigator names or the inner layers
    Given the clinical warehouse is built
    Then the role "dwh_analyst" is allowed or denied these queries:
      | query                                                            | allowed |
      | SELECT study_id, adverse_events FROM dwh.v_safety_by_study_month | yes     |
      | SELECT ae_id, grade, is_serious FROM dwh.v_adverse_event_detail  | yes     |
      | SELECT investigator_at_onset FROM dwh.v_adverse_event_detail     | no      |
      | SELECT investigator FROM dwh.dim_site                            | no      |
      | SELECT * FROM latest.adverse_event                               | no      |
      | SELECT * FROM src.subject                                        | no      |

  # ─── Traceability ─────────────────────────────────────────────────────────

  Scenario: Every requirement is verified by at least one feature, and every feature traces to one
    Then every requirement in "docs/requirements.json" is tagged on at least one feature
    And every feature carries at least one requirement tag that exists in "docs/requirements.json"

  Scenario: The traceability matrix is built from a run's results
    Given a test run reported these scenario results:
      | feature                   | requirement | scenario                     | status |
      | 03_reconciliation.feature | REQ_01      | latest.adverse_event matches | passed |
      | 06_partitions.feature     | REQ_05      | a range reads 3 partitions   | failed |
    When the traceability matrix is built
    Then the matrix shows these requirement statuses:
      | requirement | status     |
      | REQ_01      | PASSED     |
      | REQ_05      | FAILED     |
      | REQ_09      | NOT TESTED |

  # ─── Evidence ─────────────────────────────────────────────────────────────

  Scenario: An evidence pack detects any later change to a retained report
    Given the reports of a finished test run
    When an evidence pack is created from them
    Then its manifest holds a SHA-256 hash for every report, the git commit and the pinned package versions
    And verifying the pack finds no change
    When someone edits "data-quality-report.json" inside the pack
    Then verifying the pack names "data-quality-report.json" as changed
