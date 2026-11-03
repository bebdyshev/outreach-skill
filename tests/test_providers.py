import json

import pytest

import enrich as enrich_cli
import providers


@pytest.fixture(autouse=True)
def mx_ok(monkeypatch):
    monkeypatch.setattr("email_guess.has_mx", lambda domain: True)


def test_default_provider_is_guess():
    assert providers.provider_name() == "guess"
    r = providers.enrich("Acme", "acme.com", "Jane Doe")
    assert r["email"] == "jane@acme.com"
    assert r["confidence"] == "pattern-guess"
    assert r["source"] == "guess"
    assert len(r["candidates"]) == 5


def test_known_pairs_passed_through():
    known = [{"name": "John Smith", "email": "jsmith@acme.com"}]
    r = providers.enrich("Acme", "acme.com", "Jane Doe", known)
    assert r["email"] == "jdoe@acme.com"
    assert r["confidence"] == "pattern-inferred"


def test_unknown_provider(reachout_home):
    (reachout_home / "config.json").write_text(json.dumps({"provider": "nope"}))
    with pytest.raises(providers.ProviderError, match="unknown provider 'nope'"):
        providers.enrich("Acme", "acme.com", "Jane Doe")


def test_invalid_provider_name(reachout_home):
    (reachout_home / "config.json").write_text(json.dumps({"provider": "../evil"}))
    with pytest.raises(providers.ProviderError, match="invalid provider"):
        providers.enrich("Acme", "acme.com", "Jane Doe")


def test_bad_config_json(reachout_home):
    (reachout_home / "config.json").write_text("{not json")
    with pytest.raises(providers.ProviderError, match="not valid JSON"):
        providers.provider_name()


def test_cli_success(capsys):
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--person", "Jane Doe"]) == 0
    assert json.loads(capsys.readouterr().out)["email"] == "jane@acme.com"


def test_cli_bad_known_json(capsys):
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--known", "[oops"]) == 1
    assert "error" in json.loads(capsys.readouterr().err)


def test_config_not_object(reachout_home):
    (reachout_home / "config.json").write_text("[]")
    with pytest.raises(providers.ProviderError, match="JSON object"):
        providers.provider_name()


def test_config_provider_not_string(reachout_home):
    (reachout_home / "config.json").write_text(json.dumps({"provider": None}))
    with pytest.raises(providers.ProviderError, match="must be a string"):
        providers.provider_name()


def test_cli_bad_config_returns_json_error(capsys, reachout_home):
    (reachout_home / "config.json").write_text("[]")
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--person", "Jane Doe"]) == 1
    assert "error" in json.loads(capsys.readouterr().err)


def test_cli_known_wrong_shape(capsys):
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--known", '["x"]']) == 1
    assert "error" in json.loads(capsys.readouterr().err)
