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
