-- Adverse events whose grade changed after first being reported, where the warehouse does not
-- hold the latest grade (should be none).
WITH worsened AS (
    SELECT ae_id, (array_agg(grade ORDER BY change_seq DESC))[1] AS latest_grade
    FROM {hist}.adverse_event_history
    GROUP BY ae_id
    HAVING count(DISTINCT grade) > 1 AND NOT bool_or(is_deleted)
)
SELECT w.ae_id, w.latest_grade, d.grade AS warehouse_grade
FROM worsened w
LEFT JOIN {dwh}.v_adverse_event_detail d USING (ae_id)
WHERE d.grade IS DISTINCT FROM w.latest_grade
