# Review acceptance checks

The brief, Appendix A and reviewer clarifications govern these checks. The two
additional review notes supplied on 2026-09-10 were treated as test guidance, not
as evidence that an implementation had already passed.

| Requirement or review trap | Automated check |
| --- | --- |
| Exact section keys and required fields | `src/tests/test_context_schema.py`, `test_inputs.py` |
| Numeric order, decimals, signs, units and number words | `src/tests/test_validation.py` |
| Changed year, timestamp and familiar timestamps with different facts | `src/tests/test_review_acceptance.py` |
| Context cannot supply primary facts or numbers | `test_validation.py::test_context_cannot_supply_numbers` |
| Companion, family history and rejected thinking-aloud | `src/tests/test_validation.py`, `test_resolver.py` |
| Medication contradictions remain visible and uncoded | `test_review_acceptance.py::test_medication_contradiction_marks_both_and_neither_codes` |
| Confirmed, probable and differential lookup preserves certainty | `test_resolver.py::test_uncertain_diagnoses_resolve_without_changing_certainty` |
| Surgery maps only to a register procedure | `test_resolver.py::test_kind_aware_exact_lookup` |
| Future warning does not become a symptom | `test_review_acceptance.py::test_future_warning_is_not_current_symptom_or_diagnosis` |
| Unknown medicines stay present and uncoded | `test_review_acceptance.py::test_unknown_medication_stays_present_and_uncoded` |
| No model or network in resolver and knowledge | Fresh-interpreter tests in `test_resolver.py` and `test_knowledge.py` |
| Knowledge works without any note or outputs available | `test_review_acceptance.py::test_knowledge_runs_where_no_note_or_outputs_exist` |
| Real quotations cannot justify altered rule fields | `src/tests/test_knowledge.py` |
| Explicit provider failure and offline content matching | `test_extraction.py`, `test_grading_configuration.py`, `test_pipeline.py` |
| All four broken registers fail in the pipeline | `test_pipeline.py::test_all_broken_registers_fail_at_resolve_with_file_and_logs` |
| Exact input/output hashes and terminal stage records | `test_pipeline.py::test_full_cli_pipeline_with_spaces_and_actual_hashes` |
| Invalid intermediate note never gets published | `test_pipeline.py::test_invalid_intermediate_note_fails_validation_before_publication` |
| HTTP input and output contracts enforced | `src/tests/test_services.py` |
| Independently running Compose services process actual requests | `src/tests/compose_smoke.py`, also run by CI |

Review tests reproduced two related failures: negated medication statements had
different concept keys, and contractions such as `don't` were not recognised as
negation. Source-derived medication keys and shared negation rules now address
both, with straight/curly-apostrophe and leading-decimal conflict regressions.
These tests do not establish unrestricted semantic contradiction detection.

## Final submission review

`test_submission_gaps.py` reproduces the review defects independently: split-sentence
and adjacent-turn rejection, opposing allergies, mixed symptom polarity, unasked ROS
negatives, direct diagnoses, coordinated medicines and omitted model selections.
Controls cover distinct historical periods, unrelated rejected hypotheses, explicit
abstention on unsupported corrections/qualifiers, and CLI/HTTP rejection mutations.

`test_extraction.py` and `test_grading_configuration.py` exercise the sole Gemini
provider, including structured requests, missing credentials, HTTP failures,
timeouts, blocked/truncated responses, completeness and credential-safe errors.
Removed provider selection is rejected, while offline ignores live configuration.

`local_rehearsal.py` is an opt-in CLI runner, separate from pytest. It checks the
supplied, alternate and submission consultations against manually specified facts,
expected codes, conflicts, provenance markers and canonical output hashes. Its
live mode imports an explicitly named local environment file; credentials are
never written to rehearsal reports. Provider validity is separate from completeness.

See [evaluation](evaluation.md) for actual model measurements and
[end-to-end testing](end-to-end-testing.md) for manual commands. Final clean-clone
submission rehearsal and remaining writing are tracked in issue #9.
