# Testing and delivery gates

Before model code, define three evaluation sets: span-grounded bilingual notes,
adversarial attribution/numeric mutations, and catalogue/guideline resolution
cases. Include independent examples beyond the provided consultation. A bilingual
clinical reviewer labels clinical facts; engineers label deterministic contract
and failure cases, with clinical adjudication for disputed meanings.

Unit tests exercise normalization, schema invariants, evidence, matching, and
citations. CLI tests invoke the root script as a subprocess and separate stdout
from stderr. Boundary tests reject malformed inputs and outputs. Network access is
blocked during resolver tests. Fixtures drive CI extraction without pretending to
be a live model evaluation.

Mutation tests change digits, number words, decimals, units, numerical ordering,
certainty, attribution, section placement, code strings, and citations. Positive
controls ensure the original note still passes. Test missing files, malformed
JSON, empty transcripts, unknown speakers, duplicate timestamps, and each of the
four broken-register cases in Appendix A.

PR gates are Ruff, pytest, compilation, a Linux executable check, container build,
and CodeQL. Once services exist, exercise Compose health plus actual processing.
Before hand-in, run real Ollama extraction, independent validation, a complete
pipeline, and a fresh Linux clone using the README commands. Record observed
results and limitations rather than predicting that checks will pass.

## Clarification acceptance cases

Verify conflict preservation with both statements uncoded, probable/differential
resolution with unchanged certainty, and exclusion of considered_and_rejected
elements. A number appearing only in context_span cannot justify a value. Check
that optional --note does not change knowledge rows or not_in_corpus.

Test explicit provider selection, missing executable/server/model/key, HTTP errors,
malformed provider responses, and refusal to silently switch modes. Offline tests
block all network access, rename the known transcript, mutate its contents, tamper
with cached notes, and exercise unseen supported and unsupported cases. Run CPU-only
benchmarks with hardware, cold/warm latency, and validation outcomes recorded.

Tests live under src/tests; fixtures are under src/tests/fixtures. Extraction tests
exercise provider failures, schema-limited selections, content-based replay,
cache tampering and unsupported unseen input. Numeric and attribution tests use
independent mutations with positive controls. Live CPU results are separate from
credential-free CI and are recorded in [evaluation.md](evaluation.md).
