"""What a journal row says without any follow-up request (C24).

The journal is read two ways: a plain-language view (what happened, on which
account, for whom) and the accountant's view (débit/crédit and counterparts). Both
are served by one listing — the sens and the treasury account are derived from the
entry's own lines server-side, so the client never guesses them from an account
number, and the lines travel with the row so the accounting view needs no N+1.
"""

from tests.test_journal_filters import (  # noqa: F401 — reuses the shared fixtures
    _mixed_books,
    _use_test_session,
)


def _rows(client, assoc: str) -> dict[str, dict]:
    resp = client.get(f"/api/asso/{assoc}/ecritures")
    assert resp.status_code == 200, resp.text
    return {row["id"]: row for row in resp.json()}


def test_a_recette_reads_as_money_in_on_its_treasury_account():
    admin, assoc, refs = _mixed_books()

    row = _rows(admin, assoc)[refs["recette"]["id"]]

    assert row["sens"] == "recette"
    assert row["compte_libelle"] == "Banque"
    assert row["compte_contrepartie_libelle"] is None


def test_a_depense_reads_as_money_out():
    admin, assoc, refs = _mixed_books()

    row = _rows(admin, assoc)[refs["depense"]["id"]]

    assert row["sens"] == "depense"
    assert row["compte_libelle"] == "Banque"


def test_a_virement_names_both_ends():
    """Money leaves the source and lands on the destination: say both, in order."""
    admin, assoc, refs = _mixed_books()

    row = _rows(admin, assoc)[refs["virement"]["id"]]

    assert row["sens"] == "virement"
    assert row["compte_libelle"] == "Caisse"  # source (créditée)
    assert row["compte_contrepartie_libelle"] == "Banque"  # destination (débitée)


def test_a_manual_entry_claims_no_sens():
    """It carries no category and may not even touch treasury — do not invent one."""
    admin, assoc, refs = _mixed_books()

    row = _rows(admin, assoc)[refs["manuel"]["id"]]

    assert row["sens"] is None


def test_the_signed_treasury_movement_says_which_way_the_money_went():
    admin, assoc, refs = _mixed_books()

    rows = _rows(admin, assoc)
    assert rows[refs["recette"]["id"]]["montant_tresorerie"] == "150.00"
    assert rows[refs["depense"]["id"]]["montant_tresorerie"] == "-100.00"
    # A virement never adds or removes money: it claims no direction.
    assert rows[refs["virement"]["id"]]["montant_tresorerie"] is None


def test_a_contre_passation_keeps_the_sens_but_reverses_the_movement():
    """It nets out a recette, so it stays filed under Recette — with money going
    the other way. The reader needs both facts, not one of them."""
    admin, assoc, refs = _mixed_books()
    original = refs["recette"]["id"]
    assert (
        admin.post(f"/api/asso/{assoc}/ecritures/{original}/validation").status_code
        == 200
    )
    resp = admin.post(f"/api/asso/{assoc}/ecritures/{original}/contrepassation")
    assert resp.status_code == 201, resp.text

    row = _rows(admin, assoc)[resp.json()["extourne"]["id"]]

    assert row["origine"] == "extourne"
    assert row["sens"] == "recette"
    assert row["montant_tresorerie"] == "-150.00"


def test_rows_carry_their_lines_for_the_accounting_view():
    admin, assoc, refs = _mixed_books()

    row = _rows(admin, assoc)[refs["recette"]["id"]]

    lignes = row["lignes"]
    assert len(lignes) == 2
    debit = next(ligne for ligne in lignes if ligne["debit"] != "0.00")
    credit = next(ligne for ligne in lignes if ligne["credit"] != "0.00")
    assert debit["compte_numero"] == "512"
    assert debit["compte_libelle"] == "Banque"
    assert debit["debit"] == "150.00"
    assert credit["compte_numero"] == "756"
    assert credit["credit"] == "150.00"
