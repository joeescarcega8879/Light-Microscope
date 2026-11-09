import csv
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.data import auth as auth_mod
from src.data.auth import AuthError, AuthService, hash_password, verify_password
from src.data.database import Database
from src.data.history import Filters, HistoryRepository
from src.data.session import Session


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    monkeypatch.setattr(auth_mod, "PBKDF2_ITERATIONS", 1000)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


@pytest.fixture
def svc(db):
    return AuthService(db)


# ── database ──
def test_migration_sets_version_and_is_idempotent(tmp_path):
    p = tmp_path / "m.db"
    d = Database(p)
    assert d.schema_version >= 1
    d.close()
    d2 = Database(p)   # reopening must not re-run migrations
    assert d2.schema_version >= 1
    d2.close()


def test_foreign_keys_cascade_delete(db):
    db.execute("INSERT INTO batches (started_at, folder, reference, total, ok, ng, errors) "
               "VALUES ('2026-01-01 00:00:00','f','r',1,1,0,0)")
    db.execute("INSERT INTO inspections (batch_id, ts, file, path, reference, verdict) "
               "VALUES (1,'2026-01-01 00:00:00','a.png','/a.png','r','OK')")
    db.execute("DELETE FROM batches WHERE id = 1")
    assert db.query_one("SELECT COUNT(*) c FROM inspections")["c"] == 0


# ── passwords ──
def test_hash_is_salted_and_verifiable():
    a, b = hash_password("secret-pass", 1000), hash_password("secret-pass", 1000)
    assert a != b and verify_password("secret-pass", a) and not verify_password("wrong", a)
    assert not verify_password("x", "garbage") and not verify_password("x", "md5$1$aa$bb")


# ── users / roles ──
def test_create_and_authenticate(svc):
    assert not svc.has_users()
    u = svc.create_user("Alice", "correct-horse", "admin")
    assert svc.has_users() and u.role == "admin"
    assert svc.authenticate("alice", "correct-horse").id == u.id      # case-insensitive username
    assert svc.last_login(u.id) != ""


def test_validation_and_duplicates(svc):
    with pytest.raises(AuthError):
        svc.create_user("a", "longenough1")
    with pytest.raises(AuthError):
        svc.create_user("valid_name", "short")
    with pytest.raises(AuthError):
        svc.create_user("valid_name", "longenough1", "root")
    svc.create_user("bob", "longenough1")
    with pytest.raises(AuthError):
        svc.create_user("BOB", "longenough1")


def test_wrong_password_and_unknown_user_share_message(svc):
    svc.create_user("bob", "longenough1")
    with pytest.raises(AuthError) as e1:
        svc.authenticate("bob", "nope-nope")
    with pytest.raises(AuthError) as e2:
        svc.authenticate("ghost", "nope-nope")
    assert str(e1.value) == str(e2.value)


def test_lockout_after_repeated_failures(svc):
    svc.create_user("bob", "longenough1")
    for _ in range(auth_mod.MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthError):
            svc.authenticate("bob", "bad-bad-bad")
    with pytest.raises(AuthError) as e:
        svc.authenticate("bob", "longenough1")        # correct password, but locked
    assert "Too many" in str(e.value)


def test_disabled_user_cannot_login(svc):
    svc.create_user("root", "longenough1", "admin")
    u = svc.create_user("bob", "longenough1")
    svc.set_active(u.id, False)
    with pytest.raises(AuthError) as e:
        svc.authenticate("bob", "longenough1")
    assert "disabled" in str(e.value)


def test_cannot_remove_last_admin(svc):
    admin = svc.create_user("root", "longenough1", "admin")
    with pytest.raises(AuthError):
        svc.set_role(admin.id, "operator")
    with pytest.raises(AuthError):
        svc.set_active(admin.id, False)
    second = svc.create_user("root2", "longenough1", "admin")
    svc.set_role(admin.id, "supervisor")           # fine now: another admin exists
    assert svc.get_user(admin.id).role == "supervisor"


def test_password_reset_clears_lock(svc):
    u = svc.create_user("bob", "longenough1")
    for _ in range(auth_mod.MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthError):
            svc.authenticate("bob", "bad-bad-bad")
    svc.set_password(u.id, "brand-new-pass")
    assert svc.authenticate("bob", "brand-new-pass").id == u.id


def test_permissions_by_role(svc):
    op = svc.create_user("oper", "longenough1", "operator")
    sup = svc.create_user("sup", "longenough1", "supervisor")
    adm = svc.create_user("adm", "longenough1", "admin")
    assert op.can("run_inspection") and not op.can("edit_references")
    assert sup.can("edit_references") and sup.can("export_reports") and not sup.can("manage_users")
    assert adm.can("manage_users") and adm.can("delete_history")
    assert not adm.can("does_not_exist")


def test_session_audit(db, svc):
    u = svc.create_user("oper", "longenough1", "operator")
    s = Session(db, u)
    s.audit("run_batch", "demo")
    row = db.query_one("SELECT * FROM audit_log")
    assert (row["username"], row["action"], row["user_id"]) == ("oper", "run_batch", u.id)
    assert not Session(db).can("run_inspection")


# ── history ──
@dataclass
class Item:
    path: Path
    verdict: str
    defects: int = 0
    defect_area_pct: float = 0.0
    reference_index: int = 0
    reasons: str = ""
    error: str = ""


@dataclass
class Summary:
    items: list
    output_dir: object = None
    cancelled: bool = False

    @property
    def ok(self): return sum(i.verdict == "OK" for i in self.items)
    @property
    def ng(self): return sum(i.verdict == "NG" for i in self.items)
    @property
    def errors(self): return sum(i.verdict == "ERROR" for i in self.items)


def _summary(*verdicts, names=None):
    names = names or [f"p{i}.png" for i in range(len(verdicts))]
    return Summary([Item(Path("/data") / n, v, defects=int(v == "NG"), reasons="r" if v == "NG" else "")
                    for n, v in zip(names, verdicts)])


def test_record_and_query_batch(db, svc):
    user = svc.create_user("oper", "longenough1")
    repo = HistoryRepository(db)
    bid = repo.record_batch(_summary("OK", "NG", "ERROR"), "demo", "/data", user, {"threshold": 25})
    b = repo.get_batch(bid)
    assert (b["total"], b["ok"], b["ng"], b["errors"], b["username"]) == (3, 1, 1, 1, "oper")
    assert len(repo.batch_items(bid)) == 3
    assert repo.batch_items(bid)[0]["verdict"] != "OK"      # problems first
    assert [r["verdict"] for r in repo.query_inspections(Filters(verdict="NG"))] == ["NG"]


def test_filters_text_is_escaped_and_reference_filter(db):
    repo = HistoryRepository(db)
    repo.record_batch(_summary("OK", "OK", names=["100%_a.png", "other.png"]), "A", "/d")
    repo.record_batch(_summary("NG", names=["x.png"]), "B", "/d")
    assert len(repo.query_inspections(Filters(text="100%_"))) == 1       # % and _ are literals
    assert len(repo.query_inspections(Filters(text="%"))) == 1
    assert [r["file"] for r in repo.query_inspections(Filters(reference="B"))] == ["x.png"]
    assert repo.references_used() == ["A", "B"]


def test_stats_reject_rate_and_groupings(db):
    repo = HistoryRepository(db)
    repo.record_batch(_summary("OK", "OK", "OK", "NG", "ERROR"), "A", "/d")
    repo.record_batch(_summary("NG", "NG"), "B", "/d")
    s = repo.stats()
    assert (s.total, s.ok, s.ng, s.errors) == (7, 3, 3, 1)
    assert s.reject_rate == pytest.approx(50.0)          # errors excluded from the yield
    assert s.per_reference[0][0] == "B"                  # worst product first
    assert len(s.per_day) == 1 and s.per_day[0][1:] == (3, 3, 1)
    assert repo.stats(Filters(reference="A")).total == 5


def test_stats_empty_and_date_filter(db):
    repo = HistoryRepository(db)
    assert repo.stats().reject_rate == 0.0
    repo.record_batch(_summary("OK"), "A", "/d")
    assert repo.stats(Filters(date_from="2999-01-01")).total == 0
    assert repo.stats(Filters(date_to="2000-01-01")).total == 0


def test_delete_batch_cascades(db):
    repo = HistoryRepository(db)
    bid = repo.record_batch(_summary("OK", "NG"), "A", "/d")
    repo.delete_batch(bid)
    assert repo.query_inspections() == [] and repo.list_batches() == []


def test_csv_export_neutralizes_formulas(db, tmp_path):
    repo = HistoryRepository(db)
    repo.record_batch(_summary("NG", names=["=1+1.png"]), "A", "/d")
    out = tmp_path / "o.csv"
    assert repo.export_csv(out, repo.query_inspections()) == 1
    row = list(csv.DictReader(open(out, encoding="utf-8")))[0]
    assert row["file"].startswith("'=")
