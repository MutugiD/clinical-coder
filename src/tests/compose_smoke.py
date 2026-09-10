"""Exercise actual Compose health and processing endpoints using only the stdlib."""

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PORTS = {"extract": 8001, "validate": 8002, "resolve": 8003, "knowledge": 8004}


def call(stage: str, payload: dict | None = None) -> tuple[int, dict]:
    path = "/health" if payload is None else "/process"
    request = Request(
        f"http://127.0.0.1:{PORTS[stage]}{path}",
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=180) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    for stage in PORTS:
        status, body = call(stage)
        assert status == 200 and body["service"] == stage and body["version"], body
        status, body = call(stage, {})
        assert status == 422 and body["error"]["stage"] == stage, body
    fixtures = Path(__file__).parent / "fixtures"
    transcript = (fixtures / "alternate_consultation.txt").read_text()
    status, note = call("extract", {"transcript": transcript})
    assert status == 200 and len(note) == 13, note
    status, body = call("validate", {"transcript": transcript, "note": note})
    assert status == 200 and body == {"valid": True}, body
    register = "kind,code,name,synonyms\ndrug,N02BE01,Paracetamol,panadol\n"
    status, resolved = call("resolve", {"note": note, "register": register})
    assert status == 200, resolved
    assert resolved["medication_history"][0]["code"] == "N02BE01", resolved
    status, body = call("knowledge", {"source": (fixtures / "alternate_guideline.txt").read_text()})
    assert status == 200 and body["rows"] and body["not_in_corpus"], body
    note["vitals"][0]["value"] = "Temperature is 99."
    status, body = call("validate", {"transcript": transcript, "note": note})
    assert status == 422, body
    print("Four services: health, valid processing and invalid-input rejection passed.")


if __name__ == "__main__":
    main()
