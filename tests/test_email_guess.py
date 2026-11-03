import dns.exception
import pytest

import email_guess as eg


@pytest.fixture
def mx(monkeypatch):
    state = {"ok": True}
    monkeypatch.setattr(eg, "has_mx", lambda domain: state["ok"])
    return state


def test_fold():
    assert eg.fold("José") == "jose"
    assert eg.fold("O'Brien-Smith") == "obriensmith"


def test_split_name():
    assert eg.split_name("Jane van Doe") == ("Jane", "Doe")
    assert eg.split_name("  Madonna ") == ("Madonna", "")
    assert eg.split_name("") == ("", "")


def test_render_all_patterns():
    got = [eg.render(p, "Jane", "Doe") for p in eg.PATTERNS]
    assert got == ["jane", "jane.doe", "janedoe", "jdoe", "jane_doe"]


def test_detect_pattern_from_colleague():
    known = [{"name": "John Smith", "email": "JSmith@acme.com"}]
    assert eg.detect_pattern(known, "acme.com") == "flast"


def test_detect_pattern_ignores_other_domains_and_generic_inboxes():
    known = [
        {"name": "John Smith", "email": "jsmith@gmail.com"},
        {"name": "Support Team", "email": "info@acme.com"},
    ]
    assert eg.detect_pattern(known, "acme.com") is None


def test_guess_fallback(mx):
    r = eg.guess("Jane", "Doe", "Acme.com")
    assert r == {
        "email": "jane@acme.com",
        "confidence": "pattern-guess",
        "candidates": [
            "jane@acme.com", "jane.doe@acme.com", "janedoe@acme.com",
            "jdoe@acme.com", "jane_doe@acme.com",
        ],
        "mx_ok": True,
    }


def test_guess_inferred_from_colleague(mx):
    known = [{"name": "John Smith", "email": "john.smith@acme.com"}]
    r = eg.guess("Jane", "Doe", "acme.com", known)
    assert r["email"] == "jane.doe@acme.com"
    assert r["confidence"] == "pattern-inferred"
    assert r["candidates"][0] == "jane.doe@acme.com"
    assert len(r["candidates"]) == 5


def test_guess_no_mx(mx):
    mx["ok"] = False
    r = eg.guess("Jane", "Doe", "acme.com")
    assert r == {"email": None, "confidence": "unknown", "candidates": [], "mx_ok": False}


def test_guess_no_first_name(mx):
    assert eg.guess("", "Doe", "acme.com")["confidence"] == "unknown"


def test_guess_single_name(mx):
    r = eg.guess("Madonna", "", "acme.com")
    assert r["email"] == "madonna@acme.com"
    assert r["candidates"] == ["madonna@acme.com"]


def test_has_mx_true(monkeypatch):
    monkeypatch.setattr(eg.dns.resolver, "resolve", lambda domain, rtype: ["mx1"])
    assert eg.has_mx("acme.com") is True


def test_has_mx_false_on_dns_error(monkeypatch):
    def boom(domain, rtype):
        raise dns.exception.Timeout()

    monkeypatch.setattr(eg.dns.resolver, "resolve", boom)
    assert eg.has_mx("acme.com") is False
