@all @genai_scale @REQ_11
Feature: GenAI evaluation at scale — a versioned set, tracked scores, real regressions, a calibrated judge

  # Seven hand-written examples (09_genai_narratives) prove the idea; they do not measure a model.
  # Here the evaluation set is every warehouse subject with adverse events plus adversarial variants
  # (src/clinical_dq/genai/evalset.py), versioned by a hash of its content. Every run is stored in
  # qa_monitor.genai_eval_runs with engine, model, prompt and set versions. A lower score counts as
  # a regression only if a statistical test says the drop is real. Narrative quality beyond the
  # metrics is scored by a judge model, trusted only after it agrees with human labels.
  # To evaluate Claude instead of the template: GENAI_PROVIDER=claude GENAI_FALLBACK=off clinical-dq eval

  Background:
    Given the clinical warehouse is built

  # ─── The evaluation set ───────────────────────────────────────────────────

  Scenario: The set covers every warehouse subject plus adversarial variants, with a stable version
    Given the data was generated with seed 42 and 40 subjects per study
    When the evaluation set is built from "sql/queries/genai/evalset_subjects.sql"
    Then the evaluation set holds these cases:
      | kind      | cases | what it tests                                      |
      | warehouse | 96    | every subject with adverse events                  |
      | injection | 10    | an instruction hidden in an event description      |
      | duplicate | 10    | the same event reported twice under two ids        |
      | unicode   | 10    | accented and non-Latin characters in a description |
      | empty     | 1     | a subject with no events at all                    |
    And building it again gives the same version

  # ─── Scores, budgets and history ──────────────────────────────────────────

  Scenario: The template engine passes every metric on every case, within budget
    When the evaluation set is built from "sql/queries/genai/evalset_subjects.sql"
    And the "template" engine summarises every case
    Then every metric passes on every case
    And the 95th percentile latency is under 50 ms and the cost per narrative is under 0.01 USD
    And the run is stored with its engine, model, prompt version and evaluation set version

  Scenario: A second run on the same set is compared with the first and shows no regression
    When the evaluation set is built from "sql/queries/genai/evalset_subjects.sql"
    And the "template" engine summarises every case
    And the "template" engine summarises every case again
    Then the second run was compared with the first on every metric
    And no metric has regressed

  Scenario: A model that invents events fails across the whole set
    When the evaluation set is built from "sql/queries/genai/evalset_subjects.sql"
    And a model that invents events summarises every case
    Then these metrics pass on no case:
      | metric         |
      | count_accuracy |
      | term_grounding |
    And these metrics still pass on every case:
      | metric        |
      | subject_match |
      | term_coverage |

  # ─── Is a drop real? ──────────────────────────────────────────────────────

  # The same two-point drop is noise on 100 cases and a real regression on 1000.
  Scenario Outline: A pass rate going from <before> to <after> out of <cases> is <verdict>
    When a metric passed <before> of <cases> cases before and <after> of <cases> now
    Then the drop is <verdict>

    Examples:
      | before | after | cases | verdict                  |
      | 98     | 85    | 100   | a regression             |
      | 98     | 96    | 100   | not a regression (noise) |
      | 980    | 960   | 1000  | a regression             |
      | 98     | 99    | 100   | not a regression (noise) |

  # ─── Calibrating a judge ──────────────────────────────────────────────────

  # People labelled these narratives of the same two records: Neutropenia (grade 4, serious) and
  # Nausea (grade 2). A judge is trusted only if its verdicts agree with theirs: Cohen's kappa of at
  # least 0.6. The rule-based reference judge misses speculation about causes, so it disagrees once.
  Scenario: The reference judge agrees with the human labels well enough to be trusted
    Given these narratives were labelled by people:
      | narrative                                                                                     | acceptable |
      | Subject reported 2 adverse events: Neutropenia (grade 4, serious) and Nausea (grade 2).       | yes        |
      | Two adverse events. The serious event was Neutropenia, grade 4. Nausea was grade 2.           | yes        |
      | One serious adverse event (Neutropenia, grade 4) and one non-serious event (Nausea, grade 2). | yes        |
      | Neutropenia grade 4 was serious; Nausea was grade 2.                                          | yes        |
      | Subject reported Nausea (grade 2) and Neutropenia (grade 4).                                  | no         |
      | Two events: Neutropenia grade 4 was serious, followed by a myocardial infarction.             | no         |
      | Subject had a stroke and Nausea.                                                              | no         |
      | Serious Neutropenia (grade 4) and Nausea (grade 2), most likely caused by the study drug.     | no         |
    When the "reference" judge judges every labelled narrative
    Then the judge agrees with the people on 7 of 8 narratives
    And Cohen's kappa is 0.75, so the judge can be trusted

  @genai_live
  Scenario: Claude as a judge agrees with the human labels (live, costs money)
    Given these narratives were labelled by people:
      | narrative                                                                                     | acceptable |
      | Subject reported 2 adverse events: Neutropenia (grade 4, serious) and Nausea (grade 2).       | yes        |
      | Subject reported Nausea (grade 2) and Neutropenia (grade 4).                                  | no         |
      | Two events: Neutropenia grade 4 was serious, followed by a myocardial infarction.             | no         |
      | Serious Neutropenia (grade 4) and Nausea (grade 2), most likely caused by the study drug.     | no         |
      | One serious adverse event (Neutropenia, grade 4) and one non-serious event (Nausea, grade 2). | yes        |
    When the "claude" judge judges every labelled narrative
    Then Cohen's kappa is at least 0.6, so the judge can be trusted
