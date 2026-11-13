-- Every row read straight from one partition table.
SELECT ae_id, grade, is_serious FROM {dwh}.{partition_name}
