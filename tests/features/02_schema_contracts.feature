@all @schema @REQ_06
Feature: Schema contracts — every layer has an agreed shape

  # A contract lists each table, partitioned table and view with its columns in order,
  # their types, NOT NULL, and the partition keys. It is a reviewed file in sql/contracts/.
  # Differences are classed as breaking (fails: something a consumer reads is gone, retyped or may
  # now be NULL) or compatible (reported: a new nullable column, a widened type). Contracts carry a
  # semantic version, an owner and their consumers. Refresh with `clinical-dq contract`: it bumps
  # the major version for breaking changes and the minor version for compatible ones.
  # Catalogue queries: sql/checks/schema/columns.sql and sql/checks/schema/partition_keys.sql

  Background:
    Given the clinical warehouse is built

  # ─── Database vs contract ─────────────────────────────────────────────────

  Scenario Outline: The <layer> layer matches its contract
    Then the "<layer>" layer matches the contract "sql/contracts/<layer>.json"

    Examples:
      | layer  |
      | latest |
      | hist   |
      | dwh    |

  # ─── What the star schema contract promises ───────────────────────────────

  Scenario: The star schema has four dimensions, two partitioned facts and three views
    Then the contract "sql/contracts/dwh.json" describes these objects:
      | object                  | type              | partition key      |
      | dim_date                | table             |                    |
      | dim_study               | table             |                    |
      | dim_site                | table             |                    |
      | dim_subject             | table             |                    |
      | fact_adverse_event      | partitioned table | RANGE (onset_date) |
      | fact_visit              | partitioned table | RANGE (visit_date) |
      | v_adverse_event_detail  | view              |                    |
      | v_safety_by_study_month | view              |                    |
      | v_site_current          | view              |                    |

  Scenario: Keys, validity dates and partition columns are NOT NULL
    Then the contract "sql/contracts/dwh.json" declares these columns NOT NULL:
      | object             | column     |
      | dim_site           | site_sk    |
      | dim_site           | valid_from |
      | dim_site           | valid_to   |
      | dim_subject        | subject_id |
      | fact_adverse_event | ae_id      |
      | fact_adverse_event | subject_sk |
      | fact_adverse_event | site_sk    |
      | fact_adverse_event | onset_date |
      | fact_visit         | visit_date |

  # ─── Versions, owners and consumers ───────────────────────────────────────

  Scenario: The star schema contract is versioned and names who depends on it
    Then the contract "sql/contracts/dwh.json" is version "1.0.0", owned by "data engineering"
    And the contract "sql/contracts/dwh.json" names these consumers:
      | consumer                                         |
      | safety reporting (v_safety_by_study_month)       |
      | medical monitoring (v_adverse_event_detail)      |
      | narrative service input (v_adverse_event_detail) |

  # ─── Compatible changes are reported, not failed ──────────────────────────

  # Breaking changes (a dropped column, a changed type) are proven to fail in 08_defect_injection.
  Scenario Outline: <change> is compatible: reported, not failed, version 1.1.0
    Given a fresh copy of every layer, in schemas prefixed "mut_"
    When I apply the schema change "<script>" to the copy
    Then the "dwh" layer of the copy has no breaking change against "sql/contracts/dwh.json"
    And this compatible change is reported:
      | object   | column   | change   |
      | <object> | <column> | <change> |
    And the contract version would become "1.1.0"

    Examples:
      | change              | script                                                  | object      | column            |
      | new nullable column | sql/schema_changes/compatible/added_nullable_column.sql | dim_subject | ethnicity_code    |
      | type widened        | sql/schema_changes/compatible/widened_date_key_type.sql | dim_subject | enrolled_date_key |
