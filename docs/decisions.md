# Clinical and delivery decisions

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

## Guideline and model configuration

The supplied guideline is the sole clinical knowledge source. Do not infer drug
class membership from outside knowledge or turn standard dose into milligrams.
Report absent dose and paediatric guidance as corpus gaps. A plan to start a PPI
does not establish prior PPI exposure or authorize silently changing a test order.

The initially selected Gemini Ollama alias returned HTTP 410 during readiness
verification. Select a working installed model explicitly after a live check;
there is no automatic model fallback. The evaluator needs access to Ollama and any
required cloud account. CI fixtures cannot establish live model availability.

## Team exercise and authorship

The requested team-of-three answer is hypothetical. Use the specified lead,
mid-level ML engineer, and speech engineer roles. Actual implementation is an
individual workflow; the employer's requirement that code and writing be the
candidate's own remains applicable. Do not claim a review, test, or authorship
event that did not occur.
