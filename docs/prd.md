# Requirements and acceptance

The product turns a synthetic, speaker-labelled consultation into a source-backed
note, resolves supported catalogue entries without inference services, and extracts
rules from the supplied guideline. The audience is a clinician reviewing a draft
and an engineer auditing every transformation. This is not autonomous diagnosis or
prescribing software.

The supplied work-sample brief and its Appendix A are authoritative. All five parts
are required. Transcription is excluded. The target budget is 12 to 16 hours;
implementation status and actual elapsed effort belong in the final README.

The supplied `instructions-data/` directory stays local and untracked. Evaluators
provide input paths; Docker runs mount input files rather than bake them into the
image. Tests commit independently authored synthetic fixtures only. Required
derived submission outputs are separate from the supplied input directory.

| Requirement | Acceptance evidence |
| --- | --- |
| Root executable and exact CLI | Subprocess tests, Linux clean-clone run |
| Exactly 13 note sections; missing information is NOT_STATED | JSON Schema and negative schema tests |
| Verbatim timestamped spans | Source substring and timestamp validation |
| No invented or misattributed facts | Speaker, context, semantic transformation tests |
| Changed numbers rejected | Mutation tests for decimals, words, doses and reassignment |
| No note codes | Recursive scan including extra fields and keys |
| Family history cannot become assessment | Source/context validation after tampering |
| Deterministic resolver | Kind restrictions, catalogue tests, blocked network tests |
| Near matches do not force codes | Ambiguous/unresolved tests with alternatives |
| Guideline-only knowledge | Exact quotation and rule-grounding tests |
| Four independent services | Compose health and processing tests |
| Schemas enforced on both sides | Invalid request and invalid response tests |
| Fail loud on broken registers | All four Appendix A failure cases |
| Auditable stages | JSONL records, hashes, failed/skipped stage tests |
| Unseen speaker/language cases | Authored companion/nurse/thinking-aloud transcript |
| Written leadership exercise | README answer under 600 words with required roles |

No UI, database, speech model, external medical corpus, production deployment, or
automatic historical recoding is included. Partial implementation must fail or log
skipped work explicitly; a successful final pipeline cannot contain placeholders.
