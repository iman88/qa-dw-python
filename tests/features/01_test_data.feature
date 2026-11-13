@all @data @REQ_12
Feature: Test data — what the pipeline has to cope with

  # The data is synthetic and seeded, so every run produces exactly the same rows.
  # It is built to contain the problems a real CDC pipeline meets: changes delivered twice,
  # events that arrive late, records updated several times and records deleted in error.
  # Change DATA_SEED or SUBJECTS_PER_STUDY and these exact figures no longer apply (skipped).

  Background:
    Given the clinical warehouse is built
    And the data was generated with seed 42 and 40 subjects per study

  # ─── Source system ────────────────────────────────────────────────────────

  Scenario: The source system holds 3 studies, 12 sites, 120 subjects, 701 visits and 205 adverse events
    Then these queries return these values:
      | what           | query                                  | value |
      | studies        | SELECT count(*) FROM src.study         | 3     |
      | sites          | SELECT count(*) FROM src.site          | 12    |
      | subjects       | SELECT count(*) FROM src.subject       | 120   |
      | visits         | SELECT count(*) FROM src.visit         | 701   |
      | adverse events | SELECT count(*) FROM src.adverse_event | 205   |

  # ─── The change feed ──────────────────────────────────────────────────────

  # 404 deliveries carry 381 real changes: 23 were delivered twice by a retried batch.
  Scenario: The adverse event feed contains duplicates, deletes and repeated changes
    Then these queries return these values:
      | what                     | query                                                                                                                   | value |
      | deliveries               | SELECT count(*) FROM raw.adverse_event_events                                                                           | 404   |
      | distinct changes         | SELECT count(DISTINCT change_seq) FROM raw.adverse_event_events                                                         | 381   |
      | duplicate deliveries     | SELECT count(*) - count(DISTINCT change_seq) FROM raw.adverse_event_events                                              | 23    |
      | deleted adverse events   | SELECT count(DISTINCT ae_id) FROM raw.adverse_event_events WHERE op = 'D'                                               | 7     |
      | arrived in a later month | SELECT count(*) FROM raw.adverse_event_events WHERE date_trunc('month', changed_at) <> date_trunc('month', ingested_at) | 1     |

  # ─── Every layer ──────────────────────────────────────────────────────────

  # raw keeps every delivery, hist every real change, latest and dwh one row per live record.
  Scenario: Adverse events through the layers: 404 delivered, 381 changes, 205 current
    Then these queries return these values:
      | what                           | query                                                                                                    | value |
      | raw deliveries                 | SELECT count(*) FROM raw.adverse_event_events                                                            | 404   |
      | hist versions                  | SELECT count(*) FROM hist.adverse_event_history                                                          | 381   |
      | hist tombstones                | SELECT count(*) FROM hist.adverse_event_history WHERE is_deleted                                         | 7     |
      | latest current state           | SELECT count(*) FROM latest.adverse_event                                                                | 205   |
      | dwh fact rows                  | SELECT count(*) FROM dwh.fact_adverse_event                                                              | 205   |
      | dwh site versions              | SELECT count(*) FROM dwh.dim_site                                                                        | 33    |
      | facts on an older site version | SELECT count(*) FROM dwh.fact_adverse_event f JOIN dwh.dim_site s USING (site_sk) WHERE NOT s.is_current | 73    |
