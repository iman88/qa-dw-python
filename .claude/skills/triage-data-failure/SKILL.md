---
name: triage-data-failure
description: Investigate a failing reconciliation, check, contract or scenario down to the layer and row that broke, and write it up for a data engineer. Use when a data test is red.
---

# Triage a data failure

1. **Find the layer.** Open `reports/data-quality-report.html`. Every entry is named by its file:
   `sql/checks/recon/<category>/<check>` says which two layers it compares; `sql/checks/rules/...` on
   `<layer>.<table>` says which layer it guards; `sql/contracts/<layer>.json` is a schema difference.
   Data flows src/raw -> hist and latest -> dwh; the earliest failing layer is usually the cause.
2. **Read the sample.** Reconciliations list missing keys, extra keys, duplicate keys and column
   mismatches (key, column, source value, target value). Checks show the offending rows and the exact
   SQL. Contracts list each difference (missing column, type changed...).
3. **Reproduce in SQL** with `docker exec -it clinical-dq-postgres psql -U qa -d clinical`, following
   one key through the layers:
   ```sql
   SELECT change_seq, op, changed_at, ingested_at, grade FROM raw.adverse_event_events
    WHERE ae_id = 'AE-00042' ORDER BY change_seq, ingested_at;
   SELECT change_seq, op, valid_from, valid_to, is_current, is_deleted, grade
     FROM hist.adverse_event_history WHERE ae_id = 'AE-00042' ORDER BY change_seq;
   SELECT * FROM latest.adverse_event WHERE ae_id = 'AE-00042';
   SELECT * FROM dwh.v_adverse_event_detail WHERE ae_id = 'AE-00042';
   ```
   `tableoid::regclass` in a SELECT shows which partition a row sits in.
4. **Classify.** Pipeline bug (fix the script in `sql/build/<category>/`), wrong expectation (fix the
   check or the feature, and say why), or test data gap (the generator does not produce the case).
5. **Write it up** in plain words: what failed, one key traced through each layer, the likely cause,
   and the query that shows it. Never quietly loosen a check to get green.
