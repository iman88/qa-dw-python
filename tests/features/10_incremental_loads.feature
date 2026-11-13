@all @incremental @REQ_07
Feature: Incremental loads — the same result as a full rebuild

  # Production pipelines do not rebuild everything: they MERGE each new batch in. A second
  # warehouse (schemas prefixed inc_) is built from the events that arrived before 2026-01-01;
  # everything that arrived later is then applied as one incremental batch with the scripts in
  # sql/incremental/. Every layer must end up identical to the full build, compared by business
  # key (surrogate keys may differ between builds and are not compared).

  Background:
    Given the clinical warehouse is built
    And a second warehouse built incrementally from "2026-01-01", in schemas prefixed "inc_"

  # ─── The batch ────────────────────────────────────────────────────────────

  # A batch worth testing: changes to records loaded before it, deletes and redeliveries.
  Scenario: The incremental batch changes earlier records, deletes some and redelivers others
    When I run the query "sql/queries/incremental/batch_profile.sql" on the incremental build with:
      | batch_start            |
      | 2026-01-01 00:00+00:00 |
    Then the result contains:
      | events | deletes | redelivered | changes_to_earlier_records |
      | 151    | 5       | 7           | 5                          |

  # ─── Same result as a full build ──────────────────────────────────────────

  Scenario Outline: <layer>.<table> is the same in both builds
    When I compare "<query>" on layer "<layer>" of both builds for entity "<entity>" by key "<key>"
    Then both builds match

    Examples: Latest state
      | layer  | table         | entity        | key        | query                                     |
      | latest | study         | study         | study_id   | sql/checks/build_compare/latest_table.sql |
      | latest | site          | site          | site_id    | sql/checks/build_compare/latest_table.sql |
      | latest | subject       | subject       | subject_id | sql/checks/build_compare/latest_table.sql |
      | latest | visit         | visit         | visit_id   | sql/checks/build_compare/latest_table.sql |
      | latest | adverse_event | adverse_event | ae_id      | sql/checks/build_compare/latest_table.sql |

    Examples: Full history
      | layer | table                 | entity        | key        | query                                      |
      | hist  | study_history         | study         | change_seq | sql/checks/build_compare/history_table.sql |
      | hist  | site_history          | site          | change_seq | sql/checks/build_compare/history_table.sql |
      | hist  | subject_history       | subject       | change_seq | sql/checks/build_compare/history_table.sql |
      | hist  | visit_history         | visit         | change_seq | sql/checks/build_compare/history_table.sql |
      | hist  | adverse_event_history | adverse_event | change_seq | sql/checks/build_compare/history_table.sql |

  Scenario Outline: The star schema's <what> is the same in both builds
    When I compare "<query>" on layer "dwh" of both builds by key "<key>"
    Then both builds match

    Examples:
      | what                | key                 | query                                            |
      | site versions       | site_id, valid_from | sql/checks/build_compare/dim_site_versions.sql   |
      | subjects            | subject_id          | sql/checks/build_compare/dim_subject_rows.sql    |
      | adverse event facts | ae_id               | sql/checks/build_compare/adverse_event_facts.sql |
      | visit facts         | visit_id            | sql/checks/build_compare/visit_facts.sql         |

  # ─── Re-runs ──────────────────────────────────────────────────────────────

  # A scheduler retries a failed job, or someone re-runs yesterday's load: nothing may change.
  Scenario: Applying the same batch again changes nothing
    When I record a checksum of every table in the incremental build
    And the same batch from "2026-01-01" is applied again
    Then every table of the incremental build has the same checksum as before
