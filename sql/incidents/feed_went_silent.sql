-- The visit feed stopped delivering five days before the check (an upstream job died quietly).
DELETE FROM {raw}.visit_events WHERE ingested_at >= timestamptz '2026-06-25 00:00+00'
