import csv
import json

import pytest

import leads


def row(**overrides):
    base = {"company": "Acme", "domain": "https://www.Acme.com/about", "batch": "b1"}
    base.update(overrides)
    return base


def test_normalize_domain():
    assert leads.normalize_domain("https://www.Acme.com/about?x=1") == "acme.com"
    assert leads.normalize_domain("acme.com:443") == "acme.com"
    assert leads.normalize_domain("  WWW.acme.io ") == "acme.io"


def test_check_when_no_file():
    assert leads.check("acme.com") == {"exists": False, "status": None}


def test_add_then_check():
    added = leads.add(row())
    assert added["domain"] == "acme.com"
    assert added["status"] == "found"
    assert len(added["id"]) == 8
    assert added["created_at"] == added["updated_at"] != ""
    assert leads.check("www.acme.com") == {"exists": True, "status": "found"}


def test_add_duplicate_domain_rejected():
    leads.add(row())
    with pytest.raises(leads.LeadError, match="already"):
        leads.add(row(company="Acme Inc", domain="acme.com"))


def test_add_requires_company_and_domain():
    with pytest.raises(leads.LeadError, match="domain"):
        leads.add({"company": "Acme"})


def test_add_rejects_unknown_field():
    with pytest.raises(leads.LeadError, match="unknown fields: foo"):
        leads.add(row(foo="x"))


def test_add_rejects_bad_status():
    with pytest.raises(leads.LeadError, match="status"):
        leads.add(row(status="sent"))


def test_add_joins_list_fields():
    added = leads.add(row(hooks=["raised seed", "hiring SDRs"]))
    assert added["hooks"] == "raised seed|hiring SDRs"


def test_update_changes_fields():
    added = leads.add(row())
    updated = leads.update(added["id"], {"status": "approved", "person": "Jane Doe"})
    assert updated["status"] == "approved"
    assert updated["person"] == "Jane Doe"
    assert leads.list_rows(status="approved")[0]["id"] == added["id"]


def test_update_unknown_id():
    with pytest.raises(leads.LeadError, match="no lead"):
        leads.update("nope", {"status": "approved"})


def test_update_protected_field():
    added = leads.add(row())
    with pytest.raises(leads.LeadError, match="cannot change"):
        leads.update(added["id"], {"domain": "other.com"})


def test_update_bad_status():
    added = leads.add(row())
    with pytest.raises(leads.LeadError, match="status"):
        leads.update(added["id"], {"status": "sent"})


def test_list_filters():
    leads.add(row(batch="b1"))
    leads.add(row(company="Beta", domain="beta.com", batch="b2"))
    assert [r["company"] for r in leads.list_rows()] == ["Acme", "Beta"]
    assert [r["company"] for r in leads.list_rows(batch="b2")] == ["Beta"]


def test_save_keeps_backup(outreach_home):
    leads.add(row())
    leads.add(row(company="Beta", domain="beta.com"))
    with (outreach_home / "leads.csv.bak").open(newline="") as f:
        assert len(list(csv.DictReader(f))) == 1


def test_header_mismatch_aborts(outreach_home):
    (outreach_home / "leads.csv").write_text("a,b\n1,2\n")
    with pytest.raises(leads.LeadError, match="header"):
        leads.check("acme.com")


def test_cli_add_check_and_home(capsys, outreach_home):
    assert leads.main(["add", "--json", json.dumps(row())]) == 0
    capsys.readouterr()
    assert leads.main(["check", "acme.com"]) == 0
    assert json.loads(capsys.readouterr().out) == {"exists": True, "status": "found"}
    assert leads.main(["home"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "home": str(outreach_home),
        "profile_exists": False,
    }


def test_cli_error_exit(capsys):
    assert leads.main(["update", "nope", "--json", "{}"]) == 1
    assert "error" in json.loads(capsys.readouterr().err)


def run_main(args, capsys):
    code = leads.main(args)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_add_json_from_stdin(monkeypatch, capsys):
    import io
    payload = json.dumps({"company": "O'Brien Co", "domain": "ob.com",
                          "fit_reason": "FreightCo's AP team"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out, _ = run_main(["add", "--json", "-"], capsys)
    assert code == 0
    assert json.loads(out)["fit_reason"] == "FreightCo's AP team"


def test_update_json_from_stdin(monkeypatch, capsys):
    import io
    added = leads.add(row())
    monkeypatch.setattr("sys.stdin", io.StringIO('{"role": "CTO\'s office"}'))
    code, out, _ = run_main(["update", added["id"], "--json", "-"], capsys)
    assert code == 0
    assert json.loads(out)["role"] == "CTO's office"


def test_clean_rejects_dict_value():
    with pytest.raises(leads.LeadError, match="plain"):
        leads.add(row(person={"a": 1}))


def test_clean_rejects_dict_in_list():
    with pytest.raises(leads.LeadError, match="plain"):
        leads.add(row(hooks=[{"text": "x", "url": "u"}]))


def test_clean_rejects_pipe_in_list_item():
    with pytest.raises(leads.LeadError, match=r"\|"):
        leads.add(row(hooks=["a|b"]))


def test_load_accepts_bom(outreach_home):
    (outreach_home / "leads.csv").write_text(",".join(leads.COLUMNS) + "\n", encoding="utf-8-sig")
    assert leads.check("x.com")["exists"] is False


def test_load_rejects_extra_cells(outreach_home):
    (outreach_home / "leads.csv").write_text(
        ",".join(leads.COLUMNS) + "\n" + "a," * len(leads.COLUMNS) + "extra\n", encoding="utf-8")
    with pytest.raises(leads.LeadError, match="row 1 has more cells"):
        leads.load()


def test_main_bad_encoding_is_json_error(outreach_home, capsys):
    (outreach_home / "leads.csv").write_bytes(
        (",".join(leads.COLUMNS) + "\n").encode() + "Jos\xe9\n".encode("latin-1"))
    code, _, err = run_main(["check", "x.com"], capsys)
    assert code == 1
    assert "error" in json.loads(err)


def test_add_empty_domain_after_normalize():
    with pytest.raises(leads.LeadError, match="missing required field: domain"):
        leads.add(row(domain="https://"))
