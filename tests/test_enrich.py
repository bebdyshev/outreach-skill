import io
import json

import enrich as enrich_cli


def test_known_from_stdin(monkeypatch, capsys):
    seen = {}

    def fake(company, domain, person, known):
        seen["known"] = known
        return {"email": None}

    monkeypatch.setattr(enrich_cli, "enrich", fake)
    monkeypatch.setattr("sys.stdin", io.StringIO('[{"name": "Pat O\'Brien", "email": "pat@a.com"}]'))
    code = enrich_cli.main(["--company", "A", "--domain", "a.com", "--known", "-"])
    assert code == 0
    assert seen["known"][0]["name"] == "Pat O'Brien"


def test_provider_crash_is_json_error(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(enrich_cli, "enrich", boom)
    code = enrich_cli.main(["--company", "A", "--domain", "a.com"])
    assert code == 1
    assert json.loads(capsys.readouterr().err) == {"error": "provider failed: RuntimeError: boom"}
