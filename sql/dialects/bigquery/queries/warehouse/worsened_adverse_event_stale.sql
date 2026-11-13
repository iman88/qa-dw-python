-- BigQuery: adverse events whose grade changed after first being reported, where the warehouse does not hold the latest grade (should be none).
WITH worsened AS (
    SELECT ae_id, ARRAY_AGG(grade ORDER BY change_seq DESC LIMIT 1)[OFFSET(0)] AS latest_grade
    FROM {hist}.adverse_event_history
    GROUP BY ae_id
    HAVING COUNT(DISTINCT grade) > 1 AND NOT LOGICAL_OR(is_deleted)
)
SELECT w.ae_id, w.latest_grade, d.grade AS warehouse_grade
FROM worsened w
LEFT JOIN {dwh}.v_adverse_event_detail d USING (ae_id)
WHERE d.grade IS NULL OR d.grade != w.latest_grade
