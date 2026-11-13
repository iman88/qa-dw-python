@all @warehouse @REQ_01
Feature: Safety figures — the warehouse answers the same as the source system

  # The questions a medical monitor asks, asked twice: once of the clinical source system,
  # once of the warehouse. The answers must be identical.

  Background:
    Given the clinical warehouse is built

  # ─── Per study ────────────────────────────────────────────────────────────

  Scenario Outline: <study>: subjects, adverse events, serious events and subjects with events
    When I run the query "sql/queries/warehouse/study_safety_source.sql" with:
      | study_id |
      | <study>  |
    Then the result is the same as the query "sql/queries/warehouse/study_safety_dwh.sql"

    Examples:
      | study     |
      | STUDY-001 |
      | STUDY-002 |
      | STUDY-003 |

  Scenario Outline: <study>: adverse events per toxicity grade
    When I run the query "sql/queries/warehouse/study_grades_source.sql" with:
      | study_id |
      | <study>  |
    Then the result is the same as the query "sql/queries/warehouse/study_grades_dwh.sql"

    Examples:
      | study     |
      | STUDY-001 |
      | STUDY-002 |
      | STUDY-003 |

  Scenario: Adverse events per study, with exact figures for the seeded data
    Given the data was generated with seed 42 and 40 subjects per study
    When I run the query:
      """
      SELECT study_id, count(*) AS adverse_events
      FROM dwh.v_adverse_event_detail
      GROUP BY study_id
      """
    Then the result contains:
      | study_id  | adverse_events |
      | STUDY-001 | 71             |
      | STUDY-002 | 71             |
      | STUDY-003 | 63             |

  # ─── Corrections in the source ────────────────────────────────────────────

  Scenario: An adverse event deleted in the source system is not reported
    When I run the query "sql/queries/warehouse/deleted_adverse_event_still_reported.sql"
    Then the result is empty
