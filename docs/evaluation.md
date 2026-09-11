# Extraction evaluation

## Historical Ollama baseline

These measurements predate the Gemini migration and are retained as historical
evidence only. They were measured on 2026-09-10 with Ollama `qwen3:1.7b`,
thinking disabled and `num_gpu: 0`. Hardware was an AMD Ryzen 7 5800U with 8
physical cores and 16 logical processors. They are local Windows observations,
not a fresh Linux grading-machine benchmark.

| Input | Wall time | Independent validation | Output tokens |
| --- | ---: | --- | ---: |
| Supplied consultation | 55.266 s | Passed | 527 |
| Alternate consultation in src/tests/fixtures | 19.703 s | Passed | 228 |

The model was already installed and previously loaded. These are individual warm
runs, not latency percentiles or cold-start measurements. Request timeout is 180
seconds. The alternate includes companion statements, nurse observations and
rejected thinking-aloud. An earlier alternate run failed because of an invalid
evidence selection. Restricting IDs in the response schema and requiring unique
IDs in the prompt produced the successful rerun above; invalid responses still
fail rather than trigger a provider switch or automatic repair.

The supplied note and replay manifest originate from this successful historical
run. Replay verifies content hashes and independently validates the note.

## Current Gemini verification

Gemini is now the sole live provider. On 2026-09-10, `gemini-3.1-flash-lite`
processed the supplied consultation and the independent alternate consultation
through extraction, validation, resolution and knowledge in memory. The supplied
run completed in 10.33 seconds and the alternate in 2.84 seconds; both returned
structured output that passed independent validation. A third independent
submission fixture also completed the same pipeline after the safeguards were
implemented. These are warm local observations, not a fresh-machine benchmark.

The run audit records the provider/model identifier and extraction prompt hash;
the key is read only from `GEMINI_API_KEY` and is absent from source, fixtures,
logs and generated artifacts. Provider failures are explicit and never fall back
to offline mode. Offline replay remains content matched for the supplied
transcript, while unseen offline inputs use bounded rules or fail clearly.

Validation success establishes provenance, schema, numeric, attribution, section,
conflict and context checks. It does not establish unrestricted clinical
completeness or general bilingual understanding. Section routing and contradiction
detection use bounded rules; unfamiliar expressions, implicit corrections and
longer conversations require additional evaluation and clinician review.

## Grading interpretation

The acceptance behavior follows Mark's clarifications: contradictory assertions
remain separately spanned, share a conflict marker and remain uncoded; probable
and differential diagnoses may resolve with certainty preserved; contextual spans
are permitted beside each required primary span; knowledge rows and corpus gaps
come from the guideline alone, with consultation prose conditional on note input;
and mixed English/Swahili values remain verbatim where translation could add
uncertainty. Ollama was acceptable as an evaluation option, but this submission
uses Gemini as its configured live path and retains offline execution as the
credential-free path.

## Deterministic knowledge checks

The supplied excerpt produces three drug-class rules, six red-flag rows and one
test constraint. Every quotation is a verbatim substring and its source, section
and page match the citation header. The committed consultation-informed prose has
95 words. Running the required source-only command produces identical rows and
corpus gaps, with conditional prose.

The independent guideline fixture changes the source title, section, page,
treatment duration, lookback interval and alarm list. Tests cover citation and
field tampering, omitted/duplicate rules, source-only invariance, dose and age
guidance gaps, unsupported formats and network isolation. The parser intentionally
fails on unsupported sentence structures; these results do not establish coverage
of arbitrary clinical guidelines or multi-section documents.

## Pipeline and service verification

The historical supplied-transcript pipeline completed through local CPU-only
Ollama in 60.469 seconds, with extraction, validation, resolution and knowledge
all logging `ok`. The current Gemini runs likewise logged `ok` for all four
stages, and their audit records identify `gemini/gemini-3.1-flash-lite`.
Offline replay also completed all four stages successfully.

All four real Compose services passed health and processing requests, followed by
invalid-input rejection checks. Stopping extraction left the other three healthy.
The Compose processing check uses an independent transcript and guideline in
offline mode. Direct Gemini verification was completed through the CLI/in-memory
pipeline; Compose Gemini processing remains an optional extraction-service check,
while the other services require no provider credentials.
