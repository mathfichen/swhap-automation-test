"""PI-1 — personal-email lint (crit-M15): WARN, redacted, opt-in clears it."""
from conftest import make_git_repo
from swhap_validate.checks import pii
from swhap_validate.context import RepoContext
from swhap_validate.report import Report

HEADER = ("directory name,date,author name,author email,"
          "curator name,curator email,release tag,commit message\n")


def _csv(author_email, curator_email):
    return (HEADER +
            f"0.90,1993-08-09,A,{author_email},C,{curator_email},v0.90,m\n"
            ).encode("utf-8")


def _repo(tmp_path, csv_bytes, raw=b"ARCHIVE-CONTENT", journal=None):
    files = {"metadata/version_history.csv": csv_bytes,
             "raw_materials/a.tar": raw}
    if journal is not None:
        files["metadata/journal.jsonl"] = journal
    return make_git_repo(str(tmp_path / "r"), files)


def _run(repo, csv_bytes, journal=None):
    rep = Report("strict-P", "build")
    pii.run(rep, RepoContext(repo), csv_bytes=csv_bytes, journal_bytes=journal)
    return rep


def test_placeholder_emails_green(tmp_path):
    cb = _csv("a@noreply.example.org", "c@noreply.example.org")
    rep = _run(_repo(tmp_path, cb), cb)
    assert not [f for f in rep.findings if f.check_id == "PI-1"]


def test_real_author_email_warn_and_redacted(tmp_path):
    cb = _csv("peter.vanroy@uclouvain.be", "c@noreply.example.org")
    repo = _repo(tmp_path, cb)
    rep = _run(repo, cb)
    pi = [f for f in rep.findings if f.check_id == "PI-1"]
    assert pi and pi[0].severity == "WARN"
    # the literal address must never appear in the serialized report
    text = rep.serialize()
    assert "peter.vanroy@uclouvain.be" not in text
    assert "uclouvain.be" not in text  # private domain → no literal domain
    assert pi[0].object["domain_class"] == "private"
    assert len(pi[0].object["value_hmac12"]) == 12


def test_public_provider_domain_published(tmp_path):
    cb = _csv("someone@gmail.com", "c@noreply.example.org")
    rep = _run(_repo(tmp_path, cb), cb)
    pi = [f for f in rep.findings if f.check_id == "PI-1"][0]
    assert pi.object["domain_class"] == "public-provider"
    assert pi.object["domain"] == "gmail.com"
    assert "someone@gmail.com" not in rep.serialize()


def test_curator_optin_clears_curator_finding(tmp_path):
    cb = _csv("a@noreply.example.org", "carla@institution.example")
    journal = (b'{"schema":"swhap-journal/1","action":"provenance-transition",'
               b'"actor":{"kind":"curator","name":"C","tool":"t","version":"1"},'
               b'"provenance_transitions":[{"item":"pii.curator_email",'
               b'"from":"user-provided","to":"curator-approved"}]}\n')
    repo = _repo(tmp_path, cb, journal=journal)
    rep = _run(repo, cb, journal=journal)
    assert not [f for f in rep.findings
                if f.check_id == "PI-1" and f.object.get("field") == "curator email"]


def test_curator_real_email_without_optin_warns(tmp_path):
    cb = _csv("a@noreply.example.org", "carla@institution.example")
    rep = _run(_repo(tmp_path, cb), cb)
    assert [f for f in rep.findings
            if f.check_id == "PI-1" and f.object.get("field") == "curator email"]


def test_salt_is_content_derived(tmp_path):
    cb = _csv("peter@uclouvain.be", "c@noreply.example.org")
    repo1 = _repo(tmp_path / "1", cb, raw=b"AAAA")
    repo2 = _repo(tmp_path / "2", cb, raw=b"BBBB")
    t1 = [f for f in _run(repo1, cb).findings if f.check_id == "PI-1"][0]
    t2 = [f for f in _run(repo2, cb).findings if f.check_id == "PI-1"][0]
    assert t1.object["value_hmac12"] != t2.object["value_hmac12"]
