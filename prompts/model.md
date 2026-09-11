# Extraction model configuration

The live provider is Google Gemini, default model `gemini-3.1-flash-lite`.
`GEMINI_MODEL` can override the requested identifier. Actual provider model identity
is recorded in stage logs and the replay manifest for sample generation.

`extract.txt` is the exact system prompt. The user message is JSON containing
source-derived evidence candidates with IDs, text, speaker, allowed sections and
question context. The generated response schema restricts IDs and section names.
Runtime checks require all eligible IDs and all required sections exactly once.
Temperature is zero, output is bounded to 4096 tokens, and the default request
timeout is 180 seconds. A non-STOP response or incomplete selection fails explicitly.

Credentials are read from `GEMINI_API_KEY` and sent in a request header. No register
or clinical codes are sent to the model. Values and evidence are rendered locally.
