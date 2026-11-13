"""Binds every feature file in tests/features/ to the step definitions in tests/steps/."""

from pytest_bdd import scenarios

scenarios("01_test_data.feature")
scenarios("02_schema_contracts.feature")
scenarios("03_reconciliation.feature")
scenarios("04_history_and_latest.feature")
scenarios("05_star_schema.feature")
scenarios("06_partitions.feature")
scenarios("07_safety_figures.feature")
scenarios("08_defect_injection.feature")
scenarios("09_genai_narratives.feature")
scenarios("10_incremental_loads.feature")
scenarios("11_change_feed_edge_cases.feature")
scenarios("12_pushdown_reconciliation.feature")
scenarios("13_production_monitoring.feature")
scenarios("14_compliance.feature")
scenarios("15_genai_at_scale.feature")
