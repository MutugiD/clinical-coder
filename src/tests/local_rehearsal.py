"""Explicit local CLI rehearsal; optional live credentials never enter artifacts."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


def load_environment(path: Path) -> None:
    allowed = {
        "SCRIBE_PROVIDER",
        "GEMINI_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_TIMEOUT_SECONDS",
        "SCRIBE_OFFLINE",
        "SCRIBE_SERVICE",
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name.strip() not in allowed:
            raise ValueError("unsupported local environment setting")
        os.environ[name.strip()] = value.strip()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def check_facts(case, note, resolved, knowledge):
    if case == "supplied":
        assert any("three weeks" in e["value"] for e in note["history_of_presenting_illness"])
        assert note["past_medical_history"] == "NOT_STATED"
        assert note["assessment"][0]["certainty"] == "probable"
        expected = {
            "assessment": {"K29.7"},
            "past_surgical_history": {"PGP-EC-0330"},
            "medication_history": {"M01AB05", "N02BE01"},
            "allergies": {"ALG-EC-0003"},
            "plan": {"M01AB05", "A02BC01", "LAB-EC-0412"},
        }
        for section, codes in expected.items():
            assert {e["code"] for e in resolved[section] if e["code"]} == codes, section
        assert all(e["code"] is None for e in resolved["family_history"])
        assert "two weeks" in knowledge["prose"]
        assert "milligram dose" in knowledge["prose"]
    elif case == "alternate":
        assert note["vitals"][0]["attribution"] == "nurse"
        assert note["assessment"][0]["kind"] == "considered_and_rejected"
        assert resolved["assessment"][0]["code"] is None
        assert note["assessment"][-1]["certainty"] == "probable"
        assert resolved["medication_history"][0]["code"] == "N02BE01"
    else:
        assert {e["code"] for e in resolved["medication_history"]} == {"M01AB05", "N02BE01"}
        assert all(e["code"] is None and e.get("conflict") for e in resolved["allergies"])
        assert all(e["code"] is None for e in resolved["assessment"][:2])
        assert all(e["kind"] == "considered_and_rejected" for e in note["assessment"][:2])
        assert resolved["assessment"][-1]["code"] == "K21.0"
        assert note["assessment"][-1]["certainty"] == "differential"
        fever = next(e for e in note["history_of_presenting_illness"] if e["value"] == "fever.")
        denied = next(e for e in note["review_of_systems"] if e["value"] == "No fever.")
        assert fever["conflict"] == denied["conflict"]
    assert not any(
        e.get("attribution") == "companion"
        for entries in note.values()
        if isinstance(entries, list)
        for e in entries
    )
    assert len(knowledge["rows"]) == 10 and len(knowledge["prose"].split()) < 200


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--inputs", type=Path, default=Path("instructions-data"))
    parser.add_argument("--out", type=Path, default=Path("results/local-rehearsal"))
    args = parser.parse_args()
    if args.env_file:
        load_environment(args.env_file)
    out = args.out / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    records = []

    def run(arguments, success=True):
        start = perf_counter()
        result = subprocess.run(
            [sys.executable, "scribe", *map(str, arguments)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        elapsed = round(perf_counter() - start, 3)
        message = result.stderr
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            message = message.replace(key, "[REDACTED]")
        records.append(
            {
                "command": list(map(str, arguments)),
                "seconds": elapsed,
                "exit": result.returncode,
                "stderr": message,
            }
        )
        assert (result.returncode == 0) == success, message
        assert not result.stdout, "unexpected command stdout"
        return elapsed

    try:
        mode = ["--provider", "gemini"] if args.live else ["--offline"]
        run(["check", *mode])
        register, source = args.inputs / "register.csv", args.inputs / "guideline.txt"
        cases = {
            "supplied": args.inputs / "transcript_01.txt",
            "alternate": Path("src/tests/fixtures/alternate_consultation.txt"),
            "submission": Path("src/tests/fixtures/submission_consultation.txt"),
        }
        for case, transcript in cases.items():
            directory = out / case
            elapsed = run(
                [
                    "pipeline",
                    *mode,
                    "--transcript",
                    transcript,
                    "--register",
                    register,
                    "--source",
                    source,
                    "--out",
                    directory,
                ]
            )
            note, resolved, knowledge = [
                read(directory / f"{name}.json") for name in ("note", "resolved", "knowledge")
            ]
            check_facts(case, note, resolved, knowledge)
            logs = [
                json.loads(line) for line in (directory / "run_log.jsonl").read_text().splitlines()
            ]
            assert [r["stage"] for r in logs] == ["extract", "validate", "resolve", "knowledge"]
            assert all(r["status"] == "ok" for r in logs)
            assert len({r["run_id"] for r in logs}) == 1
            for record, artifact in zip(
                logs, [note, {"valid": True}, resolved, knowledge], strict=True
            ):
                assert record["output_hash"] == digest(artifact)
            run(["validate", "--transcript", transcript, "--note", directory / "note.json"])
            run(
                [
                    "resolve",
                    "--note",
                    directory / "note.json",
                    "--register",
                    register,
                    "--out",
                    directory / "standalone-resolved.json",
                ]
            )
            assert read(directory / "standalone-resolved.json") == resolved
            print(f"{case}: clinical expectations and audit hashes passed ({elapsed}s)", flush=True)
        run(
            [
                "extract",
                *mode,
                "--transcript",
                cases["supplied"],
                "--out",
                out / "standalone-note.json",
            ]
        )
        check_facts(
            "supplied",
            read(out / "standalone-note.json"),
            read(out / "supplied/resolved.json"),
            read(out / "supplied/knowledge.json"),
        )
        run(["knowledge", "--source", source, "--out", out / "source-only-knowledge.json"])
        assert (
            read(out / "source-only-knowledge.json")["rows"]
            == read(out / "supplied/knowledge.json")["rows"]
        )
        good = read(out / "supplied/note.json")
        for mutation in ("number", "code", "family"):
            bad = deepcopy(good)
            if mutation == "number":
                e = next(e for e in bad["plan"] if "20 milligrams" in e["value"])
                e["value"] = e["value"].replace("20 milligrams", "40 milligrams")
            elif mutation == "code":
                bad["chief_complaint"][0]["extra"] = {"code": "M01AB05"}
            else:
                e = bad["family_history"][0]
                e["certainty"] = "confirmed"
                bad["assessment"].append(e)
            path = out / f"tampered-{mutation}.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            run(["validate", "--transcript", cases["supplied"], "--note", path], success=False)
        print("Standalone commands and tamper rejection passed.", flush=True)
    finally:
        (out / "rehearsal.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"Rehearsal records: {out}", flush=True)


if __name__ == "__main__":
    main()
