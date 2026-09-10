import hashlib
import json

import httpx
import pytest

from clinical_scribe.config import Settings
from clinical_scribe.errors import StageError
from clinical_scribe.extraction import extract, offline_rules, transcript_hash
from clinical_scribe.output import canonical_bytes
from clinical_scribe.providers import generate
from clinical_scribe.readiness import check

TEXT = "[00:00] NURSE: Pulse 70."


@pytest.fixture
def cache(tmp_path, monkeypatch):
    note = offline_rules(TEXT)
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "note.json").write_text(json.dumps(note))
    (output / "replay-manifest.json").write_text(
        json.dumps(
            {
                "transcript_hash": transcript_hash(TEXT),
                "note_hash": "sha256:" + hashlib.sha256(canonical_bytes(note)).hexdigest(),
                "mode": "rules",
                "model": None,
                "prompt_hash": None,
            }
        )
    )
    monkeypatch.chdir(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("offline execution contacted a provider")

    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setattr(httpx, "get", forbidden)
    return output


def test_replay_uses_content_and_revalidates(cache):
    note, metadata = extract(TEXT + "\n", Settings(offline=True))
    assert note["vitals"][0]["value"] == "Pulse 70."
    assert metadata["mode"] == "replay"
    altered = json.loads((cache / "note.json").read_text())
    altered["vitals"][0]["value"] = "Pulse 80."
    (cache / "note.json").write_text(json.dumps(altered))
    manifest = json.loads((cache / "replay-manifest.json").read_text())
    manifest["note_hash"] = "sha256:" + hashlib.sha256(canonical_bytes(altered)).hexdigest()
    (cache / "replay-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(StageError, match="changes source"):
        extract(TEXT, Settings(offline=True))


def test_cache_mismatch_uses_actual_unseen_input(cache):
    note, metadata = extract(TEXT.replace("70", "82"), Settings(offline=True))
    assert note["vitals"][0]["value"] == "Pulse 82."
    assert metadata["mode"] == "rules"
    with pytest.raises(StageError, match="cannot safely classify"):
        extract("[00:00] PATIENT: Something indescribable.", Settings(offline=True))


def test_cache_hash_tampering_fails(cache):
    (cache / "note.json").write_text(json.dumps(offline_rules(TEXT.replace("70", "81"))))
    with pytest.raises(StageError, match="hash mismatch"):
        extract(TEXT, Settings(offline=True))


@pytest.mark.parametrize("provider", ["ollama", "gemini"])
@pytest.mark.parametrize("body", [[], None, {}, {"done": True, "message": {}}])
def test_malformed_provider_response_fails(monkeypatch, provider, body):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: httpx.Response(
            200, json=body, request=httpx.Request("POST", "https://example.test")
        ),
    )
    with pytest.raises(StageError):
        generate(Settings(provider=provider, gemini_api_key="test-key"), "prompt", {}, {})


@pytest.mark.parametrize("provider", ["ollama", "gemini"])
def test_provider_failure_has_no_fallback(monkeypatch, provider):
    calls = []

    def fail(url, **kwargs):
        calls.append(url)
        raise httpx.ReadTimeout("secret must not appear")

    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(StageError, match="timed out") as error:
        generate(Settings(provider=provider, gemini_api_key="test-key"), "prompt", {}, {})
    assert len(calls) == 1
    assert "secret" not in str(error.value)


def test_model_selection_cannot_create_facts(monkeypatch):
    def select(settings, prompt, payload, schema):
        assert payload["candidates"][0]["text"] == "Pulse 70."
        assert schema["properties"]["items"]["items"]["properties"]["id"]["enum"] == [0]
        return '{"items":[{"id":0,"sections":["vitals"]}]}', {"model": "fixture"}

    monkeypatch.setattr("clinical_scribe.providers.generate", select)
    note, metadata = extract(TEXT, Settings())
    assert note["vitals"][0]["value"] == "Pulse 70."
    assert metadata["mode"] == "model"


@pytest.mark.parametrize(
    "selection",
    [
        '{"items":[{"id":100,"sections":["vitals"]}]}',
        '{"items":[{"id":0,"sections":["assessment"]}]}',
        '{"items":[{"id":0,"sections":["vitals"]},{"id":0,"sections":["vitals"]}]}',
        '{"items":[],"code":"K29.7"}',
        "not JSON",
    ],
)
def test_invalid_model_selections_fail(monkeypatch, selection):
    monkeypatch.setattr("clinical_scribe.providers.generate", lambda *a: (selection, {}))
    with pytest.raises(StageError):
        extract(TEXT, Settings())


def test_offline_readiness_checks_committed_artifacts():
    assert check(Settings(offline=True)) is None
