# Extraction evaluation

Measured on 2026-09-10 with Ollama qwen3:1.7b, thinking disabled and `num_gpu: 0`.
Hardware: AMD Ryzen 7 5800U, 8 physical cores and 16 logical processors. These
are local Windows observations, not a fresh Linux grading-machine benchmark.

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

The supplied note and replay manifest originate from the successful model run.
Replay verifies content hashes and independently validates the note. The manifest
records the exact extraction prompt hash. Unseen offline inputs use conservative
rules and explicitly fail on unsupported patient turns.

Validation success establishes the implemented provenance, schema, numeric and
context checks. It does not establish clinical completeness or general bilingual
understanding. Section routing and conflict detection use bounded lexical rules;
unfamiliar expressions, implicit corrections and longer conversations require
additional evaluation and clinician review. Direct Gemini generation has not
been tested live because no provider key is configured. Controlled provider
tests are reported separately from the live local runs.
