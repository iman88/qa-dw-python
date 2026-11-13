@all @monitoring @REQ_09
Feature: Production monitoring — the same checks, on a schedule, with alerts

  # `clinical-dq monitor` runs every rule, reconciliation and contract plus the monitoring checks in
  # sql/checks/monitoring/ (freshness, volume, drift) against the live warehouse. Every result is
  # stored in qa_monitor.check_results; any failure sends one alert to the configured webhook
  # (ALERT_WEBHOOK_URL: a Slack or Teams incoming webhook, or an on-call tool).
  # The data's "now" is 2026-06-30 23:59 UTC, the end of the synthetic trial data.

  Background:
    Given a webhook that records the alerts it receives

  # ─── Healthy warehouse ────────────────────────────────────────────────────

  Scenario: A run on a healthy warehouse stores every result and sends no alert
    Given the clinical warehouse is built
    When the monitor runs as of "2026-06-30 23:59+00:00"
    Then every check of the run passed
    And the run stored a result for every check, including these monitoring checks:
      | check                                                               |
      | sql/checks/monitoring/freshness.sql on raw.visit_events             |
      | sql/checks/monitoring/freshness.sql on raw.adverse_event_events     |
      | sql/checks/monitoring/period_volume.sql on raw.visit_events         |
      | sql/checks/monitoring/period_volume.sql on raw.adverse_event_events |
      | sql/checks/monitoring/grade_drift.sql on dwh                        |
    And no alert was sent

  # ─── Incidents ────────────────────────────────────────────────────────────

  Scenario Outline: <incident> is caught by <check> and alerted
    Given a fresh copy of every layer, in schemas prefixed "mut_"
    When the incident "sql/incidents/<incident>.sql" happens on the copy
    And the monitor runs on the copy as of "2026-06-30 23:59+00:00"
    Then the check "<check>" failed in the run
    And one alert was sent, naming "<check>"

    Examples:
      | incident         | check                                                               |
      | feed_went_silent | sql/checks/monitoring/freshness.sql on raw.visit_events             |
      | lost_batches     | sql/checks/monitoring/period_volume.sql on raw.adverse_event_events |
      | grade_shift      | sql/checks/monitoring/grade_drift.sql on dwh                        |
