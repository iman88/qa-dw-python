@all @edge @REQ_02 @REQ_03 @REQ_07
Feature: Change feed edge cases — hand-built events, exact expected history

  # Each scenario writes a handful of change events for one visit, runs the real history and
  # latest SQL (sql/build/history, sql/build/latest) and states exactly what must come out.
  # Every scenario runs twice: building everything in one go, and building the first events then
  # applying the rest incrementally (sql/incremental). Both must give the same answer.
  # Times are UTC unless an offset is written. "open" means the version is still valid.

  Background:
    Given an empty change feed for visits

  # ─── Delivery problems ────────────────────────────────────────────────────

  Scenario Outline: A change delivered twice is kept once (built <how>)
    Given these visit events arrive:
      | change | op | changed at       | ingested at      | visit | status    |
      | 1      | I  | 2025-03-01 10:00 | 2025-03-01 10:05 | V1    | SCHEDULED |
      | 2      | U  | 2025-03-08 09:00 | 2025-03-08 09:30 | V1    | COMPLETED |
      | 2      | U  | 2025-03-08 09:00 | 2025-03-09 02:00 | V1    | COMPLETED |
    When history and latest are built <how>
    Then history holds:
      | visit | change | status    | valid from       | valid to         | current |
      | V1    | 1      | SCHEDULED | 2025-03-01 10:00 | 2025-03-08 09:00 | no      |
      | V1    | 2      | COMPLETED | 2025-03-08 09:00 | open             | yes     |
    And latest holds:
      | visit | status    |
      | V1    | COMPLETED |

    Examples:
      | how                                   |
      | in one go                             |
      | incrementally from "2025-03-08 09:30" |

  # The older change arrives after the newer one: the change number decides, not arrival time.
  Scenario Outline: A late, older change does not overwrite a newer one (built <how>)
    Given these visit events arrive:
      | change | op | changed at       | ingested at      | visit | status    |
      | 1      | I  | 2025-03-01 10:00 | 2025-03-01 10:05 | V1    | SCHEDULED |
      | 3      | U  | 2025-03-09 08:00 | 2025-03-09 08:10 | V1    | MISSED    |
      | 2      | U  | 2025-03-08 09:00 | 2025-03-10 07:00 | V1    | COMPLETED |
    When history and latest are built <how>
    Then history holds:
      | visit | change | status    | valid from       | valid to         | current |
      | V1    | 1      | SCHEDULED | 2025-03-01 10:00 | 2025-03-08 09:00 | no      |
      | V1    | 2      | COMPLETED | 2025-03-08 09:00 | 2025-03-09 08:00 | no      |
      | V1    | 3      | MISSED    | 2025-03-09 08:00 | open             | yes     |
    And latest holds:
      | visit | status |
      | V1    | MISSED |

    Examples:
      | how                                   |
      | in one go                             |
      | incrementally from "2025-03-10 00:00" |

  # A record deleted in error stays deleted, even when an older update arrives after the delete.
  Scenario Outline: A delete followed by a late, older update keeps the record deleted (built <how>)
    Given these visit events arrive:
      | change | op | changed at       | ingested at      | visit | status    |
      | 1      | I  | 2025-03-01 10:00 | 2025-03-01 10:05 | V1    | SCHEDULED |
      | 3      | D  | 2025-03-05 12:00 | 2025-03-05 12:01 | V1    | SCHEDULED |
      | 2      | U  | 2025-03-04 09:00 | 2025-03-07 06:00 | V1    | COMPLETED |
    When history and latest are built <how>
    Then history holds:
      | visit | change | status    | valid from       | valid to         | current | deleted |
      | V1    | 1      | SCHEDULED | 2025-03-01 10:00 | 2025-03-04 09:00 | no      | no      |
      | V1    | 2      | COMPLETED | 2025-03-04 09:00 | 2025-03-05 12:00 | no      | no      |
      | V1    | 3      | SCHEDULED | 2025-03-05 12:00 | open             | yes     | yes     |
    And latest holds no visits

    Examples:
      | how                                   |
      | in one go                             |
      | incrementally from "2025-03-06 00:00" |

  # ─── Time ─────────────────────────────────────────────────────────────────

  # Two changes stamped with the same instant: the higher change number wins. The earlier version
  # is kept in history with an empty validity range, so no point-in-time lookup ever returns it.
  Scenario Outline: Two changes at the same instant (built <how>)
    Given these visit events arrive:
      | change | op | changed at       | ingested at      | visit | status    |
      | 1      | I  | 2025-03-01 10:00 | 2025-03-01 10:05 | V1    | SCHEDULED |
      | 2      | U  | 2025-03-08 09:00 | 2025-03-08 09:05 | V1    | MISSED    |
      | 3      | U  | 2025-03-08 09:00 | 2025-03-08 09:06 | V1    | COMPLETED |
    When history and latest are built <how>
    Then history holds:
      | visit | change | status    | valid from       | valid to         | current |
      | V1    | 1      | SCHEDULED | 2025-03-01 10:00 | 2025-03-08 09:00 | no      |
      | V1    | 2      | MISSED    | 2025-03-08 09:00 | 2025-03-08 09:00 | no      |
      | V1    | 3      | COMPLETED | 2025-03-08 09:00 | open             | yes     |
    And the version of V1 valid at "2025-03-08 09:00" is change 3
    And the history timeline rules find no offending rows

    Examples:
      | how                                   |
      | in one go                             |
      | incrementally from "2025-03-08 09:06" |

  # A change at exactly midnight belongs to the new day.
  Scenario: A change at midnight UTC starts the new day
    Given these visit events arrive:
      | change | op | changed at       | ingested at      | visit | status    |
      | 1      | I  | 2025-03-01 10:00 | 2025-03-01 10:05 | V1    | SCHEDULED |
      | 2      | U  | 2025-03-02 00:00 | 2025-03-02 00:01 | V1    | COMPLETED |
    When history and latest are built in one go
    Then the version of V1 valid at "2025-03-01 23:59" is change 1
    And the version of V1 valid at "2025-03-02 00:00" is change 2

  # Romania moves its clocks forward at 03:00 local time on 2026-03-29. Two changes two minutes
  # apart in real time look an hour apart on the wall clock. Stored in UTC, the gap stays two minutes.
  Scenario: Changes across the daylight-saving switch keep their real order and duration
    Given these visit events arrive:
      | change | op | changed at             | ingested at      | visit | status    |
      | 1      | I  | 2026-03-29 02:59+02:00 | 2026-03-29 01:00 | V1    | SCHEDULED |
      | 2      | U  | 2026-03-29 04:01+03:00 | 2026-03-29 01:05 | V1    | COMPLETED |
    When history and latest are built in one go
    Then history holds:
      | visit | change | status    | valid from       | valid to         | current |
      | V1    | 1      | SCHEDULED | 2026-03-29 00:59 | 2026-03-29 01:01 | no      |
      | V1    | 2      | COMPLETED | 2026-03-29 01:01 | open             | yes     |
