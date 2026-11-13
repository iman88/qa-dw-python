-- Star schema ({dwh}). Like most warehouses it declares no foreign keys between facts and
-- dimensions, which is exactly why referential integrity is tested instead of assumed.

SET TIME ZONE 'UTC';
DROP SCHEMA IF EXISTS {dwh} CASCADE;
CREATE SCHEMA {dwh};
