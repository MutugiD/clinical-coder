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
rejected thinking-aloud needs considered_and_rejected. The initial extractor omits
both from patient facts. Questions and conditional safety-net advice are not
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

The evaluator uses a fresh CPU-only machine. The local default is qwen3:1.7b;
accuracy and CPU latency are unverified until the extraction milestone. The earlier
Gemini Ollama alias was retired; a successful cloud GLM probe does not establish
local grading readiness.

Select Ollama or direct Google Gemini through --provider or SCRIBE_PROVIDER.
Gemini reads GEMINI_API_KEY, with GEMINI_MODEL configurable. There is no automatic
provider switch after failure. --offline excludes explicit --provider and ignores
unrelated provider environment configuration.

Offline mode will replay committed outputs only for a content-hash match of the
provided transcript, then independently revalidate the note. Unseen inputs use
conservative deterministic extraction or fail clearly when unsupported. Replay
must never match by filename alone, contact a provider, or disguise stale output
as a fresh extraction. Runtime logs identify replay versus model generation.

At the CLI milestone these execution paths are declared but unimplemented.
Readiness reports missing dependencies and then reports the unfinished extraction
path rather than return success. Five-command grading setup including model pull,
CPU measurements, and actual provider verification remain delivery gates.

## Team exercise and authorship

The requested team-of-three answer is hypothetical. Use the specified lead,
mid-level ML engineer, and speech engineer roles. Actual implementation is an
individual workflow; the employer's requirement that code and writing be the
candidate's own remains applicable. Do not claim a review, test, or authorship
event that did not occur.
