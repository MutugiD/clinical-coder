import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def test_schemas_are_valid_and_missing_sections_fail():
    root = json.loads(Path("schemas/contracts.json").read_text())
    registry = Registry().with_resource(root["$id"], Resource.from_contents(root))
    for path in Path("schemas").glob("*.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text()))
    schema = json.loads(Path("schemas/extract.output.json").read_text())
    validator = Draft202012Validator(schema, registry=registry)
    note = dict.fromkeys(root["$defs"]["note"]["required"], "NOT_STATED")
    validator.validate(note)
    del note["assessment"]
    with pytest.raises(Exception, match="assessment"):
        validator.validate(note)
