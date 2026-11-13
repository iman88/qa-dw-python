-- Deduplicated latest.{entity} equals the current state of {entity} in the source system
-- Source side of the comparison.
SELECT {columns}
FROM {src}.{entity}
