"""Synthetic clinical trial data delivered as a CDC change feed.

What gets generated (seeded, so every run is identical):

* the operational source system (``src``): the current state of studies, sites,
  subjects, visits and adverse events, as the source application holds it today;
* the change feed that produced that state (``raw``): one event per insert, update
  or delete, with a global ``change_seq`` (think log sequence number), the source
  commit time and the time the event landed on the platform.

The feed behaves like a real at-least-once pipeline: some events are delivered twice,
some arrive late (sometimes in the next month), records change several times and a few
adverse events are deleted as data-entry errors. The hist and latest layers have to
cope with all of that.

All data is synthetic. Event terms are common symptom names, not patient data.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from faker import Faker

from clinical_dq.data.entities import BY_NAME, ENTITIES, STUDY

AS_OF = datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)  # data cut-off: "today" for the source system

STUDIES = [
    (
        "STUDY-001",
        "ONC-221",
        "Phase II dose-finding study in solid tumours",
        "II",
        "Oncology",
        date(2025, 1, 15),
    ),
    (
        "STUDY-002",
        "IMM-310",
        "Phase III study in moderate plaque psoriasis",
        "III",
        "Immunology",
        date(2025, 3, 1),
    ),
    (
        "STUDY-003",
        "NEU-105",
        "Phase I safety study in healthy volunteers",
        "I",
        "Neurology",
        date(2025, 5, 10),
    ),
]
COUNTRIES = ["RO", "DE", "PL", "ES", "IT", "FR", "NL", "BE"]
ARMS = ["PLACEBO", "DOSE_LOW", "DOSE_HIGH"]
VISIT_PLAN = [
    ("SCREENING", 0),
    ("BASELINE", 7),
    ("WEEK4", 35),
    ("WEEK8", 63),
    ("WEEK12", 91),
    ("WEEK24", 175),
]
TERMS = {
    "Headache": "Nervous system disorders",
    "Dizziness": "Nervous system disorders",
    "Nausea": "Gastrointestinal disorders",
    "Diarrhoea": "Gastrointestinal disorders",
    "Fatigue": "General disorders and administration site conditions",
    "Pyrexia": "General disorders and administration site conditions",
    "Rash": "Skin and subcutaneous tissue disorders",
    "Pruritus": "Skin and subcutaneous tissue disorders",
    "Neutropenia": "Blood and lymphatic system disorders",
    "Hypertension": "Vascular disorders",
    "Arthralgia": "Musculoskeletal and connective tissue disorders",
    "Pneumonia": "Infections and infestations",
    "Alanine aminotransferase increased": "Investigations",
}
GRADES = [1, 2, 3, 4, 5]
GRADE_WEIGHTS = [40, 30, 18, 8, 4]


@dataclass
class ChangeEvent:
    entity: str
    op: str  # I, U, D
    changed_at: datetime
    row: dict[str, Any]
    change_seq: int = 0


@dataclass
class GeneratedData:
    source: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # entity -> current rows
    feed: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # entity -> delivered events
    stats: dict[str, int] = field(default_factory=dict)


class _Builder:
    def __init__(self, seed: int, subjects_per_study: int) -> None:
        self.rnd = random.Random(seed)
        self.fake = Faker("en_GB")
        self.fake.seed_instance(seed)
        self.subjects_per_study = subjects_per_study
        self.events: list[ChangeEvent] = []
        self.ae_counter = 0

    # -- helpers -----------------------------------------------------------------
    def at(self, day: date) -> datetime:
        clock = time(self.rnd.randint(6, 20), self.rnd.randint(0, 59), self.rnd.randint(0, 59))
        return datetime.combine(day, clock, tzinfo=UTC)

    def emit(self, entity: str, op: str, changed_at: datetime, row: dict[str, Any]) -> None:
        if changed_at <= AS_OF:
            self.events.append(ChangeEvent(entity, op, changed_at, dict(row)))

    # -- entities ----------------------------------------------------------------
    def build(self) -> None:
        subject_no = 0
        for values in STUDIES:
            study: dict[str, Any] = dict(zip(STUDY.columns, values, strict=True))
            start: date = study["start_date"]
            self.emit("study", "I", self.at(start - timedelta(days=30)), study)
            sites = []
            for n in range(1, 5):
                site = {
                    "site_id": f"{study['study_id'][-3:]}-S{n:02d}",
                    "study_id": study["study_id"],
                    "country_code": self.rnd.choice(COUNTRIES),
                    "investigator": f"Dr {self.fake.last_name()}",
                    "status": "ACTIVE",
                }
                self.emit("site", "I", self.at(start - timedelta(days=1)), site)
                self._site_changes(site, start)
                sites.append(site)
            for _ in range(self.subjects_per_study):
                subject_no += 1
                self._subject(f"SUBJ-{subject_no:04d}", self.rnd.choice(sites), start)

    def _site_changes(self, site: dict[str, Any], start: date) -> None:
        day = start
        for _ in range(self.rnd.choice([1, 1, 2, 2, 3])):
            day = day + timedelta(days=self.rnd.randint(45, 160))
            site = dict(site)
            if self.rnd.random() < 0.6:
                site["investigator"] = f"Dr {self.fake.last_name()}"
            else:
                site["status"] = self.rnd.choice(["SUSPENDED", "ACTIVE", "CLOSED"])
            self.emit("site", "U", self.at(day), site)

    def _subject(self, subject_id: str, site: dict[str, Any], start: date) -> None:
        enrolled = start + timedelta(days=self.rnd.randint(3, 300))
        subject = {
            "subject_id": subject_id,
            "site_id": site["site_id"],
            "study_id": site["study_id"],
            "arm": self.rnd.choice(ARMS),
            "sex": self.rnd.choice("FM"),
            "birth_year": self.rnd.randint(1945, 2005),
            "enrolled_on": enrolled,
            "withdrawn_on": None,
        }
        self.emit("subject", "I", self.at(enrolled), subject)
        last_day = date(9999, 1, 1)
        if self.rnd.random() < 0.08:
            last_day = enrolled + timedelta(days=self.rnd.randint(20, 150))
            self.emit("subject", "U", self.at(last_day), {**subject, "withdrawn_on": last_day})
        self._visits(subject_id, enrolled, last_day)
        n_events = self.rnd.choices([0, 1, 2, 3, 4, 5], weights=[20, 25, 25, 15, 10, 5])[0]
        for _ in range(n_events):
            self._adverse_event(subject_id, enrolled, last_day)

    def _visits(self, subject_id: str, enrolled: date, last_day: date) -> None:
        for n, (visit_type, offset) in enumerate(VISIT_PLAN, start=1):
            visit_day = enrolled + timedelta(days=offset)
            if visit_day > last_day:
                break
            visit = {
                "visit_id": f"{subject_id}-V{n}",
                "subject_id": subject_id,
                "visit_type": visit_type,
                "visit_date": visit_day,
                "status": "SCHEDULED",
            }
            self.emit("visit", "I", self.at(enrolled), visit)
            status = "COMPLETED" if self.rnd.random() < 0.9 else "MISSED"
            done_at = self.at(visit_day + timedelta(days=self.rnd.randint(0, 2)))
            self.emit("visit", "U", done_at, {**visit, "status": status})

    def _adverse_event(self, subject_id: str, enrolled: date, last_day: date) -> None:
        window_end = min(enrolled + timedelta(days=200), last_day, AS_OF.date() - timedelta(days=1))
        if window_end <= enrolled + timedelta(days=1):
            return
        onset = enrolled + timedelta(days=self.rnd.randint(1, (window_end - enrolled).days))
        term = self.rnd.choice(list(TERMS))
        grade = self.rnd.choices(GRADES, weights=GRADE_WEIGHTS)[0]
        self.ae_counter += 1
        ae = {
            "ae_id": f"AE-{self.ae_counter:05d}",
            "subject_id": subject_id,
            "meddra_pt": term,
            "soc": TERMS[term],
            "grade": grade,
            "serious": grade >= 4 or (grade == 3 and self.rnd.random() < 0.5) or self.rnd.random() < 0.03,
            "related": self.rnd.random() < 0.4,
            "onset_date": onset,
            "resolved_date": None,
            "outcome": "FATAL" if grade == 5 else "NOT_RECOVERED",
        }
        when = self.at(onset + timedelta(days=self.rnd.randint(0, 3)))
        self.emit("adverse_event", "I", when, ae)
        if self.rnd.random() < 0.03:  # entered in error, deleted a few days later
            self.emit("adverse_event", "D", when + timedelta(days=self.rnd.randint(1, 5)), ae)
            return
        if grade < 5 and self.rnd.random() < 0.15:  # worsened
            when = when + timedelta(days=self.rnd.randint(2, 10))
            grade += 1
            ae = {
                **ae,
                "grade": grade,
                "serious": ae["serious"] or grade >= 4,
                "outcome": "FATAL" if grade == 5 else ae["outcome"],
            }
            self.emit("adverse_event", "U", when, ae)
        if grade < 5 and self.rnd.random() < 0.65:  # resolved
            resolved = onset + timedelta(days=self.rnd.randint(3, 40))
            outcome = "RECOVERED" if self.rnd.random() < 0.85 else "RECOVERED_WITH_SEQUELAE"
            ae = {**ae, "resolved_date": resolved, "outcome": outcome}
            self.emit("adverse_event", "U", max(when, self.at(resolved)) + timedelta(hours=1), ae)

    # -- delivery ----------------------------------------------------------------
    def deliver(self) -> GeneratedData:
        self.events.sort(key=lambda e: (e.changed_at, e.entity, str(e.row[BY_NAME[e.entity].key])))
        for seq, event in enumerate(self.events, start=1):
            event.change_seq = seq

        state: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        out = GeneratedData(source={e.name: [] for e in ENTITIES}, feed={e.name: [] for e in ENTITIES})
        duplicates = late = 0
        for event in self.events:
            delay = timedelta(minutes=self.rnd.randint(5, 240))
            if self.rnd.random() < 0.05:  # late arrival, one to three days
                delay = timedelta(hours=self.rnd.randint(24, 72))
                late += 1
            deliveries = [event.changed_at + delay]
            if self.rnd.random() < 0.06:  # at-least-once: a retried batch delivers it again
                deliveries.append(deliveries[0] + timedelta(hours=self.rnd.randint(1, 30)))
                duplicates += 1
            for ingested_at in deliveries:
                out.feed[event.entity].append(
                    {
                        **event.row,
                        "change_seq": event.change_seq,
                        "op": event.op,
                        "changed_at": event.changed_at,
                        "ingested_at": ingested_at,
                        "batch_id": "B" + ingested_at.strftime("%Y%m%d%H"),
                    }
                )
            key = event.row[BY_NAME[event.entity].key]
            if event.op == "D":
                state[event.entity].pop(key, None)
            else:
                state[event.entity][key] = event.row

        for entity in ENTITIES:
            out.source[entity.name] = sorted(state[entity.name].values(), key=lambda r: r[entity.key])
        out.stats = {
            "change_events": len(self.events),
            "delivered_events": sum(len(v) for v in out.feed.values()),
            "duplicate_deliveries": duplicates,
            "late_arrivals": late,
            "deletes": sum(1 for e in self.events if e.op == "D"),
            **{f"source_{k}_rows": len(v) for k, v in out.source.items()},
        }
        return out


def generate(seed: int = 42, subjects_per_study: int = 40) -> GeneratedData:
    builder = _Builder(seed, subjects_per_study)
    builder.build()
    return builder.deliver()
