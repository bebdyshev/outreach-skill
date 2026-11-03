import io
import json

import pytest

import enrich as enrich_cli


@pytest.fixture
def seen(monkeypatch):
    calls = {}

    def fake(company, domain, person, known):
        calls.update(company=company, domain=domain, person=person, known=known)
        return {"email": None}

    monkeypatch.setattr(enrich_cli, "enrich", fake)
    return calls


def test_input_from_stdin(seen, monkeypatch):
    payload = {
        "company": "O'Brien & Sons $(id)",
        "domain": "obrien.com",
        "person": "Pat O'Brien",
        "known": [{"name": "Sam `whoami`", "email": "sam@obrien.com"}],
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert enrich_cli.main(["--json", "-"]) == 0
    assert seen == payload


def test_person_and_known_default_to_empty(seen):
    assert enrich_cli.main(["--json", '{"company": "A", "domain": "a.com"}']) == 0
    assert seen["person"] == ""
    assert seen["known"] == []


@pytest.mark.parametrize("payload, message", [
    ("[]", "JSON object"),
    ('{"domain": "a.com"}', "missing required field: company"),
    ('{"company": "A", "domain": " "}', "missing required field: domain"),
    ('{"company": "A", "domain": "a.com", "person": 3}', "person must be a string"),
    ('{"company": "A", "domain": "a.com", "extra": 1}', "unknown fields: extra"),
])
def test_bad_input_is_json_error(seen, capsys, payload, message):
    assert enrich_cli.main(["--json", payload]) == 1
    assert message in json.loads(capsys.readouterr().err)["error"]


def test_provider_crash_is_json_error(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(enrich_cli, "enrich", boom)
    assert enrich_cli.main(["--json", '{"company": "A", "domain": "a.com"}']) == 1
    assert json.loads(capsys.readouterr().err) == {"error": "provider failed: RuntimeError: boom"}
