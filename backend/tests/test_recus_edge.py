"""Donation edge cases: reversal (extourne) and receipt cancellation."""

import pytest
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from tests.test_recus import (
    _admin_with_association,
    _donor,
    _fill_identity,
    _post_don,
)


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _recu(admin, assoc, tiers_id, ecriture_ids):
    return admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": tiers_id,
            "ecriture_ids": ecriture_ids,
            "date": "2026-04-01",
            "annee": 2026,
        },
    )


def _contrepasser(admin, assoc, eid):
    return admin.post(f"/api/asso/{assoc}/ecritures/{eid}/contrepassation")


def test_reversed_don_is_not_eligible():
    """A don whose validated extourne exists nets to zero: neither the original
    (cancelled) nor the extourne (money-out) is offered as a receiptable don."""
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")

    ext = _contrepasser(admin, assoc, eid).json()["extourne"]["id"]
    admin.post(f"/api/asso/{assoc}/ecritures/{ext}/validation")

    assert admin.get(f"/api/asso/{assoc}/dons").json() == []


def test_draft_reversal_keeps_don_eligible():
    """Until the extourne is validated, the don is still live (official = validé)."""
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    _contrepasser(admin, assoc, eid)  # extourne left as a brouillon

    dons = admin.get(f"/api/asso/{assoc}/dons").json()
    assert len(dons) == 1 and dons[0]["ecriture_id"] == eid


def test_cancelling_a_receipt_never_reuses_its_number():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    d1 = _donor(admin, assoc, "Donor 1")
    d2 = _donor(admin, assoc, "Donor 2")
    e1 = _post_don(admin, assoc, d1["id"], "100.00")
    e2 = _post_don(admin, assoc, d2["id"], "200.00")
    r1 = _recu(admin, assoc, d1["id"], [e1]).json()
    r2 = _recu(admin, assoc, d2["id"], [e2]).json()
    assert (r1["numero"], r2["numero"]) == (1, 2)

    # Cancel #2, then issue a new one: it must NOT reuse number 2.
    assert admin.delete(f"/api/asso/{assoc}/recus/{r2['id']}").status_code == 204
    e3 = _post_don(admin, assoc, d2["id"], "300.00")
    r3 = _recu(admin, assoc, d2["id"], [e3]).json()
    assert r3["numero"] == 3


def test_cancelling_frees_the_don_and_marks_annule():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    recu = _recu(admin, assoc, donor["id"], [eid]).json()

    admin.delete(f"/api/asso/{assoc}/recus/{recu['id']}")
    # The don is offered again…
    assert (
        len(admin.get(f"/api/asso/{assoc}/dons", params={"non_recu": True}).json()) == 1
    )
    # …the cancelled receipt stays, flagged, and no longer yields a PDF.
    recus = admin.get(f"/api/asso/{assoc}/recus").json()
    assert len(recus) == 1 and recus[0]["annule"] is True
    assert admin.get(f"/api/asso/{assoc}/recus/{recu['id']}/pdf").status_code == 409


def test_reversing_a_receipted_don_is_blocked_until_cancel():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    recu = _recu(admin, assoc, donor["id"], [eid]).json()

    # A don on an active receipt cannot be reversed.
    blocked = _contrepasser(admin, assoc, eid)
    assert blocked.status_code == 409
    assert "reçu" in blocked.json()["detail"].lower()

    # After cancelling the receipt, the reversal is allowed.
    admin.delete(f"/api/asso/{assoc}/recus/{recu['id']}")
    assert _contrepasser(admin, assoc, eid).status_code == 201
