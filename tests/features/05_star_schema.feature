@all @star @REQ_04
Feature: Star schema — dimensions, facts and reporting views

  # Warehouses rarely enforce keys, so they are tested: unique keys, every fact finds its
  # dimension row, the site dimension keeps full history (SCD type 2) and each fact points at
  # the site version that was valid when the event happened. Each check returns the offending
  # rows; none = pass.

  Background:
    Given the clinical warehouse is built

  # ─── Keys and grain ───────────────────────────────────────────────────────

  Scenario Outline: <table> has one row per <columns>
    When I run the check "sql/checks/rules/keys/unique.sql" with:
      | layer | table   | columns   |
      | dwh   | <table> | <columns> |
    Then it finds no offending rows

    Examples: Dimensions
      | table       | columns             |
      | dim_study   | study_id            |
      | dim_subject | subject_id          |
      | dim_site    | site_id, valid_from |

    Examples: Facts
      | table              | columns  |
      | fact_adverse_event | ae_id    |
      | fact_visit         | visit_id |

    Examples: Views
      | table                   | columns              |
      | v_adverse_event_detail  | ae_id                |
      | v_safety_by_study_month | study_id, year_month |

  Scenario Outline: Every <fact>.<fk> finds its row in <dim>
    When I run the check "sql/checks/rules/keys/referential_integrity.sql" with:
      | layer | fact   | fk   | dim   | pk   |
      | dwh   | <fact> | <fk> | <dim> | <pk> |
    Then it finds no offending rows

    Examples:
      | fact               | fk             | dim         | pk         |
      | fact_adverse_event | subject_sk     | dim_subject | subject_sk |
      | fact_adverse_event | study_sk       | dim_study   | study_sk   |
      | fact_adverse_event | site_sk        | dim_site    | site_sk    |
      | fact_adverse_event | onset_date_key | dim_date    | date_key   |
      | fact_visit         | subject_sk     | dim_subject | subject_sk |
      | fact_visit         | study_sk       | dim_study   | study_sk   |
      | fact_visit         | visit_date_key | dim_date    | date_key   |

  # ─── Slowly changing dimension (type 2) ───────────────────────────────────

  Scenario: The site dimension keeps every version, one current, no overlaps
    When I run the check "sql/checks/rules/history/scd2_no_overlap.sql" with:
      | layer | table    | key     |
      | dwh   | dim_site | site_id |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/history/scd2_single_current.sql" with:
      | layer | table    | key     |
      | dwh   | dim_site | site_id |
    Then it finds no offending rows
    When I run the query:
      """
      SELECT site_id, count(*) AS versions FROM dwh.dim_site GROUP BY site_id HAVING count(*) > 1
      """
    Then the result has at least 1 rows

  # A site that changed investigator mid-study: events before the change must stay linked
  # to the old version, so reports by investigator stay true to history.
  Scenario: Each adverse event points at the site version valid on its onset date
    When I run the check "sql/checks/rules/history/scd2_point_in_time_site.sql"
    Then it finds no offending rows
    When I run the query "sql/queries/history/facts_on_historic_site_versions.sql"
    Then the result value is at least 1

  # ─── Values ───────────────────────────────────────────────────────────────

  Scenario: Grades, arms and mandatory columns hold valid values
    When I run the check "sql/checks/rules/values/accepted_values.sql" with:
      | layer | table              | column | values        |
      | dwh   | fact_adverse_event | grade  | 1, 2, 3, 4, 5 |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/values/accepted_values.sql" with:
      | layer | table       | column | values                             |
      | dwh   | dim_subject | arm    | 'PLACEBO', 'DOSE_LOW', 'DOSE_HIGH' |
    Then it finds no offending rows
    When I run the check "sql/checks/rules/values/not_null.sql" with:
      | layer | table              | condition                                                               |
      | dwh   | fact_adverse_event | meddra_pt IS NULL OR soc IS NULL OR grade IS NULL OR onset_date IS NULL |
    Then it finds no offending rows

  # ─── The whole catalogue ──────────────────────────────────────────────────

  # The same set `clinical-dq check` runs: every rule file in sql/checks/rules/ on every
  # table it applies to (catalogue: src/clinical_dq/dq/checks.py).
  Scenario: Every check in the catalogue finds no offending rows on the clean build
    Then every check in the catalogue finds no offending rows
