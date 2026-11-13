@all @recon @REQ_01
Feature: Reconciliation — every layer against the one it is built from

  # Each reconciliation is a folder with source.sql and target.sql. Both queries run, rows are
  # matched by the business key and compared column by column. A failure lists missing keys,
  # extra keys, duplicate keys and every value that differs.
  # Folders under latest/ and history/ are templates that run once per entity.

  Background:
    Given the clinical warehouse is built

  # ─── Deduplication: latest layer vs source system ─────────────────────────

  Scenario Outline: latest.<entity> equals the source system
    When I reconcile "sql/checks/recon/latest/latest_vs_source" for entity "<entity>" by key "<key>"
    Then source and target match

    Examples:
      | entity        | key        |
      | study         | study_id   |
      | site          | site_id    |
      | subject       | subject_id |
      | visit         | visit_id   |
      | adverse_event | ae_id      |

  # ─── Full history: every change exactly once ──────────────────────────────

  Scenario Outline: Every <entity> change in raw is kept exactly once in history
    When I reconcile "sql/checks/recon/history/hist_vs_raw_changes" for entity "<entity>" by key "change_seq"
    Then source and target match

    Examples:
      | entity        |
      | study         |
      | site          |
      | subject       |
      | visit         |
      | adverse_event |

  # Two independent derivations of current state (history view vs latest table) must agree.
  Scenario Outline: The current-state view over history equals latest.<entity>
    When I reconcile "sql/checks/recon/history/hist_current_vs_latest" for entity "<entity>" by key "<key>"
    Then source and target match

    Examples:
      | entity        | key        |
      | study         | study_id   |
      | site          | site_id    |
      | subject       | subject_id |
      | visit         | visit_id   |
      | adverse_event | ae_id      |

  # ─── Star schema and views vs source system ───────────────────────────────

  Scenario Outline: <check> matches the source system
    When I reconcile "<folder>" by key "<key>"
    Then source and target match

    Examples: Dimensions and facts
      | check              | folder                                              | key        |
      | dim_subject        | sql/checks/recon/dimensions/dim_subject_vs_source   | subject_id |
      | fact_adverse_event | sql/checks/recon/facts/fact_adverse_event_vs_source | ae_id      |
      | fact_visit         | sql/checks/recon/facts/fact_visit_vs_source         | visit_id   |

    Examples: Aggregates
      | check                      | folder                                             | key                  |
      | safety totals per study    | sql/checks/recon/aggregates/safety_totals_by_study | study_id             |
      | completed visits per month | sql/checks/recon/aggregates/visits_by_study_month  | study_id, year_month |

    Examples: Reporting views
      | check                   | folder                                                   | key                  |
      | v_adverse_event_detail  | sql/checks/recon/views/v_adverse_event_detail_vs_source  | ae_id                |
      | v_safety_by_study_month | sql/checks/recon/views/v_safety_by_study_month_vs_source | study_id, year_month |
      | v_site_current          | sql/checks/recon/views/v_site_current_vs_source          | site_id              |

  # ─── Coverage ─────────────────────────────────────────────────────────────

  Scenario: No reconciliation folder is left without a scenario
    Then every reconciliation in "sql/checks/recon" is covered by "03_reconciliation.feature"
