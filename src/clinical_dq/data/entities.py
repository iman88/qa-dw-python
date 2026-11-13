"""Entity metadata shared by the generator, the layer SQL and the checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    name: str
    key: str
    columns: tuple[str, ...]  # business columns, key first

    @property
    def events_table(self) -> str:
        return f"{self.name}_events"

    @property
    def history_table(self) -> str:
        return f"{self.name}_history"

    @property
    def non_key_columns(self) -> tuple[str, ...]:
        return tuple(c for c in self.columns if c != self.key)


STUDY = Entity(
    "study", "study_id", ("study_id", "study_code", "title", "phase", "therapeutic_area", "start_date")
)
SITE = Entity("site", "site_id", ("site_id", "study_id", "country_code", "investigator", "status"))
SUBJECT = Entity(
    "subject",
    "subject_id",
    ("subject_id", "site_id", "study_id", "arm", "sex", "birth_year", "enrolled_on", "withdrawn_on"),
)
VISIT = Entity("visit", "visit_id", ("visit_id", "subject_id", "visit_type", "visit_date", "status"))
ADVERSE_EVENT = Entity(
    "adverse_event",
    "ae_id",
    (
        "ae_id",
        "subject_id",
        "meddra_pt",
        "soc",
        "grade",
        "serious",
        "related",
        "onset_date",
        "resolved_date",
        "outcome",
    ),
)

ENTITIES: tuple[Entity, ...] = (STUDY, SITE, SUBJECT, VISIT, ADVERSE_EVENT)
BY_NAME = {e.name: e for e in ENTITIES}
