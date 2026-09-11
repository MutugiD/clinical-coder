# Clinical coder product requirements

## Product objective

Convert a clinical consultation into a structured, reviewable note whose statements
can be traced to the conversation. Link supported elements to a supplied coding
register without model inference and extract cited rules from a supplied guideline.
Preserve uncertainty, conflicts, and missing information for clinician review.

The system supports documentation and lookup. It must not invent diagnoses,
autonomously prescribe treatment, or replace clinical judgment.

## Users and workflow

Clinicians review notes, inspect evidence, and resolve conflicting reports.
Clinical operations reviewers inspect code matches, alternatives, and catalogue
gaps. Integration engineers invoke stable contracts and diagnose failed stages.

The primary workflow is transcript → extract → validate → resolve → knowledge.
Stages are independently invocable. Pipeline execution coordinates their outcomes.
Inputs are supplied at invocation rather than embedded in application code.

## Input requirements

| Input | Structure |
| --- | --- |
| Consultation | UTF-8 `[mm:ss] SPEAKER: text`; DOCTOR, PATIENT, COMPANION, NURSE |
| Register | CSV columns kind, code, name, synonyms; semicolon-separated aliases |
| Guideline | Source text with citation metadata and recommendations |

Conversations may mix English, Swahili, and Sheng. Malformed inputs fail explicitly.
The register and guideline are the only sources of codes and guideline knowledge.

## Functional requirements

### F1 Structured note

Return exactly: chief_complaint, history_of_presenting_illness, review_of_systems,
past_medical_history, past_surgical_history, medication_history, allergies,
family_history, social_history, vitals, examination, assessment, plan.

Each section is a nonempty list or `NOT_STATED`. Elements include value,
span {ref,text}, and confidence. Assessment also requires certainty. Preserve mixed
language when translation introduces uncertainty. Do not infer missing information.

### F2 Evidence and context

Primary spans quote source words verbatim at the referenced timestamp. Optional
context_span records a conversational dependency such as the preceding question.
Its citation must exist, but it cannot supply facts or numbers missing from the
primary span. Questions are not positive findings.

### F3 Attribution and certainty

Distinguish patient reports, clinician findings, nurse observations, and companion
accounts. Retained companion material needs explicit attribution. Retained rejected
thinking-aloud needs `kind: considered_and_rejected`; neither becomes a patient fact.

Assessment certainty is `confirmed`, `probable`, or `differential`, supported by the
clinician's wording. A patient's suspicion is not a confirmed diagnosis. Family
history must remain separate from patient assessment.

### F4 Negatives and conflicts

Review of systems contains explicit negatives only for symptoms the doctor asked
about. Conditional safety-net advice is not a current symptom.

Without an explicit correction, preserve conflicting statements with separate spans
and shared conflict {id,reason} metadata. Leave the affected concept uncoded for
clinician review; do not quietly choose one statement.

### F5 Independent validation

Validate schema, quotations, timestamps, attribution, section placement, certainty,
and numeric fidelity without a model. Reject changed numbers even when substituted
digits occur elsewhere in the same source line. Preserve decimal meaning, signs,
quantities, units, durations, and their associations.

Support justified number-word conversion in both directions and permitted unit or
format normalization. Reject code-pattern strings anywhere in note.json and reject
family-history reassignment into assessment. Failed validation returns nonzero with
reasons on stderr.

### F6 Deterministic coding

Match register names and synonyms, including brands and Swahili aliases. Restrict
candidates by context and kind. Surgical history resolves to procedures rather than
similarly named active diagnoses. No model, embedding service, or network request
may participate in resolution.

Preserve sections and evidence. Add code, code_system, confidence, alternatives,
and status. Unresolved and ambiguous elements have null code. Explain matching
evidence, order alternatives deterministically, and never force a near match.
Probable/differential diagnoses may resolve while retaining certainty. Conflicts
and considered-and-rejected elements remain uncoded.

### F7 Guideline knowledge

Produce drug_class_rule rows with exposure/condition, action, severity, and citation;
red_flag rows for alarm features; and test_constraint rows for prerequisites.
Every row includes source, section, page, and a verbatim supporting quotation.

Return not_in_corpus questions for useful information absent from the source. Never
fabricate doses or import external rules. Source-only execution must work without
a note. Optional note input affects prose only, not rows or corpus gaps. Prose stays
below 200 words.

### F8 Execution modes

Provide Gemini as the sole live provider using an environment
key, and offline execution. Readiness identifies missing dependencies, models,
credentials, and artifacts. Provider failures never silently select another mode.

Offline replay matches content identity rather than filenames and revalidates
against the input. New inputs use conservative rules or fail clearly if unsupported.

### F9 CLI and service contracts

Provide the root scribe executable and Appendix A's check, extract, validate,
resolve, knowledge, and pipeline commands. Accept absolute paths and paths relative
to the repository root. Keep diagnostics separate from machine-readable artifacts.

Expose independently started services through Compose; the design uses four.
Each has /health returning HTTP 200 with name and version. Publish JSON Schemas and
enforce both sides of service boundaries. In-process and HTTP contracts are identical.

### F10 Audit and failures

Pipeline writes note.json, resolved.json, knowledge.json, and run_log.jsonl. Record
stage, run identifier, timestamp, status, hashes, model/prompt identity where
applicable, and message. Unimplemented or blocked stages are explicitly skipped.
Do not mistake stale artifacts for current success.

Reject missing register columns, duplicate codes across kinds, empty registers,
and unparseable rows. Errors identify stage, input file, and row where possible.
Unexpected failures remain visible and return nonzero.

## Quality and acceptance

Deterministic stages are reproducible for identical inputs and rule versions.
Validation is independent of provider availability. Provider execution has bounded
timeouts and measured latency. Configuration, schemas, and prompts are explicit.
Rule releases do not silently rewrite historical decisions.

Acceptance covers visible and independently authored consultations, companion/nurse
and rejected-speech cases, conflicting reports, uncertainty, mixed-language aliases,
near matches, and catalogue gaps. Mutation tests reject changed numbers, inserted
codes, fabricated citations, family-history reassignment, and misattribution. Verify
provider failures, offline hash mismatches, broken registers, service health, and
real processing requests from a clean environment.

## Product boundaries

Audio transcription, UI, external medical knowledge, automatic claim submission,
autonomous treatment, persistent patient databases, and automatic historical recoding
are outside this build. Feature completion and defects are tracked in GitHub Issues.
