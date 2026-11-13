"""Registers the step definitions (Cucumber-style glue) for every feature.

tests/features/   what is tested, in Gherkin; names every SQL file it runs
tests/steps/      how each step runs (generic SQL steps first)
sql/              every query and script, one per file, in category folders
"""

pytest_plugins = [
    "tests.steps.sql_steps",
    "tests.steps.data_steps",
    "tests.steps.recon_steps",
    "tests.steps.schema_steps",
    "tests.steps.mutation_steps",
    "tests.steps.genai_steps",
    "tests.steps.edge_case_steps",
    "tests.steps.incremental_steps",
    "tests.steps.monitoring_steps",
    "tests.steps.compliance_steps",
    "tests.steps.genai_scale_steps",
]
