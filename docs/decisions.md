# Clinical and delivery decisions

The reviewer clarification received on 2026-09-10 governs the decisions below.
It supersedes earlier assumptions about uncertain diagnoses and grading access.

## Source fidelity

The note may retain mixed-language source wording. Prefer an extractive value over
unverifiable free translation. Small, explicit number/unit normalizations are
allowed only when the validator can reproduce them. Keep numerical order and
association, not merely a bag of digits. Full semantic equivalence of unrestricted
paraphrases is outside a deterministic validator's capability; unsupported
paraphrases must be rejected rather than assumed true.

Timestamp references must identify one source line. Reject duplicate timestamps
instead of choosing an arbitrary line. PATIENT and clinician observations are
different sources. Companion material, if retained, needs companion attribution;
rejected thinking-aloud needs considered_and_rejected. The extractor omits companion material and retains rejected thinking-aloud
only with an explicit exclusion marker. Questions and conditional safety-net advice are not
positive symptoms. Past surgery and family history retain their context.

An optional context_span identifies the preceding question or another relevant
turn. Its reference and quotation must be real, but it is not evidence for the
element's clinical value. Facts and numbers must be grounded in the primary span.

When statements conflict without an explicit correction, preserve both with their
own primary spans and a shared conflict {id, reason}. Leave affected elements
uncoded for clinician review. Never quietly choose one version.

Keep probable diagnoses probable. ROS includes only explicit negatives answering
doctor questions, not an expanded list of absent symptoms. Unknown language or
unclear references remain unnormalized or fail validation. No inferred age,
unstated dose, implied diagnosis, or undocumented allergy detail is permitted.

## Resolution

Register kinds restrict candidates before name matching. Surgical "appendix" may
map through a documented contextual procedure alias; never select the diagnosis
merely because its synonym matches. Family-history conditions remain uncoded as
patient diagnoses. Near matches are suggestions until sufficiently supported by a
unique deterministic rule. Scores are matching evidence, not calibrated clinical
probabilities. Alternatives use stable ordering.

Confirmed, probable, and differential assessments are eligible for deterministic
lookup. Certainty travels unchanged into resolved.json; an uncertain diagnosis is
not automatically unresolved. Elements marked considered_and_rejected are never
coded. Conflict-marked elements remain unresolved with code null.

## Guideline and model configuration

The supplied guideline is the sole clinical knowledge source. Do not infer drug
class membership from outside knowledge or turn standard dose into milligrams.
Report absent dose and paediatric guidance as corpus gaps. A plan to start a PPI
does not establish prior PPI exposure or authorize silently changing a test order.

The knowledge command must work with --source and --out alone. Rows and
not_in_corpus depend solely on the guideline. Optional --note changes prose only;
source-only prose is conditional and does not assume the sample consultation.

The final submission uses Gemini as the sole live provider, with
GEMINI_MODEL defaulting to gemini-3.1-flash-lite and GEMINI_API_KEY supplied through
the environment. Project-level Ollama support was removed; local installations
were left untouched. Live evaluation outcomes are recorded in evaluation.md.

An explicit --provider gemini overrides SCRIBE_PROVIDER. There is no automatic
provider switch after failure. --offline excludes explicit --provider and ignores
provider environment configuration. No key is stored in the repository.

Offline mode replays committed outputs only for a content-hash match of the
provided transcript, then independently revalidate the note. Unseen inputs use
conservative deterministic extraction or fail clearly when unsupported. Replay
must never match by filename alone, contact a provider, or disguise stale output
as a fresh extraction. Runtime logs identify replay versus model generation.

Readiness verifies the selected provider dependency and model metadata, or local
replay artifacts in offline mode. It does not claim that a remote generation will
succeed or that later pipeline stages are complete. Provider failures remain explicit.

## Team exercise and authorship

The requested team-of-three answer is hypothetical. Use the specified lead,
mid-level ML engineer, and speech engineer roles. Actual implementation is an
individual workflow; the employer's requirement that code and writing be the
candidate's own remains applicable. Do not claim a review, test, or authorship
event that did not occur.
