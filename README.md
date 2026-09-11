# Clinical coder

Clinical coder produces source-backed clinical notes from speaker-labelled English
and Swahili consultations. It preserves verbatim evidence and validates notes before
writing them. Deterministic register lookup adds codes, while guideline extraction
produces cited rules for clinical review.

[Requirements](docs/prd.md) · [Architecture](docs/architecture.md) ·
[Design decisions](docs/decisions.md) · [Testing](docs/testing-strategy.md) ·
[End-to-end guide](docs/end-to-end-testing.md) ·
[Issues](https://github.com/MutugiD/clinical-coder/issues)

## Setup

Use Python 3.12 and export `GEMINI_API_KEY` in your shell. The grading harness
supplies this environment variable. The application does not load `.env` files.
From the repository checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
./scribe check
```

Readiness checks Gemini model access; generation is verified by running extraction.
On Windows, activate `.venv/Scripts/Activate.ps1` and use `python scribe`.

## Time, scope and next steps

I spent approximately 12 to 13 hours on this submission. I concentrated that time
on source-grounded extraction, strict validation, deterministic resolution,
guideline citations, failure handling, service boundaries and repeatable tests.

I cut transcription because it is not required for this track. I also kept the
offline extractor and guideline parser deliberately narrow. They handle the
supplied formats and tested variations, but they are not general Swahili or Sheng
language systems and they do not attempt to resolve unclear chronology. I did not
build a production deployment, a user interface, automated clinical terminology
updates or a clinical review workflow. Those additions would have reduced the time
available for the safety checks that determine whether an output can be trusted.

With two additional days, I would first repeat the documented setup and full test
matrix on a clean CPU-only machine. I would then add more clinician-labelled
consultations covering Sheng, indirect answers, corrections, companions and noisy
speaker labels. I would expand mutation tests around dates, doses and attribution,
run load tests across the four services, and capture latency, failure and unresolved
rate dashboards. I would finish by reviewing the new failures with a clinician and
turning only the agreed cases into versioned extraction or resolver rules.

## Extract and validate

```sh
./scribe extract --transcript consultation.txt --out results/note.json
./scribe validate --transcript consultation.txt --note results/note.json
```

The note contains the 13 contract sections. Each element includes its value,
timestamped evidence, and confidence; assessment also carries certainty.
A section with no evidence contains `NOT_STATED`.

The sole live provider is Google Gemini with `gemini-3.1-flash-lite`, temperature
zero and structured responses. Failures never silently switch execution modes.

```sh
./scribe check --provider gemini
./scribe extract --provider gemini --transcript consultation.txt --out results/note.json
./scribe extract --offline --transcript consultation.txt --out results/note.json
```

Gemini requires `GEMINI_API_KEY`. Offline execution uses verified committed output
for a matching transcript or conservative rules for a new input. Unsupported input
fails with an explanation. Every returned note is validated.

| Variable | Default |
| --- | --- |
| `SCRIBE_PROVIDER` | `gemini` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `GEMINI_API_KEY` | Required for Gemini |
| `GEMINI_TIMEOUT_SECONDS` | `180` |

`.env.example` documents settings. Export them in the shell; the application does
not load `.env` automatically. `--offline` cannot be combined with `--provider`.

## Resolve codes

```sh
./scribe resolve --note results/note.json --register register.csv --out results/resolved.json
```

Validate the note against its transcript before resolution. The resolver accepts
only the note and register, so it cannot establish source provenance itself. It
uses no model or network. A unique exact name or synonym within the allowed kind
resolves; near matches remain uncoded suggestions and competing exact matches are
ambiguous. Conflict, rejected, companion, family-history and negated elements stay
uncoded. Certainty and evidence remain unchanged. Resolution confidence describes
the lookup; the original confidence is retained as `extraction_confidence`.

For 12,000 conditions and 3,000 drugs, compile each versioned register into a
kind-partitioned alias index and token trie. Retrieve exact candidates first, then
bounded character-gram candidates for suggestions, using fixed thresholds and
stable code ordering. Version normalization and contextual aliases with the
register checksum; record selected aliases, alternatives and rule versions so each
decision can be reproduced. Review synonym changes against a frozen evaluation
set before releasing a new catalogue.

## Extract guideline knowledge

```sh
./scribe knowledge --source guideline.txt --out results/knowledge.json
./scribe knowledge --source guideline.txt --note results/note.json --out results/knowledge.json
```

The source alone determines drug-class rules, red flags, test constraints and
`not_in_corpus` gaps. Every row carries an exact quotation, source name, section
and page. The optional note affects only the review prose, which stays below 200
words. The committed example uses the supplied note for that prose.

The deterministic parser supports one citation block in the supplied format:
`SOURCE: Title, edition, Section X.Y, page N.`, followed by a matching section
heading and supported recommendation sentences. Missing metadata, additional
sections or unrecognised sentences fail explicitly. This is a bounded excerpt
parser, not a general guideline-document reader. It uses no model or network and
does not infer drug-class membership or replace clinical decisions.

## Verification

Run the complete pipeline from the repository root:

```sh
./scribe pipeline --offline --transcript consultation.txt --register register.csv --source guideline.txt --out results/run-1
```

Use `--provider gemini` instead of `--offline` for live
extraction. The pipeline runs extract → validate → resolve → knowledge and writes
three JSON artifacts plus `run_log.jsonl`. A failure exits nonzero and logs later
stages as skipped. Reusing a directory preserves prior successful files on failure;
check the latest run's records or use a fresh directory for each test.

Four independent HTTP services are available through `docker compose up -d
--build --wait`. For a credential-free service test, set `SCRIBE_OFFLINE=true`
first, then run `python src/tests/compose_smoke.py`. Their localhost ports are
8001–8004 for extract, validate, resolve and knowledge. Each provides `/health`
and `/process`; health reports liveness rather than model readiness.

See the [end-to-end guide](docs/end-to-end-testing.md) for Windows commands,
request bodies, failure checks and model configuration. The
[acceptance checks](docs/acceptance-checks.md) map the brief and review cases to tests.

```sh
ruff check .
pytest -q
python -m compileall -q src
docker build -t clinical-scribe .
docker run --rm clinical-scribe --version
```

Tests and independent fixtures live in `src/tests`. Provider mocks are distinct
from live model measurements. Use read-only input and writable output volumes for
Docker extraction. Only the extraction service receives Gemini credentials.


## Architecture

Extraction selects evidence; deterministic rendering constructs the note; validation
checks source fidelity and clinical scope. Resolution and guideline extraction use
separate contracts so their rules can evolve independently of the model. At higher
load, queue bounded model requests and scale deterministic stages separately.
Monitor latency, validation failures, unresolved rates, and provider availability
without patient text in metric labels. Version resolver rules and catalogue hashes
so a release does not silently recode historical notes. See the architecture document
for component responsibilities, data flows, and service contracts.

## Failure behavior

Exit `0` means success; `1` means processing or validation failure; `2` means invalid
arguments. Diagnostics go to stderr. Output is written only after a stage succeeds.
Unsupported language, scope, or transformations cause rejection rather than guessed
facts. Implementation coverage and defects are tracked in GitHub Issues.

## Where this would break

- **Unrecognised Sheng or indirect answers:** scope rules may not classify a relevant
  utterance. Extraction reports unsupported turns; broader bilingual
  evaluation is required before deployment.
- **Incorrect speaker labels:** a relative's account could be attributed to the
  patient. Validate attribution against the source; incorrectly labelled source
  audio still requires upstream review.
- **Ambiguous corrections and chronology:** a clinician may need to determine which
  statement is current. Preserve detected conflicts; the rules are not a general
  semantic contradiction solver.
- **Provider omissions or slow inference:** a grounded note may be incomplete or
  time out. Evaluate coverage separately from validity and record CPU latency.

## Part E: Leading the build

I would own the contracts, validator, deterministic resolver, pipeline and release
criteria. The mid-level ML engineer would own extraction experiments, prompt
changes and evidence coverage evaluation. The speech engineer would own audio
ingestion, diarisation, timestamps and speaker-role quality, while emitting the
same transcript contract used here.

I would fix the transcript format, note schema, evidence rules, service request and
response schemas, and audit record before splitting the work. I would not let the
team start separate model or service implementations until we had shared fixtures
and executable contract tests. Otherwise each component could look correct alone
while disagreeing about speakers, spans, missing values or failure states.

The first dataset would contain consented or synthetic Kenyan consultations labelled
for section, exact evidence span, speaker, certainty, negation and rejection. Two
clinicians would label it independently and adjudicate disagreements. The second
would be a safety set made from controlled mutations of valid notes, including
numbers, attribution, codes and misplaced family history. An engineer would produce
the mutations and a clinician would confirm whether each expected rejection is
clinically correct. The third would cover register and guideline grounding. A
clinical coder would label exact codes, ambiguity and unresolved cases, while a
clinician or pharmacist would verify guideline rows and citations.

I would push back on judging broad language robustness from one visible transcript
and one hidden transcript. I would keep the hidden set, but add a small labelled
development set with representative English, Swahili and Sheng patterns. That gives
the team a fair way to improve coverage without learning the final test cases and
makes failures easier to diagnose than a single aggregate score.
